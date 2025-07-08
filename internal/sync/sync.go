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

// SyncFiles synchronizes files between local and remote
func SyncFiles(prefix string, missing map[string]interface{}, fromStream io.Reader, toStream io.Writer) (int, int, error) {
	changes := map[string]int{
		"messages": 0,
		"files":    0,
	}

	// Collect files to send and receive
	filesToSend := make([]string, 0)
	filesToReceive := make([]map[string]interface{}, 0)

	// Process missing files
	for msgID, data := range missing {
		msgData, ok := data.(map[string]interface{})
		if !ok {
			continue
		}

		files, ok := msgData["files"].([]interface{})
		if !ok {
			continue
		}

		for _, f := range files {
			fileMap, ok := f.(map[string]interface{})
			if !ok {
				continue
			}

			fileName, ok := fileMap["name"].(string)
			if !ok {
				continue
			}

			fileSha, ok := fileMap["sha"].(string)
			if !ok {
				continue
			}

			// Check if we have this file locally
			localPath := filepath.Join(prefix, fileName)
			if _, err := os.Stat(localPath); err == nil {
				// We have the file, add to send list
				filesToSend = append(filesToSend, fileName)
			} else {
				// We don't have the file, add to receive list
				filesToReceive = append(filesToReceive, map[string]interface{}{
					"name": fileName,
					"sha":  fileSha,
					"id":   msgID,
				})
			}
		}
	}

	// Exchange file lists using goroutines
	var wg sync.WaitGroup
	var sendErr, recvErr error
	var remoteFilesToSend []string

	wg.Add(2)

	// Send our file list
	go func() {
		defer wg.Done()

		// Send number of files we're requesting
		if err := protocol.WriteUint32(uint32(len(filesToReceive)), toStream); err != nil {
			sendErr = err
			return
		}

		// Send file names we're requesting
		for _, f := range filesToReceive {
			fileName := f["name"].(string)
			if err := protocol.Write([]byte(fileName), toStream); err != nil {
				sendErr = err
				return
			}
		}
	}()

	// Receive their file list
	go func() {
		defer wg.Done()

		// Receive number of files they're requesting
		numFiles, err := protocol.ReadUint32(fromStream)
		if err != nil {
			recvErr = err
			return
		}

		// Receive file names they're requesting
		for i := 0; i < int(numFiles); i++ {
			fileNameData, err := protocol.Read(fromStream)
			if err != nil {
				recvErr = err
				return
			}
			remoteFilesToSend = append(remoteFilesToSend, string(fileNameData))
		}
	}()

	wg.Wait()

	if sendErr != nil {
		return 0, 0, fmt.Errorf("failed to send file list: %w", sendErr)
	}
	if recvErr != nil {
		return 0, 0, fmt.Errorf("failed to receive file list: %w", recvErr)
	}

	log.Printf("Missing file names synced.")

	// Exchange files using goroutines
	wg.Add(2)

	// Send files
	go func() {
		defer wg.Done()
		for idx, fileName := range remoteFilesToSend {
			log.Printf("%d/%d Sending %s...", idx+1, len(remoteFilesToSend), fileName)
			filePath := filepath.Join(prefix, fileName)
			if err := sendFile(filePath, toStream); err != nil {
				sendErr = err
				return
			}
		}
	}()

	// Receive files
	go func() {
		defer wg.Done()
		db, err := notmuch.OpenDatabase()
		if err != nil {
			recvErr = err
			return
		}

		for idx, f := range filesToReceive {
			fileName := f["name"].(string)
			fileSha := f["sha"].(string)
			msgID := f["id"].(string)

			log.Printf("%d/%d Receiving %s...", idx+1, len(filesToReceive), fileName)

			dstPath := filepath.Join(prefix, fileName)
			if err := receiveFile(dstPath, fromStream, fileSha); err != nil {
				recvErr = err
				return
			}

			// Add to database
			log.Printf("Adding %s to DB.", dstPath)
			if err := db.AddMessage(dstPath); err != nil {
				// Check if it's a duplicate
				if !strings.Contains(err.Error(), "duplicate") {
					recvErr = fmt.Errorf("failed to add message to database: %w", err)
					return
				}
			} else {
				changes["messages"]++

				// Set tags for the message
				if msgData, ok := missing[msgID].(map[string]interface{}); ok {
					if tags, ok := msgData["tags"].([]interface{}); ok {
						var tagStrings []string
						for _, tag := range tags {
							if tagStr, ok := tag.(string); ok {
								tagStrings = append(tagStrings, tagStr)
							}
						}

						log.Printf("Setting tags %v for received %s", tagStrings, msgID)
						if err := db.SetMessageTags(msgID, tagStrings); err != nil {
							log.Printf("Warning: failed to set tags for %s: %v", msgID, err)
						}
					}
				}
			}

			changes["files"]++
		}
	}()

	wg.Wait()

	if sendErr != nil {
		return 0, 0, fmt.Errorf("failed to send files: %w", sendErr)
	}
	if recvErr != nil {
		return 0, 0, fmt.Errorf("failed to receive files: %w", recvErr)
	}

	log.Printf("Missing files synced.")

	return changes["messages"], changes["files"], nil
}

// sendFile sends a file over the stream
func sendFile(filePath string, stream io.Writer) error {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to read file %s: %w", filePath, err)
	}

	return protocol.Write(data, stream)
}

// receiveFile receives a file from the stream
func receiveFile(filePath string, stream io.Reader, expectedSha string) error {
	data, err := protocol.Read(stream)
	if err != nil {
		return fmt.Errorf("failed to read file data: %w", err)
	}

	// Verify checksum
	actualSha := protocol.Digest(data)
	if expectedSha != "" && actualSha != expectedSha {
		return fmt.Errorf("checksum mismatch for file %s: expected %s, got %s", filePath, expectedSha, actualSha)
	}

	// Check if file already exists
	if _, err := os.Stat(filePath); err == nil {
		// File exists, check if it's the same
		existingData, err := os.ReadFile(filePath)
		if err != nil {
			return fmt.Errorf("failed to read existing file %s: %w", filePath, err)
		}

		existingSha := protocol.Digest(existingData)
		if existingSha != actualSha {
			return fmt.Errorf("file %s already exists with different content", filePath)
		}

		// File is the same, no need to write
		return nil
	}

	// Create directory if needed
	if err := os.MkdirAll(filepath.Dir(filePath), 0755); err != nil {
		return fmt.Errorf("failed to create directory for %s: %w", filePath, err)
	}

	// Write file
	if err := os.WriteFile(filePath, data, 0644); err != nil {
		return fmt.Errorf("failed to write file %s: %w", filePath, err)
	}

	return nil
}

func SyncDeletesLocal(fromStream io.Reader, toStream io.Writer, deleteNoCheck bool) (int, error) {
	ids := make(map[string][]string)
	deletions := 0

	// Use goroutines to get local IDs and receive remote IDs concurrently
	var wg sync.WaitGroup
	var getErr, recvErr error

	wg.Add(2)

	// Get local message IDs
	go func() {
		defer wg.Done()

		db, err := notmuch.OpenDatabase()
		if err != nil {
			getErr = err
			return
		}

		log.Printf("Getting all message IDs from DB...")
		localIDs, err := db.GetAllMessageIDs()
		if err != nil {
			getErr = err
			return
		}

		ids["mine"] = localIDs
	}()

	// Receive remote message IDs
	go func() {
		defer wg.Done()

		log.Printf("Receiving all message IDs from remote...")
		numIDs, err := protocol.ReadUint32(fromStream)
		if err != nil {
			recvErr = err
			return
		}

		var remoteIDs []string
		for i := 0; i < int(numIDs); i++ {
			idData, err := protocol.Read(fromStream)
			if err != nil {
				recvErr = err
				return
			}
			remoteIDs = append(remoteIDs, string(idData))
		}

		ids["theirs"] = remoteIDs
	}()

	wg.Wait()

	if getErr != nil {
		return 0, fmt.Errorf("failed to get local message IDs: %w", getErr)
	}
	if recvErr != nil {
		return 0, fmt.Errorf("failed to receive remote message IDs: %w", recvErr)
	}

	log.Printf("Message IDs synced.")

	// Use goroutines to send deletion IDs and process local deletions
	wg.Add(2)

	// Send IDs to be deleted on remote
	go func() {
		defer wg.Done()

		// Find IDs that exist on remote but not locally
		remoteSet := make(map[string]bool)
		for _, id := range ids["theirs"] {
			remoteSet[id] = true
		}

		var toDelRemote []string
		for _, id := range ids["theirs"] {
			found := false
			for _, localID := range ids["mine"] {
				if id == localID {
					found = true
					break
				}
			}
			if !found {
				toDelRemote = append(toDelRemote, id)
			}
		}

		log.Printf("Sending message IDs to be deleted to remote...")
		if err := protocol.WriteUint32(uint32(len(toDelRemote)), toStream); err != nil {
			recvErr = err
			return
		}

		for _, id := range toDelRemote {
			if err := protocol.Write([]byte(id), toStream); err != nil {
				recvErr = err
				return
			}
		}
	}()

	// Process local deletions
	go func() {
		defer wg.Done()

		// Find IDs that exist locally but not on remote
		localSet := make(map[string]bool)
		for _, id := range ids["mine"] {
			localSet[id] = true
		}

		var toDelLocal []string
		for _, id := range ids["mine"] {
			found := false
			for _, remoteID := range ids["theirs"] {
				if id == remoteID {
					found = true
					break
				}
			}
			if !found {
				toDelLocal = append(toDelLocal, id)
			}
		}

		db, err := notmuch.OpenDatabase()
		if err != nil {
			getErr = err
			return
		}

		for _, msgID := range toDelLocal {
			if err := db.DeleteMessage(msgID, deleteNoCheck); err != nil {
				log.Printf("Warning: failed to delete message %s: %v", msgID, err)
			} else {
				deletions++
			}
		}
	}()

	wg.Wait()

	if getErr != nil {
		return deletions, fmt.Errorf("failed to process local deletions: %w", getErr)
	}
	if recvErr != nil {
		return deletions, fmt.Errorf("failed to send remote deletions: %w", recvErr)
	}

	return deletions, nil
}

func SyncDeletesRemote(fromStream io.Reader, toStream io.Writer, deleteNoCheck bool) (int, error) {
	deletions := 0

	// Get all local message IDs
	db, err := notmuch.OpenDatabase()
	if err != nil {
		return 0, fmt.Errorf("failed to open database: %w", err)
	}

	localIDs, err := db.GetAllMessageIDs()
	if err != nil {
		return 0, fmt.Errorf("failed to get local message IDs: %w", err)
	}

	// Send local IDs to local side
	if err := protocol.WriteUint32(uint32(len(localIDs)), toStream); err != nil {
		return 0, fmt.Errorf("failed to send ID count: %w", err)
	}

	for _, id := range localIDs {
		if err := protocol.Write([]byte(id), toStream); err != nil {
			return 0, fmt.Errorf("failed to send ID: %w", err)
		}
	}

	// Receive IDs to delete from local side
	numToDelete, err := protocol.ReadUint32(fromStream)
	if err != nil {
		return 0, fmt.Errorf("failed to read deletion count: %w", err)
	}

	for i := 0; i < int(numToDelete); i++ {
		idData, err := protocol.Read(fromStream)
		if err != nil {
			return 0, fmt.Errorf("failed to read ID to delete: %w", err)
		}

		msgID := string(idData)
		if err := db.DeleteMessage(msgID, deleteNoCheck); err != nil {
			log.Printf("Warning: failed to delete message %s: %v", msgID, err)
		} else {
			deletions++
		}
	}

	return deletions, nil
}

func SyncMBSyncLocal(prefix string, fromStream io.Reader, toStream io.Writer) error {
	// Get local mbsync file stats
	localMBSync := make(map[string]int64)

	// Find .uidvalidity and .mbsyncstate files
	for _, pattern := range []string{".uidvalidity", ".mbsyncstate"} {
		err := filepath.Walk(prefix, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}

			if strings.HasSuffix(info.Name(), pattern) {
				relPath := strings.TrimPrefix(path, prefix)
				if strings.HasPrefix(relPath, "/") {
					relPath = relPath[1:]
				}
				localMBSync[relPath] = info.ModTime().Unix()
			}

			return nil
		})

		if err != nil {
			return fmt.Errorf("failed to find %s files: %w", pattern, err)
		}
	}

	log.Printf("Getting local mbsync file stats...")

	// Use goroutines to exchange mbsync stats
	var wg sync.WaitGroup
	var sendErr, recvErr error
	var remoteMBSync map[string]int64

	wg.Add(2)

	// Send local mbsync stats
	go func() {
		defer wg.Done()

		statsJSON, err := json.Marshal(localMBSync)
		if err != nil {
			sendErr = err
			return
		}

		sendErr = protocol.Write(statsJSON, toStream)
	}()

	// Receive remote mbsync stats
	go func() {
		defer wg.Done()

		log.Printf("Receiving mbsync file stats from remote...")
		statsData, err := protocol.Read(fromStream)
		if err != nil {
			recvErr = err
			return
		}

		recvErr = json.Unmarshal(statsData, &remoteMBSync)
	}()

	wg.Wait()

	if sendErr != nil {
		return fmt.Errorf("failed to send mbsync stats: %w", sendErr)
	}
	if recvErr != nil {
		return fmt.Errorf("failed to receive mbsync stats: %w", recvErr)
	}

	// TODO: Implement file transfer logic based on modification times
	log.Printf("MBSync stats exchanged (file transfer not yet implemented)")

	return nil
}

func SyncMBSyncRemote(prefix string, fromStream io.Reader, toStream io.Writer) error {
	// Get local mbsync file stats
	localMBSync := make(map[string]int64)

	// Find .uidvalidity and .mbsyncstate files
	for _, pattern := range []string{".uidvalidity", ".mbsyncstate"} {
		err := filepath.Walk(prefix, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}

			if strings.HasSuffix(info.Name(), pattern) {
				relPath := strings.TrimPrefix(path, prefix)
				if strings.HasPrefix(relPath, "/") {
					relPath = relPath[1:]
				}
				localMBSync[relPath] = info.ModTime().Unix()
			}

			return nil
		})

		if err != nil {
			return fmt.Errorf("failed to find %s files: %w", pattern, err)
		}
	}

	// Send local mbsync stats
	statsJSON, err := json.Marshal(localMBSync)
	if err != nil {
		return fmt.Errorf("failed to marshal mbsync stats: %w", err)
	}

	if err := protocol.Write(statsJSON, toStream); err != nil {
		return fmt.Errorf("failed to send mbsync stats: %w", err)
	}

	// Receive remote mbsync stats
	remoteStatsData, err := protocol.Read(fromStream)
	if err != nil {
		return fmt.Errorf("failed to receive mbsync stats: %w", err)
	}

	var remoteMBSync map[string]int64
	if err := json.Unmarshal(remoteStatsData, &remoteMBSync); err != nil {
		return fmt.Errorf("failed to parse remote mbsync stats: %w", err)
	}

	// TODO: Implement file transfer logic based on modification times
	log.Printf("MBSync stats exchanged (file transfer not yet implemented)")

	return nil
}
