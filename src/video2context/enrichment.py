import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from video2context.cache import Cache
from video2context.domain.models import FrameRef, OCRResult, VisionContext, VisionResult
from video2context.domain.protocols import OCRProvider, VisionProvider
from video2context.errors import ProviderAuthError, ProviderError

LABELS = {"ocr": "OCR", "vision": "Vision"}


def enrich_frames(
    frames: list[FrameRef],
    root: Path,
    cache: Cache,
    provider: OCRProvider | VisionProvider,
    stage: str,
    contexts: dict[str, VisionContext],
    workers: int,
    warn: Callable[[str], None],
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, OCRResult | VisionResult]:
    stop = threading.Event()
    failures: dict[str, list[str]] = {}
    lock = threading.Lock()

    def fail(frame: FrameRef, reason: str) -> None:
        with lock:
            failures.setdefault(reason, []).append(frame.id)

    def process(frame: FrameRef):
        if stop.is_set():
            fail(frame, "skipped after credentials were rejected")
            return frame.id, None
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
        except ProviderAuthError as exc:
            # One rejected key means every remaining request would fail the same way.
            stop.set()
            fail(frame, str(exc))
        except ProviderError as exc:
            fail(frame, str(exc))
        except Exception:
            # Provider exceptions may contain secrets and response bodies. Never echo them.
            fail(frame, "provider raised an unexpected error")
        return frame.id, None

    results = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for done, (key, value) in enumerate(pool.map(process, frames), 1):
            if progress:
                progress(stage, done, len(frames))
            if value is not None:
                results[key] = value
    label = LABELS.get(stage, stage)
    for reason, ids in failures.items():
        warn(
            f"{label} unavailable for {len(ids)} of {len(frames)} frames ({reason}); "
            f"screenshots retained. First affected: {', '.join(ids[:3])}."
        )
    return results
