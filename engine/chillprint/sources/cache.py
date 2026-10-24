"""Disk cache for every remote response (BUILD.md rule 3).

Responses are stored gzipped under data/cache/<source>/<key>.gz. Reruns read
from disk. `NETWORK_CALLS` counts real requests so the pipeline can prove a
rerun makes zero calls. Set CHILLPRINT_OFFLINE=1 to make any network call fail.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import threading
from pathlib import Path
from typing import Callable

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import CACHE_DIR

NETWORK_CALLS = {"count": 0}
_lock = threading.Lock()
_session = requests.Session()
_session.headers["User-Agent"] = "ChillPrint/0.1 (UC Davis Reboot the Earth hackathon)"


class OfflineError(RuntimeError):
    pass


class RemoteError(RuntimeError):
    """Non-retryable remote failure (4xx other than 429)."""


def _safe(key: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._=-]+", "_", key)
    if len(s) > 120:
        s = s[:80] + "_" + hashlib.sha1(key.encode()).hexdigest()[:16]
    return s


def cache_path(source: str, key: str) -> Path:
    return CACHE_DIR / source / (_safe(key) + ".gz")


def has(source: str, key: str) -> bool:
    return cache_path(source, key).exists()


def read(source: str, key: str) -> bytes | None:
    p = cache_path(source, key)
    if p.exists():
        with gzip.open(p, "rb") as f:
            return f.read()
    return None


def write(source: str, key: str, data: bytes) -> None:
    p = cache_path(source, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wb", compresslevel=6) as f:
        f.write(data)
    os.replace(tmp, p)


def cached(source: str, key: str, fetch: Callable[[], bytes]) -> bytes:
    data = read(source, key)
    if data is not None:
        return data
    data = fetch()
    write(source, key, data)
    return data


def http_get_once(url: str, params: dict | None = None, headers: dict | None = None,
                  timeout: float = 90.0, allow_redirects: bool = True) -> bytes:
    """Single attempt, no retries. Used for heavy FNRIC calls so a failure costs one call, not five."""
    if os.environ.get("CHILLPRINT_OFFLINE") == "1":
        raise OfflineError(f"offline mode: refusing network call to {url}")
    with _lock:
        NETWORK_CALLS["count"] += 1
    r = _session.get(url, params=params, headers=headers, timeout=timeout,
                     allow_redirects=allow_redirects)
    if r.status_code >= 400:
        raise RemoteError(f"{r.status_code} for {r.url}: {r.text[:300]}")
    return r.content


@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, requests.HTTPError)),
    wait=wait_exponential(multiplier=1.5, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def http_get(url: str, params: dict | None = None, headers: dict | None = None,
             timeout: float = 90.0, allow_redirects: bool = True) -> bytes:
    if os.environ.get("CHILLPRINT_OFFLINE") == "1":
        raise OfflineError(f"offline mode: refusing network call to {url}")
    with _lock:
        NETWORK_CALLS["count"] += 1
    r = _session.get(url, params=params, headers=headers, timeout=timeout,
                     allow_redirects=allow_redirects)
    if r.status_code in (429, 500, 502, 503, 504):
        r.raise_for_status()  # retried
    if r.status_code >= 400:
        raise RemoteError(f"{r.status_code} for {r.url}: {r.text[:300]}")
    return r.content
