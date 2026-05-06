import time
from dataclasses import dataclass


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
        elif source.type == "file":
            from .file import read_file_source

            self.last_result = read_file_source(source.path)
        elif source.type == "url":
            from .url import read_url_source

            self.last_result = read_url_source(source.url, source.timeout_seconds)
        else:
            self.last_result = SourceResult(ok=False, detail=f"Unsupported source type: {source.type}", fetched_at=time.time())
        return self.last_result

    def is_stale(self, now=None):
        stale_seconds = self.config.source.stale_seconds
        if stale_seconds is None or self.last_result.fetched_at is None:
            return False
        return (now or time.time()) - self.last_result.fetched_at > stale_seconds

