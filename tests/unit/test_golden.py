import json
from dataclasses import asdict
from pathlib import Path

from video2context.config import Config
from video2context.context.compress import EvidenceCompressor
from video2context.context.render_md import render_markdown
from video2context.domain.models import FrameRef, OCRResult, TranscriptSegment, VideoMetadata
from video2context.timeline.fuse import fuse
from video2context.timeline.group import group_events


def test_feedback_golden():
    config = Config(intent="ui-feedback")
    video = VideoMetadata("/source/feedback.mp4", 10, 30, 1920, 1080, True)
    frame = FrameRef("f_000001", 2, "frames/000002000.jpg", 0.8)
    speech = [TranscriptSegment(2, 4, "Move Export into the toolbar.")]
    timeline = group_events(
        fuse([frame], speech, {frame.id: OCRResult("Analytics | Export")}, {}, 10, config), config
    )
    document = EvidenceCompressor().compress(timeline, config.intent)
    markdown = render_markdown(document, video, config.intent, config.detail, 1, [])
    fixtures = Path(__file__).parents[1] / "fixtures"
    assert markdown == (fixtures / "feedback.context.md").read_text(encoding="utf-8")
    assert asdict(timeline) == json.loads(
        (fixtures / "feedback.timeline.json").read_text(encoding="utf-8")
    )
