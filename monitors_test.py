#!/usr/bin/env python3
"""
Test script to verify monitors_mapping.json configuration.

This script reads the calibration file and displays test windows on each screen
to verify that the physical-to-MPV monitor mapping is correct.

Usage:
    ./test_screens.py
"""

import json
import os
import sys
import tkinter as tk

CALIBRATION_FILE = "monitors_mapping.json"

# Try to import Quartz for precise window positioning (macOS only)
try:
    import Quartz
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False
    print("⚠️  Warning: Quartz not available. Windows may not position correctly.")
    print("   Install with: pip3 install pyobjc-framework-Quartz\n")

def load_calibration():
    """Load monitor calibration from JSON file."""
    if not os.path.exists(CALIBRATION_FILE):
        print(f"❌ Calibration file '{CALIBRATION_FILE}' not found!")
        print(f"   Please run './calibrate_monitors.py' first.")
        return None

    try:
        with open(CALIBRATION_FILE, 'r') as f:
            calibration = json.load(f)

        print(f"✓ Loaded calibration from {CALIBRATION_FILE}\n")
        return calibration
    except Exception as e:
        print(f"❌ Error loading calibration file: {e}")
        return None

def verify_calibration_structure(calibration):
    """Verify that the calibration file has the correct structure."""

    # Check if it's the new UUID-based format
    if 'video_mapping' in calibration and 'displays' in calibration:
        print("✓ Detected UUID-based calibration format")
        return verify_uuid_format(calibration)
    else:
        print("✓ Detected simple screen number format")
        return verify_simple_format(calibration)

def verify_uuid_format(calibration):
    """Verify UUID-based calibration format."""
    video_mapping = calibration.get('video_mapping', {})

    if not video_mapping:
        print("❌ No video mappings found in calibration file")
        return False

    positions = set()
    for uuid, info in video_mapping.items():
        position = info.get('position_name')
        if position:
            positions.add(position)

    required = {'CENTER', 'LEFT', 'RIGHT'}
    if not required.issubset(positions):
        missing = required - positions
        print(f"❌ Missing positions in calibration: {missing}")
        return False

    print("✓ Calibration structure is valid (UUID-based)")
    return True

def verify_simple_format(calibration):
    """Verify simple screen number format."""
    required_keys = ["CENTER", "LEFT", "RIGHT"]

    for key in required_keys:
        if key not in calibration:
            print(f"❌ Missing key '{key}' in calibration file")
            return False

        mpv_screen = calibration[key]
        if not isinstance(mpv_screen, int):
            print(f"❌ Invalid value for '{key}': {mpv_screen} (must be integer)")
            return False

    # Check for duplicates
    values = [calibration[key] for key in required_keys]
    if len(values) != len(set(values)):
        print(f"❌ Duplicate screen numbers detected: {calibration}")
        return False

    print("✓ Calibration structure is valid (simple format)")
    return True

def get_screen_mapping(calibration):
    """Extract screen number mapping from calibration data."""

    # UUID-based format
    if 'video_mapping' in calibration:
        mapping = {}
        for uuid, info in calibration['video_mapping'].items():
            position = info.get('position_name')
            screen_num = info.get('mpv_screen')
            if position and screen_num is not None:
                mapping[position] = screen_num
        return mapping

    # Simple format
    return {
        "CENTER": calibration["CENTER"],
        "LEFT": calibration["LEFT"],
        "RIGHT": calibration["RIGHT"]
    }

def get_current_display_uuids():
    """Get UUIDs of currently connected displays (matches multiplayer.py algorithm)"""
    if not HAS_QUARTZ:
        return None

    import hashlib

    displays = {}
    max_displays = 32
    (err, active_displays, display_count) = Quartz.CGGetActiveDisplayList(max_displays, None, None)

    if err != 0:
        return None

    for idx, display_id in enumerate(active_displays[:display_count]):
        serial = Quartz.CGDisplaySerialNumber(display_id)
        vendor_id = Quartz.CGDisplayVendorNumber(display_id)
        model_id = Quartz.CGDisplayModelNumber(display_id)

        bounds = Quartz.CGDisplayBounds(display_id)
        position_x = int(bounds.origin.x)
        position_y = int(bounds.origin.y)

        # Create UUID based on position (same algorithm as multiplayer.py)
        hardware_signature = f"{position_x}:{position_y}:{serial}:{vendor_id:04X}:{model_id:04X}"
        uuid_str = hashlib.sha256(hardware_signature.encode()).hexdigest()[:32]
        uuid_str = f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:32]}"

        displays[uuid_str] = {
            'mpv_index': idx,
            'position': (position_x, position_y),
            'bounds': bounds
        }

    return displays

def display_test_windows(screen_mapping, calibration):
    """
    Display test windows using Tkinter.
    Shows colored fullscreen windows with labels on each configured screen.
    Uses UUID-based matching to ensure correct screen placement.
    """
    print("🚀 Launching test windows...\n")

    # Color mapping for each position
    position_colors = {
        "CENTER": ("#0000FF", "white"),   # Blue background, white text
        "LEFT": ("#00FF00", "black"),     # Green background, black text
        "RIGHT": ("#FF0000", "white")     # Red background, white text
    }

    root = tk.Tk()
    root.withdraw()  # Hide the main window

    windows = []

    # Get current display UUIDs
    current_displays = get_current_display_uuids()
    if not current_displays:
        print("⚠️  Cannot detect current displays. Falling back to screen numbers.")

    for position, screen_num in sorted(screen_mapping.items()):
        bg_color, fg_color = position_colors.get(position, ("#FFFFFF", "black"))

        # Create a new top-level window for each screen
        window = tk.Toplevel(root)
        window.title(f"Test: {position}")
        window.configure(bg=bg_color)

        # Try to position window using UUID matching (like multiplayer.py)
        placed = False
        if HAS_QUARTZ and current_displays:
            try:
                # Find the UUID for this position from the calibration
                target_uuid = None
                for uuid, info in calibration.get('video_mapping', {}).items():
                    if info.get('position_name') == position:
                        target_uuid = uuid
                        break

                if target_uuid and target_uuid in current_displays:
                    display_info = current_displays[target_uuid]
                    bounds = display_info['bounds']
                    mpv_idx = display_info['mpv_index']

                    x = int(bounds.origin.x)
                    y = int(bounds.origin.y)
                    width = int(bounds.size.width)
                    height = int(bounds.size.height)

                    window.geometry(f"{width}x{height}+{x}+{y}")
                    window.overrideredirect(True)
                    print(f"  ✓ {position:6s} → Position ({x:5d}, {y:5d}) → MPV Screen {mpv_idx} → {bg_color.upper()} window")
                    placed = True
                else:
                    print(f"  ⚠️  UUID not found for {position}, using fallback")

            except Exception as e:
                print(f"  ⚠️  Could not position {position} window: {e}")

        if not placed:
            window.attributes('-fullscreen', True)
            print(f"  ✓ {position:6s} → Screen {screen_num} (fallback) → {bg_color.upper()} window")

        # Create label with screen information
        frame = tk.Frame(window, bg=bg_color)
        frame.pack(expand=True, fill='both')

        # Position label (big)
        position_label = tk.Label(
            frame,
            text=position,
            font=('Arial', 120, 'bold'),
            bg=bg_color,
            fg=fg_color
        )
        position_label.pack(expand=True, pady=(100, 20))

        # Screen number label
        screen_label = tk.Label(
            frame,
            text=f"Screen {screen_num}",
            font=('Arial', 60),
            bg=bg_color,
            fg=fg_color
        )
        screen_label.pack(expand=True, pady=(20, 100))

        # Raise window to top
        window.lift()
        window.attributes('-topmost', True)

        windows.append(window)

    print("\n" + "="*60)
    print("  VERIFICATION")
    print("="*60)
    print("\nPlease verify that:")
    print("  • Your LEFT screen shows GREEN")
    print("  • Your CENTER screen shows BLUE")
    print("  • Your RIGHT screen shows RED")
    print("\n" + "="*60 + "\n")
    print("Press Ctrl+C or close any window to exit...")

    root.update()

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n")

    print("✓ Test complete!\n")

def main():
    print("\n" + "="*60)
    print("  MONITOR MAPPING TEST")
    print("="*60 + "\n")

    # Load calibration
    calibration = load_calibration()
    if not calibration:
        sys.exit(1)

    # Verify structure
    if not verify_calibration_structure(calibration):
        sys.exit(1)

    print()

    # Get screen mapping
    screen_mapping = get_screen_mapping(calibration)

    print("Current mapping:")
    for position, screen_num in sorted(screen_mapping.items()):
        print(f"  {position:6s} → Screen {screen_num}")
    print()

    # Display test windows
    display_test_windows(screen_mapping, calibration)

if __name__ == "__main__":
    main()
