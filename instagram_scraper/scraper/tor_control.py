import socket
import time
from stem import Signal
from stem.control import Controller

class TorController:
    def __init__(self, control_port=9051, password=None):
        self.control_port = control_port
        self.password = password

    def new_identity(self):
        """Request a new Tor exit node (new IP)."""
        with Controller.from_port(port=self.control_port) as controller:
            if self.password:
                controller.authenticate(password=self.password)
            else:
                controller.authenticate()
            controller.signal(Signal.NEWNYM)
            # Wait for Tor to establish new circuit
            time.sleep(3)

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

