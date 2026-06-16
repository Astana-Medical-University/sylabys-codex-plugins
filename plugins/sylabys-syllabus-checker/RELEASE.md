# Release Notes

## sylabys-syllabus-checker 0.1.4

Callable skill release.

Changes:

- added manifest "skills": "./skills/";
- added syllabus-checker skill so Codex can load the plugin as an active skill in new threads;
- documented how the skill runs the bundled audit script and where the PDF report is written.
## sylabys-syllabus-checker 0.1.3

Portable declarative runtime.

Changes:

- added `config/syllabus-checker.json` for fixture discovery, output folder names, and PDF browser candidates;
- OP/RUP auto-detection now checks the syllabus folder before the plugin root;
- `scripts/run_check.py` supports `--output-root`, `--build`, and `--reports`;
- PDF rendering can be controlled with `SYLABYS_PDF_BROWSER`, `SYLABYS_SKIP_PDF`, or `SYLABYS_CHECKER_CONFIG`;
- final Markdown/PDF now reads checked OP/RUP paths from the active build directory.

## sylabys-syllabus-checker 0.1.2

PDF audit output.

Changes:

- added automatic `reports/final-report.pdf` generation;
- added `reports/final-report.html` as printable source for the PDF;
- PDF rendering uses local headless Edge/Chrome when available;
- `reports/final-report.json` records PDF artifact status.

## sylabys-syllabus-checker 0.1.1

Updated syllabus-template integration.

Changes:

- replaced the bundled `docs/syllabus-template.docx` with the new DAR template from 15.06.2026;
- added DOCX table extraction without requiring `python-docx`;
- added thematic-plan extraction for the new template columns `Л / ПЗ / СРОП / СРО`;
- added support for two-row thematic-plan headers with `Количество учебных часов`;
- made `INT-021` report hour distribution mismatches by each type: `Л`, `ПЗ`, `СРОП`, `СРО`.

## sylabys-syllabus-checker 0.1.0

Initial release.

Includes:

- `/check-syllabus` prompt;
- six custom Codex agent profiles: STR, FMT, OP, RUP, INT, TXT;
- deterministic extraction and check scripts;
- local fallback runner for environments without custom agent spawning;
- final report renderer in the audit style: what to fix, where to fix, correction level, evidence, and recommended correction;
- tests for deterministic checks.

Validation performed:

- plugin manifest validation passed;
- `python -m unittest discover -s tests -v` passed;
- full fallback run produced all expected `reports/*.json`, `reports/final-report.json`, and `reports/final-report.md`.

