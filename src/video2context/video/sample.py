import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from video2context.config import Config
from video2context.domain.models import FrameRef, VideoMetadata
from video2context.errors import MediaError
from video2context.media.probe import run_media
from video2context.video.change import change_score
from video2context.video.dedupe import distance, perceptual_hash


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


class LocalFrameSelector:
    def __init__(self, config: Config):
        self.config = config
        self.candidate_count = 0

    def select(self, video: Path, metadata: VideoMetadata, output: Path) -> list[FrameRef]:
        cfg = self.config
        interval = max(cfg.sample_interval, metadata.duration_s / cfg.max_candidates)
        capture = cv2.VideoCapture(str(video))
        if not capture.isOpened():
            raise MediaError(
                "OpenCV could not open the video. Try converting it to MP4 with FFmpeg."
            )
        candidates: list[Candidate] = []
        previous = None
        last_kept = None
        try:
            for index in range(min(cfg.max_candidates, math.ceil(metadata.duration_s / interval))):
                timestamp = index * interval
                capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ok, image = capture.read()
                if not ok:
                    continue
                self.candidate_count += 1
                width = min(cfg.preview_width, image.shape[1])
                preview = cv2.resize(
                    image, (width, max(1, round(image.shape[0] * width / image.shape[1])))
                )
                score = (
                    1.0
                    if previous is None
                    else change_score(
                        previous, preview, cfg.pixel_threshold, cfg.cursor_area_threshold
                    )
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
        finally:
            capture.release()
        if not candidates:
            raise MediaError("No readable frames were found in the input video.")
        selected = budget_candidates(candidates, cfg.max_frames, metadata.duration_s)
        output.mkdir(parents=True, exist_ok=True)
        frames = []
        for index, candidate in enumerate(selected):
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
                continue
            frames.append(
                FrameRef(
                    f"f_{index + 1:06d}",
                    candidate.timestamp,
                    f"frames/{name}",
                    candidate.score,
                    0 if index == 0 else distance(candidate.hash, selected[index - 1].hash) / 64,
                    ["initial_state" if index == 0 else candidate.reason],
                )
            )
        if not frames:
            raise MediaError("FFmpeg could not extract selected frames.")
        return frames
