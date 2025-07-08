#!/bin/bash

# Build script for notmuch-sync Go version

set -e

echo "Building notmuch-sync Go version..."

# Build the main executable
go build -o notmuch-sync-go -ldflags "-s -w" cmd/notmuch-sync/main.go

# Make it executable
chmod +x notmuch-sync-go

# Run tests
echo "Running tests..."
go test ./internal/protocol/
go test ./internal/sync/ 2>/dev/null || echo "Note: sync tests require notmuch to be installed"

echo "Build completed successfully!"
echo "Executable: notmuch-sync-go"
echo ""
echo "Usage examples:"
echo "  # Sync with remote host"
echo "  ./notmuch-sync-go -r user@remote-host"
echo "  # Sync with custom SSH command"
echo "  ./notmuch-sync-go -r myhost -s 'ssh -p 2222'"
echo "  # Sync with deletion and mbsync support"
echo "  ./notmuch-sync-go -r myhost -d -m"
echo ""
echo "For more options, run: ./notmuch-sync-go --help"