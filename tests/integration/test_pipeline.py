import json
from importlib.resources import files

import jsonschema
import pytest
from click.testing import CliRunner

from video2context.cli.main import app
from video2context.config import Config
from video2context.domain.models import OCRResult, TranscriptSegment, VisionResult
from video2context.errors import MediaError
from video2context.pipeline import run


def validate_package(output):
    for name in (
        "context.md",
        "timeline.json",
        "metadata.json",
        "transcript.json",
        "agent-prompt.md",
    ):
        assert (output / name).is_file()
    timeline = json.loads((output / "timeline.json").read_text())
    schema = json.loads(files("video2context").joinpath("schemas/timeline.schema.json").read_text())
    jsonschema.validate(timeline, schema)
    assert timeline["events"]
    for event in timeline["events"]:
        assert event["end_s"] >= event["start_s"]
        for frame in event["frames"]:
            assert (output / frame).stat().st_size > 0
    return timeline


def test_silent_video_cli_json_and_collision(make_video, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = make_video(static=True)
    args = [str(source), "--offline", "--no-ocr", "--no-vision", "--json"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    records = [json.loads(line) for line in result.output.splitlines()]
    assert records[-1]["stage"] == "complete"
    assert records[-1]["stages"]["transcript"] == "no_audio"
    assert records[-1]["metrics"]["retained_frames"] == 1
    validate_package(tmp_path / ".video-context")
    assert CliRunner().invoke(app, args).exit_code == 1
    assert CliRunner().invoke(app, [*args, "--overwrite"]).exit_code == 0


class FakeSpeech:
    name = "fake-speech"
    model = "v1"

    def transcribe(self, audio):
        return [
            TranscriptSegment(0.1, 1.0, "Move the export button."),
            TranscriptSegment(2, 2.8, "Then click Save to reproduce the error."),
        ]


class FakeOCR:
    name = "fake-ocr"
    model = "v1"

    def extract(self, image):
        return OCRResult("Export | Save")


class FakeVision:
    name = "fake-vision"
    model = "v1"

    def describe(self, image, context):
        return VisionResult("Settings", "An Export button and a Save button.", ["Export", "Save"])


def test_audio_chunks_enrichment_and_cache(make_video, tmp_path):
    source = make_video(audio=True)
    output = tmp_path / "output"
    config = Config(
        output=str(output),
        max_frames=3,
        audio_chunk_seconds=3,
        offline=True,
        intent="bug-repro",
        keep_intermediates=True,
    )
    providers = {"stt": FakeSpeech(), "ocr": FakeOCR(), "vision": FakeVision()}
    result = run(source, config, providers=providers)
    assert result.metrics["retained_frames"] <= 3
    assert result.metrics["transcript_segments"] == 4
    assert result.metrics["vision_frames"] == result.metrics["retained_frames"]
    timeline = validate_package(output)
    assert any(e["intent"] for e in timeline["events"])
    transcript = json.loads((output / "transcript.json").read_text())
    assert transcript[-1]["start_s"] == 5
    assert len(list((output / "intermediates").glob("*.wav"))) == 2
    config.overwrite = True
    repeat = run(source, config, providers=providers)
    assert repeat.metrics["cache_hits"] >= 4
    assert json.loads((output / "timeline.json").read_text()) == timeline


def test_optional_failures_do_not_leak_or_destroy_output(make_video, tmp_path):
    class Failing:
        name = "failing"
        model = "v1"

        def transcribe(self, audio):
            raise RuntimeError("authorization=SECRET")

        def extract(self, image):
            raise RuntimeError("authorization=SECRET")

        def describe(self, image, context):
            raise RuntimeError("authorization=SECRET")

    source = make_video(audio=True)
    output = tmp_path / "partial"
    result = run(
        source,
        Config(output=str(output), max_frames=2),
        providers={"stt": Failing(), "ocr": Failing(), "vision": Failing()},
    )
    validate_package(output)
    assert result.stages["transcript"] == "unavailable"
    assert result.warnings
    assert "SECRET" not in (output / "metadata.json").read_text()
    assert not (output / "intermediates").exists()


def test_auto_does_not_upload_with_keys_present(make_video, tmp_path, monkeypatch):
    import httpx

    def forbidden(*args, **kwargs):
        pytest.fail("auto must never call a remote provider")

    monkeypatch.setattr(httpx, "post", forbidden)
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    source = make_video(audio=True)
    result = run(source, Config(output=str(tmp_path / "auto"), no_ocr=True))
    assert result.stages["vision"] == "disabled"
    assert result.stages["transcript"] == "disabled"


def test_corrupt_video_has_no_package(tmp_path):
    source = tmp_path / "bad.mp4"
    source.write_text("not a video")
    with pytest.raises(MediaError):
        run(source, Config(output=str(tmp_path / "output")))
    assert not (tmp_path / "output").exists()


def test_ten_minute_static_video_is_bounded(make_video, tmp_path):
    source = make_video("long", duration=600, static=True)
    result = run(
        source,
        Config(
            output=str(tmp_path / "long-output"),
            max_frames=4,
            max_candidates=120,
            no_ocr=True,
            no_vision=True,
            offline=True,
        ),
    )
    assert result.metrics["candidate_frames"] <= 120
    assert result.metrics["retained_frames"] == 1
    assert result.metrics["dedupe_ratio"] > 0.9
    validate_package(tmp_path / "long-output")
