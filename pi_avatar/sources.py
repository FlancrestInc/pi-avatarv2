import time
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


@dataclass(frozen=True)
class SourceResult:
    ok: bool
    content: str | None = None
    detail: str = ""
    fetched_at: float | None = None


class SourceReader:
    def __init__(self, config):
        self.config = config
        self.last_result = SourceResult(ok=True, content=None, detail="No source configured", fetched_at=time.time())

    def read(self):
        source = self.config.source
        if source.type == "none":
            self.last_result = SourceResult(ok=True, content=None, detail="No source configured", fetched_at=time.time())
            return self.last_result
        if source.type == "file":
            return self._read_file(source.path)
        return self._read_url(source.url, source.timeout_seconds)

    def _read_file(self, path):
        try:
            file_path = Path(path)
            content = file_path.read_text()
            fetched_at = file_path.stat().st_mtime
        except OSError as exc:
            self.last_result = SourceResult(ok=False, detail=f"File source unavailable: {exc}", fetched_at=time.time())
            return self.last_result
        self.last_result = SourceResult(ok=True, content=content, detail=f"Read {path}", fetched_at=fetched_at)
        return self.last_result

    def _read_url(self, url, timeout_seconds):
        try:
            with request.urlopen(url, timeout=timeout_seconds) as response:
                content = response.read().decode("utf-8")
        except (OSError, error.URLError) as exc:
            self.last_result = SourceResult(ok=False, detail=f"URL source unavailable: {exc}", fetched_at=time.time())
            return self.last_result
        self.last_result = SourceResult(ok=True, content=content, detail=f"Fetched {url}", fetched_at=time.time())
        return self.last_result

    def is_stale(self, now=None):
        stale_seconds = self.config.source.stale_seconds
        if stale_seconds is None or self.last_result.fetched_at is None:
            return False
        return (now or time.time()) - self.last_result.fetched_at > stale_seconds
