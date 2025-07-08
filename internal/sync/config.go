package sync

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
)

// VerboseFlag is a custom flag type that counts occurrences
type VerboseFlag struct {
	Count int
}

func (v *VerboseFlag) String() string {
	return fmt.Sprintf("%d", v.Count)
}

func (v *VerboseFlag) Set(value string) error {
	// For boolean flags, value might be empty or "true"/"false"
	if value == "" || value == "true" {
		v.Count++
	} else if value == "false" {
		// Do nothing for false values
	} else {
		return fmt.Errorf("invalid boolean value %q", value)
	}
	return nil
}

func (v *VerboseFlag) Get() interface{} {
	return v.Count
}

func (v *VerboseFlag) IsBoolFlag() bool {
	return true
}

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
	// Also expand -vv to -v -v, -vvv to -v -v -v, etc.
	var processedArgs []string
	for _, arg := range args {
		if strings.HasPrefix(arg, "--") && len(arg) > 2 && arg[2] != '-' {
			// Convert --flag to -flag
			processedArgs = append(processedArgs, "-"+arg[2:])
		} else if strings.HasPrefix(arg, "-v") && len(arg) > 2 && strings.TrimLeft(arg[2:], "v") == "" {
			// Expand -vv to -v -v, -vvv to -v -v -v, etc.
			for j := 1; j < len(arg); j++ {
				if arg[j] == 'v' {
					processedArgs = append(processedArgs, "-v")
				} else {
					// If there's a non-v character after -v, treat it as a separate flag
					processedArgs = append(processedArgs, arg)
					break
				}
			}
		} else {
			processedArgs = append(processedArgs, arg)
		}
	}

	config := &Config{}
	verboseFlag := &VerboseFlag{}

	fs.StringVar(&config.Remote, "r", "", "remote host to connect to")
	fs.StringVar(&config.Remote, "remote", "", "remote host to connect to")
	fs.StringVar(&config.User, "u", "", "SSH user to use")
	fs.StringVar(&config.User, "user", "", "SSH user to use")
	fs.Var(verboseFlag, "v", "increases verbosity, up to twice (ignored on remote)")
	fs.Var(verboseFlag, "verbose", "increases verbosity, up to twice (ignored on remote)")
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

	// Set verbose count from the custom flag
	config.Verbose = verboseFlag.Count

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
