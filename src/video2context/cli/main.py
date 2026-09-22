import json
from pathlib import Path

import click

from video2context import __version__
from video2context.config import load_config
from video2context.errors import Video2ContextError
from video2context.pipeline import run


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
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
    help="auto uses a configured local model; whisper enables audio uploads.",
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
@click.option("--verbose", is_flag=True, help="Show stage progress and diagnostics.")
@click.version_option(__version__, prog_name="Video2Context")
def app(video: Path, json_output: bool, verbose: bool, **overrides) -> None:
    """Convert a local VIDEO into timestamped evidence for coding agents."""

    def report(stage: str, data: dict) -> None:
        if json_output:
            click.echo(json.dumps({"stage": stage, **data}))
        elif stage in {"warning", "remote"}:
            click.echo(data["message"], err=True)
        elif verbose:
            click.echo(f"{stage}: {json.dumps(data)}", err=True)

    try:
        config = load_config(overrides)
        if not json_output:
            click.echo("Video2Context — selecting video evidence")
        result = run(video, config, report)
    except (Video2ContextError, OSError) as exc:
        message = (
            str(exc)
            if isinstance(exc, Video2ContextError)
            else ("Could not read or write project files. Check paths and permissions.")
        )
        if json_output:
            click.echo(json.dumps({"stage": "error", "message": message}))
        else:
            click.echo(f"Error: {message}", err=True)
        raise click.exceptions.Exit(1) from exc
    except KeyboardInterrupt:
        report("error", {"message": "Interrupted; no incomplete package was published."})
        raise click.exceptions.Exit(130) from None
    if not json_output:
        click.echo(
            f"\nRetained {result.metrics['retained_frames']} of "
            f"{result.metrics['candidate_frames']} sampled frames; "
            f"{result.metrics['events']} events.\n"
            f"Context ready: {Path(config.output) / 'context.md'}\n\n"
            "Ask your coding agent to read context.md and inspect the referenced frames."
        )
