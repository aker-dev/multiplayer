#!/usr/bin/env python3
import subprocess
import time
import json
import socket
import os
import sys
import logging
import shutil
import signal
import threading
from pathlib import Path

# Try to import Quartz for display detection (macOS only)
try:
    import Quartz
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False
    logging.warning("Quartz not available - UUID-based monitor detection disabled")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration file location
CONFIG_FILE = Path(__file__).parent / "config.json"

# Default configuration
SOCKET_DIR = "/tmp/mpv_sockets"
SOCKET_TIMEOUT = 0.5
SYNC_DELAY = 0.05  # Reduced from 0.1 - parallel commands are faster
STARTUP_DELAY = 3
MAX_RETRIES = 3
RETRY_DELAY = 0.5

def load_config():
    """Load configuration from config.json"""
    if not CONFIG_FILE.exists():
        logger.error(f"❌ Configuration file not found: {CONFIG_FILE}")
        logger.error("Please create config.json with your settings.")
        logger.error("See config.json.example for reference.")
        return None

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        if 'num_screens' not in config:
            logger.warning("'num_screens' not in config.json, defaulting to 3")
            config['num_screens'] = 3

        return config
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parsing config.json: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Error loading config.json: {e}")
        return None

# Load configuration
config = load_config()
if config is None:
    sys.exit(1)

NUM_SCREENS = config.get('num_screens', 3)

def get_current_display_uuids():
    """Get UUIDs of currently connected displays in MPV screen order"""
    if not HAS_QUARTZ:
        logger.warning("Quartz not available - cannot detect display UUIDs")
        return None

    import hashlib

    displays = {}
    max_displays = 32
    (err, active_displays, display_count) = Quartz.CGGetActiveDisplayList(max_displays, None, None)

    if err != 0:
        logger.error(f"Error getting display list: {err}")
        return None

    for idx, display_id in enumerate(active_displays[:display_count]):
        # Get hardware identifiers
        serial = Quartz.CGDisplaySerialNumber(display_id)
        vendor_id = Quartz.CGDisplayVendorNumber(display_id)
        model_id = Quartz.CGDisplayModelNumber(display_id)

        # Get position (bounds)
        bounds = Quartz.CGDisplayBounds(display_id)
        position_x = int(bounds.origin.x)
        position_y = int(bounds.origin.y)

        # Create a stable UUID-like identifier based on position
        # Position (x, y) is the most stable identifier across reboots
        # This matches the same algorithm used in calibrate_monitors.py
        hardware_signature = f"{position_x}:{position_y}:{serial}:{vendor_id:04X}:{model_id:04X}"
        uuid_str = hashlib.sha256(hardware_signature.encode()).hexdigest()[:32]
        # Format as UUID-like string for readability
        uuid_str = f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:32]}"

        displays[idx] = uuid_str

    return displays

def load_monitor_mapping():
    """
    Load monitor mapping from calibration file.
    Returns a dict mapping MPV screen index to video path.
    """
    mapping_file = Path(__file__).parent / "monitors_mapping.json"

    if not mapping_file.exists():
        logger.error("❌ monitors_mapping.json NOT FOUND!")
        logger.error("")
        logger.error("You MUST calibrate your monitors before running multiplayer.")
        logger.error("This ensures videos always play on the correct screens,")
        logger.error("even after reboots when macOS may change monitor numbering.")
        logger.error("")
        logger.error("Please run: ./monitors_calibrate.py")
        logger.error("")
        return None

    try:
        with open(mapping_file, 'r') as f:
            mapping_data = json.load(f)

        # Validate file structure
        if 'video_mapping' not in mapping_data or 'displays' not in mapping_data:
            logger.error("❌ Invalid monitors_mapping.json format!")
            logger.error("The calibration file is corrupted or outdated.")
            logger.error("Please re-run: ./monitors_calibrate.py")
            return None

        if len(mapping_data['video_mapping']) == 0:
            logger.error("❌ monitors_mapping.json contains no video mappings!")
            logger.error("Please re-run: ./monitors_calibrate.py")
            return None

        logger.info("✓ Loaded monitor mapping from calibration file")

        # Get current display UUIDs
        current_uuids = get_current_display_uuids()

        if current_uuids is None:
            logger.warning("Cannot detect current display UUIDs - using saved MPV screen numbers")
            # Fallback: use saved MPV screen numbers directly
            result = {}
            for _, info in mapping_data['video_mapping'].items():
                mpv_screen = info['mpv_screen']
                video_path = info['video_path']
                result[mpv_screen] = video_path
            return result

        # Map current MPV screen indices to videos using UUID matching
        result = {}
        for mpv_screen_idx, current_uuid in current_uuids.items():
            # Find this UUID in the calibration data
            if current_uuid in mapping_data['video_mapping']:
                video_info = mapping_data['video_mapping'][current_uuid]
                video_path = video_info['video_path']
                position_name = video_info['position_name']
                result[mpv_screen_idx] = video_path
                logger.info(f"✓ MPV Screen {mpv_screen_idx} → {position_name} ({os.path.basename(video_path)})")
            else:
                logger.warning(f"⚠️  MPV Screen {mpv_screen_idx} UUID not found in calibration - monitor may have changed")

        # Verify we have mappings for all screens
        if len(result) != NUM_SCREENS:
            logger.error(f"Monitor configuration has changed! Expected {NUM_SCREENS} screens, found {len(result)}")
            logger.error("Please run ./calibrate_monitors.py again to recalibrate")
            return None

        return result

    except Exception as e:
        logger.error(f"Error loading monitor mapping: {e}")
        logger.error("Please run ./calibrate_monitors.py to create a valid mapping")
        return None

# Load monitor mapping (UUID-based if available, otherwise default)
VIDEO_MONITOR_MAPPING = load_monitor_mapping()

if VIDEO_MONITOR_MAPPING is None:
    logger.error("Failed to load monitor mapping")
    sys.exit(1)

# Build videos list from mapping to maintain compatibility with existing code
videos = [VIDEO_MONITOR_MAPPING.get(i, "") for i in range(NUM_SCREENS)]

# Validate configuration
if not 1 <= NUM_SCREENS <= 8:
    logger.error(f"NUM_SCREENS must be between 1 and 8, got {NUM_SCREENS}")
    sys.exit(1)

# Ensure we have enough video paths
if len(videos) < NUM_SCREENS:
    logger.warning(f"Only {len(videos)} videos specified for {NUM_SCREENS} screens. Reusing last video.")
    videos.extend([videos[-1]] * (NUM_SCREENS - len(videos)))
elif len(videos) > NUM_SCREENS:
    logger.warning(f"More videos ({len(videos)}) than screens ({NUM_SCREENS}). Using first {NUM_SCREENS} videos.")
    videos = videos[:NUM_SCREENS]

# Validate video files exist
logger.info("Validating video files...")
for i, video_path in enumerate(videos):
    if not video_path:
        logger.error(f"No video configured for MPV screen {i}")
        sys.exit(1)
    if not os.path.isfile(video_path):
        logger.error(f"Video file not found for MPV screen {i}: {video_path}")
        sys.exit(1)

    # Log which video is on which monitor
    video_name = os.path.basename(video_path).replace('.mov', '').replace('ecran_', '')
    logger.info(f"✓ MPV Screen {i} → {video_name}")

# Check if MPV is installed
if not shutil.which('mpv'):
    logger.error("MPV not found. Please install MPV media player.")
    sys.exit(1)

# Create IPC sockets directory
os.makedirs(SOCKET_DIR, exist_ok=True)

# Clean up old sockets
for old_socket in Path(SOCKET_DIR).glob("mpv_screen_*.sock"):
    try:
        old_socket.unlink()
        logger.debug(f"Removed old socket: {old_socket}")
    except Exception as e:
        logger.warning(f"Could not remove old socket {old_socket}: {e}")

sockets = [
    f"{SOCKET_DIR}/mpv_screen_{i}.sock"
    for i in range(NUM_SCREENS)
]

# Function to send a command to an MPV instance with retry logic
def send_command(socket_path, command, retries=MAX_RETRIES):
    """Send command to MPV instance via IPC socket with retry logic"""
    for attempt in range(retries):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.connect(socket_path)
            sock.send((json.dumps(command) + '\n').encode())
            sock.close()
            return True
        except FileNotFoundError:
            logger.error(f"Socket not found: {socket_path}")
            return False
        except socket.timeout:
            logger.warning(f"Socket timeout on {socket_path} (attempt {attempt + 1}/{retries})")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
        except ConnectionRefusedError:
            logger.warning(f"Connection refused on {socket_path} (attempt {attempt + 1}/{retries})")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error(f"Error sending command to {socket_path}: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY)
    return False

def send_command_parallel(sockets_list, command, retries=MAX_RETRIES):
    """Send the same command to multiple MPV instances in parallel using threading"""
    results = [False] * len(sockets_list)
    threads = []

    def send_to_socket(idx, sock_path):
        results[idx] = send_command(sock_path, command, retries)

    # Create and start threads for parallel execution
    for idx, sock_path in enumerate(sockets_list):
        thread = threading.Thread(target=send_to_socket, args=(idx, sock_path))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    return results

# Global variable to track processes for cleanup
processes = []

def cleanup_processes():
    """Clean up all MPV processes and sockets"""
    logger.info("Cleaning up processes...")

    # Try to quit MPV gracefully first
    for sock in sockets:
        send_command(sock, {"command": ["quit"]}, retries=1)

    time.sleep(0.5)

    # Force kill any remaining processes
    for proc in processes:
        if proc.poll() is None:  # Process still running
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            except Exception as e:
                logger.error(f"Error terminating process: {e}")

    # Clean up sockets
    for sock_path in sockets:
        try:
            if os.path.exists(sock_path):
                os.unlink(sock_path)
        except Exception as e:
            logger.warning(f"Could not remove socket {sock_path}: {e}")

    logger.info("Cleanup completed")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("\nReceived interrupt signal...")
    cleanup_processes()
    sys.exit(0)

# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Launch the multiple MPV instances
logger.info(f"Launching {NUM_SCREENS} MPV instance(s)...")
for i, video in enumerate(videos):
    cmd = [
        'mpv',
        f'--title=mpv-{i+1:02d}',  # Window title: mpv-01, mpv-02, etc.
        '--loop',#
        '--fullscreen',#
        f'--screen={i}',# Specify screen index
        f'--input-ipc-server={sockets[i]}',
        '--no-audio',  # Disable audio except for one instance
        '--force-window',# Keep window open even if no video
        '--vo=gpu',  # Use GPU rendering for better performance
        '--hwdec=auto',  # Hardware decoding
        '--cache=yes',  # Enable caching
        '--demuxer-max-bytes=50M',# Increase demuxer cache
        '--no-osc',  # Hide on-screen controller
        '--no-osd-bar',  # Hide OSD bar (seek bar, volume bar)
        '--osd-level=0',  # Disable all OSD messages
        '--cursor-autohide=500',  # Hide cursor immediately
        '--no-input-default-bindings',  # Disable default keyboard/mouse controls
        '--video-sync=display-resample',  # Better A/V sync
        video
    ]

    # Enable audio only on the central screen (middle screen for odd numbers, first half for even)
    if i == NUM_SCREENS // 2:
        cmd.remove('--no-audio')
        logger.info(f"Audio enabled on screen {i}")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        processes.append(proc)
        video_name = os.path.basename(video).replace('.mov', '').replace('ecran_', '')
        logger.info(f"✓ MPV instance {i} (PID: {proc.pid}) → Monitor {i} playing '{video_name}'")
    except Exception as e:
        logger.error(f"Failed to start MPV instance {i}: {e}")
        cleanup_processes()
        sys.exit(1)

# Wait for sockets to be created and verify processes are healthy
logger.info(f"Waiting {STARTUP_DELAY}s for MPV instances to initialize...")
time.sleep(STARTUP_DELAY)

# Check if all processes are still running
dead_processes = []
for i, proc in enumerate(processes):
    if proc.poll() is not None:
        dead_processes.append(i)

if dead_processes:
    logger.error(f"MPV instance(s) {dead_processes} died during startup")
    cleanup_processes()
    sys.exit(1)

# Wait for all sockets to be available
logger.info("Waiting for IPC sockets...")
for i, sock_path in enumerate(sockets):
    timeout = 10
    start_time = time.time()
    while not os.path.exists(sock_path):
        if time.time() - start_time > timeout:
            logger.error(f"Socket {sock_path} not created after {timeout}s")
            cleanup_processes()
            sys.exit(1)
        time.sleep(0.1)
    logger.info(f"Socket {i} ready: {sock_path}")

def check_processes_health():
    """Check if all MPV processes are still running"""
    dead = []
    for i, proc in enumerate(processes):
        if proc.poll() is not None:
            dead.append(i)
    return dead

# Precise synchronization function with validation
def sync_all():
    """Synchronize all MPV instances with retry logic using parallel command sending"""
    logger.info("Synchronizing all instances...")

    # Check process health before syncing
    dead = check_processes_health()
    if dead:
        logger.error(f"Cannot sync: MPV instance(s) {dead} are not running")
        return False

    # 1. Pause all instances in parallel
    results = send_command_parallel(sockets, {"command": ["set_property", "pause", True]})
    success_count = sum(results)

    if success_count < NUM_SCREENS:
        logger.warning(f"Only paused {success_count}/{NUM_SCREENS} instances")
        for i, success in enumerate(results):
            if not success:
                logger.warning(f"Failed to pause instance {i}")

    time.sleep(SYNC_DELAY)

    # 2. Reposition all instances to the beginning (0 seconds) in parallel
    results = send_command_parallel(sockets, {"command": ["seek", 0, "absolute"]})
    success_count = sum(results)

    if success_count < NUM_SCREENS:
        logger.warning(f"Only seeked {success_count}/{NUM_SCREENS} instances")
        for i, success in enumerate(results):
            if not success:
                logger.warning(f"Failed to seek instance {i}")

    time.sleep(SYNC_DELAY)

    # 3. Resume all instances simultaneously in parallel
    results = send_command_parallel(sockets, {"command": ["set_property", "pause", False]})
    success_count = sum(results)

    if success_count < NUM_SCREENS:
        logger.warning(f"Only resumed {success_count}/{NUM_SCREENS} instances")
        for i, success in enumerate(results):
            if not success:
                logger.warning(f"Failed to resume instance {i}")
        return False

    logger.info("✓ Synchronization completed successfully")
    return True

# Function to get video position with better error handling
def get_video_position(socket_path):
    """Get current playback position from MPV instance"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        sock.connect(socket_path)
        sock.send((json.dumps({"command": ["get_property", "time-pos"]}) + '\n').encode())
        response = sock.recv(1024).decode()
        sock.close()
        data = json.loads(response)
        if data.get("error") == "success":
            return data.get("data", 0)
    except FileNotFoundError:
        logger.error(f"Socket not found: {socket_path}")
    except socket.timeout:
        logger.debug(f"Timeout getting position from {socket_path}")
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON response from {socket_path}")
    except Exception as e:
        logger.debug(f"Error getting position: {e}")
    return None

# Synchronize at startup
logger.info("Performing initial synchronization...")
if not sync_all():
    logger.error("Initial synchronization failed")
    cleanup_processes()
    sys.exit(1)

# Simulate click to activate window and hide cursor on CENTER screen
logger.info("Simulating click on center screen to activate window...")
try:
    # Find which MPV screen index has the CENTER video
    center_screen_idx = None
    for mpv_idx, video_path in VIDEO_MONITOR_MAPPING.items():
        if 'ecran_centre' in video_path or 'center' in video_path.lower():
            center_screen_idx = mpv_idx
            break

    if center_screen_idx is not None:
        # Get the center screen's display bounds using Quartz
        if HAS_QUARTZ:
            (err, active_displays, display_count) = Quartz.CGGetActiveDisplayList(32, None, None)
            if err == 0 and center_screen_idx < display_count:
                display_id = active_displays[center_screen_idx]
                bounds = Quartz.CGDisplayBounds(display_id)
                # Click at the center of the display
                center_x = bounds.origin.x + bounds.size.width / 2
                center_y = bounds.origin.y + bounds.size.height / 2
                subprocess.run(['cliclick', f'c:{int(center_x)},{int(center_y)}'], check=True, capture_output=True)
                logger.info(f"✓ Clicked on center screen at ({int(center_x)}, {int(center_y)})")
            else:
                logger.warning("Could not get center screen bounds, clicking at current position")
                subprocess.run(['cliclick', 'c:.'], check=True, capture_output=True)
        else:
            logger.warning("Quartz not available, clicking at current position")
            subprocess.run(['cliclick', 'c:.'], check=True, capture_output=True)
    else:
        logger.warning("Could not identify center screen, clicking at current position")
        subprocess.run(['cliclick', 'c:.'], check=True, capture_output=True)

    time.sleep(0.2)
except FileNotFoundError:
    logger.warning("cliclick not found. Install with: brew install cliclick")
except Exception as e:
    logger.warning(f"Could not simulate click: {e}")

logger.info("=" * 50)
logger.info(f"✓ {NUM_SCREENS} screen(s) synchronized and ready!")
logger.info("Press Ctrl+C to stop")
logger.info("=" * 50)

try:
    last_position = 0
    loop_detected = False
    health_check_interval = 10  # Check process health every 10 iterations
    iteration = 0
    failed_position_reads = 0
    max_failed_reads = 5

    while True:
        time.sleep(1)  # Check every second
        iteration += 1

        # Periodic health check
        if iteration % health_check_interval == 0:
            dead = check_processes_health()
            if dead:
                logger.error(f"MPV instance(s) {dead} have died!")
                cleanup_processes()
                sys.exit(1)

        # Get the position of the first instance
        current_position = get_video_position(sockets[0])

        if current_position is not None:
            failed_position_reads = 0  # Reset counter on successful read

            # Detect if we've looped (current position < previous position)
            # Use threshold of 1 second to avoid false positives
            if current_position < last_position - 1:
                logger.info(f"🔄 Loop detected (pos: {current_position:.1f}s -> resync)")
                if not sync_all():
                    logger.error("Re-synchronization failed!")
                loop_detected = True

            last_position = current_position

            # Display position periodically
            if int(current_position) % 30 == 0 and not loop_detected:
                logger.info(f"Playback position: {current_position:.1f}s")

            loop_detected = False
        else:
            failed_position_reads += 1
            if failed_position_reads >= max_failed_reads:
                logger.error(f"Failed to read position {max_failed_reads} times in a row")
                cleanup_processes()
                sys.exit(1)

except KeyboardInterrupt:
    # Signal handler will handle cleanup
    pass
except Exception as e:
    logger.error(f"Unexpected error in main loop: {e}")
    cleanup_processes()
    sys.exit(1)