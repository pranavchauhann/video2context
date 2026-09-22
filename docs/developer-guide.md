# Developer guide

Install FFmpeg and the editable package with the development extra, as in README.

The package has an src layout and one console command. Invoke either `v2c` or
`python -m video2context`. Tests inject providers through `pipeline.run(..., providers=...)`;
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
CI installs both and runs on Linux/macOS with Python 3.11 and 3.12.

`metadata.json` records stage status, warnings, candidate and retained counts, timings, cache
hits, and retries. `--keep-intermediates` retains WAV chunks and diagnostics inside the package;
`--verbose` reports stage details to stderr. Avoid logging raw provider exceptions because
SDK/HTTP exceptions can expose request data or secrets.

The timeline schema lives in `src/video2context/schemas/timeline.schema.json` and is included
in wheels. Schema version changes are independent of package version changes. Breaking CLI
or schema contracts should use a major package version.
