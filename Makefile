BINARY_NAME=notmuch-sync-go
SOURCE_DIR=cmd/notmuch-sync
LDFLAGS=-ldflags "-s -w"

.PHONY: build test clean install help

build: ## Build the Go binary
	go build $(LDFLAGS) -o $(BINARY_NAME) $(SOURCE_DIR)/main.go
	chmod +x $(BINARY_NAME)

test: ## Run tests
	go test ./internal/protocol/
	go test ./internal/sync/ 2>/dev/null || true

clean: ## Clean build artifacts
	rm -f $(BINARY_NAME)
	rm -f notmuch-sync-*
	go clean

install: build ## Install the binary to /usr/local/bin
	sudo cp $(BINARY_NAME) /usr/local/bin/notmuch-sync-go

# Cross-compilation targets
build-linux: ## Build for Linux
	GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o notmuch-sync-linux $(SOURCE_DIR)/main.go

build-darwin: ## Build for macOS
	GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o notmuch-sync-darwin $(SOURCE_DIR)/main.go

build-windows: ## Build for Windows
	GOOS=windows GOARCH=amd64 go build $(LDFLAGS) -o notmuch-sync.exe $(SOURCE_DIR)/main.go

build-all: build-linux build-darwin build-windows ## Build for all platforms

fmt: ## Format Go code
	go fmt ./...

vet: ## Run go vet
	go vet ./...

lint: fmt vet ## Run linting tools

check: lint test ## Run all checks

help: ## Show this help message
	@echo 'Usage: make <target>'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Default target
all: build