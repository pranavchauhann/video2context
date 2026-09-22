import re
from bisect import bisect_right

from video2context.config import Config
from video2context.domain.models import (
    FrameRef,
    OCRResult,
    Timeline,
    TimelineEvent,
    TranscriptSegment,
    VisionResult,
)

REQUEST = re.compile(
    r"\b(please|should|need to|want|move|change|fix|remove|add|reduce|increase|align|replace|"
    r"make|keep|hide|show)\b",
    re.IGNORECASE,
)
BUG = re.compile(
    r"\b(error|fail\w*|broken|crash\w*|bug|click|open|then|reproduce)\b", re.IGNORECASE
)


def speech_relevance(text: str, intent: str) -> float:
    matcher = BUG if intent == "bug-repro" else REQUEST
    return 1.0 if matcher.search(text) else (0.4 if text.strip() else 0.0)


def fuse(
    frames: list[FrameRef],
    transcript: list[TranscriptSegment],
    ocr: dict[str, OCRResult],
    vision: dict[str, VisionResult],
    duration: float,
    config: Config,
) -> Timeline:
    """Keep every speech segment, even when a long static screen has only one frame."""
    events: list[TimelineEvent] = []
    for frame in frames:
        visual = vision.get(frame.id, VisionResult())
        text = ocr.get(frame.id, OCRResult()).text
        events.append(
            TimelineEvent(
                "",
                frame.timestamp_s,
                min(duration, frame.timestamp_s + config.sample_interval),
                visual.screen or "Screen recording",
                ocr=[text] if text else [],
                visual=visual.description,
                frames=[frame.path],
                importance=min(
                    1,
                    0.30 * frame.change_score
                    + 0.20 * bool(text)
                    + 0.15 * ("scene_change" in frame.selected_reason)
                    + 0.10,
                ),
            )
        )
    timestamps = [frame.timestamp_s for frame in frames]
    for segment in transcript:
        # Speech belongs to the screen visible when it started: the latest frame at or
        # before the segment, never an earlier frame whose event grew through prior speech.
        anchor = frames[max(0, bisect_right(timestamps, segment.start_s) - 1)] if frames else None
        anchor_frames = [anchor.path] if anchor else []
        overlap = [
            e
            for e in events
            if e.frames == anchor_frames
            and e.start_s <= segment.end_s
            and e.end_s >= segment.start_s
        ]
        event = min(overlap, key=lambda e: abs(e.start_s - segment.start_s)) if overlap else None
        if event is None:
            event = TimelineEvent("", segment.start_s, segment.end_s, frames=anchor_frames)
            if anchor:
                result = vision.get(anchor.id, VisionResult())
                event.screen = result.screen or "Screen recording"
            events.append(event)
        event.start_s = min(event.start_s, segment.start_s)
        event.end_s = max(event.end_s, segment.end_s)
        event.speech.append(segment.text)
        relevance = speech_relevance(segment.text, config.intent)
        event.importance = min(1.0, max(event.importance, 0.35) + 0.25 * relevance)
        if relevance == 1.0:
            # Exact speech is safer than a fabricated paraphrase or inferred engineering request.
            event.intent = " ".join(filter(None, [event.intent, segment.text]))
    events.sort(key=lambda e: (e.start_s, e.end_s))
    for i, event in enumerate(events, 1):
        event.id = f"evt_{i:04d}"
    return Timeline(events)
