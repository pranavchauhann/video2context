import json
from dataclasses import asdict

import httpx
from click.testing import CliRunner

from video2context.cache import Cache
from video2context.cli.main import app
from video2context.config import Config
from video2context.domain.models import TranscriptSegment, VisionContext
from video2context.providers import RemoteTransport
from video2context.transcript.providers import WhisperProvider
from video2context.transcript.service import transcribe
from video2context.vision.providers import OpenAIVisionProvider


def test_cli_help_version_and_invalid_input(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert "0.1.0" in runner.invoke(app, ["--version"]).output
    result = runner.invoke(app, ["missing.mp4", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["stage"] == "error"
    assert runner.invoke(app, ["missing.mp4", "--max-frames", "0"]).exit_code == 2


def test_offline_rejects_remote_before_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["missing.mp4", "--offline", "--vision-provider", "openai", "--json"]
    )
    assert result.exit_code == 1
    assert "offline" in json.loads(result.output)["message"]


def test_missing_ffmpeg_is_actionable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("V2C_FFMPEG", "does-not-exist-v2c")
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    result = CliRunner().invoke(app, [str(source), "--json"])
    assert result.exit_code == 1
    assert "Install FFmpeg" in json.loads(result.output)["message"]


def test_remote_retry_and_normalized_whisper(tmp_path, monkeypatch):
    monkeypatch.setenv("V2C_STT_API_KEY", "test-secret")
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"segments": [{"start": 0, "end": 1, "text": "Move it."}]})

    monkeypatch.setattr(httpx, "post", post)
    provider = WhisperProvider(Config(retry_delay=0))
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wave")
    result = provider.transcribe(audio)
    assert result == [TranscriptSegment(0, 1, "Move it.")]
    assert calls[0]["files"]["file"][1] == calls[1]["files"]["file"][1] == b"wave"
    assert provider.transport.retries == 1


def test_vision_contract_and_cache_offsets(tmp_path, monkeypatch):
    monkeypatch.setenv("V2C_VISION_API_KEY", "secret")
    provider = OpenAIVisionProvider(Config())
    monkeypatch.setattr(
        RemoteTransport,
        "post",
        lambda *a, **k: {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "screen": "Settings",
                                "description": "A settings panel.",
                                "components": ["Save"],
                            }
                        )
                    }
                }
            ],
        },
    )
    source = tmp_path / "image.jpg"
    source.write_bytes(b"image")
    assert asdict(provider.describe(source, VisionContext("general")))["screen"] == "Settings"

    class FakeSTT:
        name = "fake"
        model = "one"

        def transcribe(self, audio):
            return [TranscriptSegment(0, 2, "Speech")]

    cache = Cache(tmp_path / "cache")
    assert transcribe(FakeSTT(), source, cache, 10, 20)[0].start_s == 10
    assert transcribe(FakeSTT(), source, cache, 15, 20)[0].start_s == 15
    assert cache.hits == 1
