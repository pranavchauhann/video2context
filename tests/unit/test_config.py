import pytest

from video2context.config import Config, load_config
from video2context.errors import ConfigurationError


def test_precedence_and_false_override(tmp_path):
    user = tmp_path / "user.toml"
    project = tmp_path / "project.toml"
    user.write_text('max_frames = 10\nintent = "walkthrough"\noffline = true\n')
    project.write_text('[video2context]\nmax_frames = 20\ndetail = "compact"\n')
    cfg = load_config(
        {"max_frames": 40, "offline": False},
        user=user,
        project=project,
        environ={"V2C_MAX_FRAMES": "30", "V2C_DETAIL": "detailed"},
    )
    assert cfg.max_frames == 40
    assert cfg.intent == "walkthrough"
    assert cfg.detail == "detailed"
    assert cfg.offline is False
    assert (
        load_config(user=user, project=project, environ={"V2C_MAX_FRAMES": "30"}).max_frames == 30
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_frames": 0},
        {"sample_interval": float("nan")},
        {"intent": "anything"},
        {"offline": True, "vision_provider": "openai"},
        {"offline": True, "stt_provider": "whisper"},
        {"audio_chunk_seconds": 601},
        {"hash_threshold": 65},
    ],
)
def test_invalid_settings(kwargs):
    with pytest.raises(ConfigurationError):
        Config(**kwargs).validate()


def test_unknown_keys_and_invalid_boolean(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("max_frame = 10")
    with pytest.raises(ConfigurationError, match="Unknown"):
        load_config(user=path, project=tmp_path / "none", environ={})
    path.write_text('offline = "maybe"')
    with pytest.raises(ConfigurationError, match="boolean"):
        load_config(user=path, project=tmp_path / "none", environ={})


def test_secrets_are_not_configuration(tmp_path):
    cfg = load_config(
        user=tmp_path / "u",
        project=tmp_path / "p",
        environ={"V2C_STT_API_KEY": "secret", "OPENAI_API_KEY": "secret"},
    )
    assert "secret" not in repr(cfg)
