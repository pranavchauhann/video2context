import math
from dataclasses import asdict
from pathlib import Path

from video2context.cache import Cache
from video2context.domain.models import TranscriptSegment
from video2context.domain.protocols import SpeechToTextProvider
from video2context.errors import ProviderError


def normalize(segments: list[TranscriptSegment], duration: float) -> list[TranscriptSegment]:
    normalized = []
    for segment in segments:
        if not math.isfinite(segment.start_s) or not math.isfinite(segment.end_s):
            raise ProviderError("Transcript timestamps must be finite.")
        start, end = max(0.0, segment.start_s), min(duration, segment.end_s)
        text = segment.text.strip()
        if end > start and text:
            confidence = segment.confidence
            if confidence is not None and (
                not math.isfinite(confidence) or not 0 <= confidence <= 1
            ):
                confidence = None
            normalized.append(TranscriptSegment(start, end, text, confidence))
    return sorted(normalized, key=lambda x: (x.start_s, x.end_s))


def transcribe(
    provider: SpeechToTextProvider, audio: Path, cache: Cache, offset: float, duration: float
) -> list[TranscriptSegment]:
    records = cache.get_or_compute(
        audio,
        {"stage": "stt", "provider": provider.name, "model": provider.model, "version": 1},
        lambda: [asdict(s) for s in normalize(provider.transcribe(audio), duration - offset)],
    )
    return normalize(
        [
            TranscriptSegment(
                float(s["start_s"]) + offset,
                float(s["end_s"]) + offset,
                str(s["text"]),
                s.get("confidence"),
            )
            for s in records
        ],
        duration,
    )
