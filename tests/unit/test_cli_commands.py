import json

from click.testing import CliRunner

from video2context.cli.main import app
from video2context.models import download_model, models_dir, resolve_local_model


def test_video_first_and_options_first_both_reach_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    first = runner.invoke(app, ["missing.mp4", "--max-frames", "5", "--json"])
    second = runner.invoke(app, ["--max-frames", "5", "--json", "missing.mp4"])
    third = runner.invoke(app, ["run", "missing.mp4", "--json"])
    for result in (first, second, third):
        assert result.exit_code == 1, result.output
        assert json.loads(result.output.splitlines()[-1])["stage"] == "error"
    assert runner.invoke(app, ["missing.mp4", "--no-such-flag"]).exit_code == 2


def test_group_help_lists_commands_and_run_help_lists_options():
    runner = CliRunner()
    top = runner.invoke(app, ["--help"])
    assert top.exit_code == 0
    for name in ("doctor", "setup-speech", "VIDEO"):
        assert name in top.output
    assert "--max-frames" in runner.invoke(app, ["run", "--help"]).output
    assert "--max-frames" in runner.invoke(app, ["some-video.mov", "--help"]).output


def test_doctor_reports_prerequisites(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = CliRunner().invoke(app, ["doctor"])
    assert "ffmpeg" in result.output
    assert "Tesseract" in result.output
    assert "Speech model" in result.output
    assert "secret" not in result.output


def test_doctor_fails_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setenv("V2C_FFMPEG", "does-not-exist-v2c")
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "MISSING" in result.output


def test_setup_speech_explains_missing_dependency(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_faster_whisper(name, *args, **kwargs):
        if name.startswith("faster_whisper"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_faster_whisper)
    result = CliRunner().invoke(app, ["setup-speech", "--model", "tiny"])
    assert result.exit_code == 1
    assert "pipx inject video2context" in result.output


def test_model_resolution_prefers_paths_then_names_then_default(tmp_path):
    root = models_dir()
    assert resolve_local_model("") is None
    assert resolve_local_model("base") is None
    (root / "base").mkdir(parents=True)
    assert resolve_local_model("base") == root / "base"
    assert resolve_local_model("") is None
    (root / "default").write_text("base\n")
    assert resolve_local_model("") == root / "base"
    explicit = tmp_path / "custom-model"
    explicit.mkdir()
    assert resolve_local_model(str(explicit)) == explicit


def test_download_records_default(monkeypatch):
    import sys
    import types

    calls = []
    fake = types.ModuleType("faster_whisper")
    fake.download_model = lambda name, output_dir=None: calls.append((name, output_dir))
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    path = download_model("tiny")
    assert calls == [("tiny", str(models_dir() / "tiny"))]
    assert path == models_dir() / "tiny"
    assert resolve_local_model("") == path
