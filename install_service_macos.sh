#!/bin/bash

# Installation script for macOS launchd service
# This will auto-restart the multiplayer script on crash or reboot

SERVICE_NAME="com.multiplayer.video"
PLIST_FILE="$SERVICE_NAME.plist"
INSTALL_DIR="$HOME/Library/LaunchAgents"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing multiplayer as a launchd service..."
echo ""

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Copy plist file
cp "$SCRIPT_DIR/$PLIST_FILE" "$INSTALL_DIR/"

# Unload if already loaded
launchctl unload "$INSTALL_DIR/$PLIST_FILE" 2>/dev/null || true

# Load the service
launchctl load "$INSTALL_DIR/$PLIST_FILE"

echo "✓ Service installed successfully!"
echo ""
echo "Commands:"
echo "  Start:   launchctl start $SERVICE_NAME"
echo "  Stop:    launchctl stop $SERVICE_NAME"
echo "  Restart: launchctl stop $SERVICE_NAME && launchctl start $SERVICE_NAME"
echo "  Unload:  launchctl unload $INSTALL_DIR/$PLIST_FILE"
echo ""
echo "Logs:"
echo "  stdout:  /tmp/multiplayer.out.log"
echo "  stderr:  /tmp/multiplayer.err.log"
echo ""
echo "The service will auto-start on login and restart on crash."
