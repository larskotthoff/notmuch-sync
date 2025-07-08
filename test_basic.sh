#!/bin/bash

# Simple test to verify the Go implementation works

echo "Testing Go notmuch-sync implementation..."

# Test help
echo "1. Testing help output..."
./notmuch-sync-go --help

# Test that it runs without crashing in remote mode
echo "2. Testing remote mode (should exit cleanly on no input)..."
echo "" | timeout 5 ./notmuch-sync-go || echo "Remote mode test completed"

echo "Basic functionality test completed"