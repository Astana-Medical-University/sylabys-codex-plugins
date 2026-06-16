# Installing Sylabys Syllabus Checker

This file is for the Sylabys Codex plugins marketplace repository.

## Install

From a local checkout:

```powershell
codex plugin marketplace add "D:\github\sylabys-codex-plugins"
codex plugin add sylabys-syllabus-checker@sylabys-codex-plugins
```

From Git after the repository is published:

```powershell
codex plugin marketplace add https://github.com/<org>/sylabys-codex-plugins.git --ref main
codex plugin add sylabys-syllabus-checker@sylabys-codex-plugins
```

Start a new Codex thread after installing.

## Run

Open Codex in the folder that contains the syllabus, OP passport, and RUP files, then run:

```powershell
@sylabys-syllabus-checker Проверь силлабус "<path-to-syllabus.docx>" через 6 субагентов
```

This path uses the plugin-provided MCP tool `prepare_syllabus_audit`; Codex then spawns six real subagents and writes the final report.

Emergency local fallback without plugin MCP or custom Codex agents:

```powershell
python scripts/run_check.py "<path-to-syllabus.docx>" --op "<op-passport.docx>" --rup "<rup.xlsx>"
```

Portable folder run:

```powershell
python scripts/run_check.py "<path-to-syllabus.docx>" --output-root "<folder-with-syllabus-op-rup>"
```

The checker reads default settings from `config/syllabus-checker.json`. You can override them with a local `sylabys-checker.json` or `SYLABYS_CHECKER_CONFIG`. For PDF output, set `SYLABYS_PDF_BROWSER` if Edge/Chrome is installed in a non-standard location; set `SYLABYS_SKIP_PDF=1` to write only Markdown/HTML/JSON.

## Output

The main reports are written to:

```text
reports/final-report.md
reports/final-report.pdf
```

It is formatted as a human-readable audit: what to fix, where to fix it, the correction level, evidence, and recommended correction.
