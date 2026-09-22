<div align="center">

# Video2Context

**Turn a screen recording into context your coding agent can read.**

`v2c` picks the screenshots that matter, pulls out on-screen text and speech, and hands
Claude Code, Codex or Cursor a timestamped `context.md` instead of a video.

[![CI](https://github.com/pranavchauhann/video2context/actions/workflows/ci.yml/badge.svg)](https://github.com/pranavchauhann/video2context/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![macOS · Linux · Windows](https://img.shields.io/badge/macOS_·_Linux_·_Windows-555)](#install)
[![Local by default](https://img.shields.io/badge/Processing-local_by_default-15803D)](docs/usage.md#privacy-and-limits)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

[Install](#install) · [Use](#use) · [Extras](#optional-extras) · [Full guide](docs/usage.md)

</div>

---

```console
$ v2c recording.mov

Video2Context 0.1.0 — recording.mov
Reading video metadata…
Selecting screenshots…
Writing context package…

Done in 9.7s: kept 34 of 116 sampled frames, 34 events.
Context ready: .video-context/context.md
```

Record a bug, a UI review or a walkthrough. Run `v2c` on it. Paste one prompt into your
agent. Everything runs on your machine: no account, no API key, nothing uploaded.

## Install

You need **FFmpeg** and **pipx**. Pick your OS, run the commands, then open a new terminal.

<!-- After the PyPI release, replace the git URL below with: pipx install video2context -->

<details open>
<summary><b>macOS</b></summary>

```bash
brew install ffmpeg pipx && pipx ensurepath
pipx install "git+https://github.com/pranavchauhann/video2context.git"
```

No Homebrew yet? Install it first from [brew.sh](https://brew.sh).

</details>

<details>
<summary><b>Ubuntu / Debian</b></summary>

```bash
sudo apt update && sudo apt install -y ffmpeg pipx && pipx ensurepath
pipx install "git+https://github.com/pranavchauhann/video2context.git"
```

Needs Python 3.11 or newer (`python3 --version`).

</details>

<details>
<summary><b>Windows</b></summary>

In PowerShell:

```powershell
winget install Gyan.FFmpeg Git.Git Python.Python.3.12
```

Open a new PowerShell window, then:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install "git+https://github.com/pranavchauhann/video2context.git"
```

</details>

Open a new terminal and confirm everything is ready:

```bash
v2c doctor
```

Every line should say `OK`. `OFF` marks optional extras; `MISSING` comes with the command
that fixes it.

## Use

From the project folder your agent works in:

```bash
v2c "/path/to/recording.mov"
```

`v2c` writes `.video-context/` and prints a prompt. Paste it into your agent and fill in
the two brackets:

```text
Read .video-context/context.md and .video-context/timeline.json, and inspect the
referenced screenshots. This is a screencast of [what you recorded].
[What you want done.] Cite the timestamp and screenshot for every finding.
```

| You want to… | Run |
| --- | --- |
| Get UI feedback implemented | `v2c "clip.mov" --intent ui-feedback` |
| Investigate a bug | `v2c "clip.mov" --intent bug-repro --detail detailed` |
| Keep more screenshots | `v2c "clip.mov" --max-frames 60` |
| Replace the previous output | `v2c "clip.mov" --overwrite` |
| See every option | `v2c run --help` |

Add `.video-context*/` to your project's `.gitignore`. Agent prompts for analysis vs.
implementation, the output layout and every flag are in the [usage guide](docs/usage.md).

## Optional extras

**Speech** — transcribe narration on your machine, no API key:

```bash
pipx inject video2context 'faster-whisper>=1.0,<2'
v2c setup-speech
```

**On-screen text** — install Tesseract and `v2c` uses it automatically:

```bash
brew install tesseract            # macOS
sudo apt install tesseract-ocr    # Ubuntu / Debian
```

Windows: install the [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki) and
add it to PATH.

**AI screenshot descriptions** are off by default and need an explicit `--vision-provider openai`.
See [speech, OCR and vision](docs/usage.md#speech-ocr-and-vision).

## Learn more

| | |
| --- | --- |
| [Usage guide](docs/usage.md) | Agent prompts, output files, all options, configuration, troubleshooting, privacy |
| [Providers](docs/providers.md) | Local and remote speech, OCR and vision settings |
| [Architecture](docs/architecture.md) | How frames are selected and evidence is fused |
| [Developer guide](docs/developer-guide.md) | Local setup, tests, diagnostics |
| [Changelog](CHANGELOG.md) | Release history |

---

<div align="center">

**Keep the evidence. Skip the repeated frames.**

[Report an issue](https://github.com/pranavchauhann/video2context/issues) · [MIT License](LICENSE)

</div>
