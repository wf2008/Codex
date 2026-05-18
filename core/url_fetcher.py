"""Background URL fetcher from GitHub"""
import requests
import time
import threading
from config import GITHUB_RAW_URL, URL_POLL_INTERVAL

_current_url = ""
_last_fetch = 0
_lock = threading.Lock()


def fetch_tunnel_url():
    """Fetch the latest tunnel URL from GitHub"""
    global _current_url, _last_fetch
    try:
        resp = requests.get(GITHUB_RAW_URL, timeout=15)
        resp.raise_for_status()
        url = resp.text.strip()
        if url.startswith("http"):
            with _lock:
                _current_url = url
                _last_fetch = time.time()
            return url
    except Exception as e:
        print(f"[URL Fetcher] Error: {e}")
    return _current_url


def get_current_url():
    """Get the current tunnel URL"""
    with _lock:
        return _current_url


def start_url_updater():
    """Start background thread to poll URL every N seconds"""
    def updater():
        while True:
            fetch_tunnel_url()
            time.sleep(URL_POLL_INTERVAL)
    thread = threading.Thread(target=updater, daemon=True)
    thread.start()
    return thread
