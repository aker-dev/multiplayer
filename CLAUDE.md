# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based multi-screen video synchronization system that uses MPV media player to display synchronized video playback across multiple screens. The application controls multiple MPV instances via IPC sockets and maintains frame-perfect synchronization by detecting video loops and re-syncing all instances.

## Running the Application

### First Time Setup (REQUIRED!)

**IMPORTANT**: You MUST run the calibration tool before using multiplayer.py. The application will refuse to start without a valid `monitors_mapping.json` file.

```bash
chmod +x monitors_calibrate.py
./monitors_calibrate.py
```

This will create a `monitors_mapping.json` file that ensures each video always plays on the correct physical screen, regardless of how macOS numbers the monitors.

### Normal Usage

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
- **config.json must exist** with video file paths (copy from `config.json.example`)
- **monitors_mapping.json must exist** (created by running `./monitors_calibrate.py`)

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

### Monitor Mapping (Important!)

**Problem:** macOS may change monitor numbering after reboots, causing videos to appear on wrong screens.

**Solution:** The system uses a calibration file (`monitors_mapping.json`) to maintain correct video-to-monitor mapping:

1. **After reboot or if videos appear on wrong screens:**
   ```bash
   ./calibrate_monitors.py
   ```

2. **The calibration tool will:**
   - Open test windows on each monitor
   - Ask you to identify which MPV monitor number appears on each physical screen
   - Save the mapping to `monitors_mapping.json`

3. **multiplayer.py requires calibration:**
   - MUST have a valid `monitors_mapping.json` file to start
   - Loads the calibration file and validates its structure
   - Uses UUID-based mapping (based on screen position + hardware) to ensure correct video placement
   - Exits with an error if the calibration file is missing or invalid

### Configuration

All configuration is now managed through `config.json`:

```json
{
  "video_files": {
    "CENTER": "/path/to/center_video.mov",
    "LEFT": "/path/to/left_video.mov",
    "RIGHT": "/path/to/right_video.mov"
  },
  "num_screens": 3
}
```

- **video_files**: Paths to video files for each screen position
- **num_screens**: Number of physical screens to use

Both `monitors_calibrate.py` and `multiplayer.py` read from this file, ensuring consistency.

### Audio

Audio is enabled by default on the central screen ([multiplayer.py:179-182](multiplayer.py#L179-L182)).

## Technical Notes

### UUID-Based Monitor Detection

The system uses **position-based UUIDs** to identify monitors:

- **UUID Algorithm**: `SHA256(position_x:position_y:serial:vendor_id:model_id)`
- **Why position-based?**: Physical screen positions (x, y coordinates) remain stable across reboots because they're tied to the physical port connection
- **Handles identical monitors**: Two ASUS monitors with the same serial/vendor/model are differentiated by their position
- **Implementation**: Same UUID generation algorithm in both `monitors_calibrate.py` and `multiplayer.py`

**Important**: If you physically rearrange your monitors or change their position in System Preferences → Displays, you MUST recalibrate.

### MPV Communication

- Uses JSON-RPC protocol for MPV communication
- Socket timeout set to 0.5s to prevent blocking
- Loop detection threshold: -1 second to avoid false positives
- Position monitoring interval: 1 second
- MPV GPU rendering enabled for performance (`--vo=gpu`)
