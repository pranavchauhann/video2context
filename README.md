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

[Install](#install) · [Use](#use) · [Clean up](#clean-up) · [Extras](#optional-extras) · [Full guide](docs/usage.md)

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

Everything runs on your machine: no account, no API key, nothing uploaded.

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

Open a new terminal and check the setup:

```bash
v2c doctor
```

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

Processing another recording? Add `--overwrite`. All options: `v2c run --help`.

Add `.video-context*/` to your project's `.gitignore`.

## Clean up

Delete the generated files when you're done. Your video and code are untouched:

```bash
rm -rf .video-context .video-context.v2c-cache
```

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

Windows: [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki), added to PATH.

## Learn more

[Usage guide](docs/usage.md) (agent prompts, output files, all options, troubleshooting) ·
[Providers](docs/providers.md) · [Architecture](docs/architecture.md) ·
[Developer guide](docs/developer-guide.md) · [Changelog](CHANGELOG.md)

---

<div align="center">

**Keep the evidence. Skip the repeated frames.**

[Report an issue](https://github.com/pranavchauhann/video2context/issues) · [MIT License](LICENSE)

</div>
