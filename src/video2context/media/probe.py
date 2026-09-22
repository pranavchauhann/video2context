import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from video2context.domain.models import VideoMetadata
from video2context.errors import MediaError


def require_binary(name: str) -> None:
    if not shutil.which(name):
        raise MediaError(
            f"Missing {name}. Install FFmpeg (macOS: brew install ffmpeg; Ubuntu: sudo apt "
            "install ffmpeg; Windows: winget install Gyan.FFmpeg) and ensure ffmpeg and "
            "ffprobe are on PATH."
        )


def run_media(args: list[str], timeout: float = 300) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(args, capture_output=True, check=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise MediaError(f"Missing executable: {args[0]}. Install FFmpeg.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Media processing timed out. Check the source file.") from exc
    except subprocess.CalledProcessError as exc:
        raise MediaError("Media processing failed. Verify the input is a readable video.") from exc


def parse_metadata(data: dict[str, Any], path: Path) -> VideoMetadata:
    try:
        streams = data["streams"]
        video = next(
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        )
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = float(data.get("format", {}).get("duration") or video.get("duration", 0))
        rate = video.get("avg_frame_rate", "0/0")
        try:
            fps = float(Fraction(rate))
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        width, height = int(video["width"]), int(video["height"])
        if not math.isfinite(duration) or duration <= 0 or min(width, height) <= 0:
            raise ValueError("Invalid dimensions/duration")
        return VideoMetadata(
            str(path.resolve()),
            duration,
            fps,
            width,
            height,
            audio is not None,
            video.get("codec_name", "unknown"),
            audio.get("codec_name") if audio else None,
        )
    except (KeyError, ValueError, TypeError, StopIteration) as exc:
        raise MediaError("No usable video stream or duration in this file.") from exc


class FFprobe:
    def __init__(self, executable: str = "ffprobe", runner=run_media):
        self.executable = executable
        self.runner = runner

    def probe(self, video: Path) -> VideoMetadata:
        result = self.runner(
            [
                self.executable,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                "-i",
                str(video.resolve()),
            ]
        )
        try:
            return parse_metadata(json.loads(result.stdout), video)
        except json.JSONDecodeError as exc:
            raise MediaError("ffprobe returned invalid metadata.") from exc
