#!/usr/bin/env python3
"""
Setup verification tool for multiplayer video synchronization system.
Checks that all required files and configuration are in place.
"""

import json
import os
import sys
from pathlib import Path

def check_config():
    """Check if config.json exists and is valid"""
    config_file = Path(__file__).parent / "config.json"

    print("1. Checking config.json...")

    if not config_file.exists():
        print("   ❌ config.json NOT FOUND")
        print("      Run: cp config.json.example config.json")
        print("      Then edit config.json with your video file paths")
        return False

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)

        # Check structure
        if 'video_files' not in config:
            print("   ❌ Missing 'video_files' in config.json")
            return False

        if 'num_screens' not in config:
            print("   ⚠️  Missing 'num_screens' in config.json (will default to 3)")

        # Check video files
        video_files = config['video_files']
        required = {'CENTER', 'LEFT', 'RIGHT'}
        positions = set(video_files.keys())

        if not required.issubset(positions):
            missing = required - positions
            print(f"   ❌ Missing positions in config.json: {missing}")
            return False

        print("   ✅ config.json is valid")

        # Check if video files exist
        print("\n2. Checking video files...")
        all_exist = True
        for position, path in video_files.items():
            if os.path.isfile(path):
                print(f"   ✅ {position:6s} → {os.path.basename(path)}")
            else:
                print(f"   ❌ {position:6s} → FILE NOT FOUND: {path}")
                all_exist = False

        return all_exist

    except json.JSONDecodeError as e:
        print(f"   ❌ Invalid JSON in config.json: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error reading config.json: {e}")
        return False

def check_calibration():
    """Check if monitors_mapping.json exists"""
    mapping_file = Path(__file__).parent / "monitors_mapping.json"

    print("\n3. Checking monitor calibration...")

    if not mapping_file.exists():
        print("   ❌ monitors_mapping.json NOT FOUND")
        print("      Run: ./monitors_calibrate.py")
        return False

    try:
        with open(mapping_file, 'r') as f:
            mapping = json.load(f)

        if 'video_mapping' not in mapping or 'displays' not in mapping:
            print("   ❌ Invalid monitors_mapping.json format")
            print("      Run: ./monitors_calibrate.py")
            return False

        if len(mapping['video_mapping']) == 0:
            print("   ❌ No monitor mappings in monitors_mapping.json")
            print("      Run: ./monitors_calibrate.py")
            return False

        print("   ✅ monitors_mapping.json is valid")

        # Display current mapping
        print("\n   Current monitor mapping:")
        for uuid, info in sorted(mapping['video_mapping'].items(), key=lambda x: x[1]['position_name']):
            pos_name = info['position_name']
            pos = info['display_info']['position']
            video = info['video_path'].split('/')[-1]
            print(f"      {pos_name:6s} → Position ({pos['x']:5d}, {pos['y']:5d}) → {video}")

        return True

    except Exception as e:
        print(f"   ❌ Error reading monitors_mapping.json: {e}")
        return False

def check_mpv():
    """Check if MPV is installed"""
    import subprocess

    print("\n4. Checking MPV installation...")

    result = subprocess.run(['which', 'mpv'], capture_output=True)
    if result.returncode == 0:
        mpv_path = result.stdout.decode().strip()
        print(f"   ✅ MPV found at: {mpv_path}")
        return True
    else:
        print("   ❌ MPV not found")
        print("      Install with: brew install mpv")
        return False

def check_quartz():
    """Check if Quartz framework is available"""
    print("\n5. Checking Quartz framework...")

    try:
        import Quartz
        print("   ✅ Quartz framework available")
        return True
    except ImportError:
        print("   ❌ Quartz framework not available")
        print("      Install with: pip3 install pyobjc-framework-Quartz")
        return False

def main():
    print("="*70)
    print("  MULTIPLAYER SETUP VERIFICATION")
    print("="*70)
    print()

    checks = [
        check_config(),
        check_calibration(),
        check_mpv(),
        check_quartz()
    ]

    print()
    print("="*70)
    print("  SUMMARY")
    print("="*70)

    if all(checks):
        print("\n✅ ALL CHECKS PASSED!")
        print("\nYou can now run: ./multiplayer.py")
    else:
        print("\n❌ SOME CHECKS FAILED")
        print("\nPlease fix the issues above before running multiplayer.py")
        sys.exit(1)

    print()

if __name__ == "__main__":
    main()
