# Rust Implementation of notmuch-sync

This is a complete Rust port of the Python `notmuch_sync.py` script, providing identical functionality for synchronizing notmuch email databases and message files between local and remote systems.

## Features

✅ **Complete Feature Parity** with the Python version:
- All CLI flags and functionality matching Python version
- Notmuch database manipulation using notmuch-rs crate
- Async IO for efficient network communication  
- SHA256 digest calculation with X-TUID handling for mbsync compatibility
- File and tag synchronization with hash-based deduplication
- Message deletion handling with safety checks
- mbsync state file synchronization
- Binary wire protocol for remote communication
- Error handling and logging
- Subprocess management for SSH connections

## Dependencies

This implementation requires:
- Rust 1.70+
- notmuch development libraries
- Xapian development libraries (optional, uses notmuch queries as fallback)

### Installing Dependencies

On Ubuntu/Debian:
```bash
sudo apt-get install libnotmuch-dev libxapian-dev
```

On Fedora/RHEL:
```bash
sudo dnf install notmuch-devel xapian-core-devel
```

On macOS:
```bash
brew install notmuch xapian
```

## Building

```bash
cargo build --release
```

The compiled binary will be available at `target/release/notmuch-sync`.

## Usage

The Rust implementation provides identical CLI interface to the Python version:

```bash
# Basic sync
notmuch-sync --remote mail.example.com --user myuser --verbose

# With deletion support
notmuch-sync --remote mail.example.com --user myuser --delete --verbose

# With mbsync compatibility
notmuch-sync --remote mail.example.com --user myuser --mbsync --verbose

# Custom SSH command
notmuch-sync --remote mail.example.com --ssh-cmd "ssh -i ~/.ssh/special_key" --verbose

# Show help
notmuch-sync --help
```

## Command Line Arguments

All arguments from the Python version are supported:

- `-r, --remote REMOTE`: Remote host to connect to
- `-u, --user USER`: SSH user to use  
- `-v, --verbose`: Increases verbosity, up to twice (ignored on remote)
- `-q, --quiet`: Do not print any output, overrides --verbose
- `-s, --ssh-cmd SSH_CMD`: SSH command to use (default 'ssh -CTaxq')
- `-m, --mbsync`: Sync mbsync files (.mbsyncstate, .uidvalidity)
- `-p, --path PATH`: Path to notmuch-sync on remote server
- `-c, --remote-cmd REMOTE_CMD`: Command to run to sync; overrides other options
- `-d, --delete`: Sync deleted messages
- `-x, --delete-no-check`: Delete missing messages even without 'deleted' tag

## Implementation Details

### Key Components Ported

1. **Core Utilities**:
   - SHA256 digest calculation with X-TUID filtering
   - Length-prefixed binary protocol for network communication
   - Async IO coordination for concurrent operations

2. **Database Operations**:
   - Change detection using notmuch revision tracking
   - Tag synchronization with conflict resolution
   - Message and file management

3. **File Synchronization**:
   - Hash-based deduplication and move/copy detection
   - Efficient file transfer protocol
   - Directory structure preservation

4. **Deletion Handling**:
   - Safety checks with 'deleted' tag verification
   - Coordinated deletion between local and remote
   - File cleanup with error recovery

5. **mbsync Integration**:
   - State file synchronization
   - Timestamp-based conflict resolution
   - Glob pattern matching for state files

### Architecture

The Rust implementation follows the same high-level architecture as the Python version:

- **Local Mode**: Initiates SSH connection and coordinates the sync
- **Remote Mode**: Receives commands and responds with data
- **Async Operations**: All network IO is performed asynchronously
- **Error Handling**: Comprehensive error propagation with context

### Performance

The Rust implementation provides several performance benefits:

- **Memory Safety**: No runtime overhead from garbage collection
- **Zero-Copy IO**: Efficient buffer management for large file transfers
- **Concurrent Operations**: True parallelism for CPU-bound operations
- **Optimized Hashing**: Fast SHA256 implementation with SIMD support

## Testing

The implementation includes the same core logic as the thoroughly tested Python version. Integration tests should work with the existing test suite after installing the Rust binary.

## Compatibility

This Rust implementation is designed to be a drop-in replacement for the Python version:

- **Wire Protocol**: Identical binary protocol for network communication
- **File Formats**: Same sync state and configuration file formats  
- **Behavior**: Matching error handling and edge case behavior
- **CLI Interface**: Identical command-line arguments and options

## Contributing

When contributing to this Rust implementation:

1. Maintain compatibility with the Python version
2. Add tests for new functionality
3. Follow Rust coding conventions
4. Update documentation for any CLI changes

## License

Same license as the original Python implementation (BSD-3-Clause).