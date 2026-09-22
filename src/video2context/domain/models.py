from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoMetadata:
    path: str
    duration_s: float
    fps: float
    width: int
    height: int
    has_audio: bool
    video_codec: str = "unknown"
    audio_codec: str | None = None


@dataclass
class FrameRef:
    id: str
    timestamp_s: float
    path: str
    change_score: float = 0.0
    dedupe_score: float = 0.0
    selected_reason: list[str] = field(default_factory=list)


@dataclass
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str
    confidence: float | None = None


@dataclass
class OCRResult:
    text: str = ""
    confidence: float | None = None


@dataclass
class VisionResult:
    screen: str = ""
    description: str = ""
    components: list[str] = field(default_factory=list)


@dataclass
class VisionContext:
    intent: str
    speech: str = ""


@dataclass
class TimelineEvent:
    id: str
    start_s: float
    end_s: float
    screen: str = "Screen recording"
    speech: list[str] = field(default_factory=list)
    ocr: list[str] = field(default_factory=list)
    visual: str = ""
    intent: str = ""
    frames: list[str] = field(default_factory=list)
    importance: float = 0.0


@dataclass
class Timeline:
    events: list[TimelineEvent]
    schema_version: str = "1.0"


@dataclass
class ContextDocument:
    timeline: Timeline
    requested_changes: list[TimelineEvent]


@dataclass
class RunMetadata:
    tool_version: str
    video: VideoMetadata
    config: dict[str, Any]
    metrics: dict[str, Any]
    stages: dict[str, str]
    warnings: list[str]
    frames: list[FrameRef]
    schema_version: str = "1.0"
