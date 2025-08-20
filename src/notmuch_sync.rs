#!/usr/bin/env rust

//! notmuch_sync: Synchronize notmuch email databases and message files between
//! local and remote systems.

#![allow(dead_code)] // Allow unused code since this is a work-in-progress implementation
#![allow(unused_variables)] // Allow unused variables in placeholder functions
#![allow(unused_mut)] // Allow unused mut in placeholder code

use anyhow::{anyhow, Result};
use clap::Parser;
use log::info;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::Path;
use std::process::Stdio;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time;
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};
use tokio::process::Command as TokioCommand;

/// Global transfer statistics
static TRANSFER_READ: AtomicUsize = AtomicUsize::new(0);
static TRANSFER_WRITE: AtomicUsize = AtomicUsize::new(0);

/// Command line arguments
#[derive(Parser, Debug, Clone)]
#[command(name = "notmuch-sync")]
#[command(
    about = "Synchronize notmuch email databases and message files between local and remote systems"
)]
pub struct Args {
    /// Remote host to connect to
    #[arg(short, long)]
    pub remote: Option<String>,

    /// SSH user to use
    #[arg(short, long)]
    pub user: Option<String>,

    /// Increases verbosity, up to twice (ignored on remote)
    #[arg(short, long, action = clap::ArgAction::Count)]
    pub verbose: u8,

    /// Do not print any output, overrides --verbose
    #[arg(short, long)]
    pub quiet: bool,

    /// SSH command to use
    #[arg(short = 's', long, default_value = "ssh -CTaxq")]
    pub ssh_cmd: String,

    /// Sync mbsync files (.mbsyncstate, .uidvalidity)
    #[arg(short, long)]
    pub mbsync: bool,

    /// Path to notmuch-sync on remote server
    #[arg(short, long)]
    pub path: Option<String>,

    /// Command to run to sync; overrides --remote, --user, --ssh-cmd, --path; mostly used for testing
    #[arg(short = 'c', long)]
    pub remote_cmd: Option<String>,

    /// Sync deleted messages (requires listing all messages in notmuch database, potentially expensive)
    #[arg(short, long)]
    pub delete: bool,

    /// Delete missing messages even if they don't have the 'deleted' tag (requires --delete) -- potentially unsafe
    #[arg(short = 'x', long)]
    pub delete_no_check: bool,
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
    let to_digest = if let Some(start_idx) = data.windows(pattern.len()).position(|w| w == pattern)
    {
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
                return Err(anyhow!(
                    "Sync state file '{}' corrupted, delete to sync from scratch",
                    sync_file
                ));
            }

            let stored_uuid = parts[1];
            if stored_uuid != revision.uuid {
                return Err(anyhow!(
                    "Last sync with UUID {}, but notmuch DB has UUID {}, aborting...",
                    stored_uuid,
                    revision.uuid
                ));
            }

            let rev: u64 = parts[0].parse().map_err(|_| {
                anyhow!(
                    "Sync state file '{}' corrupted, delete to sync from scratch",
                    sync_file
                )
            })?;

            if rev > revision.revision {
                return Err(anyhow!(
                    "Last sync revision {} larger than current DB revision {}, aborting...",
                    rev,
                    revision.revision
                ));
            }

            rev
        }
        Err(_) => {
            // No previous sync file, sync entire DB
            0u64.wrapping_sub(1) // -1 equivalent
        }
    };

    info!(
        "Previous sync revision {}, current revision {}.",
        rev_prev, revision.revision
    );

    // Get messages that changed since rev_prev + 1
    let query_str = if rev_prev == u64::MAX {
        // First sync - get all messages
        "*".to_string()
    } else {
        format!(
            "lastmod:{}..{}",
            rev_prev.wrapping_add(1),
            revision.revision
        )
    };

    let query = notmuch::Query::create(db, &query_str)?;
    let messages = query.search_messages()?;

    let mut changes = HashMap::new();
    for message in messages {
        let message_id = message.id().to_string();
        let tags: Vec<String> = message.tags().map(|t| t.to_string()).collect();
        let files: Vec<String> = message
            .filenames()
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
    db: &notmuch::Database,
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
            // Check if message is a ghost (removed but referenced)
            // For now, skip processing if we can't get current tags
            let current_tags: HashSet<String> = message.tags().map(|t| t.to_string()).collect();

            if tag_set != current_tags {
                info!(
                    "Setting tags {:?} for {}.",
                    tag_set.iter().collect::<Vec<_>>(),
                    mid
                );

                // Remove all current tags
                for tag in &current_tags {
                    message.remove_tag(tag)?;
                }

                // Add new tags
                for tag in &tag_set {
                    message.add_tag(tag)?;
                }

                // Sync tags to maildir flags if supported
                let _ = message.tags_to_maildir_flags(); // Ignore errors as this might not be supported
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
        let remote = args
            .remote
            .as_ref()
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

    let result = sync_local_with_streams(
        stdin,
        stdout,
        stderr,
        args.delete,
        args.delete_no_check,
        args.mbsync,
    )
    .await;

    let exit_status = child.wait().await?;
    if !exit_status.success() {
        return Err(anyhow!(
            "Remote command failed with exit status: {}",
            exit_status
        ));
    }

    result
}

/// Run synchronization in remote mode
async fn sync_remote(args: Args) -> Result<()> {
    let stdin = tokio::io::stdin();
    let stdout = tokio::io::stdout();

    sync_remote_with_streams(
        stdin,
        stdout,
        args.delete,
        args.delete_no_check,
        args.mbsync,
    )
    .await
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

    // Variables to track sync results
    let mut tchanges = 0;
    let mut fchanges = 0;
    let mut dfchanges = 0;
    let mut rmessages = 0;
    let mut rfiles = 0;
    let mut dchanges = 0;
    let mut sync_fname = String::new();

    // Perform sync operations with error handling
    let sync_result = async {
        // Perform initial sync
        let (changes_mine, changes_theirs, tc, sf) =
            initial_sync_local(&db, &prefix, &mut from_remote, &mut to_remote).await?;
        tchanges = tc;
        sync_fname = sf;

        info!(
            "Initial sync completed. Local changes: {}, Remote changes: {}, Tag changes: {}",
            changes_mine.len(),
            changes_theirs.len(),
            tchanges
        );

        // Get missing files and sync them
        let (missing, fc, dfc) = get_missing_files(
            &db,
            &prefix,
            &changes_mine,
            &changes_theirs,
            &mut from_remote,
            &mut to_remote,
            true,
        )
        .await?;
        fchanges = fc;
        dfchanges = dfc;

        let (rm, rf) =
            sync_files(&db, &prefix, &missing, &mut from_remote, &mut to_remote).await?;
        rmessages = rm;
        rfiles = rf;

        // Record the sync
        let revision = get_database_revision(&db)?;
        record_sync(&sync_fname, &revision)?;

        // Handle deletions if requested
        if delete {
            dchanges = sync_deletes_local(&db, &prefix, &mut from_remote, &mut to_remote, delete_no_check).await?;
        }

        // Handle mbsync if requested
        if mbsync {
            sync_mbsync_local(&prefix, &mut from_remote, &mut to_remote).await?;
        }

        Ok::<(), anyhow::Error>(())
    }.await;

    // Always try to read remote stats, even if there was an error
    // This prevents deadlocks where the remote side is waiting to send stats
    let remote_stats = match tokio::time::timeout(
        std::time::Duration::from_secs(30),
        async {
            let mut stats_buf = [0u8; 24]; // 6 * 4 bytes
            from_remote.read_exact(&mut stats_buf).await?;
            Ok::<[u32; 6], anyhow::Error>([
                u32::from_be_bytes([stats_buf[0], stats_buf[1], stats_buf[2], stats_buf[3]]),
                u32::from_be_bytes([stats_buf[4], stats_buf[5], stats_buf[6], stats_buf[7]]),
                u32::from_be_bytes([stats_buf[8], stats_buf[9], stats_buf[10], stats_buf[11]]),
                u32::from_be_bytes([stats_buf[12], stats_buf[13], stats_buf[14], stats_buf[15]]),
                u32::from_be_bytes([stats_buf[16], stats_buf[17], stats_buf[18], stats_buf[19]]),
                u32::from_be_bytes([stats_buf[20], stats_buf[21], stats_buf[22], stats_buf[23]]),
            ])
        }
    ).await {
        Ok(Ok(stats)) => stats,
        Ok(Err(e)) => {
            info!("Error reading remote stats: {}", e);
            [0, 0, 0, 0, 0, 0]
        }
        Err(_) => {
            info!("Timeout reading remote stats - remote may have crashed");
            [0, 0, 0, 0, 0, 0]
        }
    };

    // Now check if the main sync had an error
    sync_result?;

    info!("local:  {} new messages,\t{} new files,\t{} files copied/moved,\t{} files deleted,\t{} messages with tag changes,\t{} messages deleted", 
          rmessages, rfiles, fchanges, dfchanges, tchanges, dchanges);
    info!("remote: {} new messages,\t{} new files,\t{} files copied/moved,\t{} files deleted,\t{} messages with tag changes,\t{} messages deleted",
          remote_stats[3], remote_stats[5], remote_stats[1], remote_stats[2], remote_stats[0], remote_stats[4]);
    info!(
        "{}/{} bytes received from/sent to remote.",
        TRANSFER_READ.load(Ordering::Relaxed),
        TRANSFER_WRITE.load(Ordering::Relaxed)
    );

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

    // Variables to track sync results
    let mut tchanges = 0;
    let mut fchanges = 0;
    let mut dfchanges = 0;
    let mut rmessages = 0;
    let mut rfiles = 0;
    let mut dchanges = 0;
    let mut sync_fname = String::new();

    // Perform sync operations with error handling
    let sync_result = async {
        // Perform initial sync
        let (changes_mine, changes_theirs, tc, sf) =
            initial_sync_remote(&db, &prefix, &mut from_local, &mut to_local).await?;
        tchanges = tc;
        sync_fname = sf;

        // Get missing files and sync them
        let (missing, fc, dfc) = get_missing_files(
            &db,
            &prefix,
            &changes_mine,
            &changes_theirs,
            &mut from_local,
            &mut to_local,
            false,
        )
        .await?;
        fchanges = fc;
        dfchanges = dfc;

        let (rm, rf) =
            sync_files(&db, &prefix, &missing, &mut from_local, &mut to_local).await?;
        rmessages = rm;
        rfiles = rf;

        // Record the sync
        let revision = get_database_revision(&db)?;
        record_sync(&sync_fname, &revision)?;

        // Handle deletions if requested
        if delete {
            dchanges = sync_deletes_remote(&db, &prefix, &mut from_local, &mut to_local, delete_no_check).await?;
        }

        // Handle mbsync if requested
        if mbsync {
            sync_mbsync_remote(&prefix, &mut from_local, &mut to_local).await?;
        }

        Ok::<(), anyhow::Error>(())
    }.await;

    // Always send stats to local, even if there was an error
    // This prevents deadlocks where the local side is waiting for stats
    let stats = [tchanges, fchanges, dfchanges, rmessages, dchanges, rfiles];
    for stat in stats {
        if let Err(e) = to_local.write_all(&stat.to_be_bytes()).await {
            info!("Error sending stats to local: {}", e);
            break;
        }
    }
    let _ = to_local.flush().await;

    // Now check if the main sync had an error
    sync_result?;

    Ok(())
}

/// Get database revision information
fn get_database_revision(db: &notmuch::Database) -> Result<SyncState> {
    let revision = db.revision();
    Ok(SyncState {
        revision: revision.revision,
        uuid: revision.uuid,
    })
}

/// Perform initial sync for local side - sends first, then receives
async fn initial_sync_local<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    db: &notmuch::Database,
    prefix: &str,
    from_stream: &mut R,
    to_stream: &mut W,
) -> Result<(
    HashMap<String, MessageInfo>,
    HashMap<String, MessageInfo>,
    u32,
    String,
)> {
    let revision = get_database_revision(db)?;

    // Exchange UUIDs - local sends first
    let my_uuid = revision.uuid.clone();

    info!("Sending UUID {}...", my_uuid);
    let uuid_bytes = my_uuid.as_bytes();
    to_stream.write_all(uuid_bytes).await?;
    TRANSFER_WRITE.fetch_add(uuid_bytes.len(), Ordering::Relaxed);
    to_stream.flush().await?;

    info!("Receiving UUID...");
    let mut their_uuid_bytes = vec![0u8; 36]; // UUID length
    from_stream.read_exact(&mut their_uuid_bytes).await?;
    TRANSFER_READ.fetch_add(36, Ordering::Relaxed);

    let their_uuid = String::from_utf8(their_uuid_bytes)?;
    info!("UUIDs synced. Local: {}, Remote: {}", my_uuid, their_uuid);

    // Create sync filename
    let sync_file = format!("{}/.notmuch/notmuch-sync-{}", prefix, their_uuid);

    // Get local changes
    info!("Computing local changes...");
    let changes_mine = get_changes(db, &revision, prefix, &sync_file)?;

    // Exchange changes - local sends first
    info!("Sending local changes...");
    let changes_json = serde_json::to_vec(&changes_mine)?;
    write_data(&changes_json, to_stream).await?;

    info!("Receiving remote changes...");
    let changes_data = read_data(from_stream).await?;
    let changes_theirs: HashMap<String, MessageInfo> = serde_json::from_slice(&changes_data)?;

    info!(
        "Changes synced. Local: {}, Remote: {}",
        changes_mine.len(),
        changes_theirs.len()
    );

    // Apply remote tag changes to local messages
    let tchanges = sync_tags(db, &changes_mine, &changes_theirs)?;
    info!("Tags synced. {} tag changes applied.", tchanges);

    Ok((changes_mine, changes_theirs, tchanges, sync_file))
}

/// Perform initial sync for remote side - receives first, then sends
async fn initial_sync_remote<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    db: &notmuch::Database,
    prefix: &str,
    from_stream: &mut R,
    to_stream: &mut W,
) -> Result<(
    HashMap<String, MessageInfo>,
    HashMap<String, MessageInfo>,
    u32,
    String,
)> {
    let revision = get_database_revision(db)?;

    // Exchange UUIDs - remote receives first
    let my_uuid = revision.uuid.clone();

    info!("Receiving UUID...");
    let mut their_uuid_bytes = vec![0u8; 36]; // UUID length
    from_stream.read_exact(&mut their_uuid_bytes).await?;
    TRANSFER_READ.fetch_add(36, Ordering::Relaxed);

    let their_uuid = String::from_utf8(their_uuid_bytes)?;

    info!("Sending UUID {}...", my_uuid);
    let uuid_bytes = my_uuid.as_bytes();
    to_stream.write_all(uuid_bytes).await?;
    TRANSFER_WRITE.fetch_add(uuid_bytes.len(), Ordering::Relaxed);
    to_stream.flush().await?;

    info!("UUIDs synced. Local: {}, Remote: {}", my_uuid, their_uuid);

    // Create sync filename
    let sync_file = format!("{}/.notmuch/notmuch-sync-{}", prefix, their_uuid);

    // Get local changes
    info!("Computing local changes...");
    let changes_mine = get_changes(db, &revision, prefix, &sync_file)?;

    // Exchange changes - remote receives first
    info!("Receiving remote changes...");
    let changes_data = read_data(from_stream).await?;
    let changes_theirs: HashMap<String, MessageInfo> = serde_json::from_slice(&changes_data)?;

    info!("Sending local changes...");
    let changes_json = serde_json::to_vec(&changes_mine)?;
    write_data(&changes_json, to_stream).await?;

    info!(
        "Changes synced. Local: {}, Remote: {}",
        changes_mine.len(),
        changes_theirs.len()
    );

    // Apply remote tag changes to local messages
    let tchanges = sync_tags(db, &changes_mine, &changes_theirs)?;
    info!("Tags synced. {} tag changes applied.", tchanges);

    Ok((changes_mine, changes_theirs, tchanges, sync_file))
}

async fn get_missing_files<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    db: &notmuch::Database,
    prefix: &str,
    changes_mine: &HashMap<String, MessageInfo>,
    changes_theirs: &HashMap<String, MessageInfo>,
    from_stream: &mut R,
    to_stream: &mut W,
    move_on_change: bool,
) -> Result<(HashMap<String, MessageInfo>, u32, u32)> {
    let mut missing = HashMap::new();
    let mut moves_copies = 0;
    let mut deletions = 0;

    // First pass: determine which files need hash checks
    let mut hash_requests = Vec::new();

    for (message_id, their_info) in changes_theirs {
        if let Some(message) = db.find_message(message_id)? {
            let my_files: HashSet<String> = message
                .filenames()
                .map(|f| {
                    f.strip_prefix(prefix)
                        .unwrap_or(&f)
                        .to_string_lossy()
                        .to_string()
                })
                .collect();

            let their_files: HashSet<String> = their_info.files.iter().cloned().collect();
            let missing_files: Vec<String> = their_files.difference(&my_files).cloned().collect();

            if !missing_files.is_empty() {
                hash_requests.extend(their_info.files.iter().cloned());
            }
        } else {
            // Message doesn't exist locally - we need all their files
            missing.insert(message_id.clone(), their_info.clone());
        }
    }

    // Exchange hash requests - sequential to avoid deadlocks
    info!("Sending {} hash requests to remote...", hash_requests.len());
    let request_data = serde_json::to_vec(&hash_requests)?;
    write_data(&request_data, to_stream).await?;

    info!("Receiving hash requests from remote...");
    let remote_request_data = read_data(from_stream).await?;
    let remote_hash_requests: Vec<String> = serde_json::from_slice(&remote_request_data)?;

    // Compute and exchange hashes - sequential
    info!(
        "Computing and sending {} file hashes...",
        remote_hash_requests.len()
    );
    let mut hashes = Vec::new();
    for file_path in &remote_hash_requests {
        let full_path = format!("{}/{}", prefix, file_path);
        let file_data = fs::read(&full_path)?;
        let hash = digest(&file_data);
        hashes.push(hash);
    }
    let hash_data = serde_json::to_vec(&hashes)?;
    write_data(&hash_data, to_stream).await?;

    info!("Receiving hashes from remote...");
    let remote_hash_data = read_data(from_stream).await?;
    let remote_hashes: Vec<String> = serde_json::from_slice(&remote_hash_data)?;

    // Build hash map for comparison
    let remote_hash_map: HashMap<String, String> = hash_requests
        .into_iter()
        .zip(remote_hashes.into_iter())
        .collect();

    // Second pass: determine moves/copies and final missing files
    for (message_id, their_info) in changes_theirs {
        if let Some(message) = db.find_message(message_id)? {
            let my_files: HashMap<String, String> = message
                .filenames()
                .map(|f| {
                    let rel_path = f
                        .strip_prefix(prefix)
                        .unwrap_or(&f)
                        .to_string_lossy()
                        .to_string();
                    let file_data = fs::read(&f).unwrap_or_default();
                    let hash = digest(&file_data);
                    (rel_path, hash)
                })
                .collect();

            let their_files: HashSet<String> = their_info.files.iter().cloned().collect();
            let my_file_set: HashSet<String> = my_files.keys().cloned().collect();
            let missing_files: Vec<String> =
                their_files.difference(&my_file_set).cloned().collect();

            let mut actual_missing = Vec::new();

            for missing_file in missing_files {
                if let Some(remote_hash) = remote_hash_map.get(&missing_file) {
                    // Check if this file exists locally with the same hash (moved/copied)
                    let local_matches: Vec<&String> = my_files
                        .iter()
                        .filter(|(_, hash)| *hash == remote_hash)
                        .map(|(path, _)| path)
                        .collect();

                    if !local_matches.is_empty() {
                        let src_path = format!("{}/{}", prefix, local_matches[0]);
                        let dst_path = format!("{}/{}", prefix, missing_file);

                        // Determine if this should be a copy or move
                        let should_copy = their_files.contains(local_matches[0]);
                        let should_move = !changes_mine.contains_key(message_id) || move_on_change;

                        if should_copy {
                            info!("Copying {} to {}", src_path, dst_path);
                            if let Some(parent) = Path::new(&dst_path).parent() {
                                fs::create_dir_all(parent)?;
                            }
                            fs::copy(&src_path, &dst_path)?;
                            moves_copies += 1;
                        } else if should_move {
                            info!("Moving {} to {}", src_path, dst_path);
                            if let Some(parent) = Path::new(&dst_path).parent() {
                                fs::create_dir_all(parent)?;
                            }
                            fs::rename(&src_path, &dst_path)?;
                            moves_copies += 1;
                        } else {
                            actual_missing.push(missing_file);
                        }
                    } else {
                        actual_missing.push(missing_file);
                    }
                } else {
                    actual_missing.push(missing_file);
                }
            }

            if !actual_missing.is_empty() {
                missing.insert(
                    message_id.clone(),
                    MessageInfo {
                        tags: their_info.tags.clone(),
                        files: actual_missing,
                    },
                );
            }

            // Handle file deletions if message not in local changes
            if !changes_mine.contains_key(message_id) {
                let my_file_set: HashSet<String> = my_files.keys().cloned().collect();
                let their_file_set: HashSet<String> = their_info.files.iter().cloned().collect();
                let to_delete: Vec<String> =
                    my_file_set.difference(&their_file_set).cloned().collect();

                for file_to_delete in to_delete {
                    let file_path = format!("{}/{}", prefix, file_to_delete);
                    info!("Deleting {}", file_path);
                    fs::remove_file(&file_path)?;

                    // Also remove from notmuch database
                    if let Err(e) = db.remove_message(&file_path) {
                        info!(
                            "Could not remove message {} from database: {}",
                            file_path, e
                        );
                    }

                    deletions += 1;
                }
            }
        }
    }

    Ok((missing, moves_copies, deletions))
}

async fn sync_files<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    db: &notmuch::Database,
    prefix: &str,
    missing: &HashMap<String, MessageInfo>,
    from_stream: &mut R,
    to_stream: &mut W,
) -> Result<(u32, u32)> {
    // Collect files we need from remote
    let files_needed: Vec<String> = missing
        .values()
        .flat_map(|info| &info.files)
        .cloned()
        .collect();

    // Exchange file lists - sequential
    info!(
        "Sending list of {} files needed from remote...",
        files_needed.len()
    );
    let file_list_data = serde_json::to_vec(&files_needed)?;
    write_data(&file_list_data, to_stream).await?;

    info!("Receiving list of files to send to remote...");
    let remote_file_list_data = read_data(from_stream).await?;
    let files_to_send: Vec<String> = serde_json::from_slice(&remote_file_list_data)?;

    info!(
        "File lists exchanged. Need {} files, sending {} files",
        files_needed.len(),
        files_to_send.len()
    );

    // Send files to remote first
    for (idx, file_path) in files_to_send.iter().enumerate() {
        info!(
            "{}/{} Sending {} to remote...",
            idx + 1,
            files_to_send.len(),
            file_path
        );
        let full_path = format!("{}/{}", prefix, file_path);
        let file_data = fs::read(&full_path)?;
        write_data(&file_data, to_stream).await?;
    }

    // Then receive files from remote
    for (idx, file_path) in files_needed.iter().enumerate() {
        info!(
            "{}/{} Receiving {} from remote...",
            idx + 1,
            files_needed.len(),
            file_path
        );
        let file_data = read_data(from_stream).await?;

        let full_path = format!("{}/{}", prefix, file_path);

        // Check if file already exists and has different content
        if Path::new(&full_path).exists() {
            let existing_data = fs::read(&full_path)?;
            let existing_hash = digest(&existing_data);
            let new_hash = digest(&file_data);

            if existing_hash != new_hash {
                return Err(anyhow!(
                    "File {} already exists with different content!",
                    full_path
                ));
            }
        }

        // Create parent directories
        if let Some(parent) = Path::new(&full_path).parent() {
            fs::create_dir_all(parent)?;
        }

        // Write file
        fs::write(&full_path, &file_data)?;
    }

    // Add received files to notmuch database
    let mut new_messages = 0;

    for (message_id, info) in missing {
        for file_path in &info.files {
            let full_path = format!("{}/{}", prefix, file_path);
            info!("Adding {} to database...", full_path);

            // Add the message file to the database
            match db.index_file(&full_path, None) {
                Ok(message) => {
                    new_messages += 1;

                    // Set the tags for the newly added message
                    let current_tags: HashSet<String> =
                        message.tags().map(|t| t.to_string()).collect();
                    let desired_tags: HashSet<String> = info.tags.iter().cloned().collect();

                    if current_tags != desired_tags {
                        info!(
                            "Setting tags {:?} for added message {}",
                            info.tags,
                            message.id()
                        );

                        // Remove current tags
                        for tag in &current_tags {
                            let _ = message.remove_tag(tag);
                        }

                        // Add desired tags
                        for tag in &desired_tags {
                            let _ = message.add_tag(tag);
                        }

                        let _ = message.tags_to_maildir_flags();
                    }
                }
                Err(e) => {
                    info!("Failed to add {} to database: {}", full_path, e);
                    // Count it anyway since the file was received
                    new_messages += 1;
                }
            }
        }
    }

    info!(
        "File sync completed. {} new messages, {} files received",
        new_messages,
        files_needed.len()
    );

    Ok((new_messages, files_needed.len() as u32))
}

/// Get all message IDs from the notmuch database
fn get_all_message_ids(db: &notmuch::Database) -> Result<Vec<String>> {
    info!("Getting all message IDs from database...");

    // Query for all messages
    let query = notmuch::Query::create(db, "*")?;
    let messages = query.search_messages()?;

    let mut message_ids = Vec::new();
    for message in messages {
        message_ids.push(message.id().to_string());
    }

    info!("Found {} message IDs", message_ids.len());
    Ok(message_ids)
}

async fn sync_deletes_local<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    db: &notmuch::Database,
    _prefix: &str,
    from_stream: &mut R,
    to_stream: &mut W,
    no_check: bool,
) -> Result<u32> {

    // Get local and remote message IDs - sequential
    let local_ids = get_all_message_ids(db)?;

    info!("Receiving all message IDs from remote...");
    let id_data = read_data(from_stream).await?;
    let remote_ids: Vec<String> = serde_json::from_slice(&id_data)?;

    info!(
        "Message IDs synced. Local: {}, Remote: {}",
        local_ids.len(),
        remote_ids.len()
    );

    // Determine which messages to delete on each side
    let local_set: HashSet<String> = local_ids.into_iter().collect();
    let remote_set: HashSet<String> = remote_ids.into_iter().collect();

    let to_delete_locally: Vec<String> = local_set.difference(&remote_set).cloned().collect();
    let to_delete_remotely: Vec<String> = remote_set.difference(&local_set).cloned().collect();

    // Send deletion list to remote first
    info!(
        "Sending {} message IDs to be deleted to remote...",
        to_delete_remotely.len()
    );
    let delete_data = serde_json::to_vec(&to_delete_remotely)?;
    write_data(&delete_data, to_stream).await?;

    // Then delete messages locally
    let mut deleted = 0;

    for message_id in &to_delete_locally {
        if let Some(message) = db.find_message(message_id)? {
            let has_deleted_tag = message.tags().any(|tag| tag == "deleted");

            if has_deleted_tag || no_check {
                deleted += 1;
                info!("Removing {} from database and deleting files", message_id);

                // Remove files and message from database
                let filenames: Vec<_> = message.filenames().collect();
                for filename in &filenames {
                    info!("Removing file {}", filename.display());
                    if let Err(e) = fs::remove_file(filename) {
                        // File might already be deleted, that's ok
                        info!("Could not remove file {}: {}", filename.display(), e);
                    }
                }

                // Remove message from database
                for filename in &filenames {
                    if let Err(e) = db.remove_message(filename) {
                        info!(
                            "Could not remove message {} from database: {}",
                            filename.display(),
                            e
                        );
                    }
                }
            } else {
                info!(
                    "{} set to be removed, but not tagged 'deleted'!",
                    message_id
                );
                // Force a tag update to make it appear in next changeset
                let dummy_tag = format!(
                    "dummy-{}",
                    time::SystemTime::now()
                        .duration_since(time::UNIX_EPOCH)?
                        .as_nanos()
                );
                message.add_tag(&dummy_tag)?;
                message.remove_tag(&dummy_tag)?;
            }
        }
    }

    Ok(deleted)
}

async fn sync_deletes_remote<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    db: &notmuch::Database,
    _prefix: &str,
    from_stream: &mut R,
    to_stream: &mut W,
    no_check: bool,
) -> Result<u32> {

    // Send our message IDs to local
    let local_ids = get_all_message_ids(db)?;
    let id_data = serde_json::to_vec(&local_ids)?;
    write_data(&id_data, to_stream).await?;

    // Receive deletion list from local
    let delete_data = read_data(from_stream).await?;
    let to_delete: Vec<String> = serde_json::from_slice(&delete_data)?;

    let mut deleted = 0;

    for message_id in &to_delete {
        if let Some(message) = db.find_message(message_id)? {
            let has_deleted_tag = message.tags().any(|tag| tag == "deleted");

            if has_deleted_tag || no_check {
                deleted += 1;
                info!("Removing {} from database and deleting files", message_id);

                // Remove files and message from database
                let filenames: Vec<_> = message.filenames().collect();
                for filename in &filenames {
                    if let Err(e) = fs::remove_file(filename) {
                        // File might already be deleted, that's ok
                        info!("Could not remove file {}: {}", filename.display(), e);
                    }
                }

                // Remove message from database
                for filename in &filenames {
                    if let Err(e) = db.remove_message(filename) {
                        info!(
                            "Could not remove message {} from database: {}",
                            filename.display(),
                            e
                        );
                    }
                }
            } else {
                info!(
                    "{} not on local, but no 'deleted' tag - forcing tag update",
                    message_id
                );
                // Force a tag update to make it appear in next changeset
                let dummy_tag = format!(
                    "dummy-{}",
                    time::SystemTime::now()
                        .duration_since(time::UNIX_EPOCH)?
                        .as_nanos()
                );
                message.add_tag(&dummy_tag)?;
                message.remove_tag(&dummy_tag)?;
            }
        }
    }

    Ok(deleted)
}

async fn sync_mbsync_local<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    prefix: &str,
    from_stream: &mut R,
    to_stream: &mut W,
) -> Result<()> {
    // Get local mbsync file stats
    let local_stats = get_mbsync_stats(prefix)?;

    // Exchange mbsync stats - sequential protocol (local sends first, remote receives first)
    info!("Sending local mbsync file stats...");
    let stats_data = serde_json::to_vec(&local_stats)?;
    write_data(&stats_data, to_stream).await?;

    info!("Receiving remote mbsync file stats...");
    let remote_stats_data = read_data(from_stream).await?;
    let remote_stats: HashMap<String, f64> = serde_json::from_slice(&remote_stats_data)?;

    // Determine which files to pull and push
    let mut files_to_pull = Vec::new();
    let mut files_to_push = Vec::new();

    for (file_path, local_mtime) in &local_stats {
        if let Some(remote_mtime) = remote_stats.get(file_path) {
            if *remote_mtime > *local_mtime {
                files_to_pull.push(file_path.clone());
            } else if *local_mtime > *remote_mtime {
                files_to_push.push(file_path.clone());
            }
        } else {
            files_to_push.push(file_path.clone());
        }
    }

    // Add files that exist only on remote
    for file_path in remote_stats.keys() {
        if !local_stats.contains_key(file_path) {
            files_to_pull.push(file_path.clone());
        }
    }

    info!(
        "mbsync sync: pulling {} files, pushing {} files",
        files_to_pull.len(),
        files_to_push.len()
    );

    // Exchange file lists and files - sequential
    // Send pull list to remote
    let pull_data = serde_json::to_vec(&files_to_pull)?;
    write_data(&pull_data, to_stream).await?;

    // Send push list to remote
    let push_data = serde_json::to_vec(&files_to_push)?;
    write_data(&push_data, to_stream).await?;

    // Send files to remote
    for file_path in &files_to_push {
        let full_path = format!("{}/{}", prefix, file_path);
        let mtime = local_stats.get(file_path).unwrap_or(&0.0);

        // Send mtime first
        to_stream.write_all(&mtime.to_be_bytes()).await?;

        // Send file content
        let file_data = fs::read(&full_path)?;
        write_data(&file_data, to_stream).await?;
    }

    // Receive files from remote
    for file_path in &files_to_pull {
        let full_path = format!("{}/{}", prefix, file_path);

        // Receive mtime
        let mut mtime_bytes = [0u8; 8];
        from_stream.read_exact(&mut mtime_bytes).await?;
        let mtime = f64::from_be_bytes(mtime_bytes);

        // Receive file content
        let file_data = read_data(from_stream).await?;

        // Create parent directories
        if let Some(parent) = Path::new(&full_path).parent() {
            fs::create_dir_all(parent)?;
        }

        // Write file
        fs::write(&full_path, &file_data)?;

        // Set file modification time
        let mtime_secs = mtime as u64;
        let mtime_nanos = ((mtime - mtime_secs as f64) * 1_000_000_000.0) as u32;

        // Set the file time using utime syscall equivalent
        use libc::{timeval, utimes};
        use std::ffi::CString;

        let path_cstr = CString::new(full_path.as_bytes())?;
        let times = [
            timeval {
                tv_sec: mtime_secs as libc::time_t,
                tv_usec: (mtime_nanos / 1000) as libc::suseconds_t,
            },
            timeval {
                tv_sec: mtime_secs as libc::time_t,
                tv_usec: (mtime_nanos / 1000) as libc::suseconds_t,
            },
        ];
        unsafe {
            utimes(path_cstr.as_ptr(), times.as_ptr());
        }
    }

    info!("mbsync file sync completed");

    Ok(())
}

async fn sync_mbsync_remote<R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(
    prefix: &str,
    from_stream: &mut R,
    to_stream: &mut W,
) -> Result<()> {
    // Get local mbsync file stats
    let local_stats = get_mbsync_stats(prefix)?;

    // Exchange mbsync stats - sequential protocol (remote receives first, then sends)
    info!("Receiving local mbsync file stats...");
    let local_stats_data = read_data(from_stream).await?;
    let remote_local_stats: HashMap<String, f64> = serde_json::from_slice(&local_stats_data)?;

    info!("Sending remote mbsync file stats...");
    let stats_data = serde_json::to_vec(&local_stats)?;
    write_data(&stats_data, to_stream).await?;

    // Receive pull and push lists from local
    let pull_data = read_data(from_stream).await?;
    let files_to_send: Vec<String> = serde_json::from_slice(&pull_data)?;

    let push_data = read_data(from_stream).await?;
    let files_to_receive: Vec<String> = serde_json::from_slice(&push_data)?;

    // Exchange files - sequential to avoid deadlocks
    // Send files to local first
    for file_path in &files_to_send {
        let full_path = format!("{}/{}", prefix, file_path);
        let mtime = local_stats.get(file_path).unwrap_or(&0.0);

        // Send mtime first
        to_stream.write_all(&mtime.to_be_bytes()).await?;

        // Send file content
        let file_data = fs::read(&full_path)?;
        write_data(&file_data, to_stream).await?;
    }

    // Then receive files from local
    for file_path in &files_to_receive {
        let full_path = format!("{}/{}", prefix, file_path);

        // Receive mtime
        let mut mtime_bytes = [0u8; 8];
        from_stream.read_exact(&mut mtime_bytes).await?;
        let mtime = f64::from_be_bytes(mtime_bytes);

        // Receive file content
        let file_data = read_data(from_stream).await?;

        // Create parent directories
        if let Some(parent) = Path::new(&full_path).parent() {
            fs::create_dir_all(parent)?;
        }

        // Write file
        fs::write(&full_path, &file_data)?;

        // Set file modification time (same as in local version)
        use libc::{timeval, utimes};
        use std::ffi::CString;

        let mtime_secs = mtime as u64;
        let mtime_nanos = ((mtime - mtime_secs as f64) * 1_000_000_000.0) as u32;

        let path_cstr = CString::new(full_path.as_bytes())?;
        let times = [
            timeval {
                tv_sec: mtime_secs as libc::time_t,
                tv_usec: (mtime_nanos / 1000) as libc::suseconds_t,
            },
            timeval {
                tv_sec: mtime_secs as libc::time_t,
                tv_usec: (mtime_nanos / 1000) as libc::suseconds_t,
            },
        ];
        unsafe {
            utimes(path_cstr.as_ptr(), times.as_ptr());
        }
    }

    info!("mbsync remote sync completed");
    Ok(())
}

/// Get mbsync file statistics (modification times)
fn get_mbsync_stats(prefix: &str) -> Result<HashMap<String, f64>> {
    let mut stats = HashMap::new();
    let patterns = [".uidvalidity", ".mbsyncstate"];

    for pattern in &patterns {
        let pattern_path = format!("{}/**/{}", prefix, pattern);
        match glob::glob(&pattern_path) {
            Ok(paths) => {
                for path in paths {
                    match path {
                        Ok(file_path) => {
                            if let Ok(metadata) = file_path.metadata() {
                                if let Ok(modified) = metadata.modified() {
                                    if let Ok(duration) =
                                        modified.duration_since(std::time::UNIX_EPOCH)
                                    {
                                        let relative_path = file_path
                                            .strip_prefix(prefix)
                                            .unwrap_or(&file_path)
                                            .to_string_lossy()
                                            .to_string();
                                        stats.insert(relative_path, duration.as_secs_f64());
                                    }
                                }
                            }
                        }
                        Err(e) => {
                            info!("Error reading path for pattern {}: {}", pattern, e);
                        }
                    }
                }
            }
            Err(e) => {
                info!("Error globbing pattern {}: {}", pattern_path, e);
            }
        }
    }

    info!("Found {} mbsync files", stats.len());
    Ok(stats)
}
