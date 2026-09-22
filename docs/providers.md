# Providers

| Stage | Selection | Behavior |
| --- | --- | --- |
| Speech | auto | Uses the local model from `v2c setup-speech` (or `local_stt_model`); otherwise skipped with a one-line note |
| Speech | local | faster-whisper from a downloaded model, CPU/int8; fails loudly if none is set up |
| Speech | whisper | OpenAI `/v1/audio/transcriptions`, timestamped `verbose_json` |
| OCR | auto / local | Tesseract executable; optional and local |
| Vision | auto / none | Disabled |
| Vision | openai | Structured JSON from `/v1/chat/completions` image input |

### Local speech models

`v2c setup-speech [--model base]` downloads a faster-whisper model into
`$XDG_CACHE_HOME/video2context/models/<name>` (default `~/.cache/video2context/models`) and
records it as the default in a `default` file beside it. Nothing is downloaded at any other
time. `local_stt_model` / `V2C_LOCAL_STT_MODEL` accepts either an absolute model directory or
the name of a downloaded model (`small`); when unset, the recorded default is used. The
`faster-whisper` package itself is an optional extra (`video2context[local-stt]`, or
`pipx inject video2context 'faster-whisper>=1.0,<2'`) because it pulls in CTranslate2.

Use `none` to disable any stage explicitly. `--offline` rejects remote selections even
if the corresponding skip flag is present. It does not fetch local models.

Configuration: `stt_model` (default `whisper-1`), `vision_model` (default `gpt-4o-mini`),
`local_stt_model` (existing directory), `ocr_language` (installed Tesseract language),
`workers`, `retries`, `retry_delay`, `request_timeout`, `max_vision_requests`, and
`vision_requests_per_minute`. Choose a speech model supporting timestamped `verbose_json`
and a vision model supporting image input and JSON object responses.

API contract references:
[OpenAI audio](https://platform.openai.com/docs/api-reference/audio) and
[Chat Completions](https://platform.openai.com/docs/api-reference/chat).
Real paid calls are not part of the automated suite; transport tests use deterministic mocks.

To add a provider, implement a domain protocol and normalize into its dataclasses. Keep
provider imports outside `domain/`, register selection in config/pipeline, include its model
identity in cache keys, and add contract tests. Increment the cache version when prompts or
normalization behavior changes. Local model directories should be immutable: replacing weights
in place requires deleting the cache or using a new model directory name.
