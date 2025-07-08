package sync

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"github.com/google/shlex"
	"github.com/larskotthoff/notmuch-sync/internal/notmuch"
	"github.com/larskotthoff/notmuch-sync/internal/protocol"
)

// SyncLocal runs synchronization in local mode
func SyncLocal(config *Config) error {
	var cmd []string
	
	if config.RemoteCmd != "" {
		// Use shlex to split the remote command
		var err error
		cmd, err = shlex.Split(config.RemoteCmd)
		if err != nil {
			return fmt.Errorf("failed to parse remote command: %w", err)
		}
	} else {
		// Build SSH command
		sshCmd, err := shlex.Split(config.SSHCmd)
		if err != nil {
			return fmt.Errorf("failed to parse SSH command: %w", err)
		}
		
		host := config.Remote
		if config.User != "" {
			host = config.User + "@" + host
		}
		
		rargs := []string{host, config.Path}
		if config.Delete {
			rargs = append(rargs, "--delete")
		}
		if config.DeleteNoCheck {
			rargs = append(rargs, "--delete-no-check")
		}
		if config.MBSync {
			rargs = append(rargs, "--mbsync")
		}
		
		cmd = append(sshCmd, rargs...)
	}
	
	if config.Verbose >= 1 {
		log.Printf("Connecting to remote...")
	}
	
	// Start remote process
	proc := exec.Command(cmd[0], cmd[1:]...)
	
	stdin, err := proc.StdinPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdin pipe: %w", err)
	}
	
	stdout, err := proc.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}
	
	stderr, err := proc.StderrPipe()
	if err != nil {
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}
	
	if err := proc.Start(); err != nil {
		return fmt.Errorf("failed to start remote process: %w", err)
	}
	
	// Handle the synchronization
	var localChanges, remoteChanges map[string]interface{}
	var tchanges int
	var syncFilename string
	var rev *notmuch.Revision
	var prefix string
	
	// Run initial sync
	prefix, localChanges, remoteChanges, tchanges, syncFilename, rev, err = InitialSync(stdout, stdin)
	if err != nil {
		return fmt.Errorf("initial sync failed: %w", err)
	}
	
	if config.Verbose >= 2 {
		log.Printf("Local changes %+v, remote changes %+v", localChanges, remoteChanges)
	}
	
	// Get missing files and sync them
	missing, fchanges, dfchanges, err := GetMissingFiles(localChanges, remoteChanges, prefix, true)
	if err != nil {
		return fmt.Errorf("failed to get missing files: %w", err)
	}
	
	if config.Verbose >= 2 {
		log.Printf("Local missing files %+v", missing)
	}
	
	rmessages, rfiles, err := SyncFiles(prefix, missing, stdout, stdin)
	if err != nil {
		return fmt.Errorf("failed to sync files: %w", err)
	}
	
	// Record sync state
	if err := notmuch.RecordSync(syncFilename, rev); err != nil {
		return fmt.Errorf("failed to record sync: %w", err)
	}
	
	// Handle deletions if requested
	dchanges := 0
	if config.Delete {
		dchanges, err = SyncDeletesLocal(stdout, stdin, config.DeleteNoCheck)
		if err != nil {
			return fmt.Errorf("failed to sync deletions: %w", err)
		}
	}
	
	// Handle mbsync if requested
	if config.MBSync {
		if err := SyncMBSyncLocal(prefix, stdout, stdin); err != nil {
			return fmt.Errorf("failed to sync mbsync: %w", err)
		}
	}
	
	// Get remote change statistics
	if config.Verbose >= 1 {
		log.Printf("Getting change numbers from remote...")
	}
	
	remoteStatsData := make([]byte, 24) // 6 * 4 bytes
	if _, err := io.ReadFull(stdout, remoteStatsData); err != nil {
		return fmt.Errorf("failed to read remote statistics: %w", err)
	}
	protocol.GlobalTransfer.Read += 24
	
	// Parse remote statistics (6 uint32 values)
	// Order: tag changes, copied/moved files, deleted files, new messages, deleted messages, new files
	remoteStats := make([]uint32, 6)
	for i := 0; i < 6; i++ {
		remoteStats[i] = uint32(remoteStatsData[i*4])<<24 | 
						uint32(remoteStatsData[i*4+1])<<16 | 
						uint32(remoteStatsData[i*4+2])<<8 | 
						uint32(remoteStatsData[i*4+3])
	}
	
	// Close pipes
	stdin.Close()
	stdout.Close()
	
	// Wait for process to complete
	if err := proc.Wait(); err != nil {
		// Check for stderr output
		stderrData, _ := io.ReadAll(stderr)
		if len(stderrData) > 0 {
			log.Printf("Remote error: %s", string(stderrData))
			return fmt.Errorf("remote process failed: %w", err)
		}
		return fmt.Errorf("remote process failed: %w", err)
	}
	
	// Log statistics
	if config.Verbose >= 1 {
		log.Printf("local:\t%d new messages,\t%d new files,\t%d files copied/moved,\t%d files deleted,\t%d messages with tag changes,\t%d messages deleted", 
			rmessages, rfiles, fchanges, dfchanges, tchanges, dchanges)
		log.Printf("remote:\t%d new messages,\t%d new files,\t%d files copied/moved,\t%d files deleted,\t%d messages with tag changes,\t%d messages deleted", 
			remoteStats[3], remoteStats[5], remoteStats[1], remoteStats[2], remoteStats[0], remoteStats[4])
		log.Printf("%d/%d bytes received from/sent to remote.", protocol.GlobalTransfer.Read, protocol.GlobalTransfer.Write)
	}
	
	return nil
}

// SyncRemote runs synchronization in remote mode
func SyncRemote(config *Config) error {
	// Run initial sync using stdin/stdout
	prefix, localChanges, remoteChanges, tchanges, syncFilename, rev, err := InitialSync(os.Stdin, os.Stdout)
	if err != nil {
		return fmt.Errorf("initial sync failed: %w", err)
	}
	
	missing, fchanges, dfchanges, err := GetMissingFiles(localChanges, remoteChanges, prefix, false)
	if err != nil {
		return fmt.Errorf("failed to get missing files: %w", err)
	}
	
	rmessages, rfiles, err := SyncFiles(prefix, missing, os.Stdin, os.Stdout)
	if err != nil {
		return fmt.Errorf("failed to sync files: %w", err)
	}
	
	// Record sync state
	if err := notmuch.RecordSync(syncFilename, rev); err != nil {
		return fmt.Errorf("failed to record sync: %w", err)
	}
	
	// Handle deletions if requested
	dchanges := 0
	if config.Delete {
		dchanges, err = SyncDeletesRemote(os.Stdin, os.Stdout, config.DeleteNoCheck)
		if err != nil {
			return fmt.Errorf("failed to sync deletions: %w", err)
		}
	}
	
	// Handle mbsync if requested
	if config.MBSync {
		if err := SyncMBSyncRemote(prefix, os.Stdin, os.Stdout); err != nil {
			return fmt.Errorf("failed to sync mbsync: %w", err)
		}
	}
	
	// Send statistics to local
	stats := []uint32{
		uint32(tchanges),  // tag changes
		uint32(fchanges),  // copied/moved files
		uint32(dfchanges), // deleted files
		uint32(rmessages), // new messages
		uint32(dchanges),  // deleted messages
		uint32(rfiles),    // new files
	}
	
	statsData := make([]byte, 24) // 6 * 4 bytes
	for i, stat := range stats {
		statsData[i*4] = byte(stat >> 24)
		statsData[i*4+1] = byte(stat >> 16)
		statsData[i*4+2] = byte(stat >> 8)
		statsData[i*4+3] = byte(stat)
	}
	
	if _, err := os.Stdout.Write(statsData); err != nil {
		return fmt.Errorf("failed to write statistics: %w", err)
	}
	
	if err := os.Stdout.Sync(); err != nil {
		return fmt.Errorf("failed to flush stdout: %w", err)
	}
	
	return nil
}

// InitialSync performs the initial synchronization handshake
func InitialSync(fromStream io.Reader, toStream io.Writer) (string, map[string]interface{}, map[string]interface{}, int, string, *notmuch.Revision, error) {
	// Open notmuch database
	db, err := notmuch.OpenDatabase()
	if err != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to open database: %w", err)
	}
	
	prefix := db.Path
	
	// Get current revision
	revision, err := db.GetRevision()
	if err != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to get revision: %w", err)
	}
	
	// Exchange UUIDs concurrently
	var wg sync.WaitGroup
	var sendErr, recvErr error
	var theirUUID string
	
	wg.Add(2)
	
	// Send our UUID
	go func() {
		defer wg.Done()
		log.Printf("Sending UUID...")
		// Write exactly 36 bytes
		uuidToSend := revision.UUID
		if len(uuidToSend) < 36 {
			uuidToSend += strings.Repeat("\x00", 36-len(uuidToSend))
		} else if len(uuidToSend) > 36 {
			uuidToSend = uuidToSend[:36]
		}
		
		if _, err := toStream.Write([]byte(uuidToSend)); err != nil {
			sendErr = err
			return
		}
		protocol.GlobalTransfer.Write += 36
		
		if flusher, ok := toStream.(interface{ Flush() error }); ok {
			sendErr = flusher.Flush()
		}
	}()
	
	// Receive their UUID
	go func() {
		defer wg.Done()
		log.Printf("Receiving UUID...")
		uuidBytes := make([]byte, 36)
		if _, err := io.ReadFull(fromStream, uuidBytes); err != nil {
			recvErr = err
			return
		}
		protocol.GlobalTransfer.Read += 36
		theirUUID = string(uuidBytes)
	}()
	
	wg.Wait()
	
	if sendErr != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to send UUID: %w", sendErr)
	}
	if recvErr != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to receive UUID: %w", recvErr)
	}
	
	log.Printf("UUIDs synced.")
	
	// Create sync filename
	syncFilename := filepath.Join(prefix, ".notmuch", fmt.Sprintf("notmuch-sync-%s", strings.TrimRight(theirUUID, "\x00")))
	
	// Get local changes
	log.Printf("Computing local changes...")
	localChanges, err := db.GetChanges(revision, prefix, syncFilename)
	if err != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to get local changes: %w", err)
	}
	
	// Exchange changes concurrently
	var remoteChanges map[string]interface{}
	
	wg.Add(2)
	
	// Send local changes
	go func() {
		defer wg.Done()
		log.Printf("Sending local changes...")
		changesJSON, err := json.Marshal(localChanges)
		if err != nil {
			sendErr = err
			return
		}
		sendErr = protocol.Write(changesJSON, toStream)
	}()
	
	// Receive remote changes
	go func() {
		defer wg.Done()
		log.Printf("Receiving remote changes...")
		changesData, err := protocol.Read(fromStream)
		if err != nil {
			recvErr = err
			return
		}
		recvErr = json.Unmarshal(changesData, &remoteChanges)
	}()
	
	wg.Wait()
	
	if sendErr != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to send changes: %w", sendErr)
	}
	if recvErr != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to receive changes: %w", recvErr)
	}
	
	log.Printf("Changes synced.")
	
	// Sync tags
	tchanges, err := db.SyncTags(localChanges, remoteChanges)
	if err != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to sync tags: %w", err)
	}
	
	log.Printf("Tags synced.")
	
	// Get updated revision after tag sync
	updatedRevision, err := db.GetRevision()
	if err != nil {
		return "", nil, nil, 0, "", nil, fmt.Errorf("failed to get updated revision: %w", err)
	}
	
	return prefix, localChanges, remoteChanges, tchanges, syncFilename, updatedRevision, nil
}

// Placeholder functions that need to be implemented
func GetMissingFiles(localChanges, remoteChanges map[string]interface{}, prefix string, moveOnChange bool) (map[string]interface{}, int, int, error) {
	// TODO: Implement missing file detection logic
	return make(map[string]interface{}), 0, 0, nil
}

func SyncFiles(prefix string, missing map[string]interface{}, fromStream io.Reader, toStream io.Writer) (int, int, error) {
	// TODO: Implement file synchronization logic
	return 0, 0, nil
}

func SyncDeletesLocal(fromStream io.Reader, toStream io.Writer, deleteNoCheck bool) (int, error) {
	// TODO: Implement deletion synchronization for local mode
	return 0, nil
}

func SyncDeletesRemote(fromStream io.Reader, toStream io.Writer, deleteNoCheck bool) (int, error) {
	// TODO: Implement deletion synchronization for remote mode
	return 0, nil
}

func SyncMBSyncLocal(prefix string, fromStream io.Reader, toStream io.Writer) error {
	// TODO: Implement mbsync synchronization for local mode
	return nil
}

func SyncMBSyncRemote(prefix string, fromStream io.Reader, toStream io.Writer) error {
	// TODO: Implement mbsync synchronization for remote mode
	return nil
}