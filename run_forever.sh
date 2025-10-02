#!/bin/bash

# Auto-restart wrapper for multiplayer.py
# This script will automatically restart the Python script if it crashes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/multiplayer.py"
RESTART_DELAY=3

echo "Starting multiplayer with auto-restart..."
echo "Press Ctrl+C twice quickly to stop permanently"
echo "=========================================="

while true; do
    # Run the Python script
    python3 "$SCRIPT"

    EXIT_CODE=$?

    # Exit code 0 means normal exit (Ctrl+C)
    if [ $EXIT_CODE -eq 0 ]; then
        echo "Normal exit detected. Stopping..."
        break
    fi

    # Any other exit code means crash
    echo ""
    echo "⚠️  Script crashed with exit code $EXIT_CODE"
    echo "Restarting in $RESTART_DELAY seconds..."
    echo "Press Ctrl+C to stop"
    echo ""

    sleep $RESTART_DELAY
done

echo "Multiplayer stopped."
