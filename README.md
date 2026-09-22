# Video2Context

Turn screen recordings, bug reproductions, and UI feedback into compact, timestamped
evidence that Codex, Claude Code, Cursor, or another coding agent can read locally.
Video2Context generates context; it does **not** modify your application or run an agent.

## Quick start

Requirements: Python 3.11+ and **FFmpeg + ffprobe** on PATH.

```sh
# macOS
brew install ffmpeg
# Ubuntu/Debian: sudo apt install ffmpeg

# From this source checkout (the package is not published to PyPI yet)
pipx install .

# From YOUR application directory, including an IntelliJ/VS Code terminal
v2c ~/Downloads/feedback.mp4 --intent ui-feedback
```

After a release is published, installation will be `pipx install video2context`.
There is no need for end users to clone the source after publication.

Your coding agent can then read `.video-context/agent-prompt.md`, or you can ask:

> Read .video-context/context.md and inspect its referenced frames. Implement the
> changes supported by this evidence and my request. Ask about ambiguous intent.

## Output

```text
.video-context/
  context.md         # readable evidence and speech-derived requests
  timeline.json      # complete timestamped events, schema version 1.0
  transcript.json    # normalized speech segments (empty without STT)
  metadata.json      # source, frame timestamps, settings, metrics, stage status
  agent-prompt.md    # handoff prompt
  frames/            # selected full-resolution JPEGs
```

The default run stays local: visual sampling and deduplication always run; local
Tesseract OCR runs when installed. Speech needs a configured local model or an explicit
remote provider. `auto` never uploads data, even when API keys are present. Without
speech or vision, the package contains screenshots and OCR evidence, not invented
descriptions or requested changes.

```sh
v2c feedback.mp4 --offline --no-vision --no-ocr
v2c feedback.mp4 --intent bug-repro --detail detailed --max-frames 60
v2c feedback.mp4 --output evidence --overwrite --json
v2c --help
```

`--overwrite` only replaces a marked Video2Context package. Other existing directories
are protected. Outputs are staged privately and published after successful export.

## Speech, OCR and vision

**Local OCR:** install Tesseract (`brew install tesseract` or
`sudo apt install tesseract-ocr`). No Python OCR extra is needed.

**Local speech:** install `pipx install '.[local-stt]'` from this checkout, obtain a
faster-whisper/CTranslate2 model separately, and set `V2C_LOCAL_STT_MODEL` to its local
directory. No model downloads happen implicitly, including in offline mode.

```sh
export V2C_LOCAL_STT_MODEL=/absolute/path/to/faster-whisper-model
v2c feedback.mp4 --offline --stt-provider local
```

**Remote speech and vision (explicit opt-in):**

```sh
export V2C_STT_API_KEY='your-key'
export V2C_VISION_API_KEY='your-key'
v2c feedback.mp4 --stt-provider whisper --vision-provider openai
```

`OPENAI_API_KEY` is a fallback for both. Speech sends 16 kHz mono audio in chunks of
at most ten minutes. Vision sends only retained screenshots and nearby transcript text.
The original video is never uploaded. Vision calls have per-run and per-minute limits;
transient HTTP/network failures use bounded retries. Optional provider failures yield a
partial package with explicit warnings. See [providers](docs/providers.md).

## Configuration

Precedence: CLI > `V2C_*` environment variables > `.video2context.toml` in the current
directory > `$XDG_CONFIG_HOME/video2context/config.toml` (default `~/.config`) > defaults.
Unknown settings and invalid values fail before processing. API keys are environment-only.

```toml
# .video2context.toml
[video2context]
intent = "ui-feedback"
detail = "balanced"
max_frames = 36
sample_interval = 1.0
max_candidates = 7200
change_threshold = 0.06
hash_threshold = 6
workers = 2
max_vision_requests = 36
vision_requests_per_minute = 30
vision_model = "gpt-4o-mini"
```

Every setting in [config.py](src/video2context/config.py) also has an uppercase `V2C_`
environment equivalent. Boolean flags have inverse forms so CLI overrides can disable
project defaults. `--json` emits newline-delimited status records; progress and optional
stage errors appear as records, ending in `complete` or `error`. CLI usage errors use
Click's standard stderr/exit 2 behavior. Processing errors exit 1; interruption exits 130.

`--detail compact` filters low-relevance visual-only events in Markdown. Balanced keeps
all events and trims very long OCR text; detailed keeps full OCR and speech. Canonical
`timeline.json` always retains all events.

## Privacy and limitations

Generated screenshots, transcripts, and the adjacent `.video-context.v2c-cache/` contain
source-derived data. Add both to your project's `.gitignore`, and delete both to clear
local evidence. Cache keys include content, provider, model, prompt version, and vision
context. Credentials and provider response bodies are never written to diagnostics.

This first release uses configurable heuristics, not learned relevance ranking. A hard
frame budget and periodic sampling can miss brief/subtle UI states. Lower `sample_interval`
and `change_threshold`, or increase `max_frames`, for dense bug recordings. Preview scoring
is low resolution; only selected screenshots are exported at full resolution. Speech-derived
requests remain quotations, and model descriptions are labeled. Review them against the source.

Implemented providers: local Tesseract OCR, local faster-whisper, Whisper-compatible OpenAI
speech, and OpenAI vision. Anthropic, Gemini, local vision, cloud OCR, URL ingestion, diarization,
and direct agent execution are not implemented. Unsupported providers are rejected explicitly.

## Development

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest
python -m build
```

Tests generate short videos with FFmpeg; no customer media or API keys are required.
See [architecture](docs/architecture.md), [developer guide](docs/developer-guide.md), and
[release checklist](docs/release.md). Publishing requires your PyPI project and trusted
publisher configuration; this repository does not publish automatically on a tag.
