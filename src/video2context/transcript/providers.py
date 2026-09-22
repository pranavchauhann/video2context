from pathlib import Path

from video2context.config import Config
from video2context.domain.models import TranscriptSegment
from video2context.errors import ProviderError
from video2context.providers import RemoteTransport


class WhisperProvider:
    name = "whisper"

    def __init__(self, config: Config):
        self.model = config.stt_model
        self.transport = RemoteTransport(config, "V2C_STT_API_KEY")

    def transcribe(self, audio: Path) -> list[TranscriptSegment]:
        result = self.transport.post(
            "audio/transcriptions",
            data={"model": self.model, "response_format": "verbose_json"},
            files={"file": (audio.name, audio.read_bytes(), "audio/wav")},
        )
        try:
            return [
                TranscriptSegment(float(s["start"]), float(s["end"]), str(s["text"]))
                for s in result["segments"]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("STT response did not contain timestamped segments.") from exc


class LocalWhisperProvider:
    name = "local-whisper"

    def __init__(self, config: Config):
        path = Path(config.local_stt_model).expanduser()
        if not config.local_stt_model or not path.is_dir():
            raise ProviderError(
                "Set V2C_LOCAL_STT_MODEL to a downloaded faster-whisper model directory. "
                "Video2Context never downloads models implicitly."
            )
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ProviderError(
                'Install local speech support: pip install "video2context[local-stt]"'
            ) from exc
        self.model = str(path.resolve())
        self.engine = WhisperModel(
            self.model, device="cpu", compute_type="int8", local_files_only=True
        )

    def transcribe(self, audio: Path) -> list[TranscriptSegment]:
        segments, _ = self.engine.transcribe(str(audio), beam_size=5)
        return [TranscriptSegment(s.start, s.end, s.text) for s in segments]
