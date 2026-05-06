import time
from pathlib import Path

from .base import SourceResult


def read_file_source(path):
    try:
        file_path = Path(path)
        content = file_path.read_text()
        fetched_at = file_path.stat().st_mtime
    except OSError as exc:
        return SourceResult(ok=False, detail=f"File source unavailable: {exc}", fetched_at=time.time())
    return SourceResult(ok=True, content=content, detail=f"Read {path}", fetched_at=fetched_at)

