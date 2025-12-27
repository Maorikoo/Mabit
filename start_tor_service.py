import os
import subprocess
import time

# === SET THIS TO YOUR TOR BUNDLE FOLDER! ===
TOR_DIR = r"C:\TorService"  # Change to extracted Tor folder, ASCII-only path
TOR_EXE = os.path.join(TOR_DIR, "tor", "tor.exe")  # tor.exe is in C:\TorService\tor\tor.exe
TORRC = os.path.join(TOR_DIR, "data", "torrc")

def is_tor_running():
    # Check if any process called tor is running
    try:
        out = subprocess.check_output('tasklist', shell=True, encoding='utf-8')
        return 'tor.exe' in out or 'tor ' in out  # Check for both tor.exe and tor
    except Exception:
        return False

def start_tor():
    if is_tor_running():
        print("Tor is already running.")
        return
    
    # Check if tor executable exists
    if not os.path.exists(TOR_EXE):
        print(f"ERROR: Tor executable not found at {TOR_EXE}")
        print(f"Please check that Tor is extracted to {TOR_DIR}")
        return
    
    # Check if torrc exists
    if not os.path.exists(TORRC):
        print(f"ERROR: torrc file not found at {TORRC}")
        print(f"Please check that torrc is at {TORRC}")
        return
    
    print(f"Starting Tor from {TOR_EXE} ...")
    try:
        # Try with CREATE_NO_WINDOW first (hidden)
        subprocess.Popen([TOR_EXE, "-f", TORRC], creationflags=subprocess.CREATE_NO_WINDOW)
    except PermissionError:
        # If that fails, try without the flag (will show a window)
        print("Note: Starting Tor with visible window (admin may be needed)...")
        subprocess.Popen([TOR_EXE, "-f", TORRC])
    time.sleep(3)  # Allow time to boot

def wait_for_tor_ready(port=9050, max_attempts=30):
    import socket
    for i in range(max_attempts):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                print("Tor SOCKS proxy is ready.")
                return True
        except Exception:
            time.sleep(1)
    print("Timed out waiting for Tor to be ready.")
    return False

if __name__ == "__main__":
    start_tor()
    wait_for_tor_ready()

