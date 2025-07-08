# notmuch-sync Go Implementation

This is a Go implementation of the notmuch-sync tool that maintains full compatibility with the existing Python version.

## Features

The Go version implements all features from the Python version:

- **Binary Protocol Compatibility**: Uses the same 4-byte length-prefixed binary protocol
- **Tag Synchronization**: Syncs tags with conflict resolution (union of local and remote tags)
- **File Synchronization**: Handles file moves, copies, and transfers with SHA256 checksums
- **Deletion Synchronization**: Safely deletes messages with the "deleted" tag
- **mbsync Support**: Synchronizes mbsync state files (.mbsyncstate, .uidvalidity)
- **X-TUID Handling**: Removes X-TUID lines from mail files before computing checksums
- **Async Operations**: Uses goroutines for concurrent operations
- **Error Handling**: Comprehensive error handling and logging

## Building

```bash
# Run the build script
./build.sh

# Or build manually
go build -o notmuch-sync-go cmd/notmuch-sync/main.go
```

## Usage

The Go version supports all the same command-line options as the Python version:

```bash
# Basic sync
./notmuch-sync-go -r user@remote-host

# With custom SSH command
./notmuch-sync-go -r myhost -s 'ssh -p 2222'

# With deletion and mbsync support
./notmuch-sync-go -r myhost -d -m

# Verbose output
./notmuch-sync-go -r myhost -v -v

# Custom remote command (for testing)
./notmuch-sync-go -c 'cat'
```

## Command-Line Options

- `-r, --remote`: Remote host to connect to
- `-u, --user`: SSH user to use
- `-v, --verbose`: Increase verbosity (up to twice)
- `-q, --quiet`: Suppress all output
- `-s, --ssh-cmd`: SSH command to use (default: "ssh -CTaxq")
- `-m, --mbsync`: Sync mbsync files (.mbsyncstate, .uidvalidity)
- `-p, --path`: Path to notmuch-sync on remote server
- `-c, --remote-cmd`: Custom command to run (overrides SSH options)
- `-d, --delete`: Sync deleted messages
- `-x, --delete-no-check`: Delete messages without checking for "deleted" tag

## Implementation Details

### Architecture

The Go implementation is organized into several packages:

- `cmd/notmuch-sync/`: Main entry point
- `internal/protocol/`: Binary protocol implementation and SHA256 digests
- `internal/notmuch/`: Notmuch database operations using command-line calls
- `internal/sync/`: Core synchronization logic

### Key Differences from Python Version

1. **Database Access**: Uses `notmuch` command-line tool instead of Python bindings
2. **Concurrency**: Uses goroutines instead of Python's asyncio
3. **Error Handling**: Go's explicit error handling instead of exceptions
4. **Type Safety**: Compile-time type checking

### Protocol Compatibility

The Go version maintains full binary protocol compatibility with the Python version:

- 36-byte UUID exchange
- 4-byte length prefixes for all data
- JSON-encoded change lists
- Same file transfer format
- Same deletion synchronization protocol
- Same mbsync file synchronization

## Testing

```bash
# Run protocol tests
go test ./internal/protocol/

# Run basic functionality test
./test_basic.sh
```

## Compatibility

The Go version is designed to be fully compatible with the Python version:

- Can be used as a drop-in replacement
- Supports mixed deployments (Go client with Python server, or vice versa)
- Same configuration and usage patterns
- Same wire protocol and file formats

## Performance

The Go version offers several performance benefits:

- Faster startup time (no Python interpreter overhead)
- Better memory efficiency
- Concurrent operations with goroutines
- Single static binary (no dependencies)

## Dependencies

The Go version has minimal dependencies:

- Go 1.16+ (for building)
- `notmuch` command-line tool (for database operations)
- `ssh` (for remote connections)

## Building for Different Platforms

```bash
# Linux
GOOS=linux GOARCH=amd64 go build -o notmuch-sync-linux cmd/notmuch-sync/main.go

# macOS
GOOS=darwin GOARCH=amd64 go build -o notmuch-sync-macos cmd/notmuch-sync/main.go

# Windows
GOOS=windows GOARCH=amd64 go build -o notmuch-sync.exe cmd/notmuch-sync/main.go
```

## Migration from Python Version

To migrate from the Python version:

1. Build the Go version: `./build.sh`
2. Test with your configuration: `./notmuch-sync-go --help`
3. Replace the Python script with the Go binary
4. All existing sync state and configuration will work unchanged

The Go version can be used immediately without any changes to your existing setup or sync state.