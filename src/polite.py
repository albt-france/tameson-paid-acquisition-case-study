"""Polite HTTP helper used by every collector.

Rules applied to every request:
- robots.txt is checked before fetching (urllib.robotparser);
- at least 2 seconds between two requests to any host;
- a generic, non-personal User-Agent;
- every raw response is saved with the collection date so the snapshot is reproducible.
"""
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = "Mozilla/5.0 (compatible; case-study-research/1.0)"
MIN_DELAY_S = 2.5
_last_call = 0.0
_robots_cache = {}


def allowed(url: str) -> bool:
    """Return True if robots.txt of the host allows our User-Agent to fetch url."""
    parts = urlparse(url)
    root = f"{parts.scheme}://{parts.netloc}"
    if root not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(root + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])  # no robots.txt reachable -> default allow
        _robots_cache[root] = rp
    return _robots_cache[root].can_fetch(USER_AGENT, url)


def get(url: str, **kwargs) -> requests.Response | None:
    """GET a URL if robots.txt allows it, waiting MIN_DELAY_S between calls."""
    global _last_call
    if not allowed(url):
        print(f"[robots] disallowed, skipped: {url}")
        return None
    wait = MIN_DELAY_S - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    headers.update(kwargs.pop("headers", {}))
    try:
        return requests.get(url, headers=headers, timeout=30, **kwargs)
    except requests.RequestException as e:
        print(f"[error] {url}: {e}")
        return None
