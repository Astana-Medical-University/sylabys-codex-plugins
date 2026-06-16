# Changelog

## 0.1.6 - 2026-06-16

- Switched `sylabys-syllabus-checker` to plugin-only invocation through `@sylabys-syllabus-checker`.
- Removed the bundled `skills` manifest entry and deleted the skill component from the release.
- Updated plugin-level description and `/check-syllabus` to require real Codex subagents without a non-subagent fallback.

## 0.1.5 - 2026-06-16

- Added explicit real Codex subagent workflow to the syllabus-checker skill and `/check-syllabus` prompt.
- Added `scripts/run_suite.py` so each subagent can run exactly one suite with absolute paths.
- Added `scripts/write_final_report.py` to collect six suite reports into the human-readable Markdown/HTML/PDF/JSON audit.
- Kept `scripts/run_check.py` as a fallback for Codex environments without subagent capability.

## Unreleased

## v0.1.4 - 2026-06-16

- Added skills: ./skills/ to the plugin manifest.
- Added the syllabus-checker skill so installed plugins are visible as active skill capabilities in new Codex threads.

- Added `PPS_USER_GUIDE.md`: app-only Russian guide for faculty, without CLI commands.
- Added 12 visual step screenshots under `screenshots/`.
- Updated faculty install flow to match the current Codex app marketplace UI.
- Added real Codex app screenshots for adding the GitHub marketplace and connecting the plugin.
- Added `PPS_USER_GUIDE.pdf` and corrected the app install step to use the top-right dropdown menu instead of the plus button wording.
- Rebuilt `PPS_USER_GUIDE.pdf` with embedded screenshots so the images display when the PDF is opened or downloaded.

## v0.1.3 - 2026-06-15

Initial Git marketplace release.

Includes `sylabys-syllabus-checker` 0.1.3:

- declarative runtime config in `config/syllabus-checker.json`;
- OP/RUP discovery from the syllabus folder first;
- `--output-root`, `--build`, and `--reports` for portable report output;
- PDF generation through configurable local browser discovery;
- human-readable Russian audit output in Markdown, HTML, PDF, and JSON.

