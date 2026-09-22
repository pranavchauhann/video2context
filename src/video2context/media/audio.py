from collections.abc import Iterator
from pathlib import Path

from video2context.domain.models import VideoMetadata
from video2context.media.probe import run_media


def extract_chunks(
    video: Path, metadata: VideoMetadata, output: Path, executable: str, chunk_seconds: int
) -> Iterator[tuple[float, Path]]:
    """16 kHz mono PCM chunks stay below Whisper's upload limit; offsets remain absolute."""
    if not metadata.has_audio:
        return
    output.mkdir(parents=True, exist_ok=True)
    for start in range(0, int(metadata.duration_s) + 1, chunk_seconds):
        if start >= metadata.duration_s:
            break
        path = output / f"audio-{start:08d}.wav"
        run_media(
            [
                executable,
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-ss",
                str(start),
                "-i",
                str(video.resolve()),
                "-t",
                str(min(chunk_seconds, metadata.duration_s - start)),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(path),
            ],
            timeout=max(300, chunk_seconds * 2),
        )
        yield float(start), path
