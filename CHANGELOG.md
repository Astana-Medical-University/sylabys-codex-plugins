# Changelog

## Unreleased

- Added `PPS_USER_GUIDE.md`: app-only Russian guide for faculty, without CLI commands.
- Added 12 visual step screenshots under `screenshots/`.
- Updated faculty install flow to match the current Codex app marketplace UI.
- Added real Codex app screenshots for adding the GitHub marketplace and connecting the plugin.

## v0.1.3 - 2026-06-15

Initial Git marketplace release.

Includes `sylabys-syllabus-checker` 0.1.3:

- declarative runtime config in `config/syllabus-checker.json`;
- OP/RUP discovery from the syllabus folder first;
- `--output-root`, `--build`, and `--reports` for portable report output;
- PDF generation through configurable local browser discovery;
- human-readable Russian audit output in Markdown, HTML, PDF, and JSON.
