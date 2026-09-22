import shutil
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from video2context import __version__
from video2context.cache import Cache
from video2context.config import Config
from video2context.context.compress import EvidenceCompressor
from video2context.context.render_md import render_markdown
from video2context.domain.models import RunMetadata, VisionContext
from video2context.enrichment import enrich_frames
from video2context.errors import ConfigurationError, MediaError, ProviderError
from video2context.export.package import atomic_package, export_package, validate_output, write_json
from video2context.media.audio import extract_chunks
from video2context.media.probe import FFprobe, require_binary
from video2context.models import resolve_local_model
from video2context.ocr.providers import TesseractProvider
from video2context.timeline.fuse import fuse
from video2context.timeline.group import group_events
from video2context.transcript.providers import LocalWhisperProvider, WhisperProvider
from video2context.transcript.service import transcribe
from video2context.video.sample import LocalFrameSelector
from video2context.vision.providers import OpenAIVisionProvider

Report = Callable[[str, dict], None]


def run(
    video: Path,
    config: Config,
    report: Report | None = None,
    *,
    providers: dict | None = None,
) -> RunMetadata:
    """Run in a private staging directory; publish only a complete, useful package."""
    config.validate()
    report = report or (lambda stage, data: None)
    video = video.expanduser().resolve()
    if not video.is_file():
        raise MediaError(
            f"Input is not a readable local file: {video}. Check the path and keep it quoted."
        )
    target = Path(config.output).expanduser().absolute()
    validate_output(target, config.overwrite)
    if target.resolve() in video.parents:
        raise ConfigurationError("The source video cannot be inside the output directory.")
    require_binary(config.ffmpeg)
    require_binary(config.ffprobe)
    started = time.monotonic()
    warnings: list[str] = []
    counts: dict[str, int] = {}
    lock = threading.Lock()
    stages: dict[str, str] = {}
    timings: dict[str, float] = {}

    def warn(message: str) -> None:
        # Identical messages are reported once and counted, not repeated per frame.
        with lock:
            counts[message] = counts.get(message, 0) + 1
            if counts[message] > 1:
                return
            warnings.append(message)
        report("warning", {"message": message})

    def progress(task: str, done: int, total: int) -> None:
        report("progress", {"task": task, "done": done, "total": total})

    def load_provider(stage: str, factory):
        try:
            return factory()
        except ProviderError as exc:
            warn(str(exc))
        except Exception:
            warn(f"{stage} provider could not initialize; continuing without it.")
        stages[stage] = "unavailable"
        return None

    report("probe", {})
    metadata = FFprobe(config.ffprobe).probe(video)
    injected = providers or {}
    stt = injected.get("stt")
    ocr_provider = injected.get("ocr")
    vision_provider = injected.get("vision")
    # auto never selects remote providers, even when API keys exist.
    if stt is None and metadata.has_audio:
        if config.stt_provider == "whisper":
            report("remote", {"message": "Audio chunks will be sent to OpenAI for transcription."})
            stt = load_provider("transcript", lambda: WhisperProvider(config))
        elif config.stt_provider == "local":
            stt = load_provider("transcript", lambda: LocalWhisperProvider(config))
        elif config.stt_provider == "auto":
            # auto is best-effort: a missing model is a hint, not a provider failure.
            if resolve_local_model(config.local_stt_model) is None:
                warn(
                    "Speech not transcribed: run `v2c setup-speech` once to enable local "
                    "transcription, or pass --stt-provider none to hide this note."
                )
            else:
                stt = load_provider("transcript", lambda: LocalWhisperProvider(config))
    if not config.no_ocr and config.ocr_provider != "none" and ocr_provider is None:
        ocr_provider = load_provider("ocr", lambda: TesseractProvider(config.ocr_language))
    if not config.no_vision and config.vision_provider == "openai" and vision_provider is None:
        report(
            "remote", {"message": "Selected screenshots and nearby speech will be sent to OpenAI."}
        )
        vision_provider = load_provider("vision", lambda: OpenAIVisionProvider(config))
    cache = Cache(target.parent / f"{target.name}.v2c-cache")
    with atomic_package(target, config.overwrite) as root:
        report("frames", {"max_frames": config.max_frames})
        start = time.monotonic()
        selector = LocalFrameSelector(config, progress)
        frames = selector.select(video, metadata, root / "frames")
        timings["frames"] = time.monotonic() - start
        stages["frames"] = "ready"
        transcript = []
        stages.setdefault("transcript", "no_audio" if not metadata.has_audio else "disabled")
        if stt and metadata.has_audio:
            report("transcript", {})
            start = time.monotonic()
            failures = 0
            try:
                for offset, audio in extract_chunks(
                    video,
                    metadata,
                    root / "intermediates",
                    config.ffmpeg,
                    config.audio_chunk_seconds,
                ):
                    try:
                        transcript.extend(
                            transcribe(stt, audio, cache, offset, metadata.duration_s)
                        )
                    except ProviderError as exc:
                        failures += 1
                        warn(f"Speech unavailable for audio chunk at {offset:.1f}s: {exc}")
                    except Exception:
                        failures += 1
                        warn(
                            f"Speech unavailable for audio chunk at {offset:.1f}s; "
                            "visual evidence retained."
                        )
                    finally:
                        if not config.keep_intermediates:
                            audio.unlink(missing_ok=True)
            except MediaError:
                failures += 1
                warn("Audio extraction failed; continuing with visual evidence.")
            stages["transcript"] = (
                ("partial" if transcript else "unavailable") if failures else "ready"
            )
            timings["transcript"] = time.monotonic() - start
        contexts = {
            frame.id: VisionContext(
                config.intent,
                " ".join(
                    s.text
                    for s in transcript
                    if s.start_s <= frame.timestamp_s + config.speech_window
                    and s.end_s >= frame.timestamp_s - config.speech_window
                ),
            )
            for frame in frames
        }
        enrichments = {}
        for stage, provider, disabled in (
            ("ocr", ocr_provider, config.no_ocr or config.ocr_provider == "none"),
            ("vision", vision_provider, config.no_vision or config.vision_provider == "none"),
        ):
            result = {}
            stages.setdefault(stage, "disabled")
            if provider and not disabled:
                selected = frames
                if stage == "vision":
                    selected = sorted(frames, key=lambda f: (-f.change_score, f.timestamp_s))[
                        : config.max_vision_requests
                    ]
                report(stage, {"requests_at_most": len(selected)})
                start = time.monotonic()
                result = enrich_frames(
                    selected,
                    root,
                    cache,
                    provider,
                    stage,
                    contexts,
                    config.workers,
                    warn,
                    progress,
                )
                stages[stage] = (
                    "ready"
                    if len(result) == len(selected)
                    else ("partial" if result else "unavailable")
                )
                if len(selected) < len(frames):
                    stages[stage] = "budget_limited"
                timings[stage] = time.monotonic() - start
            enrichments[stage] = result
        report("export", {})
        timeline = group_events(
            fuse(
                frames,
                transcript,
                enrichments["ocr"],
                enrichments["vision"],
                metadata.duration_s,
                config,
            ),
            config,
        )
        document = EvidenceCompressor(config.detail).compress(timeline, config.intent)
        retries = sum(
            getattr(getattr(p, "transport", None), "retries", 0) for p in (stt, vision_provider)
        )
        metrics = {
            "duration_s": metadata.duration_s,
            "candidate_frames": selector.candidate_count,
            "retained_frames": len(frames),
            "dedupe_ratio": 1 - len(frames) / max(1, selector.candidate_count),
            "transcript_segments": len(transcript),
            "ocr_frames": len(enrichments["ocr"]),
            "vision_frames": len(enrichments["vision"]),
            "events": len(timeline.events),
            "cache_hits": cache.hits,
            "provider_retries": retries,
            "elapsed_s": round(time.monotonic() - started, 3),
            "stage_timings_s": {k: round(v, 3) for k, v in timings.items()},
        }
        with lock:
            warnings[:] = sorted(
                w if counts.get(w, 1) == 1 else f"{w} (repeated {counts[w]} times)"
                for w in warnings
            )
        run_metadata = RunMetadata(
            __version__, metadata, asdict(config), metrics, stages, warnings, frames
        )
        markdown = render_markdown(
            document, metadata, config.intent, config.detail, len(frames), warnings
        )
        export_package(root, markdown, timeline, transcript, run_metadata, target)
        if not config.keep_intermediates:
            shutil.rmtree(root / "intermediates", ignore_errors=True)
        else:
            (root / "logs").mkdir()
            write_json(
                root / "logs" / "diagnostics.json", {"metrics": metrics, "warnings": warnings}
            )
    report("complete", {"output": str(target), "metrics": metrics, "stages": stages})
    return run_metadata
