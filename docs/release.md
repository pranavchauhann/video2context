# Release checklist

- Run lint, tests, CLI smoke checks, and wheel/sdist build.
- Test a representative real 10–20 minute feedback recording locally; synthetic tests are
  not a substitute for evaluating speech accuracy or subtle screen transitions.
- Test selected paid providers with consent to upload the test evidence.
- Update version and CHANGELOG. Check package-name availability on PyPI/TestPyPI.
- Configure trusted publishers for this repository and the `testpypi` / `pypi` environments.
- Tag the version and dispatch Release with that exact tag and `testpypi` first.
- Install the TestPyPI artifact into an isolated pipx environment and test from another project.
- Dispatch the same immutable tag to `pypi` after verification. Configure environment protection
  rules in GitHub to require release approval.
- Create release notes with install/upgrade instructions.

No package has been published as part of initial implementation. The provided workflow requires
manual dispatch and configured registry credentials via GitHub OIDC.
