import socket
import time
import logging
from stem import Signal
from stem.control import Controller

logger = logging.getLogger(__name__)

class TorController:
    def __init__(self, control_port=9051, password=None):
        self.control_port = control_port
        self.password = password

    def new_identity(self, log_callback=None):
        """Request a new Tor exit node (new IP)."""
        log_msg = log_callback if callable(log_callback) else logger.info
        log_msg("[TOR] Requesting new circuit (rotating IP)...")
        
        try:
            with Controller.from_port(port=self.control_port) as controller:
                if self.password:
                    controller.authenticate(password=self.password)
                else:
                    # Try cookie authentication first, fall back to password if needed
                    try:
                        controller.authenticate()
                    except Exception:
                        # If cookie auth fails and we have a password, use it
                        if self.password:
                            controller.authenticate(password=self.password)
                        else:
                            raise ValueError("Tor control requires password authentication but no password provided")
                
                log_msg("[TOR] Authenticated with Tor control port, sending NEWNYM signal...")
                controller.signal(Signal.NEWNYM)
                # Wait for Tor to establish new circuit
                log_msg("[TOR] Waiting 3 seconds for new circuit to establish...")
                time.sleep(3)
                log_msg("[TOR] New circuit established, IP rotation complete")
        except Exception as e:
            # Re-raise with more context
            error_msg = f"Failed to rotate Tor IP: {e}"
            log_msg(f"[TOR] ERROR: {error_msg}")
            raise RuntimeError(error_msg) from e

    def get_current_ip(self, socks_port=9050):
        """Test the current Tor IP by making a request over Tor SOCKS5."""
        import requests
        proxies = {
            "http": f"socks5h://127.0.0.1:{socks_port}",
            "https": f"socks5h://127.0.0.1:{socks_port}"
        }
        try:
            response = requests.get("https://api.ipify.org?format=text", proxies=proxies, timeout=10)
            return response.text.strip()
        except Exception as e:
            return f"Error: {e}"

