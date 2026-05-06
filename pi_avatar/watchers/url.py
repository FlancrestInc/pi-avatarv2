import time
from urllib import error, request

from .base import SourceResult


def read_url_source(url, timeout_seconds):
    try:
        with request.urlopen(url, timeout=timeout_seconds) as response:
            content = response.read().decode("utf-8")
    except (OSError, error.URLError) as exc:
        return SourceResult(ok=False, detail=f"URL source unavailable: {exc}", fetched_at=time.time())
    return SourceResult(ok=True, content=content, detail=f"Fetched {url}", fetched_at=time.time())

