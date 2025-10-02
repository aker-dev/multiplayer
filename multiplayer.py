#!/usr/bin/env python3
import subprocess
import time
import json
import socket
import os

# Video paths (split into 3 parts)
videos = [
    "sources/10min.webm",
    "sources/10min.webm"
]

# Create IPC sockets
socket_dir = "/tmp/mpv_sockets"
os.makedirs(socket_dir, exist_ok=True)

sockets = [
    f"{socket_dir}/mpv_screen_{i}.sock"
    for i in range(3)
]

# Function to send a command to an MPV instance
def send_command(socket_path, command):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.5)  # Short timeout to avoid blocking
        sock.connect(socket_path)
        sock.send((json.dumps(command) + '\n').encode())
        sock.close()
        return True
    except:
        return False

# Launch the multiple MPV instances
processes = []
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
        video
    ]
    
    # Enable audio only on the central screen
    # if i == 1:
    #     cmd.remove('--no-audio')
    
    processes.append(subprocess.Popen(cmd))

# Wait for sockets to be created
time.sleep(2)

# Precise synchronization function
def sync_all():
    print("Synchronizing...")
    
    # 1. Pause all instances
    for sock in sockets:
        send_command(sock, {"command": ["set_property", "pause", True]})
    
    time.sleep(0.05)
    
    # 2. Reposition all instances to the beginning (0 seconds)
    for sock in sockets:
        send_command(sock, {"command": ["seek", 0, "absolute"]})
    
    time.sleep(0.05)
    
    # 3. Resume all instances simultaneously
    for sock in sockets:
        send_command(sock, {"command": ["set_property", "pause", False]})
    
    print("✓ Synchronization completed")

# Function to detect loop beginning
def get_video_position(socket_path):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        sock.connect(socket_path)
        sock.send((json.dumps({"command": ["get_property", "time-pos"]}) + '\n').encode())
        response = sock.recv(1024).decode()
        sock.close()
        data = json.loads(response)
        if data.get("error") == "success":
            return data.get("data", 0)
    except:
        pass
    return None

# Synchronize at startup
print("Synchronizing players...")
sync_all()

print("Screens are synchronized!")
print("Press Ctrl+C to stop")

try:
    last_position = 0
    loop_detected = False
    
    while True:
        time.sleep(1)  # Check every second
        
        # Get the position of the first instance
        current_position = get_video_position(sockets[0])
        
        if current_position is not None:
            # Detect if we've looped (current position < previous position)
            if current_position < last_position - 1:  # -1 to avoid false positives
                print(f"🔄 Loop start detected (pos: {current_position:.1f}s)")
                sync_all()
                loop_detected = True
            
            last_position = current_position
            
            # Display position from time to time
            if int(current_position) % 10 == 0 and not loop_detected:
                print(f"Position: {current_position:.1f}s")
            
            loop_detected = False
        
except KeyboardInterrupt:
    print("\nStopping players...")
    for sock in sockets:
        send_command(sock, {"command": ["quit"]})