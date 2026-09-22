# Changelog

## 0.1.0 — Unreleased

### Added
- `v2c doctor` checks FFmpeg, Tesseract, faster-whisper, the local speech model and API-key
  presence, and prints the fix for anything missing.
- `v2c setup-speech [--model base]` downloads a local faster-whisper model once and makes it
  the default, so recordings with audio are transcribed on-device without any configuration.
- Progress output by default: stage lines, an in-place counter on interactive terminals, and
  a ready-to-paste agent prompt at the end. `--verbose` adds details, `--json` is unchanged.
- `local_stt_model` accepts a downloaded model name as well as a directory.

### Fixed
- Frame sampling now streams from one FFmpeg decode pass instead of seeking per second with
  OpenCV. Variable-frame-rate screen recordings (QuickTime, OBS) previously scored a frame
  from a different moment than the screenshot that was exported (drift of 20 s observed);
  sampling is also 2–3× faster.
- Speech is attached to the frame that was on screen when it started. A long narration
  could previously pull later sentences back onto an earlier screen's event.
- Per-frame OCR/vision failures are summarized into one warning per cause instead of one
  line per frame, and a rejected API key stops the stage after the first request.
- Tesseract language data is validated up front; a missing language is one clear message.
- Unexpected exceptions produce a short error and a tracker link instead of a traceback;
  file-system errors include the failing path.
- The provider cache directory is only created when something is cached.
- `ffprobe` receives the input via `-i`, so paths beginning with `-` work.

### Changed
- Initial installable CLI, local media pipeline, visual selection and perceptual dedupe.
- Optional timestamped speech, local OCR, OpenAI vision, caching and graceful degradation.
- Timestamped evidence fusion, Markdown/JSON export, safe package replacement and diagnostics.
- Configuration precedence, offline mode, regression tests and release workflows.
- `agent-prompt.md` is now the generic template with placeholders for the reader's task.
