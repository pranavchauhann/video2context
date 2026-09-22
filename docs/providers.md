# Providers

| Stage | Selection | Behavior |
| --- | --- | --- |
| Speech | auto | Uses a configured local model; otherwise disabled with a warning |
| Speech | local | faster-whisper from an existing model directory, CPU/int8 |
| Speech | whisper | OpenAI `/v1/audio/transcriptions`, timestamped `verbose_json` |
| OCR | auto / local | Tesseract executable; optional and local |
| Vision | auto / none | Disabled |
| Vision | openai | Structured JSON from `/v1/chat/completions` image input |

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
