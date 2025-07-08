package notmuch

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
)

// Database represents a notmuch database
type Database struct {
	Path string
}

// Revision represents a database revision
type Revision struct {
	Rev  int64
	UUID string
}

// Message represents a notmuch message
type Message struct {
	ID       string   `json:"id"`
	Tags     []string `json:"tags"`
	Filenames []string `json:"filename"`
}

// OpenDatabase opens a notmuch database
func OpenDatabase() (*Database, error) {
	// Get default notmuch database path
	cmd := exec.Command("notmuch", "config", "get", "database.path")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to get database path: %w", err)
	}
	
	path := strings.TrimSpace(string(output))
	if path == "" {
		return nil, fmt.Errorf("empty database path")
	}
	
	return &Database{Path: path}, nil
}

// GetRevision gets the current database revision
func (db *Database) GetRevision() (*Revision, error) {
	// Get revision number
	cmd := exec.Command("notmuch", "count", "--lastmod")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to get revision: %w", err)
	}
	
	parts := strings.Fields(string(output))
	if len(parts) < 2 {
		return nil, fmt.Errorf("invalid revision output: %s", output)
	}
	
	rev, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		return nil, fmt.Errorf("failed to parse revision: %w", err)
	}
	
	// Get UUID - read from .notmuch directory
	uuidFile := filepath.Join(db.Path, ".notmuch", "uuid")
	uuidData, err := os.ReadFile(uuidFile)
	if err != nil {
		return nil, fmt.Errorf("failed to read UUID: %w", err)
	}
	
	uuid := strings.TrimSpace(string(uuidData))
	// Pad UUID to 36 characters as expected by the protocol
	if len(uuid) < 36 {
		uuid = uuid + strings.Repeat("\x00", 36-len(uuid))
	}
	
	return &Revision{Rev: rev, UUID: uuid}, nil
}

// GetChanges gets changes since the given revision
func (db *Database) GetChanges(revision *Revision, prefix string, syncFile string) (map[string]interface{}, error) {
	var sinceRev int64 = -1
	
	// Try to read previous sync state
	if syncFile != "" {
		if data, err := os.ReadFile(syncFile); err == nil {
			lines := strings.Split(string(data), "\n")
			if len(lines) >= 2 {
				if rev, err := strconv.ParseInt(lines[0], 10, 64); err == nil {
					uuid := strings.TrimSpace(lines[1])
					if uuid == revision.UUID {
						sinceRev = rev
					}
				}
			}
		}
	}
	
	// Build search query
	var query []string
	if sinceRev >= 0 {
		query = append(query, fmt.Sprintf("lastmod:%d..", sinceRev+1))
	} else {
		query = append(query, "*")
	}
	
	// Get messages with changes
	cmd := exec.Command("notmuch", "search", "--format=json", "--output=messages", strings.Join(query, " "))
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to search messages: %w", err)
	}
	
	var messageIDs []string
	if err := json.Unmarshal(output, &messageIDs); err != nil {
		return nil, fmt.Errorf("failed to parse message IDs: %w", err)
	}
	
	changes := make(map[string]interface{})
	
	// Get details for each message
	for _, msgID := range messageIDs {
		msg, err := db.GetMessage(msgID, prefix)
		if err != nil {
			return nil, fmt.Errorf("failed to get message %s: %w", msgID, err)
		}
		
		// Convert to the format expected by the protocol
		files := make([]map[string]interface{}, len(msg.Filenames))
		for i, filename := range msg.Filenames {
			// Make filename relative to prefix
			relPath := strings.TrimPrefix(filename, prefix)
			if relPath == filename && strings.HasPrefix(filename, prefix) {
				relPath = filename[len(prefix):]
			}
			if strings.HasPrefix(relPath, "/") {
				relPath = relPath[1:]
			}
			
			files[i] = map[string]interface{}{
				"name": relPath,
				"sha":  "", // Will be computed when needed
			}
		}
		
		changes[msgID] = map[string]interface{}{
			"tags":  msg.Tags,
			"files": files,
		}
	}
	
	return changes, nil
}

// GetMessage gets a specific message by ID
func (db *Database) GetMessage(messageID string, prefix string) (*Message, error) {
	cmd := exec.Command("notmuch", "show", "--format=json", "--", messageID)
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to show message: %w", err)
	}
	
	var result [][]map[string]interface{}
	if err := json.Unmarshal(output, &result); err != nil {
		return nil, fmt.Errorf("failed to parse message: %w", err)
	}
	
	if len(result) == 0 || len(result[0]) == 0 {
		return nil, fmt.Errorf("message not found")
	}
	
	msgData := result[0][0]
	
	// Extract tags
	var tags []string
	if tagsData, ok := msgData["tags"].([]interface{}); ok {
		for _, tag := range tagsData {
			if tagStr, ok := tag.(string); ok {
				tags = append(tags, tagStr)
			}
		}
	}
	
	// Extract filenames
	var filenames []string
	if filenamesData, ok := msgData["filename"].([]interface{}); ok {
		for _, filename := range filenamesData {
			if filenameStr, ok := filename.(string); ok {
				filenames = append(filenames, filenameStr)
			}
		}
	} else if filenameData, ok := msgData["filename"].(string); ok {
		filenames = append(filenames, filenameData)
	}
	
	return &Message{
		ID:        messageID,
		Tags:      tags,
		Filenames: filenames,
	}, nil
}

// SyncTags synchronizes tags between local and remote changes
func (db *Database) SyncTags(localChanges, remoteChanges map[string]interface{}) (int, error) {
	changeCount := 0
	
	// Process remote changes
	for msgID, remoteData := range remoteChanges {
		remoteMsg, ok := remoteData.(map[string]interface{})
		if !ok {
			continue
		}
		
		remoteTags, ok := remoteMsg["tags"].([]interface{})
		if !ok {
			continue
		}
		
		// Convert to string slice
		var remoteTagsStr []string
		for _, tag := range remoteTags {
			if tagStr, ok := tag.(string); ok {
				remoteTagsStr = append(remoteTagsStr, tagStr)
			}
		}
		
		// Check if we have local changes for this message
		var localTagsStr []string
		if localData, exists := localChanges[msgID]; exists {
			if localMsg, ok := localData.(map[string]interface{}); ok {
				if localTags, ok := localMsg["tags"].([]interface{}); ok {
					for _, tag := range localTags {
						if tagStr, ok := tag.(string); ok {
							localTagsStr = append(localTagsStr, tagStr)
						}
					}
				}
			}
		}
		
		// If we have both local and remote changes, merge tags
		var finalTags []string
		if len(localTagsStr) > 0 {
			// Union of local and remote tags
			tagSet := make(map[string]bool)
			for _, tag := range localTagsStr {
				tagSet[tag] = true
			}
			for _, tag := range remoteTagsStr {
				tagSet[tag] = true
			}
			
			for tag := range tagSet {
				finalTags = append(finalTags, tag)
			}
		} else {
			finalTags = remoteTagsStr
		}
		
		// Apply tags to message
		if err := db.SetMessageTags(msgID, finalTags); err != nil {
			return changeCount, fmt.Errorf("failed to set tags for message %s: %w", msgID, err)
		}
		
		changeCount++
	}
	
	return changeCount, nil
}

// SetMessageTags sets tags for a message
func (db *Database) SetMessageTags(messageID string, tags []string) error {
	// First, get current tags
	currentMsg, err := db.GetMessage(messageID, "")
	if err != nil {
		return err
	}
	
	// Remove all current tags
	for _, tag := range currentMsg.Tags {
		cmd := exec.Command("notmuch", "tag", "-"+tag, "--", messageID)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to remove tag %s: %w", tag, err)
		}
	}
	
	// Add new tags
	for _, tag := range tags {
		cmd := exec.Command("notmuch", "tag", "+"+tag, "--", messageID)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to add tag %s: %w", tag, err)
		}
	}
	
	return nil
}

// AddMessage adds a message file to the database
func (db *Database) AddMessage(filename string) error {
	cmd := exec.Command("notmuch", "insert", "--no-hooks", "--", filename)
	return cmd.Run()
}

// GetAllMessageIDs gets all message IDs from the database
func (db *Database) GetAllMessageIDs() ([]string, error) {
	cmd := exec.Command("notmuch", "search", "--output=messages", "*")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("failed to get all message IDs: %w", err)
	}
	
	var messageIDs []string
	if err := json.Unmarshal(output, &messageIDs); err != nil {
		return nil, fmt.Errorf("failed to parse message IDs: %w", err)
	}
	
	return messageIDs, nil
}

// DeleteMessage deletes a message if it has the deleted tag or if noCheck is true
func (db *Database) DeleteMessage(messageID string, noCheck bool) error {
	// Get message details
	msg, err := db.GetMessage(messageID, "")
	if err != nil {
		// Message doesn't exist, ignore
		return nil
	}
	
	// Check if message has "deleted" tag
	hasDeletedTag := false
	for _, tag := range msg.Tags {
		if tag == "deleted" {
			hasDeletedTag = true
			break
		}
	}
	
	if !hasDeletedTag && !noCheck {
		// Message doesn't have deleted tag and we're not bypassing check
		// Set a dummy tag to trigger sync in next changeset
		log.Printf("%s set to be removed, but not tagged 'deleted'!", messageID)
		
		// Add and remove a dummy tag to trigger a change
		cmd := exec.Command("notmuch", "tag", "+dummy", "--", messageID)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to add dummy tag: %w", err)
		}
		
		cmd = exec.Command("notmuch", "tag", "-dummy", "--", messageID)
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("failed to remove dummy tag: %w", err)
		}
		
		return nil
	}
	
	// Delete the message files
	log.Printf("Removing %s from DB and deleting files.", messageID)
	for _, filename := range msg.Filenames {
		log.Printf("Removing %s.", filename)
		
		// Remove from notmuch database
		cmd := exec.Command("notmuch", "remove", "--", filename)
		if err := cmd.Run(); err != nil {
			log.Printf("Warning: failed to remove %s from database: %v", filename, err)
		}
		
		// Remove file from filesystem
		if err := os.Remove(filename); err != nil {
			log.Printf("Warning: failed to remove file %s: %v", filename, err)
		}
	}
	
	return nil
}

// RecordSync records the sync state
func RecordSync(filename string, revision *Revision) error {
	// Create directory if it doesn't exist
	dir := filepath.Dir(filename)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create directory %s: %w", dir, err)
	}
	
	// Write revision and UUID
	content := fmt.Sprintf("%d\n%s\n", revision.Rev, revision.UUID)
	if err := os.WriteFile(filename, []byte(content), 0644); err != nil {
		return fmt.Errorf("failed to write sync file: %w", err)
	}
	
	return nil
}