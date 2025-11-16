#!/usr/bin/env python3
"""
Monitor Calibration Tool with Hardware-Based Detection

This tool detects monitors using stable hardware identifiers (UUID, serial number, etc.)
that persist across reboots, ensuring videos always play on the correct physical screen.

The tool uses macOS CoreGraphics APIs to get stable display identifiers and creates
a mapping file that multiplayer.py uses to correctly assign videos to monitors.
"""

import subprocess
import json
import os
import sys
import time
from pathlib import Path

# Configuration file location
CONFIG_FILE = Path(__file__).parent / "config.json"

# Try to import Quartz (macOS only)
try:
    import Quartz
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False
    print("⚠️  Warning: Quartz not available. Install with: pip3 install pyobjc-framework-Quartz")

def get_display_hardware_info():
    """
    Get stable hardware identifiers for all connected displays.
    Returns a dict mapping MPV screen index to hardware info.
    """
    if not HAS_QUARTZ:
        return None

    displays = {}

    # Get all active displays
    max_displays = 32
    (err, active_displays, display_count) = Quartz.CGGetActiveDisplayList(max_displays, None, None)

    if err != 0:
        print(f"Error getting display list: {err}")
        return None

    print(f"\n🖥️  Detected {display_count} active display(s)\n")

    for idx, display_id in enumerate(active_displays[:display_count]):
        # Get serial number (most stable identifier available)
        serial = Quartz.CGDisplaySerialNumber(display_id)

        # Get vendor and model IDs
        vendor_id = Quartz.CGDisplayVendorNumber(display_id)
        model_id = Quartz.CGDisplayModelNumber(display_id)

        # Get display bounds (position and size)
        bounds = Quartz.CGDisplayBounds(display_id)

        # Check if main display
        is_main = Quartz.CGDisplayIsMain(display_id)

        # Check if built-in (laptop screen)
        is_builtin = Quartz.CGDisplayIsBuiltin(display_id)

        # Create a stable UUID-like identifier based on position
        # Position (x, y) is the most stable identifier across reboots
        # because it's determined by the physical port connection and display arrangement
        import hashlib
        position_x = int(bounds.origin.x)
        position_y = int(bounds.origin.y)

        # Create unique signature from position + hardware info (without display_id)
        # Position is the primary discriminator for identical monitors
        hardware_signature = f"{position_x}:{position_y}:{serial}:{vendor_id:04X}:{model_id:04X}"
        uuid_str = hashlib.sha256(hardware_signature.encode()).hexdigest()[:32]
        # Format as UUID-like string for readability
        uuid_str = f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:32]}"

        displays[idx] = {
            'uuid': uuid_str,
            'serial': serial,
            'vendor_id': vendor_id,
            'model_id': model_id,
            'display_id': int(display_id),
            'is_main': bool(is_main),
            'is_builtin': bool(is_builtin),
            'position': {
                'x': int(bounds.origin.x),
                'y': int(bounds.origin.y),
                'width': int(bounds.size.width),
                'height': int(bounds.size.height)
            }
        }

        # Print info
        print(f"Monitor {idx}:")
        print(f"  UUID:        {uuid_str}")
        print(f"  Serial:      {serial if serial != 0 else 'N/A'}")
        print(f"  Vendor ID:   0x{vendor_id:04X}")
        print(f"  Model ID:    0x{model_id:04X}")
        print(f"  Display ID:  {display_id}")
        print(f"  Position:    ({bounds.origin.x}, {bounds.origin.y})")
        print(f"  Size:        {bounds.size.width} x {bounds.size.height}")
        print(f"  Main:        {'Yes' if is_main else 'No'}")
        print(f"  Built-in:    {'Yes' if is_builtin else 'No'}")
        print()

    return displays

def get_system_profiler_info():
    """
    Get detailed display information including connection type using system_profiler.
    This provides info about Thunderbolt, HDMI, DisplayPort connections.
    """
    print("📊 Fetching detailed display information (this may take a few seconds)...\n")

    try:
        result = subprocess.run(
            ['system_profiler', 'SPDisplaysDataType', '-json'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data
        else:
            print(f"⚠️  system_profiler returned error code {result.returncode}")
            return None
    except subprocess.TimeoutExpired:
        print("⚠️  system_profiler timed out")
        return None
    except json.JSONDecodeError:
        print("⚠️  Could not parse system_profiler output")
        return None
    except Exception as e:
        print(f"⚠️  Error running system_profiler: {e}")
        return None

def load_config():
    """Load configuration from config.json"""
    if not CONFIG_FILE.exists():
        print(f"❌ Error: Configuration file not found: {CONFIG_FILE}")
        print(f"   Please create config.json with video file paths.")
        sys.exit(1)

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        if 'video_files' not in config:
            print(f"❌ Error: 'video_files' not found in config.json")
            sys.exit(1)

        return config
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing config.json: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading config.json: {e}")
        sys.exit(1)

def display_system_profiler_summary(profiler_data):
    """Display a summary of connection types from system_profiler data"""
    if not profiler_data:
        return

    print("🔌 Connection Information:")
    print()

    try:
        displays_info = profiler_data.get('SPDisplaysDataType', [])
        for gpu in displays_info:
            displays = gpu.get('spdisplays_ndrvs', [])
            for display in displays:
                name = display.get('_name', 'Unknown Display')
                connection = display.get('spdisplays_connection_type', 'Unknown')
                resolution = display.get('_spdisplays_resolution', 'Unknown')

                print(f"  • {name}")
                print(f"    Connection: {connection}")
                print(f"    Resolution: {resolution}")
                print()
    except Exception as e:
        print(f"  Could not parse connection info: {e}\n")

def launch_test_windows(num_screens):
    """
    Launch Tkinter test windows on each screen to help user identify them.
    Each window shows a different color and screen number.
    """
    print(f"🚀 Launching test windows on {num_screens} screen(s)...")
    print("   Each window will show its screen number with a colored background.\n")

    import tkinter as tk

    # Colors for each screen
    colors = [
        ("#FF0000", "CENTER"),    # Red
        ("#00FF00", "LEFT"),      # Green
        ("#0000FF", "RIGHT"),     # Blue
        ("#FFFF00", "SCREEN 3"),  # Yellow
        ("#FF00FF", "SCREEN 4"),  # Magenta
        ("#00FFFF", "SCREEN 5"),  # Cyan
        ("#FFA500", "SCREEN 6"),  # Orange
        ("#800080", "SCREEN 7")   # Purple
    ]

    root = tk.Tk()
    root.withdraw()  # Hide the main window

    windows = []

    for i in range(num_screens):
        color, label = colors[i] if i < len(colors) else ("#FFFFFF", f"SCREEN {i}")

        # Create a new top-level window for each screen
        window = tk.Toplevel(root)
        window.title(f"Calibration Screen {i}")
        window.configure(bg=color)

        # Try to position window on the correct screen using Quartz
        if HAS_QUARTZ:
            try:
                max_displays = 32
                (err, active_displays, display_count) = Quartz.CGGetActiveDisplayList(max_displays, None, None)
                if err == 0 and i < display_count:
                    display_id = active_displays[i]
                    bounds = Quartz.CGDisplayBounds(display_id)
                    x = int(bounds.origin.x)
                    y = int(bounds.origin.y)
                    width = int(bounds.size.width)
                    height = int(bounds.size.height)
                    window.geometry(f"{width}x{height}+{x}+{y}")
                    window.overrideredirect(True)  # Remove window decorations
            except Exception as e:
                print(f"  Warning: Could not position window {i}: {e}")
                window.attributes('-fullscreen', True)
        else:
            window.attributes('-fullscreen', True)

        # Create label with screen information
        frame = tk.Frame(window, bg=color)
        frame.pack(expand=True, fill='both')

        screen_label = tk.Label(
            frame,
            text=f"Screen {i}",
            font=('Arial', 120, 'bold'),
            bg=color,
            fg='white' if color in ['#0000FF', '#800080', '#FF0000'] else 'black'
        )
        screen_label.pack(expand=True)

        position_label = tk.Label(
            frame,
            text=label,
            font=('Arial', 80),
            bg=color,
            fg='white' if color in ['#0000FF', '#800080', '#FF0000'] else 'black'
        )
        position_label.pack(expand=True)

        # Raise window to top
        window.lift()
        window.attributes('-topmost', True)

        windows.append(window)
        print(f"  ✓ Test window {i} created ({label})")

    root.update()

    return {'root': root, 'windows': windows}

def cleanup_test_windows(tk_data):
    """Clean up test windows"""
    print("\n🧹 Cleaning up test windows...")

    if tk_data and 'root' in tk_data:
        try:
            root = tk_data['root']
            if root:
                root.quit()
                root.destroy()
        except:
            pass

def create_monitor_mapping(displays, num_screens, video_files):
    """
    Interactive process to map physical screens to video files.
    User identifies which MPV screen number appears on each physical location.
    """
    print("\n" + "="*70)
    print("📍 MONITOR IDENTIFICATION")
    print("="*70)
    print()
    print("Test windows will appear on each screen.")
    print("Each window shows 'MPV Screen X' with a colored background.")
    print()

    # Launch test windows
    tk_data = launch_test_windows(num_screens)

    time.sleep(2)

    print("\nPlease identify which screen number appears on each physical location:\n")

    mapping = {}

    for position_name, video_path in video_files.items():
        while True:
            try:
                response = input(f"Which screen number shows the {position_name} position? (0-{num_screens-1}): ").strip()
                mpv_screen = int(response)

                if 0 <= mpv_screen < num_screens:
                    if mpv_screen in mapping.values():
                        print(f"  ⚠️  Screen {mpv_screen} already assigned. Please choose a different screen.")
                        continue

                    mapping[position_name] = mpv_screen
                    print(f"  ✓ {position_name} position → Screen {mpv_screen}")
                    break
                else:
                    print(f"  ⚠️  Please enter a number between 0 and {num_screens-1}")
            except ValueError:
                print("  ⚠️  Please enter a valid number")
            except KeyboardInterrupt:
                print("\n\n❌ Calibration cancelled")
                cleanup_test_windows(tk_data)
                sys.exit(0)

    # Clean up test windows
    cleanup_test_windows(tk_data)

    # Create the final mapping structure
    final_mapping = {
        'displays': displays,
        'video_mapping': {}
    }

    # Map UUID to video file
    for position_name, mpv_screen in mapping.items():
        video_path = video_files[position_name]
        display_info = displays[mpv_screen]
        uuid = display_info['uuid']

        final_mapping['video_mapping'][uuid] = {
            'video_path': video_path,
            'position_name': position_name,
            'mpv_screen': mpv_screen,
            'display_info': display_info
        }

    return final_mapping

def save_mapping(mapping, filename='monitors_mapping.json'):
    """Save the monitor mapping to a JSON file"""
    filepath = Path(__file__).parent / filename

    with open(filepath, 'w') as f:
        json.dump(mapping, f, indent=2)

    print(f"\n✅ Monitor mapping saved to: {filepath}")
    return filepath

def display_mapping_summary(mapping):
    """Display a summary of the created mapping"""
    print("\n" + "="*70)
    print("📋 MAPPING SUMMARY")
    print("="*70)
    print()

    for uuid, info in mapping['video_mapping'].items():
        position = info['position_name']
        mpv_screen = info['mpv_screen']
        video = os.path.basename(info['video_path'])

        print(f"Physical {position} Screen:")
        print(f"  UUID:        {uuid}")
        print(f"  MPV Screen:  {mpv_screen}")
        print(f"  Video:       {video}")

        display = info['display_info']
        if display['serial'] != 0:
            print(f"  Serial:      {display['serial']}")
        print(f"  Vendor/Model: 0x{display['vendor_id']:04X} / 0x{display['model_id']:04X}")
        print()

def main():
    print("="*70)
    print("🎯 MONITOR CALIBRATION TOOL")
    print("="*70)
    print()
    print("This tool creates a stable monitor mapping using hardware identifiers.")
    print("The mapping ensures videos always play on the correct physical screen,")
    print("even if macOS changes the screen numbering after reboot.")
    print()

    # Load configuration
    config = load_config()
    video_files = config['video_files']

    print(f"✓ Loaded configuration from {CONFIG_FILE}")
    print(f"  Video files configured for positions: {', '.join(video_files.keys())}")
    print()

    # Check if MPV is installed
    if not subprocess.run(['which', 'mpv'], capture_output=True).returncode == 0:
        print("❌ Error: MPV not found. Please install MPV first.")
        print("   Install with: brew install mpv")
        sys.exit(1)

    # Get hardware info
    displays = get_display_hardware_info()

    if not displays:
        print("❌ Error: Could not detect displays.")
        print("   Make sure Quartz framework is installed:")
        print("   pip3 install pyobjc-framework-Quartz")
        sys.exit(1)

    num_screens = len(displays)

    # Get system profiler info for connection details
    profiler_data = get_system_profiler_info()
    display_system_profiler_summary(profiler_data)

    # Interactive mapping process
    mapping = create_monitor_mapping(displays, num_screens, video_files)

    # Save mapping
    filepath = save_mapping(mapping)

    # Display summary
    display_mapping_summary(mapping)

    print("="*70)
    print("✅ CALIBRATION COMPLETE!")
    print("="*70)
    print()
    print("The monitor mapping has been saved and will be used by multiplayer.py")
    print("to ensure videos always play on the correct physical screens.")
    print()
    print("You can now run: ./multiplayer.py")
    print()

if __name__ == "__main__":
    main()
