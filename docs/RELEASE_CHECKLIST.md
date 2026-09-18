# QuotaPilot Release Checklist

Publishing, tagging, and GitHub release creation require a separate explicit
instruction. This checklist only establishes readiness.

## Quality

- [ ] `uv run pytest`
- [ ] `uv run ruff check .`
- [ ] `uv run pyright`
- [ ] Offline end-to-end smoke passes
- [ ] Opt-in live provider integration result recorded
- [ ] No real execution occurs in normal tests or CI

## Build and installation

- [ ] Project version is correct in `pyproject.toml`
- [ ] `uv build` succeeds
- [ ] Wheel and sdist contents inspected
- [ ] Clean temporary environment installs the wheel
- [ ] Installed `quotapilot --version` and `--help` pass
- [ ] Installed bundled model profiles and calibration scenarios load

## Security and privacy

- [ ] Staged-tree secret/account/task/telemetry scan passes
- [ ] Fixtures remain synthetic/sanitized with provenance
- [ ] Unsafe shell/YAML/config patterns absent
- [ ] Doctor fake-secret regression passes
- [ ] Status/Waybar/JSON privacy tests pass
- [ ] Dependencies and third-party attribution reviewed

## Documentation and repository

- [ ] README commands and installation steps re-verified
- [ ] Configuration/environment variables documented
- [ ] Waybar snippet/classes verified
- [ ] Privacy and execution safety documented
- [ ] CHANGELOG current
- [ ] LICENSE present and compatible
- [ ] SECURITY.md current
- [ ] CONTRIBUTING.md current
- [ ] CI includes pytest, Ruff, Pyright, and build
- [ ] Git working tree clean
- [ ] Release tag ready but not created
