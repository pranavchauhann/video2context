import math
import subprocess
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from video2context.config import Config
from video2context.domain.models import FrameRef, VideoMetadata
from video2context.errors import MediaError
from video2context.media.probe import run_media
from video2context.video.change import change_score
from video2context.video.dedupe import distance, perceptual_hash

Progress = Callable[[str, int, int], None]


@dataclass
class Candidate:
    timestamp: float
    score: float
    hash: int
    mean: tuple[float, ...]
    reason: str


def budget_candidates(
    candidates: list[Candidate], maximum: int, duration: float
) -> list[Candidate]:
    if len(candidates) <= maximum:
        return sorted(candidates, key=lambda x: x.timestamp)
    # Temporal bins guarantee coverage; remaining places take globally strong transitions.
    selected: list[Candidate] = []
    for bucket in range(maximum):
        items = [
            c
            for c in candidates
            if min(maximum - 1, int(c.timestamp / duration * maximum)) == bucket
        ]
        if items:
            selected.append(max(items, key=lambda c: (c.score, -c.timestamp)))
    seen = {c.timestamp for c in selected}
    remaining = sorted(
        (c for c in candidates if c.timestamp not in seen), key=lambda c: (-c.score, c.timestamp)
    )
    selected.extend(remaining[: maximum - len(selected)])
    return sorted(selected, key=lambda x: x.timestamp)


def preview_size(metadata: VideoMetadata, preview_width: int) -> tuple[int, int]:
    width = min(preview_width, metadata.width)
    height = max(2, round(metadata.height * width / metadata.width / 2) * 2)
    return width, height


def iter_previews(
    video: Path,
    metadata: VideoMetadata,
    executable: str,
    interval: float,
    size: tuple[int, int],
    limit: int,
) -> Iterator[tuple[float, np.ndarray]]:
    """One sequential decode pass, resampled by wall-clock time.

    Seeking per sample is slow on long-GOP media and lands on the wrong moment for
    variable-frame-rate screen recordings; the fps filter uses real timestamps instead.
    """
    width, height = size
    frame_bytes = width * height * 3
    args = [
        executable,
        "-nostdin",
        "-v",
        "error",
        "-noautorotate",
        "-i",
        str(video),
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"fps={1 / interval:.6f},scale={width}:{height}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-",
    ]
    try:
        process = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
    except OSError as exc:
        raise MediaError(f"Missing executable: {executable}. Install FFmpeg.") from exc
    assert process.stdout is not None
    try:
        for index in range(limit):
            data = process.stdout.read(frame_bytes)
            if len(data) < frame_bytes:
                break
            yield index * interval, np.frombuffer(data, np.uint8).reshape(height, width, 3).copy()
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait()


class LocalFrameSelector:
    def __init__(self, config: Config, progress: Progress | None = None):
        self.config = config
        self.candidate_count = 0
        self.progress = progress or (lambda task, done, total: None)

    def select(self, video: Path, metadata: VideoMetadata, output: Path) -> list[FrameRef]:
        cfg = self.config
        interval = max(cfg.sample_interval, metadata.duration_s / cfg.max_candidates)
        expected = max(1, min(cfg.max_candidates, math.ceil(metadata.duration_s / interval)))
        candidates: list[Candidate] = []
        previous = None
        last_kept = None
        previews = iter_previews(
            video,
            metadata,
            cfg.ffmpeg,
            interval,
            preview_size(metadata, cfg.preview_width),
            expected,
        )
        for timestamp, preview in previews:
            self.candidate_count += 1
            if self.candidate_count % 10 == 0 or self.candidate_count == expected:
                self.progress("sampling", self.candidate_count, expected)
            score = (
                1.0
                if previous is None
                else change_score(previous, preview, cfg.pixel_threshold, cfg.cursor_area_threshold)
            )
            # Compare with the last retained state too, preserving gradual transitions.
            cumulative = (
                score
                if last_kept is None
                else change_score(
                    last_kept, preview, cfg.pixel_threshold, cfg.cursor_area_threshold
                )
            )
            previous = preview
            if candidates and max(score, cumulative) < cfg.change_threshold:
                continue
            phash = perceptual_hash(preview)
            mean = tuple(float(v) for v in np.mean(preview, axis=(0, 1)))
            scene = score >= cfg.scene_threshold
            # Only adjacent-state dedupe: A -> B -> A is meaningful in a bug reproduction.
            if candidates and not scene:
                prior = candidates[-1]
                color_delta = max(abs(a - b) for a, b in zip(mean, prior.mean, strict=True))
                if distance(phash, prior.hash) <= cfg.hash_threshold and color_delta < 8:
                    continue
            candidates.append(
                Candidate(
                    timestamp,
                    max(score, cumulative),
                    phash,
                    mean,
                    "scene_change" if scene else "layout_change",
                )
            )
            last_kept = preview
        if not candidates:
            raise MediaError(
                "No readable frames were found in the input video. "
                "Try converting it to MP4 with FFmpeg."
            )
        selected = budget_candidates(candidates, cfg.max_frames, metadata.duration_s)
        output.mkdir(parents=True, exist_ok=True)

        def extract(item: tuple[int, Candidate]) -> FrameRef | None:
            index, candidate = item
            name = f"{round(candidate.timestamp * 1000):09d}.jpg"
            path = output / name
            run_media(
                [
                    cfg.ffmpeg,
                    "-nostdin",
                    "-v",
                    "error",
                    "-y",
                    "-ss",
                    str(candidate.timestamp),
                    "-i",
                    str(video.resolve()),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(path),
                ]
            )
            if not path.is_file() or not path.stat().st_size:
                return None
            return FrameRef(
                f"f_{index + 1:06d}",
                candidate.timestamp,
                f"frames/{name}",
                candidate.score,
                0 if index == 0 else distance(candidate.hash, selected[index - 1].hash) / 64,
                ["initial_state" if index == 0 else candidate.reason],
            )

        frames: list[FrameRef] = []
        with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as pool:
            for done, frame in enumerate(pool.map(extract, enumerate(selected)), 1):
                self.progress("extracting", done, len(selected))
                if frame is not None:
                    frames.append(frame)
        if not frames:
            raise MediaError("FFmpeg could not extract selected frames.")
        return frames
