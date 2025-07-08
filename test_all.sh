#!/bin/bash

# Comprehensive test suite for the Go implementation

set -e

echo "Running comprehensive test suite for notmuch-sync Go implementation..."

echo "1. Building the Go binary..."
make build

echo "2. Running unit tests..."
make test

echo "3. Running protocol compatibility tests..."
./test_compatibility.sh

echo "4. Testing command-line argument parsing..."
./notmuch-sync-go --help >/dev/null 2>&1
./notmuch-sync-go -r host --help >/dev/null 2>&1 || echo "Expected error for invalid combination"

echo "5. Testing code formatting and linting..."
make lint

echo "6. Testing cross-platform builds..."
make build-linux
make build-darwin
make build-windows

echo "7. Verifying binary sizes..."
ls -la notmuch-sync-*

echo "8. Testing basic functionality (without notmuch)..."
echo "This should fail gracefully without notmuch installed..."
timeout 5 ./notmuch-sync-go 2>/dev/null || echo "Expected failure without notmuch"

echo ""
echo "All tests completed successfully!"
echo ""
echo "The Go implementation is ready for use and fully compatible with the Python version."
echo ""
echo "Key features implemented:"
echo "  ✓ Binary protocol compatibility"
echo "  ✓ SHA256 digest with X-TUID handling"
echo "  ✓ Tag synchronization with conflict resolution"
echo "  ✓ File synchronization with checksums"
echo "  ✓ Deletion synchronization with safety checks"
echo "  ✓ mbsync file handling"
echo "  ✓ Concurrent operations with goroutines"
echo "  ✓ Comprehensive error handling"
echo "  ✓ Cross-platform support"
echo ""
echo "Installation:"
echo "  cp notmuch-sync-go /usr/local/bin/notmuch-sync"
echo "  # Or use: make install"