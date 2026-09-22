"""Strict, secret-free configuration: flags > environment > project > user > defaults."""

import math
import os
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from video2context.domain.enums import Detail, Intent
from video2context.errors import ConfigurationError


@dataclass
class Config:
    output: str = ".video-context"
    intent: str = "general"
    detail: str = "balanced"
    vision_provider: str = "auto"
    stt_provider: str = "auto"
    ocr_provider: str = "auto"
    max_frames: int = 36
    offline: bool = False
    no_vision: bool = False
    no_ocr: bool = False
    keep_intermediates: bool = False
    overwrite: bool = False
    sample_interval: float = 1.0
    preview_width: int = 320
    max_candidates: int = 7200
    change_threshold: float = 0.06
    scene_threshold: float = 0.30
    hash_threshold: int = 6
    pixel_threshold: int = 24
    cursor_area_threshold: float = 0.003
    group_gap: float = 12.0
    max_event_duration: float = 30.0
    speech_window: float = 8.0
    workers: int = 2
    retries: int = 2
    retry_delay: float = 1.0
    max_vision_requests: int = 36
    vision_requests_per_minute: int = 30
    vision_model: str = "gpt-4o-mini"
    stt_model: str = "whisper-1"
    local_stt_model: str = ""
    ocr_language: str = "eng"
    audio_chunk_seconds: int = 600
    request_timeout: float = 90.0
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"

    def validate(self) -> "Config":
        choices = {
            "intent": set(Intent),
            "detail": set(Detail),
            "vision_provider": {"auto", "openai", "none"},
            "stt_provider": {"auto", "whisper", "local", "none"},
            "ocr_provider": {"auto", "local", "none"},
        }
        for key, values in choices.items():
            if getattr(self, key) not in values:
                raise ConfigurationError(f"Unsupported {key}: {getattr(self, key)!r}.")
        positive = (
            "max_frames",
            "sample_interval",
            "preview_width",
            "max_candidates",
            "workers",
            "vision_requests_per_minute",
            "audio_chunk_seconds",
            "request_timeout",
            "max_event_duration",
            "group_gap",
            "speech_window",
        )
        for key in positive:
            if not math.isfinite(getattr(self, key)) or getattr(self, key) <= 0:
                raise ConfigurationError(f"{key} must be positive and finite.")
        for key in ("change_threshold", "scene_threshold", "cursor_area_threshold"):
            if not 0 <= getattr(self, key) <= 1:
                raise ConfigurationError(f"{key} must be between 0 and 1.")
        if not 0 <= self.hash_threshold <= 64 or not 0 <= self.pixel_threshold <= 255:
            raise ConfigurationError("Invalid hash_threshold or pixel_threshold.")
        if (
            self.retries < 0
            or self.max_vision_requests < 0
            or not math.isfinite(self.retry_delay)
            or self.retry_delay < 0
        ):
            raise ConfigurationError("Retry and request budgets cannot be negative.")
        if self.audio_chunk_seconds > 600:
            raise ConfigurationError("audio_chunk_seconds cannot exceed 600 (upload size limit).")
        if self.offline and (self.vision_provider == "openai" or self.stt_provider == "whisper"):
            raise ConfigurationError("--offline rejects remote providers; select auto/local/none.")
        return self


def load_config(
    overrides: dict[str, Any] | None = None,
    *,
    project: Path | None = None,
    user: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Config:
    env = os.environ if environ is None else environ
    user = user or Path(env.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / (
        "video2context/config.toml"
    )
    project = project or Path.cwd() / ".video2context.toml"
    defaults = asdict(Config())
    merged = dict(defaults)
    try:
        for path in (user, project):
            if path.is_file():
                data = tomllib.loads(path.read_text())
                data = data.get("video2context", data)
                unknown = set(data) - set(defaults)
                if unknown:
                    raise ConfigurationError(f"Unknown configuration keys: {', '.join(unknown)}")
                merged.update(data)
        for item in fields(Config):
            key = f"V2C_{item.name.upper()}"
            if key in env:
                merged[item.name] = env[key]
        merged.update({k: v for k, v in (overrides or {}).items() if v is not None})
        for key, value in merged.items():
            kind = type(defaults[key])
            if kind is bool:
                if str(value).lower() not in {"true", "false", "1", "0", "yes", "no"}:
                    raise ValueError(f"{key} expects a boolean")
                merged[key] = str(value).lower() in {"true", "1", "yes"}
            else:
                if kind is int and (isinstance(value, bool) or isinstance(value, float)):
                    raise ValueError(f"{key} expects an integer")
                merged[key] = kind(value)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ConfigurationError(f"Invalid configuration: {exc}") from exc
    return Config(**merged).validate()
