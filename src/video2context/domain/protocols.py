from pathlib import Path
from typing import Protocol

from video2context.domain.models import (
    ContextDocument,
    FrameRef,
    OCRResult,
    Timeline,
    TranscriptSegment,
    VideoMetadata,
    VisionContext,
    VisionResult,
)


class MediaProbe(Protocol):
    def probe(self, video: Path) -> VideoMetadata: ...


class FrameSelector(Protocol):
    def select(self, video: Path, metadata: VideoMetadata, output: Path) -> list[FrameRef]: ...


class SpeechToTextProvider(Protocol):
    name: str
    model: str

    def transcribe(self, audio: Path) -> list[TranscriptSegment]: ...


class OCRProvider(Protocol):
    name: str
    model: str

    def extract(self, image: Path) -> OCRResult: ...


class VisionProvider(Protocol):
    name: str
    model: str

    def describe(self, image: Path, context: VisionContext) -> VisionResult: ...


class ContextCompressor(Protocol):
    def compress(self, timeline: Timeline, intent: str) -> ContextDocument: ...
