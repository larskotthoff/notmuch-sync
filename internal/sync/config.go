package sync

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
)

// Config holds the command-line arguments
type Config struct {
	Remote        string
	User          string
	Verbose       int
	Quiet         bool
	SSHCmd        string
	MBSync        bool
	Path          string
	RemoteCmd     string
	Delete        bool
	DeleteNoCheck bool
}

// ParseArgs parses command-line arguments
func ParseArgs(args []string) (*Config, error) {
	fs := flag.NewFlagSet("notmuch-sync", flag.ExitOnError)

	// Preprocess arguments to convert double-dash to single-dash for compatibility with Python version
	processedArgs := make([]string, len(args))
	for i, arg := range args {
		if strings.HasPrefix(arg, "--") && len(arg) > 2 && arg[2] != '-' {
			// Convert --flag to -flag
			processedArgs[i] = "-" + arg[2:]
		} else {
			processedArgs[i] = arg
		}
	}

	config := &Config{}

	fs.StringVar(&config.Remote, "r", "", "remote host to connect to")
	fs.StringVar(&config.Remote, "remote", "", "remote host to connect to")
	fs.StringVar(&config.User, "u", "", "SSH user to use")
	fs.StringVar(&config.User, "user", "", "SSH user to use")
	fs.IntVar(&config.Verbose, "v", 0, "increases verbosity, up to twice (ignored on remote)")
	fs.IntVar(&config.Verbose, "verbose", 0, "increases verbosity, up to twice (ignored on remote)")
	fs.BoolVar(&config.Quiet, "q", false, "do not print any output, overrides --verbose")
	fs.BoolVar(&config.Quiet, "quiet", false, "do not print any output, overrides --verbose")
	fs.StringVar(&config.SSHCmd, "s", "ssh -CTaxq", "SSH command to use")
	fs.StringVar(&config.SSHCmd, "ssh-cmd", "ssh -CTaxq", "SSH command to use")
	fs.BoolVar(&config.MBSync, "m", false, "sync mbsync files (.mbsyncstate, .uidvalidity)")
	fs.BoolVar(&config.MBSync, "mbsync", false, "sync mbsync files (.mbsyncstate, .uidvalidity)")
	fs.StringVar(&config.Path, "p", "", "path to notmuch-sync on remote server")
	fs.StringVar(&config.Path, "path", "", "path to notmuch-sync on remote server")
	fs.StringVar(&config.RemoteCmd, "c", "", "command to run to sync; overrides --remote, --user, --ssh-cmd, --path; mostly used for testing")
	fs.StringVar(&config.RemoteCmd, "remote-cmd", "", "command to run to sync; overrides --remote, --user, --ssh-cmd, --path; mostly used for testing")
	fs.BoolVar(&config.Delete, "d", false, "sync deleted messages (requires listing all messages in notmuch database, potentially expensive)")
	fs.BoolVar(&config.Delete, "delete", false, "sync deleted messages (requires listing all messages in notmuch database, potentially expensive)")
	fs.BoolVar(&config.DeleteNoCheck, "x", false, "delete missing messages even if they don't have the 'deleted' tag (requires --delete) -- potentially unsafe")
	fs.BoolVar(&config.DeleteNoCheck, "delete-no-check", false, "delete missing messages even if they don't have the 'deleted' tag (requires --delete) -- potentially unsafe")

	if err := fs.Parse(processedArgs); err != nil {
		return nil, err
	}

	// Set default path if not provided
	if config.Path == "" {
		config.Path = filepath.Base(os.Args[0])
	}

	return config, nil
}

// SetupLogging configures logging based on the config
func SetupLogging(config *Config) {
	if config.Quiet {
		log.SetOutput(os.Stderr) // Disable logging
		log.SetFlags(0)
		return
	}

	// Set logging format similar to Python version
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	// Note: Go's log package doesn't have levels like Python's logging
	// We'll handle verbosity in the actual logging calls
}

// IsRemoteMode returns true if we're running in remote mode
func IsRemoteMode(config *Config) bool {
	return config.Remote == "" && config.RemoteCmd == ""
}

// Run is the main entry point
func Run(args []string) error {
	config, err := ParseArgs(args)
	if err != nil {
		return fmt.Errorf("failed to parse arguments: %w", err)
	}

	SetupLogging(config)

	if config.Remote != "" || config.RemoteCmd != "" {
		return SyncLocal(config)
	} else {
		return SyncRemote(config)
	}
}
