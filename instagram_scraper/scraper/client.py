import random
import time
import threading
import requests

# =========================
# Global pause gate (shared by all threads)
# =========================
_PAUSE_LOCK = threading.Lock()
_PAUSE_UNTIL = 0.0  # monotonic timestamp


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


def get_pause_remaining_seconds() -> int:
    """How many seconds remain in the current global pause (0 if none)."""
    with _PAUSE_LOCK:
        remaining = _PAUSE_UNTIL - time.monotonic()
    return max(0, int(remaining))


def wait_for_pause_to_end():
    """Block until the global pause is finished."""
    while True:
        remaining = get_pause_remaining_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1))


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

    def __init__(self, timeout: int = 15, max_retries: int = 3, backoff_base: float = 0.7):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def _headers(self) -> dict:
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "referer": "https://mollygram.com/",
            "user-agent": random.choice(self.USER_AGENTS),
        }

    def get(self, url: str) -> requests.Response:
        last_exc = None

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
