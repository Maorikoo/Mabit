import subprocess
import sys
import time
import os

# ==== ENTER YOUR TOR CONTROL PASSWORD HERE ====
TOR_CONTROL_PASSWORD = "yourpassword"  # <-- Set to the password you chose when generating the hash
# =============================================

print("=== Tor Setup & Test Utility ===")

def print_status(msg):
    print(f"[Tor Setup] {msg}")

def check_tor_running(socks_port=9050, control_port=9051):
    import socket
    s = socket.socket()
    try:
        s.connect(("127.0.0.1", socks_port))
        s.close()
        print_status(f"Tor SOCKS proxy is running on port {socks_port}.")
    except Exception:
        print_status(f"Tor SOCKS proxy NOT detected on port {socks_port}. Start Tor browser or service.")
        return False
    s = socket.socket()
    try:
        s.connect(("127.0.0.1", control_port))
        s.close()
        print_status(f"Tor Control port is running on {control_port} (required for IP switching).")
    except Exception:
        print_status(f"Tor Control port NOT detected on {control_port}. Configure ControlPort in torrc if needed.")
        return False
    return True

def test_ip(msg):
    from instagram_scraper.scraper.tor_control import TorController
    tc = TorController(password=TOR_CONTROL_PASSWORD)
    print_status(msg)
    print_status(" Tor IP: " + tc.get_current_ip())

if __name__ == '__main__':
    print_status("Checking for Tor and required ports...")
    if not check_tor_running():
        print_status("\n[HELP] To install Tor:")
        print("  - On Windows: Download from https://www.torproject.org/download/ and run.")
        print("  - On Linux: `sudo apt install tor` then `sudo service tor start`")
        print("  - Ensure Tor Browser or Service is running WITH ControlPort enabled (see docs).")
        sys.exit(1)
    test_ip("Testing initial Tor IP (should be different from your real IP)...")
    print_status("Requesting new circuit (new Tor exit IP)...")
    from instagram_scraper.scraper.tor_control import TorController
    TorController(password=TOR_CONTROL_PASSWORD).new_identity()
    time.sleep(3)
    test_ip("Testing Tor IP after circuit change:")
    print_status("If both tests returned IPs, Tor + circuit change are working!\n")