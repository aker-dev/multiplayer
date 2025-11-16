#!/bin/bash

# Installation script for macOS launchd service
# This will auto-restart the multiplayer script on crash or reboot

SERVICE_NAME="com.multiplayer.video"
PLIST_FILE="$SERVICE_NAME.plist"
INSTALL_DIR="$HOME/Library/LaunchAgents"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_TARGET="gui/$(id -u)/$SERVICE_NAME"

echo "Installing multiplayer as a launchd service..."
echo ""

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Make run_forever.sh executable
chmod +x "$SCRIPT_DIR/run_forever.sh"

# Copy plist file
cp "$SCRIPT_DIR/$PLIST_FILE" "$INSTALL_DIR/"

# Unload if already loaded (using modern bootout command)
echo "Unloading existing service (if any)..."
launchctl bootout "$SERVICE_TARGET" 2>/dev/null || true

# Load the service (using modern bootstrap command)
echo "Loading service..."
launchctl bootstrap gui/$(id -u) "$INSTALL_DIR/$PLIST_FILE"

echo ""
echo "✓ Service installed successfully!"
echo ""
echo "Commands (modern macOS syntax):"
echo "  Load:    launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/$PLIST_FILE"
echo "  Unload:  launchctl bootout $SERVICE_TARGET"
echo "  Restart: launchctl kickstart -k $SERVICE_TARGET"
echo "  Status:  launchctl list | grep $SERVICE_NAME"
echo ""
echo "Logs:"
echo "  stdout:  /tmp/multiplayer.out.log"
echo "  stderr:  /tmp/multiplayer.err.log"
echo "  tail -f: tail -f /tmp/multiplayer.err.log"
echo ""
echo "The service will auto-start on login and restart on crash."
