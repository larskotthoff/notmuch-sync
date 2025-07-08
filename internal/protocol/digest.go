package protocol

import (
	"bytes"
	"crypto/sha256"
	"fmt"
)

// Digest computes SHA256 digest of data, removing any X-TUID: lines.
// This is necessary because mbsync adds these lines to keep track of internal
// progress, but they make identical emails that were retrieved separately
// different.
func Digest(data []byte) string {
	pattern := []byte("X-TUID: ")
	toDigest := data

	// Find X-TUID line and remove it
	startIdx := bytes.Index(data, pattern)
	if startIdx != -1 {
		searchStart := startIdx + len(pattern)
		endIdx := bytes.Index(data[searchStart:], []byte("\n"))

		if endIdx != -1 {
			endIdx += searchStart
			// Remove the X-TUID line including the newline
			toDigest = append(data[:startIdx], data[endIdx+1:]...)
		}
	}

	hash := sha256.Sum256(toDigest)
	return fmt.Sprintf("%x", hash)
}
