from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from video2context.cache import Cache
from video2context.domain.models import FrameRef, OCRResult, VisionContext, VisionResult
from video2context.domain.protocols import OCRProvider, VisionProvider


def enrich_frames(
    frames: list[FrameRef],
    root: Path,
    cache: Cache,
    provider: OCRProvider | VisionProvider,
    stage: str,
    contexts: dict[str, VisionContext],
    workers: int,
    warn: Callable[[str], None],
) -> dict[str, OCRResult | VisionResult]:
    def process(frame: FrameRef):
        try:
            context = contexts.get(frame.id, VisionContext("general"))
            identity = {
                "stage": stage,
                "provider": provider.name,
                "model": provider.model,
                "version": 1,
            }
            if stage == "vision":
                identity["context"] = asdict(context)
            record = cache.get_or_compute(
                root / frame.path,
                identity,
                lambda: asdict(
                    provider.extract(root / frame.path)
                    if stage == "ocr"
                    else provider.describe(root / frame.path, context)
                ),
            )
            result = OCRResult(**record) if stage == "ocr" else VisionResult(**record)
            return frame.id, result
        except Exception:
            # Provider exceptions may contain secrets and response bodies. Never echo them.
            warn(f"{stage} unavailable for {frame.id}; retained the source frame.")
            return frame.id, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return {key: value for key, value in pool.map(process, frames) if value is not None}
