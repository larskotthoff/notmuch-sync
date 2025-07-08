package sync

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/larskotthoff/notmuch-sync/internal/notmuch"
	"github.com/larskotthoff/notmuch-sync/internal/protocol"
)

// GetMissingFiles determines which files are missing locally compared to the remote,
// and handles file moves/copies based on SHA256 checksums.
func GetMissingFiles(localChanges, remoteChanges map[string]interface{}, prefix string, moveOnChange bool) (map[string]interface{}, int, int, error) {
	ret := make(map[string]interface{})
	mcChanges := 0
	dChanges := 0

	// Open notmuch database
	db, err := notmuch.OpenDatabase()
	if err != nil {
		return nil, 0, 0, fmt.Errorf("failed to open database: %w", err)
	}

	for msgID, remoteData := range remoteChanges {
		remoteMsg, ok := remoteData.(map[string]interface{})
		if !ok {
			continue
		}

		remoteFiles, ok := remoteMsg["files"].([]interface{})
		if !ok {
			continue
		}

		// Get remote filenames
		var remoteFilenames []string
		for _, f := range remoteFiles {
			if fileMap, ok := f.(map[string]interface{}); ok {
				if name, ok := fileMap["name"].(string); ok {
					remoteFilenames = append(remoteFilenames, name)
				}
			}
		}

		// Get local message
		msg, err := db.GetMessage(msgID, prefix)
		if err != nil {
			// Message is a ghost - add to missing files
			ret[msgID] = remoteData
			continue
		}

		// Get local filenames (make them relative to prefix)
		var localFilenames []string
		for _, filename := range msg.Filenames {
			relPath := strings.TrimPrefix(filename, prefix)
			if relPath == filename && strings.HasPrefix(filename, prefix) {
				relPath = filename[len(prefix):]
			}
			if strings.HasPrefix(relPath, "/") {
				relPath = relPath[1:]
			}
			localFilenames = append(localFilenames, relPath)
		}

		// Find missing files
		var missingFiles []string
		for _, remoteFile := range remoteFilenames {
			found := false
			for _, localFile := range localFilenames {
				if remoteFile == localFile {
					found = true
					break
				}
			}
			if !found {
				missingFiles = append(missingFiles, remoteFile)
			}
		}

		if len(missingFiles) > 0 {
			// Compute hashes for local files
			var localHashes []map[string]string
			for _, filename := range msg.Filenames {
				relPath := strings.TrimPrefix(filename, prefix)
				if relPath == filename && strings.HasPrefix(filename, prefix) {
					relPath = filename[len(prefix):]
				}
				if strings.HasPrefix(relPath, "/") {
					relPath = relPath[1:]
				}

				// Read file and compute hash
				data, err := os.ReadFile(filename)
				if err != nil {
					log.Printf("Warning: failed to read file %s: %v", filename, err)
					continue
				}

				hash := protocol.Digest(data)
				localHashes = append(localHashes, map[string]string{
					"name": relPath,
					"sha":  hash,
				})
			}

			// Process each missing file
			for _, f := range remoteFiles {
				fileMap, ok := f.(map[string]interface{})
				if !ok {
					continue
				}

				fileName, ok := fileMap["name"].(string)
				if !ok {
					continue
				}

				// Check if this file is missing
				found := false
				for _, missingFile := range missingFiles {
					if fileName == missingFile {
						found = true
						break
					}
				}
				if !found {
					continue
				}

				fileSha, ok := fileMap["sha"].(string)
				if !ok {
					continue
				}

				// Check if we have this file with a different name (moved/copied)
				var matches []map[string]string
				for _, localHash := range localHashes {
					if fileSha == localHash["sha"] {
						matches = append(matches, localHash)
					}
				}

				if len(matches) > 0 {
					srcPath := filepath.Join(prefix, matches[0]["name"])
					dstPath := filepath.Join(prefix, fileName)

					// Check if this file is also in remote changes
					remoteFileInChanges := false
					for _, rf := range remoteFiles {
						if rfMap, ok := rf.(map[string]interface{}); ok {
							if rfName, ok := rfMap["name"].(string); ok && rfName == matches[0]["name"] {
								remoteFileInChanges = true
								break
							}
						}
					}

					if remoteFileInChanges {
						// Copy file
						mcChanges++
						if err := copyFile(srcPath, dstPath); err != nil {
							log.Printf("Warning: failed to copy %s to %s: %v", srcPath, dstPath, err)
						} else {
							log.Printf("Copying %s to %s", srcPath, dstPath)
							localFilenames = append(localFilenames, fileName)

							// Add to database
							if err := db.AddMessage(dstPath); err != nil {
								log.Printf("Warning: failed to add %s to database: %v", dstPath, err)
							}
						}
					} else if _, exists := localChanges[msgID]; !exists || moveOnChange {
						// Move file
						mcChanges++
						if err := moveFile(srcPath, dstPath); err != nil {
							log.Printf("Warning: failed to move %s to %s: %v", srcPath, dstPath, err)
						} else {
							log.Printf("Moving %s to %s", srcPath, dstPath)

							// Update local filenames
							for i, localFile := range localFilenames {
								if localFile == matches[0]["name"] {
									localFilenames[i] = fileName
									break
								}
							}

							// Update database
							if err := db.AddMessage(dstPath); err != nil {
								log.Printf("Warning: failed to add %s to database: %v", dstPath, err)
							}
						}
					}
				} else {
					// File needs to be transferred
					if ret[msgID] == nil {
						ret[msgID] = remoteData
					}
				}
			}

			// Remove duplicate files that are not on remote
			localFilesNotOnRemote := make(map[string]bool)
			for _, localFile := range localFilenames {
				found := false
				for _, remoteFile := range remoteFilenames {
					if localFile == remoteFile {
						found = true
						break
					}
				}
				if !found {
					localFilesNotOnRemote[localFile] = true
				}
			}

			// Check if these files are duplicates
			for localFile := range localFilesNotOnRemote {
				localPath := filepath.Join(prefix, localFile)

				// Read file and compute hash
				data, err := os.ReadFile(localPath)
				if err != nil {
					continue
				}

				localHash := protocol.Digest(data)

				// Check if this hash exists in remote files
				isDuplicate := false
				for _, f := range remoteFiles {
					if fileMap, ok := f.(map[string]interface{}); ok {
						if remoteSha, ok := fileMap["sha"].(string); ok && remoteSha == localHash {
							isDuplicate = true
							break
						}
					}
				}

				if isDuplicate {
					dChanges++
					log.Printf("Removing duplicate file %s", localPath)

					// Remove from database first
					if err := os.Remove(localPath); err != nil {
						log.Printf("Warning: failed to remove %s: %v", localPath, err)
					}
				}
			}
		}
	}

	return ret, mcChanges, dChanges, nil
}

// copyFile copies a file from src to dst
func copyFile(src, dst string) error {
	// Create destination directory if it doesn't exist
	if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
		return fmt.Errorf("failed to create directory: %w", err)
	}

	// Read source file
	data, err := os.ReadFile(src)
	if err != nil {
		return fmt.Errorf("failed to read source file: %w", err)
	}

	// Write destination file
	if err := os.WriteFile(dst, data, 0644); err != nil {
		return fmt.Errorf("failed to write destination file: %w", err)
	}

	return nil
}

// moveFile moves a file from src to dst
func moveFile(src, dst string) error {
	// Create destination directory if it doesn't exist
	if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
		return fmt.Errorf("failed to create directory: %w", err)
	}

	// Try to rename first (faster if on same filesystem)
	if err := os.Rename(src, dst); err != nil {
		// If rename fails, copy and remove
		if err := copyFile(src, dst); err != nil {
			return err
		}

		if err := os.Remove(src); err != nil {
			return fmt.Errorf("failed to remove source file: %w", err)
		}
	}

	return nil
}
