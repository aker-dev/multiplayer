#!/bin/bash

# Uninstallation script for macOS launchd service

SERVICE_NAME="com.multiplayer.video"
PLIST_FILE="$SERVICE_NAME.plist"
INSTALL_DIR="$HOME/Library/LaunchAgents"
SERVICE_TARGET="gui/$(id -u)/$SERVICE_NAME"

echo "Uninstalling multiplayer launchd service..."
echo ""

# Unload the service
echo "Unloading service..."
launchctl bootout "$SERVICE_TARGET" 2>/dev/null || true

# Remove plist file
if [ -f "$INSTALL_DIR/$PLIST_FILE" ]; then
    rm "$INSTALL_DIR/$PLIST_FILE"
    echo "✓ Removed $INSTALL_DIR/$PLIST_FILE"
else
    echo "⚠ Plist file not found at $INSTALL_DIR/$PLIST_FILE"
fi

echo ""
echo "✓ Service uninstalled successfully!"
echo ""
echo "Note: Log files remain at:"
echo "  /tmp/multiplayer.out.log"
echo "  /tmp/multiplayer.err.log"
echo ""
echo "To remove logs, run: rm /tmp/multiplayer.*.log"
