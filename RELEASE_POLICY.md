# Release Policy

This repository uses semantic versioning for plugins.

## Version Rules

- Patch: bug fixes, extractor improvements, documentation updates, report wording changes.
- Minor: new checks, new report sections, new CLI options, additional plugin capabilities.
- Major: incompatible prompt, output, config, or installation changes.

## Required Release Checks

Run these before tagging:

```powershell
python C:\Users\User\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\sylabys-syllabus-checker
python -m unittest discover -s plugins\sylabys-syllabus-checker\tests -v
```

For release candidates, also run a real audit against a sample syllabus folder and confirm that `reports/final-report.pdf` is produced when a browser is available.

## Tag Format

Use `vX.Y.Z` because the repository currently ships one plugin.

If this repository later ships multiple independent plugins, use plugin-scoped tags such as:

```text
sylabys-syllabus-checker/v0.2.0
```
