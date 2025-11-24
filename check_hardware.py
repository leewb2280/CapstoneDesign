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

print("="*50)
print(" 🕵️  Raspberry Pi Hardware Diagnostic Tool")
print("="*50)

# 1. Check Python Libraries
print("\n[1] Checking Python Libraries...")
libs = ["spidev", "RPi.GPIO", "cv2", "numpy"]
for lib in libs:
    check_library(lib)

# 2. Check Camera Command
print("\n[2] Checking Camera System...")
# 2. Check Camera Command
print("\n[2] Checking Camera System...")
has_rpicam = check_command("rpicam-still")
has_libcamera = check_command("libcamera-still")
has_raspistill = check_command("raspistill")

# Check for camera listing tool
list_cmd = None
if check_command("rpicam-hello"):
    list_cmd = ["rpicam-hello", "--list-cameras"]
elif check_command("libcamera-hello"):
    list_cmd = ["libcamera-hello", "--list-cameras"]

if list_cmd:
    print("\n[2-1] Listing Available Cameras...")
    try:
        result = subprocess.run(list_cmd, capture_output=True, text=True)
        print(result.stdout)
        if "Available cameras" not in result.stdout and "seq" not in result.stdout:
             print("    ⚠️  Warning: Output does not look like a camera list. Check connection.")
    except Exception as e:
        print(f"    Error listing cameras: {e}")

target_cmd = None
if has_rpicam:
    target_cmd = "rpicam-still"
elif has_libcamera:
    target_cmd = "libcamera-still"
elif has_raspistill:
    target_cmd = "raspistill"

if not target_cmd:
    print("❌ No camera software found!")
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

# 3. Check SPI (for Moisture Sensor)
print("\n[4] Checking SPI Interface...")
if os.path.exists("/dev/spidev0.0"):
    print("    ✅ /dev/spidev0.0 found (SPI enabled)")
else:
    print("    ❌ /dev/spidev0.0 NOT found. Please enable SPI in raspi-config.")

print("\n" + "="*50)
print("Diagnostic Complete.")
