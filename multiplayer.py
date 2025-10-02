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
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
NUM_SCREENS = 1  # Change this value between 1 and 8
SOCKET_DIR = "/tmp/mpv_sockets"
SOCKET_TIMEOUT = 0.5
SYNC_DELAY = 0.1
STARTUP_DELAY = 3
MAX_RETRIES = 3
RETRY_DELAY = 0.5

# Video paths - can specify different videos per screen or use the same one
videos = [
    "sources/impossible.webm"
]

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
for i, video_path in enumerate(videos):
    if not os.path.isfile(video_path):
        logger.error(f"Video file not found: {video_path}")
        sys.exit(1)
    logger.info(f"Screen {i}: {video_path}")

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
        '--loop',
        '--fullscreen',
        f'--screen={i}',
        f'--input-ipc-server={sockets[i]}',
        '--no-audio',  # Disable audio except for one instance
        '--force-window',
        '--vo=gpu',  # Use GPU rendering for better performance
        '--hwdec=auto',  # Hardware decoding
        '--cache=yes',
        '--demuxer-max-bytes=50M',
        video
    ]

    # Enable audio only on the central screen (middle screen for odd numbers, first half for even)
    if i == NUM_SCREENS // 2:
        cmd.remove('--no-audio')
        logger.info(f"Audio enabled on screen {i}")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        processes.append(proc)
        logger.info(f"Started MPV instance {i} (PID: {proc.pid})")
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
    """Synchronize all MPV instances with retry logic"""
    logger.info("Synchronizing all instances...")

    # Check process health before syncing
    dead = check_processes_health()
    if dead:
        logger.error(f"Cannot sync: MPV instance(s) {dead} are not running")
        return False

    success_count = 0

    # 1. Pause all instances
    for i, sock in enumerate(sockets):
        if send_command(sock, {"command": ["set_property", "pause", True]}):
            success_count += 1
        else:
            logger.warning(f"Failed to pause instance {i}")

    if success_count < NUM_SCREENS:
        logger.warning(f"Only paused {success_count}/{NUM_SCREENS} instances")

    time.sleep(SYNC_DELAY)

    # 2. Reposition all instances to the beginning (0 seconds)
    success_count = 0
    for i, sock in enumerate(sockets):
        if send_command(sock, {"command": ["seek", 0, "absolute"]}):
            success_count += 1
        else:
            logger.warning(f"Failed to seek instance {i}")

    if success_count < NUM_SCREENS:
        logger.warning(f"Only seeked {success_count}/{NUM_SCREENS} instances")

    time.sleep(SYNC_DELAY)

    # 3. Resume all instances simultaneously
    success_count = 0
    for i, sock in enumerate(sockets):
        if send_command(sock, {"command": ["set_property", "pause", False]}):
            success_count += 1
        else:
            logger.warning(f"Failed to resume instance {i}")

    if success_count < NUM_SCREENS:
        logger.warning(f"Only resumed {success_count}/{NUM_SCREENS} instances")
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