import os
import sys
import subprocess
import shutil
import time

def check_library(name):
    print(f"[*] Checking library: {name}...", end=" ")
    try:
        __import__(name)
        print("OK")
        return True
    except ImportError:
        print("FAIL (Not installed)")
        return False

def check_command(cmd):
    print(f"[*] Checking command: {cmd}...", end=" ")
    path = shutil.which(cmd)
    if path:
        print(f"OK ({path})")
        return True
    else:
        print("FAIL (Not found in PATH)")
        return False

def check_config_file(filename):
    if not os.path.exists(filename):
        return None
    
    print(f"    Reading {filename}...")
    with open(filename, 'r') as f:
        content = f.read()
        
    issues = []
    if "start_x=1" in content:
        issues.append("⚠️  'start_x=1' found (Legacy Camera Mode enabled). This disables libcamera/rpicam!")
    
    if "camera_auto_detect=0" in content:
        issues.append("⚠️  'camera_auto_detect=0' found. Ensure your camera is explicitly defined.")
        
    return issues

print("="*50)
print(" 🕵️  Raspberry Pi Hardware Diagnostic Tool v2.0")
print("="*50)

# 1. Check Python Libraries
print("\n[1] Checking Python Libraries...")
libs = ["spidev", "RPi.GPIO", "cv2", "numpy"]
for lib in libs:
    check_library(lib)

# 2. Check Camera Command
print("\n[2] Checking Camera System...")
has_rpicam = check_command("rpicam-still")
has_libcamera = check_command("libcamera-still")
has_raspistill = check_command("raspistill")

# 2-1. Check Config Files (Common Issues)
print("\n[2-1] Checking System Configuration...")
config_files = ["/boot/config.txt", "/boot/firmware/config.txt"]
found_config = False
for cf in config_files:
    issues = check_config_file(cf)
    if issues is not None:
        found_config = True
        if not issues:
            print(f"    ✅ {cf} looks OK.")
        else:
            for issue in issues:
                print(f"    {issue}")

if not found_config:
    print("    ℹ️  Could not find config.txt (might be different OS structure).")

# 2-2. List Cameras
list_cmd = None
if check_command("rpicam-hello"):
    list_cmd = ["rpicam-hello", "--list-cameras"]
elif check_command("libcamera-hello"):
    list_cmd = ["libcamera-hello", "--list-cameras"]

if list_cmd:
    print("\n[2-2] Listing Available Cameras...")
    try:
        result = subprocess.run(list_cmd, capture_output=True, text=True)
        print(result.stdout)
        if "Available cameras" not in result.stdout and "seq" not in result.stdout:
             print("    ❌ NO CAMERAS DETECTED by the system.")
    except Exception as e:
        print(f"    Error listing cameras: {e}")

# 3. Test Capture
target_cmd = None
if has_rpicam:
    target_cmd = "rpicam-still"
elif has_libcamera:
    target_cmd = "libcamera-still"
elif has_raspistill:
    target_cmd = "raspistill"

if not target_cmd:
    print("\n❌ No camera software found!")
else:
    print(f"\n[3] Testing Camera Capture ({target_cmd})...")
    try:
        cmd = [target_cmd, "-o", "test_image.jpg", "-t", "1000", "--width", "640", "--height", "480", "--nopreview"]
        print(f"    Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("    ✅ Capture SUCCESS! (saved to test_image.jpg)")
            if os.path.exists("test_image.jpg"):
                print(f"    File size: {os.path.getsize('test_image.jpg')} bytes")
        else:
            print("    ❌ Capture FAILED!")
            print("    Error Output:")
            print("-" * 20)
            print(result.stderr)
            print("-" * 20)
    except Exception as e:
        print(f"    Error executing command: {e}")

# 4. Check SPI
print("\n[4] Checking SPI Interface...")
if os.path.exists("/dev/spidev0.0"):
    print("    ✅ /dev/spidev0.0 found (SPI enabled)")
else:
    print("    ❌ /dev/spidev0.0 NOT found. Please enable SPI in raspi-config.")

print("\n" + "="*50)
print("Diagnostic Complete.")
