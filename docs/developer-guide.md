# Developer guide

Install FFmpeg and the editable package with the development extra, as in README.

The package has an src layout and one console command with three subcommands: `run`
(the default, so `v2c video.mov` equals `v2c run video.mov`), `doctor`, and `setup-speech`.
`DefaultGroup` in `cli/main.py` routes anything that is not a subcommand name to `run`, in
either argument order. Invoke either `v2c` or `python -m video2context`. Tests inject providers through `pipeline.run(..., providers=...)`;
production selections go through validated config. Tests never require API credentials.

Useful checks:

```sh
ruff check .
ruff format --check .
pytest -q
python -m build
v2c --help
v2c --version
```

Integration tests create fixtures at runtime in pytest temporary directories. ffmpeg and
ffprobe must be installed to run these tests; missing tools cause explicit skips locally.
CI installs both and runs on Linux/macOS with Python 3.11, 3.12 and 3.13. Tests isolate
`XDG_CACHE_HOME`, so a speech model downloaded on your machine never changes results.

`metadata.json` records stage status, warnings, candidate and retained counts, timings, cache
hits, and retries. `--keep-intermediates` retains WAV chunks and diagnostics inside the package;
`--verbose` reports stage details to stderr. Avoid logging raw provider exceptions because
SDK/HTTP exceptions can expose request data or secrets.

The timeline schema lives in `src/video2context/schemas/timeline.schema.json` and is included
in wheels. Schema version changes are independent of package version changes. Breaking CLI
or schema contracts should use a major package version.
