import pytest

from video2context.config import Config
from video2context.context.compress import EvidenceCompressor
from video2context.context.render_md import escape, timestamp
from video2context.domain.models import FrameRef, Timeline, TimelineEvent, TranscriptSegment
from video2context.errors import ProviderError
from video2context.timeline.fuse import fuse
from video2context.timeline.group import group_events
from video2context.transcript.service import normalize


def test_speech_on_static_screen_is_not_lost():
    frame = FrameRef("f_1", 0, "frames/000000000.jpg")
    speech = [
        TranscriptSegment(100, 110, "Move the button into the toolbar."),
        TranscriptSegment(300, 310, "Reduce the padding."),
    ]
    timeline = group_events(fuse([frame], speech, {}, {}, 400, Config()), Config())
    assert {s for e in timeline.events for s in e.speech} == {s.text for s in speech}
    assert all(e.frames for e in timeline.events)
    assert timeline.events[-1].start_s == 300


def test_speech_attaches_to_the_screen_visible_when_spoken():
    frames = [
        FrameRef("f_1", 0, "frames/000000000.jpg"),
        FrameRef("f_2", 20, "frames/000020000.jpg"),
    ]
    speech = [
        TranscriptSegment(0, 26, "Here is the dashboard and I talk about it for a while."),
        TranscriptSegment(25, 27, "Move the button into the toolbar."),
    ]
    timeline = fuse(frames, speech, {}, {}, 60, Config())
    request = next(e for e in timeline.events if e.intent)
    # The second screen was on display at 25s; the grown first event must not capture it.
    assert request.frames == ["frames/000020000.jpg"]
    assert request.start_s == 25


def test_new_requests_and_new_frames_do_not_merge():
    events = [
        TimelineEvent("a", 0, 1, frames=["a"]),
        TimelineEvent("b", 2, 3, frames=["a"], intent="Move button"),
        TimelineEvent("c", 4, 5, frames=["b"]),
    ]
    assert len(group_events(Timeline(events), Config()).events) == 3


def test_adjacent_identical_evidence_merges():
    events = [
        TimelineEvent("a", 0, 1, frames=["a"], speech=["Hello"]),
        TimelineEvent("b", 2, 3, frames=["a"], speech=["Hello", "World"]),
    ]
    result = group_events(Timeline(events), Config())
    assert len(result.events) == 1
    assert result.events[0].speech == ["Hello", "World"]
    assert result.events[0].end_s == 3


def test_normalization_clamps_and_orders():
    result = normalize(
        [
            TranscriptSegment(4, 20, " end "),
            TranscriptSegment(-1, 2, " first "),
            TranscriptSegment(3, 2, "bad"),
        ],
        10,
    )
    assert [(s.start_s, s.end_s, s.text) for s in result] == [(0, 2, "first"), (4, 10, "end")]
    with pytest.raises(ProviderError):
        normalize([TranscriptSegment(float("nan"), 1, "bad")], 10)


def test_compression_does_not_mutate_canonical_data():
    timeline = Timeline([TimelineEvent(str(i), i, i + 1) for i in range(5)])
    assert len(EvidenceCompressor("compact").compress(timeline, "general").timeline.events) == 2
    assert len(timeline.events) == 5


def test_timestamp_rounding_and_untrusted_markdown():
    assert timestamp(59.9999) == "00:01:00.000"
    assert timestamp(3661.123) == "01:01:01.123"
    assert "<script>" not in escape("<script>hi</script>")
    assert "\\[" in escape("[run](command)")
