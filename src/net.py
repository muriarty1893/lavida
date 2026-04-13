"""Network helpers with host allow-listing and bounded response reads."""

import logging
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "img.youtube.com",
}

_USER_AGENT = "Mozilla/5.0"


def is_safe_youtube_url(url: str) -> bool:
    """Return True only if url is an http/https URL pointing to a known YouTube host."""
    try:
        p = urlparse(url)
    except ValueError:
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower()
    return host in _ALLOWED_HOSTS


def fetch_bounded(url: str, max_bytes: int, timeout: float = 5.0) -> bytes | None:
    """Fetch url, enforcing host allow-list and a hard cap on response size.

    Returns the raw bytes on success, or None if the URL is rejected,
    the request fails, or the response exceeds max_bytes.
    """
    if not is_safe_youtube_url(url):
        logger.warning("Rejected unsafe URL: %s", url)
        return None
    try:
        with requests.get(
            url,
            timeout=timeout,
            stream=True,
            allow_redirects=False,
            headers={"User-Agent": _USER_AGENT},
        ) as r:
            if r.status_code != 200:
                return None
            buf = bytearray()
            for chunk in r.iter_content(chunk_size=16 * 1024):
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    logger.warning("Response too large (>%d bytes) for %s", max_bytes, url)
                    return None
            return bytes(buf)
    except requests.RequestException as e:
        logger.warning("Request failed for %s: %s", url, e)
        return None
