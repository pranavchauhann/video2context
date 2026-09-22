"""Private, versioned content cache. Never include credentials in keys or records."""

import hashlib
import json
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, root: Path):
        self.root = root
        self.hits = 0
        self._lock = threading.Lock()

    def get_or_compute(
        self, source: Path, identity: dict[str, Any], compute: Callable[[], Any]
    ) -> Any:
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode())
        with source.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        path = self.root / f"{digest.hexdigest()}.json"
        try:
            record = json.loads(path.read_text())
            if record.get("version") == 1:
                with self._lock:
                    self.hits += 1
                return record["result"]
        except (OSError, ValueError, KeyError, AttributeError):
            pass
        value = compute()
        # Created lazily so provider-free runs leave no empty cache directory behind.
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"version": 1, "result": value}, stream, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return value
