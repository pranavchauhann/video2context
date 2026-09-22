from pathlib import Path

import numpy as np
import pytest

from video2context.errors import MediaError
from video2context.media.probe import parse_metadata
from video2context.video.change import change_score
from video2context.video.dedupe import distance, perceptual_hash
from video2context.video.sample import Candidate, budget_candidates


def test_probe_fractional_fps_and_no_audio():
    result = parse_metadata(
        {
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                }
            ],
            "format": {"duration": "2.5"},
        },
        Path("test.mp4"),
    )
    assert result.fps == pytest.approx(29.97002997)
    assert not result.has_audio


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"streams": []},
        {"streams": [{"codec_type": "audio"}]},
        {
            "streams": [{"codec_type": "video", "width": 1, "height": 1}],
            "format": {"duration": "nan"},
        },
    ],
)
def test_bad_probe(data):
    with pytest.raises(MediaError):
        parse_metadata(data, Path("bad.mp4"))


def test_cursor_suppression_and_modal_change():
    image = np.zeros((180, 320, 3), dtype=np.uint8)
    cursor = image.copy()
    cursor[50:55, 50:55] = 255
    assert change_score(image, cursor) == 0
    modal = image.copy()
    modal[30:150, 50:270] = 255
    assert change_score(image, modal) > 0.06
    assert distance(perceptual_hash(image), perceptual_hash(image.copy())) == 0
    assert distance(0, 2**64 - 1) == 64


def test_budget_covers_whole_video():
    candidates = [Candidate(float(i), 1 / (i + 1), i, (0, 0, 0), "scene") for i in range(100)]
    selected = budget_candidates(candidates, 4, 100)
    assert len(selected) == 4
    assert [int(c.timestamp / 25) for c in selected] == [0, 1, 2, 3]
