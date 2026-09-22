import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import click

from video2context import __version__
from video2context.config import load_config
from video2context.errors import Video2ContextError
from video2context.models import KNOWN_MODELS, download_model, models_dir, resolve_local_model
from video2context.pipeline import run

ISSUES = "https://github.com/pranavchauhann/video2context/issues"
STAGE_LABELS = {
    "probe": "Reading video metadata…",
    "frames": "Selecting screenshots…",
    "transcript": "Transcribing speech…",
    "ocr": "Reading on-screen text (OCR)…",
    "vision": "Describing screenshots (vision)…",
    "export": "Writing context package…",
}


class DefaultGroup(click.Group):
    """`v2c VIDEO [OPTIONS]` runs the default command; named subcommands still work."""

    default = "run"

    def collect_usage_pieces(self, ctx):
        return ["VIDEO [OPTIONS]  |  COMMAND [ARGS]..."]

    def resolve_command(self, ctx, args):
        original = list(args)
        try:
            # Click parses the list in place while looking for --help, so hand it a copy.
            return super().resolve_command(ctx, list(args))
        except click.UsageError:
            # Not a subcommand name: every argument belongs to the default command.
            return self.default, self.commands[self.default], original


@click.group(
    cls=DefaultGroup,
    context_settings={"help_option_names": ["-h", "--help"], "ignore_unknown_options": True},
)
@click.version_option(__version__, prog_name="Video2Context")
def app() -> None:
    """Turn a screen recording into timestamped evidence for your coding agent.

    \b
      v2c recording.mov          Process a video (same as: v2c run recording.mov)
      v2c doctor                 Check FFmpeg, Tesseract and speech setup
      v2c setup-speech           Download a local speech model once (optional)
      v2c run --help             All processing options
    """


@app.command("run", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("video", type=click.Path(path_type=Path))
@click.option("--output", type=click.Path(), help="Output directory (default: .video-context).")
@click.option("--intent", type=click.Choice(["ui-feedback", "bug-repro", "walkthrough", "general"]))
@click.option("--detail", type=click.Choice(["compact", "balanced", "detailed"]))
@click.option(
    "--vision-provider",
    type=click.Choice(["auto", "openai", "none"]),
    help="auto stays local; openai explicitly enables screenshot uploads.",
)
@click.option(
    "--stt-provider",
    type=click.Choice(["auto", "whisper", "local", "none"]),
    help="auto uses a local model when one is set up; whisper enables audio uploads.",
)
@click.option("--ocr-provider", type=click.Choice(["auto", "local", "none"]))
@click.option("--max-frames", type=click.IntRange(min=1), help="Hard retained-frame limit.")
@click.option("--offline/--online", default=None, help="Reject all remote provider configurations.")
@click.option("--no-vision/--vision", default=None)
@click.option("--no-ocr/--ocr", default=None)
@click.option("--keep-intermediates/--discard-intermediates", default=None)
@click.option(
    "--overwrite", is_flag=True, default=None, help="Replace an existing v2c package safely."
)
@click.option("--json", "json_output", is_flag=True, help="Emit newline-delimited JSON status.")
@click.option("--verbose", is_flag=True, help="Show stage details and diagnostics.")
def run_command(video: Path, json_output: bool, verbose: bool, **overrides) -> None:
    """Convert a local VIDEO into timestamped evidence for coding agents."""
    interactive = sys.stderr.isatty() and not json_output
    progress_open = False

    def end_progress() -> None:
        nonlocal progress_open
        if progress_open:
            click.echo("", err=True)
            progress_open = False

    def report(stage: str, data: dict) -> None:
        nonlocal progress_open
        if json_output:
            click.echo(json.dumps({"stage": stage, **data}))
            return
        if stage == "progress":
            if interactive:
                click.echo(
                    f"\r  {data['task']}: {data['done']}/{data['total']}", nl=False, err=True
                )
                progress_open = data["done"] < data["total"]
                if not progress_open:
                    click.echo("", err=True)
            return
        end_progress()
        if stage == "warning":
            click.echo(f"Note: {data['message']}", err=True)
        elif stage == "remote":
            click.echo(data["message"], err=True)
        elif stage in STAGE_LABELS:
            click.echo(STAGE_LABELS[stage], err=True)
        if verbose and data:
            click.echo(f"  {stage}: {json.dumps(data)}", err=True)

    def fail(message: str, code: int = 1) -> None:
        end_progress()
        if json_output:
            click.echo(json.dumps({"stage": "error", "message": message}))
        else:
            click.echo(f"Error: {message}", err=True)
        raise click.exceptions.Exit(code)

    try:
        config = load_config(overrides)
        if not json_output:
            click.echo(f"Video2Context {__version__} — {video}", err=True)
        result = run(video, config, report)
    except Video2ContextError as exc:
        fail(str(exc))
    except OSError as exc:
        fail(f"Could not read or write project files ({exc}). Check paths and permissions.")
    except KeyboardInterrupt:
        fail("Interrupted; no incomplete package was published.", 130)
    except Exception as exc:  # A bug, not a user error: keep it short and point at the tracker.
        if verbose:
            traceback.print_exc()
        fail(
            f"Unexpected {type(exc).__name__}. Re-run with --verbose for details and report "
            f"it at {ISSUES}"
        )
    if json_output:
        return
    output = Path(config.output)
    metrics = result.metrics
    click.echo(
        f"\nDone in {metrics['elapsed_s']:.1f}s: kept {metrics['retained_frames']} of "
        f"{metrics['candidate_frames']} sampled frames, {metrics['events']} events"
        + (
            f", {metrics['transcript_segments']} speech segments"
            if metrics["transcript_segments"]
            else ""
        )
        + f".\nContext ready: {output / 'context.md'}\n",
        err=True,
    )
    click.echo(
        "Next, paste this into your coding agent and fill in the brackets:\n\n"
        f"  Read {output / 'context.md'} and {output / 'timeline.json'}, and inspect the\n"
        "  referenced screenshots. This is a screencast of [what you recorded].\n"
        "  [What you want done.] Cite the timestamp and screenshot for every finding.\n"
    )


def _version_line(executable: str) -> str:
    try:
        out = subprocess.run(
            [executable, "-version" if "ff" in executable else "--version"],
            capture_output=True,
            timeout=15,
            check=False,
        )
        text = (out.stdout or out.stderr).decode("utf-8", errors="replace").strip()
        return text.splitlines()[0][:70] if text else ""
    except (OSError, subprocess.SubprocessError):
        return ""


@app.command()
def doctor() -> None:
    """Check prerequisites and explain how to fix anything missing."""
    ok = click.style("OK ", fg="green")
    bad = click.style("MISSING", fg="red")
    opt = click.style("OFF", fg="yellow")
    required_missing = False
    rows: list[tuple[str, str, str]] = []
    rows.append(("Python", ok, f"{sys.version.split()[0]} (3.11+ required)"))
    try:
        config = load_config({})
        rows.append(("Configuration", ok, "valid"))
    except Video2ContextError as exc:
        config = None
        rows.append(("Configuration", bad, str(exc)))
    for name in ("ffmpeg", "ffprobe"):
        executable = getattr(config, name, name) if config else name
        path = shutil.which(executable)
        if path:
            rows.append((name, ok, _version_line(executable) or path))
        else:
            required_missing = True
            rows.append(
                (
                    name,
                    bad,
                    "required: brew install ffmpeg (macOS) or sudo apt install ffmpeg (Ubuntu)",
                )
            )
    if shutil.which("tesseract"):
        from video2context.ocr.providers import installed_languages

        languages = installed_languages()
        rows.append(("Tesseract OCR", ok, f"languages: {', '.join(languages) or 'unknown'}"))
    else:
        rows.append(
            (
                "Tesseract OCR",
                opt,
                "optional on-screen text: brew install tesseract / apt install tesseract-ocr",
            )
        )
    try:
        import faster_whisper  # noqa: F401

        rows.append(("faster-whisper", ok, "local speech support installed"))
        have_fw = True
    except ImportError:
        have_fw = False
        rows.append(
            (
                "faster-whisper",
                opt,
                "optional local speech: pipx inject video2context 'faster-whisper>=1.0,<2'",
            )
        )
    model = resolve_local_model(config.local_stt_model if config else "")
    if model:
        rows.append(("Speech model", ok, str(model)))
    else:
        hint = (
            "run `v2c setup-speech`"
            if have_fw
            else "install faster-whisper, then `v2c setup-speech`"
        )
        rows.append(("Speech model", opt, f"none downloaded ({models_dir()}); {hint}"))
    import os

    keys = [
        k for k in ("V2C_STT_API_KEY", "V2C_VISION_API_KEY", "OPENAI_API_KEY") if os.environ.get(k)
    ]
    rows.append(
        (
            "Remote API keys",
            ok if keys else opt,
            (
                ", ".join(keys)
                + " set (used only with --stt-provider whisper / --vision-provider openai)"
            )
            if keys
            else "none set (fine: processing is local by default)",
        )
    )
    width = max(len(r[0]) for r in rows)
    click.echo(f"Video2Context {__version__} doctor\n")
    for name, status, detail in rows:
        click.echo(f"  {name.ljust(width)}  {status}  {detail}")
    click.echo("")
    if required_missing:
        click.echo(
            "Install the missing required tools, reopen your terminal, and run `v2c doctor` again."
        )
        raise click.exceptions.Exit(1)
    click.echo('Ready. Process a recording with:  v2c "/path/to/recording.mov"')


@app.command("setup-speech")
@click.option(
    "--model",
    default="base",
    show_default=True,
    help="Model size: " + ", ".join(f"{k} ({v})" for k, v in KNOWN_MODELS.items()) + ".",
)
def setup_speech(model: str) -> None:
    """Download a local faster-whisper model once, so speech is transcribed on this machine.

    Nothing is downloaded unless you run this command. The model becomes the default for
    `--stt-provider auto` and `local`; override with V2C_LOCAL_STT_MODEL.
    """
    click.echo(
        f"Downloading speech model {model!r} (~{KNOWN_MODELS.get(model, 'size varies')}) "
        f"to {models_dir() / model} …"
    )
    try:
        path = download_model(model)
    except Video2ContextError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise click.exceptions.Exit(1) from exc
    click.echo(
        f"Speech model ready: {path}\n"
        "Recordings with audio will now be transcribed locally. Run `v2c doctor` to confirm."
    )
