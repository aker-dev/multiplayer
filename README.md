# Multiplayer

AKER project - Multi-screen video synchronization system using MPV.

This system provides **frame-perfect synchronization** across multiple screens with **stable UUID-based monitor detection** to ensure videos always play on the correct physical screen, even after system reboots.

## Features

✨ **UUID-Based Monitor Mapping** - Uses hardware identifiers (UUID, serial numbers) to reliably identify each physical screen
🎯 **Automatic Re-sync on Loop** - Detects video loops and re-synchronizes all instances
⚡ **IPC-Based Control** - Fast communication with MPV instances via Unix sockets
🔄 **Persistent Configuration** - Monitors are identified by hardware, not position

## Installation

### Prerequisites

```bash
# Install MPV
brew install mpv  # macOS

# Install Python dependencies
pip3 install pyobjc-framework-Quartz  # Required for UUID-based monitor detection
```

### Configuration File

Create a `config.json` file from the example:

```bash
cp config.json.example config.json
```

Edit `config.json` to specify your video file paths:

```json
{
  "video_files": {
    "CENTER": "/path/to/your/center_video.mov",
    "LEFT": "/path/to/your/left_video.mov",
    "RIGHT": "/path/to/your/right_video.mov"
  },
  "num_screens": 3
}
```

**Note**: `config.json` is gitignored so you can customize paths without affecting the repository.

### Verify Setup

Run the setup verification script to check all requirements:

```bash
./check_setup.py
```

This will verify:
- ✅ `config.json` exists and is valid
- ✅ Video files exist at configured paths
- ✅ `monitors_mapping.json` exists (after calibration)
- ✅ MPV is installed
- ✅ Quartz framework is available

## First-Time Setup (IMPORTANT!)

### Monitor Calibration

**You MUST run the calibration tool once** to create a stable monitor mapping:

```bash
./calibrate_monitors.py
```

This will:
1. **Detect all connected monitors** and show their hardware details (UUID, serial number, vendor/model IDs)
2. **Display connection information** (Thunderbolt, HDMI, DisplayPort, etc.)
3. **Launch test windows** on each screen showing "MPV Screen 0", "MPV Screen 1", etc.
4. **Ask you to identify** which MPV screen number corresponds to each physical location (CENTER, LEFT, RIGHT)
5. **Save the mapping** to `monitors_mapping.json`

#### Why is calibration necessary?

macOS may change screen numbering after reboots or when monitors are disconnected/reconnected. The UUID-based system ensures videos always play on the **correct physical screen** by identifying monitors by their hardware, not their position in macOS.

### Example Calibration Session

```
🖥️  Detected 3 active display(s)

Monitor 0:
  UUID:        A1B2C3D4-E5F6-7890-ABCD-EF1234567890
  Serial:      12345678
  Vendor ID:   0x10AC
  Model ID:    0x4567
  Connection:  DisplayPort

Monitor 1:
  UUID:        B2C3D4E5-F6A7-8901-BCDE-F12345678901
  ...

📍 MONITOR IDENTIFICATION

Which MPV screen number shows the CENTER position? (0-2): 0
  ✓ CENTER position → MPV Screen 0

Which MPV screen number shows the LEFT position? (0-2): 2
  ✓ LEFT position → MPV Screen 2

Which MPV screen number shows the RIGHT position? (0-2): 1
  ✓ RIGHT position → MPV Screen 1

✅ Monitor mapping saved to: monitors_mapping.json
```

## Usage

### Normal Operation

⚠️ **IMPORTANT**: You MUST run `./monitors_calibrate.py` first to create `monitors_mapping.json`. The system will **refuse to start** without this file.

After calibration, simply run:

```bash
./multiplayer.py
```

The system will:
- ✅ Load the UUID-based monitor mapping from `monitors_mapping.json`
- ✅ Detect current screen configuration using hardware UUIDs
- ✅ Automatically assign videos to the correct physical screens
- ❌ Exit with an error if `monitors_mapping.json` is missing or invalid
- ✅ Synchronize playback and monitor for loops

### When to Re-Calibrate

You need to run `./calibrate_monitors.py` again if:
- ❌ You connect different monitors (different hardware)
- ❌ Videos appear on the wrong screens after reboot
- ❌ You see "Monitor configuration has changed!" error

You do **NOT** need to re-calibrate if:
- ✅ You simply reboot the system (UUID mapping handles this)
- ✅ macOS changes the screen numbering (UUID mapping handles this)
- ✅ Monitors are temporarily disconnected then reconnected

## How It Works

### UUID-Based Detection

The system uses macOS CoreGraphics APIs to get stable hardware identifiers for each display:

1. **During Calibration** ([calibrate_monitors.py](calibrate_monitors.py)):
   - Detects UUID, serial number, vendor/model IDs for each connected display
   - Creates a mapping: `{UUID → Video File Path + Physical Position}`
   - Saves to `monitors_mapping.json`

2. **During Playback** ([multiplayer.py](multiplayer.py)):
   - Detects current display UUIDs
   - Matches UUIDs against calibration file
   - Assigns correct video to each MPV screen index
   - Even if screen numbers change, UUIDs remain stable

### Synchronization

- Monitors playback position every second
- Detects loops when `current_position < previous_position`
- Three-phase sync: pause → seek to 0 → resume
- Maintains frame-perfect synchronization across all screens

## Configuration

### Number of Screens

Edit [multiplayer.py:30](multiplayer.py#L30):

```python
NUM_SCREENS = 3  # Change this value between 1 and 8
```

### Audio

Audio is enabled on the central screen by default ([multiplayer.py:195-197](multiplayer.py#L195-L197)).

## Troubleshooting

### "Quartz not available" warning

```bash
pip3 install pyobjc-framework-Quartz
```

### Videos on wrong screens after reboot

```bash
# Re-run calibration
./calibrate_monitors.py
```

### "Monitor configuration has changed!" error

This means the connected monitors are different from when you calibrated. Run:

```bash
./calibrate_monitors.py
```

### MPV instances fail to start

Check that:
- Video files exist at the specified paths
- MPV is installed: `which mpv`
- Permissions allow creating sockets in `/tmp/mpv_sockets/`

## Files

- [multiplayer.py](multiplayer.py) - Main synchronization system
- [calibrate_monitors.py](calibrate_monitors.py) - Monitor calibration tool
- `monitors_mapping.json` - Generated mapping file (UUID → Video)
- [CLAUDE.md](CLAUDE.md) - Technical documentation for Claude Code

## Technical Details

See [CLAUDE.md](CLAUDE.md) for detailed technical documentation including:
- IPC socket management
- MPV process control
- Synchronization algorithm
- Loop detection logic
- UUID-based mapping implementation
