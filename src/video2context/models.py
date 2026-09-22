"""Explicit local speech-model management. Nothing here runs implicitly."""

import os
from pathlib import Path

from video2context.errors import ProviderError

# Sizes are approximate download sizes for the CTranslate2 int8/float16 weights.
KNOWN_MODELS = {
    "tiny": "75 MB",
    "base": "145 MB",
    "small": "480 MB",
    "medium": "1.5 GB",
    "large-v3": "3.1 GB",
}
DEFAULT_FILE = "default"


def models_dir(environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    base = Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "video2context" / "models"


def resolve_local_model(value: str) -> Path | None:
    """Accept a model directory, a downloaded model name, or "" for the setup-speech default."""
    root = models_dir()
    if value:
        path = Path(value).expanduser()
        if path.is_dir():
            return path
        candidate = root / value
        return candidate if candidate.is_dir() else None
    marker = root / DEFAULT_FILE
    if marker.is_file():
        name = marker.read_text(encoding="utf-8").strip()
        if name and (root / name).is_dir():
            return root / name
    return None


def download_model(name: str) -> Path:
    """Download a faster-whisper model once, on request, and make it the default."""
    try:
        from faster_whisper import download_model as fetch
    except ImportError as exc:
        raise ProviderError(
            "Local speech support is not installed. Run: "
            "pipx inject video2context 'faster-whisper>=1.0,<2' "
            "(or pip install 'video2context[local-stt]'), then retry."
        ) from exc
    root = models_dir()
    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    try:
        fetch(name, output_dir=str(target))
    except ValueError as exc:
        raise ProviderError(f"Unknown speech model {name!r}: {exc}") from exc
    except Exception as exc:
        raise ProviderError(
            f"Could not download speech model {name!r} ({type(exc).__name__}). "
            "Check your internet connection and retry."
        ) from exc
    (root / DEFAULT_FILE).write_text(f"{name}\n", encoding="utf-8")
    return target
