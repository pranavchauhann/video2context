"""Shared bounded remote transport, without leaking request bodies or credentials."""

import os
import threading
import time

import httpx

from video2context.config import Config
from video2context.errors import ProviderError


class RemoteTransport:
    def __init__(self, config: Config, key_variable: str):
        self.config = config
        self.key = os.environ.get(key_variable) or os.environ.get("OPENAI_API_KEY")
        if not self.key:
            raise ProviderError(f"Set {key_variable} to enable the selected remote provider.")
        self.retries = 0
        self._lock = threading.Lock()
        self._next_request = 0.0

    def post(self, endpoint: str, *, limited: bool = False, **kwargs) -> dict:
        for attempt in range(self.config.retries + 1):
            if limited:
                with self._lock:
                    now = time.monotonic()
                    delay = max(0, self._next_request - now)
                    self._next_request = max(now, self._next_request) + (
                        60 / self.config.vision_requests_per_minute
                    )
                time.sleep(delay)
            try:
                response = httpx.post(
                    f"https://api.openai.com/v1/{endpoint}",
                    headers={"Authorization": f"Bearer {self.key}"},
                    timeout=self.config.request_timeout,
                    **kwargs,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.config.retries:
                        self.retries += 1
                        time.sleep(self.config.retry_delay * 2**attempt)
                        continue
                if response.is_error:
                    raise ProviderError(f"Remote provider returned HTTP {response.status_code}.")
                return response.json()
            except (httpx.TransportError, ValueError) as exc:
                if attempt >= self.config.retries:
                    raise ProviderError(
                        "Remote provider unavailable or returned invalid JSON."
                    ) from exc
                self.retries += 1
                time.sleep(self.config.retry_delay * 2**attempt)
        raise ProviderError("Remote provider retry budget exhausted.")
