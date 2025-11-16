#!/bin/bash

# Wait 30 seconds after boot to ensure all monitors are detected
sleep 5

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the multiplayer script
exec /opt/homebrew/bin/python3 "$SCRIPT_DIR/multiplayer.py"
