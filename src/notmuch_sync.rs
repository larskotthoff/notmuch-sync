#!/usr/bin/env rust

//! notmuch_sync: Synchronize notmuch email databases and message files between
//! local and remote systems.

use anyhow::{anyhow, Result};
use clap::Parser;
use log::info;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use tokio::process::Command as TokioCommand;

/// Global transfer statistics
static TRANSFER_READ: AtomicUsize = AtomicUsize::new(0);
static TRANSFER_WRITE: AtomicUsize = AtomicUsize::new(0);

/// Command line arguments
#[derive(Parser, Debug)]
#[command(name = "notmuch-sync")]
#[command(about = "Synchronize notmuch email databases and message files between local and remote systems")]
struct Args {
    /// Remote host to connect to
    #[arg(short, long)]
    remote: Option<String>,

    /// SSH user to use
    #[arg(short, long)]
    user: Option<String>,

    /// Increases verbosity, up to twice (ignored on remote)
    #[arg(short, long, action = clap::ArgAction::Count)]
    verbose: u8,

    /// Do not print any output, overrides --verbose
    #[arg(short, long)]
    quiet: bool,

    /// SSH command to use
    #[arg(short = 's', long, default_value = "ssh -CTaxq")]
    ssh_cmd: String,

    /// Sync mbsync files (.mbsyncstate, .uidvalidity)
    #[arg(short, long)]
    mbsync: bool,

    /// Path to notmuch-sync on remote server
    #[arg(short, long)]
    path: Option<String>,

    /// Command to run to sync; overrides --remote, --user, --ssh-cmd, --path; mostly used for testing
    #[arg(short = 'c', long)]
    remote_cmd: Option<String>,

    /// Sync deleted messages (requires listing all messages in notmuch database, potentially expensive)
    #[arg(short, long)]
    delete: bool,

    /// Delete missing messages even if they don't have the 'deleted' tag (requires --delete) -- potentially unsafe
    #[arg(short = 'x', long)]
    delete_no_check: bool,
}

/// Message information structure
#[derive(Debug, Clone, Serialize, Deserialize)]
struct MessageInfo {
    tags: Vec<String>,
    files: Vec<String>,
}

/// Sync state information
#[derive(Debug)]
struct SyncState {
    revision: u64,
    uuid: String,
}

/// Compute SHA256 digest of data, removing any X-TUID: lines.
/// This is necessary because mbsync adds these lines to keep track of internal
/// progress, but they make identical emails that were retrieved separately different.
fn digest(data: &[u8]) -> String {
    let pattern = b"X-TUID: ";
    let to_digest = if let Some(start_idx) = data.windows(pattern.len()).position(|w| w == pattern) {
        let search_start = start_idx + pattern.len();
        if let Some(end_idx) = data[search_start..].iter().position(|&b| b == b'\n') {
            let end_idx = search_start + end_idx;
            let mut result = Vec::with_capacity(data.len() - (end_idx + 1 - start_idx));
            result.extend_from_slice(&data[..start_idx]);
            result.extend_from_slice(&data[end_idx + 1..]);
            result
        } else {
            data.to_vec()
        }
    } else {
        data.to_vec()
    };

    format!("{:x}", Sha256::digest(&to_digest))
}

/// Write data to a stream with a 4-byte length prefix
async fn write_data<W: AsyncWrite + Unpin>(data: &[u8], stream: &mut W) -> Result<()> {
    let len = data.len() as u32;
    stream.write_all(&len.to_be_bytes()).await?;
    TRANSFER_WRITE.fetch_add(4, Ordering::Relaxed);
    
    stream.write_all(data).await?;
    TRANSFER_WRITE.fetch_add(data.len(), Ordering::Relaxed);
    
    stream.flush().await?;
    Ok(())
}

/// Read 4-byte length-prefixed data from a stream
async fn read_data<R: AsyncRead + Unpin>(stream: &mut R) -> Result<Vec<u8>> {
    let mut len_buf = [0u8; 4];
    stream.read_exact(&mut len_buf).await?;
    TRANSFER_READ.fetch_add(4, Ordering::Relaxed);
    
    let len = u32::from_be_bytes(len_buf) as usize;
    let mut data = vec![0u8; len];
    stream.read_exact(&mut data).await?;
    TRANSFER_READ.fetch_add(len, Ordering::Relaxed);
    
    Ok(data)
}

/// Run two async functions concurrently
async fn run_async<F1, F2, R1, R2>(f1: F1, f2: F2) -> Result<(R1, R2)>
where
    F1: std::future::Future<Output = Result<R1>>,
    F2: std::future::Future<Output = Result<R2>>,
{
    let (r1, r2) = tokio::try_join!(f1, f2)?;
    Ok((r1, r2))
}

/// Get changes that happened since the last sync, or everything in the DB if no previous sync
fn get_changes(
    db: &notmuch::Database,
    revision: &SyncState,
    prefix: &str,
    sync_file: &str,
) -> Result<HashMap<String, MessageInfo>> {
    let rev_prev = match fs::read_to_string(sync_file) {
        Ok(content) => {
            let parts: Vec<&str> = content.trim().split(' ').collect();
            if parts.len() != 2 {
                return Err(anyhow!("Sync state file '{}' corrupted, delete to sync from scratch", sync_file));
            }
            
            let stored_uuid = parts[1];
            if stored_uuid != revision.uuid {
                return Err(anyhow!(
                    "Last sync with UUID {}, but notmuch DB has UUID {}, aborting...",
                    stored_uuid, revision.uuid
                ));
            }
            
            let rev: u64 = parts[0].parse()
                .map_err(|_| anyhow!("Sync state file '{}' corrupted, delete to sync from scratch", sync_file))?;
            
            if rev > revision.revision {
                return Err(anyhow!(
                    "Last sync revision {} larger than current DB revision {}, aborting...",
                    rev, revision.revision
                ));
            }
            
            rev
        }
        Err(_) => {
            // No previous sync file, sync entire DB
            0u64.wrapping_sub(1) // -1 equivalent
        }
    };

    info!("Previous sync revision {}, current revision {}.", rev_prev, revision.revision);
    
    // Get messages that changed since rev_prev + 1
    let query_str = format!("lastmod:{}..{}", rev_prev.wrapping_add(1), revision.revision);
    let query = db.create_query(&query_str)?;
    let messages = query.search_messages()?;
    
    let mut changes = HashMap::new();
    for message in messages {
        let message_id = message.id().to_string();
        let tags: Vec<String> = message.tags().map(|t| t.to_string()).collect();
        let files: Vec<String> = message.filenames()
            .map(|f| {
                f.strip_prefix(prefix)
                    .unwrap_or(&f)
                    .to_string_lossy()
                    .to_string()
            })
            .collect();
        
        changes.insert(message_id, MessageInfo { tags, files });
    }
    
    Ok(changes)
}

/// Synchronize tags between local and remote changes
fn sync_tags(
    db: &mut notmuch::Database,
    changes_mine: &HashMap<String, MessageInfo>,
    changes_theirs: &HashMap<String, MessageInfo>,
) -> Result<u32> {
    let mut changes = 0;
    
    for (mid, their_info) in changes_theirs {
        let mut tags = their_info.tags.clone();
        
        // If message appears in both local and remote changes, take union of tags
        if let Some(my_info) = changes_mine.get(mid) {
            let mut tag_set: HashSet<String> = tags.into_iter().collect();
            tag_set.extend(my_info.tags.iter().cloned());
            tags = tag_set.into_iter().collect();
        }
        
        let tag_set: HashSet<String> = tags.into_iter().collect();
        
        if let Some(message) = db.find_message(mid)? {
            // Check if message is a ghost
            let current_tags: HashSet<String> = message.tags().map(|t| t.to_string()).collect();
            
            if tag_set != current_tags {
                info!("Setting tags {:?} for {}.", 
                     tag_set.iter().collect::<Vec<_>>(), mid);
                
                // Remove all current tags
                for tag in &current_tags {
                    message.remove_tag(tag)?;
                }
                
                // Add new tags
                for tag in &tag_set {
                    message.add_tag(tag)?;
                }
                
                message.tags_to_maildir_flags()?;
                changes += 1;
            }
        }
        // If message not found locally, it will be synced later when syncing files
    }
    
    Ok(changes)
}

/// Record last sync revision
fn record_sync(fname: &str, revision: &SyncState) -> Result<()> {
    info!("Writing last sync revision {}.", revision.revision);
    fs::write(fname, format!("{} {}", revision.revision, revision.uuid))?;
    Ok(())
}

/// Entry point for the command-line interface
#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    
    // Set up logging
    if args.remote.is_some() || args.remote_cmd.is_some() {
        let log_level = if args.quiet {
            log::LevelFilter::Off
        } else {
            match args.verbose {
                0 => log::LevelFilter::Warn,
                1 => log::LevelFilter::Info,
                _ => log::LevelFilter::Debug,
            }
        };
        
        env_logger::Builder::new()
            .filter_level(log_level)
            .format_timestamp_millis()
            .init();
            
        sync_local(args).await?;
    } else {
        // Remote mode - disable logging
        env_logger::Builder::new()
            .filter_level(log::LevelFilter::Off)
            .init();
            
        sync_remote(args).await?;
    }
    
    Ok(())
}

/// Run synchronization in local mode, communicating with the remote over SSH or a custom command
async fn sync_local(args: Args) -> Result<()> {
    let cmd = if let Some(remote_cmd) = &args.remote_cmd {
        shell_split(remote_cmd)?
    } else {
        let remote = args.remote.as_ref()
            .ok_or_else(|| anyhow!("Either --remote or --remote-cmd must be specified"))?;
        
        let mut cmd_parts = shell_split(&args.ssh_cmd)?;
        let user_host = if let Some(user) = &args.user {
            format!("{}@{}", user, remote)
        } else {
            remote.clone()
        };
        cmd_parts.push(user_host);
        
        let path = args.path.as_deref().unwrap_or("notmuch-sync");
        cmd_parts.push(path.to_string());
        
        if args.delete {
            cmd_parts.push("--delete".to_string());
        }
        if args.delete_no_check {
            cmd_parts.push("--delete-no-check".to_string());
        }
        if args.mbsync {
            cmd_parts.push("--mbsync".to_string());
        }
        
        cmd_parts
    };

    info!("Connecting to remote...");
    
    let mut child = TokioCommand::new(&cmd[0])
        .args(&cmd[1..])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;

    let stdin = child.stdin.take().unwrap();
    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let result = sync_local_with_streams(stdin, stdout, stderr, args.delete, args.delete_no_check, args.mbsync).await;
    
    let exit_status = child.wait().await?;
    if !exit_status.success() {
        return Err(anyhow!("Remote command failed with exit status: {}", exit_status));
    }
    
    result
}

/// Run synchronization in remote mode
async fn sync_remote(args: Args) -> Result<()> {
    let stdin = tokio::io::stdin();
    let stdout = tokio::io::stdout();
    
    sync_remote_with_streams(stdin, stdout, args.delete, args.delete_no_check, args.mbsync).await
}

/// Split shell command string into parts
fn shell_split(cmd: &str) -> Result<Vec<String>> {
    // Simple shell splitting - for production use a proper shell parser
    Ok(cmd.split_whitespace().map(|s| s.to_string()).collect())
}

/// Sync logic for local mode with provided streams
async fn sync_local_with_streams(
    mut to_remote: tokio::process::ChildStdin,
    mut from_remote: tokio::process::ChildStdout,
    mut _err_remote: tokio::process::ChildStderr,
    delete: bool,
    delete_no_check: bool,
    mbsync: bool,
) -> Result<()> {
    // Open notmuch database
    let db = notmuch::Database::open_with_config(
        None::<&Path>,
        notmuch::DatabaseMode::ReadWrite,
        None::<&Path>,
        None,
    )?;
    let prefix = db.path().to_string_lossy().to_string();
    
    // Perform initial sync
    let (changes_mine, changes_theirs, tchanges, sync_fname) = 
        initial_sync(&db, &prefix, &mut from_remote, &mut to_remote).await?;
    
    info!("Initial sync completed. Local changes: {}, Remote changes: {}, Tag changes: {}", 
          changes_mine.len(), changes_theirs.len(), tchanges);
    
    // Get missing files and sync them
    let (missing, fchanges, dfchanges) = 
        get_missing_files(&db, &prefix, &changes_mine, &changes_theirs, 
                         &mut from_remote, &mut to_remote, true).await?;
    
    let (rmessages, rfiles) = 
        sync_files(&db, &prefix, &missing, &mut from_remote, &mut to_remote).await?;
    
    // Record the sync
    let revision = get_database_revision(&db)?;
    record_sync(&sync_fname, &revision)?;
    
    // Handle deletions if requested
    let dchanges = if delete {
        sync_deletes_local(&prefix, &mut from_remote, &mut to_remote, delete_no_check).await?
    } else {
        0
    };
    
    // Handle mbsync if requested
    if mbsync {
        sync_mbsync_local(&prefix, &mut from_remote, &mut to_remote).await?;
    }
    
    // Read remote stats
    let mut stats_buf = [0u8; 24]; // 6 * 4 bytes
    from_remote.read_exact(&mut stats_buf).await?;
    let remote_stats = [
        u32::from_be_bytes([stats_buf[0], stats_buf[1], stats_buf[2], stats_buf[3]]),
        u32::from_be_bytes([stats_buf[4], stats_buf[5], stats_buf[6], stats_buf[7]]),
        u32::from_be_bytes([stats_buf[8], stats_buf[9], stats_buf[10], stats_buf[11]]),
        u32::from_be_bytes([stats_buf[12], stats_buf[13], stats_buf[14], stats_buf[15]]),
        u32::from_be_bytes([stats_buf[16], stats_buf[17], stats_buf[18], stats_buf[19]]),
        u32::from_be_bytes([stats_buf[20], stats_buf[21], stats_buf[22], stats_buf[23]]),
    ];
    
    info!("local:  {} new messages,\t{} new files,\t{} files copied/moved,\t{} files deleted,\t{} messages with tag changes,\t{} messages deleted", 
          rmessages, rfiles, fchanges, dfchanges, tchanges, dchanges);
    info!("remote: {} new messages,\t{} new files,\t{} files copied/moved,\t{} files deleted,\t{} messages with tag changes,\t{} messages deleted",
          remote_stats[3], remote_stats[5], remote_stats[1], remote_stats[2], remote_stats[0], remote_stats[4]);
    info!("{}/{} bytes received from/sent to remote.", 
          TRANSFER_READ.load(Ordering::Relaxed), TRANSFER_WRITE.load(Ordering::Relaxed));
    
    Ok(())
}

/// Sync logic for remote mode with provided streams  
async fn sync_remote_with_streams<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    mut from_local: R,
    mut to_local: W,
    delete: bool,
    delete_no_check: bool,
    mbsync: bool,
) -> Result<()> {
    // Open notmuch database
    let db = notmuch::Database::open_with_config(
        None::<&Path>,
        notmuch::DatabaseMode::ReadWrite,
        None::<&Path>,
        None,
    )?;
    let prefix = db.path().to_string_lossy().to_string();
    
    // Perform initial sync
    let (changes_mine, changes_theirs, tchanges, sync_fname) = 
        initial_sync(&db, &prefix, &mut from_local, &mut to_local).await?;
    
    // Get missing files and sync them
    let (missing, fchanges, dfchanges) = 
        get_missing_files(&db, &prefix, &changes_mine, &changes_theirs, 
                         &mut from_local, &mut to_local, false).await?;
    
    let (rmessages, rfiles) = 
        sync_files(&db, &prefix, &missing, &mut from_local, &mut to_local).await?;
    
    // Record the sync
    let revision = get_database_revision(&db)?;
    record_sync(&sync_fname, &revision)?;
    
    // Handle deletions if requested
    let dchanges = if delete {
        sync_deletes_remote(&prefix, &mut from_local, &mut to_local, delete_no_check).await?
    } else {
        0
    };
    
    // Handle mbsync if requested
    if mbsync {
        sync_mbsync_remote(&prefix, &mut from_local, &mut to_local).await?;
    }
    
    // Send stats to local
    let stats = [tchanges, fchanges, dfchanges, rmessages, dchanges, rfiles];
    for stat in stats {
        to_local.write_all(&(stat as u32).to_be_bytes()).await?;
    }
    to_local.flush().await?;
    
    Ok(())
}

/// Get database revision information
fn get_database_revision(_db: &notmuch::Database) -> Result<SyncState> {
    // For now, use a placeholder implementation
    // The notmuch crate might not expose revision APIs directly
    Ok(SyncState {
        revision: 0, // TODO: Get actual revision from notmuch
        uuid: "placeholder-uuid".to_string(), // TODO: Get actual UUID
    })
}

/// Placeholder implementations for missing functions
async fn initial_sync<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    _db: &notmuch::Database,
    _prefix: &str,
    _from_stream: &mut R,
    _to_stream: &mut W,
) -> Result<(HashMap<String, MessageInfo>, HashMap<String, MessageInfo>, u32, String)> {
    todo!("initial_sync implementation")
}

async fn get_missing_files<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    _db: &notmuch::Database,
    _prefix: &str,
    _changes_mine: &HashMap<String, MessageInfo>,
    _changes_theirs: &HashMap<String, MessageInfo>,
    _from_stream: &mut R,
    _to_stream: &mut W,
    _move_on_change: bool,
) -> Result<(HashMap<String, MessageInfo>, u32, u32)> {
    todo!("get_missing_files implementation")
}

async fn sync_files<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    _db: &notmuch::Database,
    _prefix: &str,
    _missing: &HashMap<String, MessageInfo>,
    _from_stream: &mut R,
    _to_stream: &mut W,
) -> Result<(u32, u32)> {
    todo!("sync_files implementation")
}

async fn sync_deletes_local<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    _prefix: &str,
    _from_stream: &mut R,
    _to_stream: &mut W,
    _no_check: bool,
) -> Result<u32> {
    todo!("sync_deletes_local implementation")
}

async fn sync_deletes_remote<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    _prefix: &str,
    _from_stream: &mut R,
    _to_stream: &mut W,
    _no_check: bool,
) -> Result<u32> {
    todo!("sync_deletes_remote implementation")
}

async fn sync_mbsync_local<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    _prefix: &str,
    _from_stream: &mut R,
    _to_stream: &mut W,
) -> Result<()> {
    todo!("sync_mbsync_local implementation")
}

async fn sync_mbsync_remote<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    _prefix: &str,
    _from_stream: &mut R,
    _to_stream: &mut W,
) -> Result<()> {
    todo!("sync_mbsync_remote implementation")
}