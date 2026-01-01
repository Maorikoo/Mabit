import random
import time
import threading
import logging
import requests
import os
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

# TOR defaults
TOR_SOCKS_PORT = int(os.environ.get("TOR_SOCKS_PORT", 9050))
TOR_PROXY = f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}"


# =========================
# Global pause gate (shared by all threads)
# =========================
_PAUSE_LOCK = threading.Lock()
_PAUSE_UNTIL = 0.0  # monotonic timestamp

# =========================
# Circuit rotation lock (only one thread rotates at a time)
# =========================
_CIRCUIT_ROTATION_LOCK = threading.Lock()
_CIRCUIT_ROTATION_IN_PROGRESS = False


def _maybe_pause():
    """
    If a global pause is active, sleep until it expires.
    All threads will respect this before making a request.
    """
    while True:
        with _PAUSE_LOCK:
            remaining = _PAUSE_UNTIL - time.monotonic()

        if remaining <= 0:
            return

        # Log only once per pause period to avoid spam
        if remaining > 0.5:  # Only log if more than 0.5 seconds remaining
            logger.debug(f"[PAUSE] Waiting {remaining:.1f}s before next request...")
        
        time.sleep(min(remaining, 1.0))


def trigger_global_pause(seconds: int):
    """
    Activate or extend a global pause window.
    Called when we detect 'temporarily blocked'.
    """
    global _PAUSE_UNTIL
    until = time.monotonic() + seconds

    with _PAUSE_LOCK:
        if until > _PAUSE_UNTIL:
            _PAUSE_UNTIL = until
            logger.info(f"[PAUSE] Global pause activated for {seconds} seconds - all threads will wait")


def get_pause_remaining_seconds() -> int:
    """How many seconds remain in the current global pause (0 if none)."""
    with _PAUSE_LOCK:
        remaining = _PAUSE_UNTIL - time.monotonic()
    return max(0, int(remaining))


def wait_for_pause_to_end():
    """Block until the global pause is finished."""
    initial_remaining = get_pause_remaining_seconds()
    if initial_remaining > 0:
        logger.info(f"[PAUSE] Waiting for global pause to end ({initial_remaining}s remaining)...")
    
    while True:
        remaining = get_pause_remaining_seconds()
        if remaining <= 0:
            if initial_remaining > 0:
                logger.info("[PAUSE] Global pause ended, resuming work")
            return
        time.sleep(min(remaining, 1))


def rotate_circuit_if_needed(log_callback=None):
    """
    Rotate Tor circuit if not already in progress.
    Only one thread will perform the rotation, others will return False immediately.
    Returns True if this thread performed the rotation, False if another thread is doing it.
    """
    global _CIRCUIT_ROTATION_IN_PROGRESS
    log_msg = log_callback if callable(log_callback) else logger.info
    
    # Try to acquire the lock - only one thread will succeed immediately
    acquired = _CIRCUIT_ROTATION_LOCK.acquire(blocking=False)
    
    if not acquired:
        # Another thread is already rotating - return False immediately
        # The calling thread will handle waiting 60 seconds
        return False
    
    # This thread will perform the rotation
    try:
        _CIRCUIT_ROTATION_IN_PROGRESS = True
        log_msg("[TOR] This thread will rotate the circuit (others will wait 60s)...")
        
        # Get password from settings
        import os
        from django.conf import settings
        tor_password = os.environ.get('TOR_CONTROL_PASSWORD') or getattr(settings, 'TOR_CONTROL_PASSWORD', None)
        
        if not tor_password:
            raise ValueError("TOR_CONTROL_PASSWORD not configured. Set it in settings.py or environment variable.")
        
        # Perform the rotation
        from .tor_control import TorController
        tor = TorController(password=tor_password)
        tor.new_identity(log_callback=log_callback)
        
        return True
    finally:
        _CIRCUIT_ROTATION_IN_PROGRESS = False
        _CIRCUIT_ROTATION_LOCK.release()


# =========================
# Scraper client
# =========================
class ScraperClient:
    """
    Resilient HTTP client:
    - Rotates User-Agent
    - Retries with exponential backoff
    - Thread-safe global pause on block detection
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    ]

    def __init__(self, timeout: int = 15, max_retries: int = 3, backoff_base: float = 0.7, use_tor: bool = True):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.use_tor = use_tor
        if self.use_tor:
            self.session.proxies = {
                "http": TOR_PROXY,
                "https": TOR_PROXY,
            }

    def _headers(self) -> dict:
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://mollygram.com/",
            "user-agent": random.choice(self.USER_AGENTS),
        }

    def get(self, url: str) -> requests.Response:
        last_exc = None
        # NOTE: All requests are routed through Tor if use_tor is True

        for attempt in range(1, self.max_retries + 1):
            # ⏸ respect global pause before every request
            _maybe_pause()

            try:
                resp = self.session.get(
                    url,
                    headers=self._headers(),
                    timeout=self.timeout,
                )

                # Retry on transient server errors
                if resp.status_code in (429, 500, 502, 503, 504):
                    self._sleep_backoff(attempt)
                    continue

                return resp

            except (requests.Timeout, requests.ConnectionError) as e:
                last_exc = e
                self._sleep_backoff(attempt)
                continue

        if last_exc:
            raise last_exc
        raise RuntimeError("Request failed after retries")

    def _sleep_backoff(self, attempt: int) -> None:
        delay = (self.backoff_base ** attempt) + random.uniform(0.0, 0.35)
        time.sleep(delay)
