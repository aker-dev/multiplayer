# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based multi-screen video synchronization system that uses MPV media player to display synchronized video playback across multiple screens. The application controls multiple MPV instances via IPC sockets and maintains frame-perfect synchronization by detecting video loops and re-syncing all instances.

## Running the Application

```bash
# Make the script executable (if needed)
chmod +x multiplayer.py

# Run the synchronization system
./multiplayer.py
# or
python3 multiplayer.py
```

**Prerequisites:**
- MPV media player must be installed on the system
- Video files must be placed in the `sources/` directory
- Currently configured to use `sources/10min.webm`

## Architecture

### Core Components

1. **IPC Socket Management** ([multiplayer.py:14-21](multiplayer.py#L14-L21))
   - Creates Unix domain sockets in `/tmp/mpv_sockets/`
   - Each MPV instance gets its own socket for IPC communication
   - Socket paths: `/tmp/mpv_sockets/mpv_screen_{i}.sock`

2. **MPV Process Management** ([multiplayer.py:36-54](multiplayer.py#L36-L54))
   - Launches multiple MPV instances with specific configurations
   - Each instance runs fullscreen on a designated screen (`--screen={i}`)
   - Audio is disabled on all instances (can be enabled on central screen via commented code)

3. **Synchronization System** ([multiplayer.py:60-79](multiplayer.py#L60-L79))
   - Three-phase sync: pause → seek to 0 → resume
   - Uses small delays (0.05s) between phases to ensure commands are processed
   - Triggered on startup and when video loop is detected

4. **Loop Detection** ([multiplayer.py:82-127](multiplayer.py#L82-L127))
   - Monitors video position of first instance every second
   - Detects when current position < previous position (indicating a loop)
   - Automatically triggers re-sync when loop is detected

### Key Functions

- `send_command(socket_path, command)`: Sends JSON-RPC commands to MPV via Unix socket
- `sync_all()`: Performs three-phase synchronization across all instances
- `get_video_position(socket_path)`: Queries current playback position from MPV instance

## Configuration

### Video Sources
Edit the `videos` list ([multiplayer.py:9-12](multiplayer.py#L9-L12)) to specify video files for each screen. Currently configured for 3 screens but only 2 video paths defined.

### Screen Count
The number of screens is determined by the length of the `videos` list. Adjust the range in socket creation ([multiplayer.py:18-21](multiplayer.py#L18-L21)) to match.

### Audio
Audio is disabled by default. To enable audio on the central screen (screen 1), uncomment lines 51-52 in [multiplayer.py:51-52](multiplayer.py#L51-L52).

## Technical Notes

- Uses JSON-RPC protocol for MPV communication
- Socket timeout set to 0.5s to prevent blocking
- Loop detection threshold: -1 second to avoid false positives
- Position monitoring interval: 1 second
- MPV GPU rendering enabled for performance (`--vo=gpu`)
