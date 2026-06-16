# Sylabys Syllabus Checker

Codex plugin for auditing medical university syllabi against an educational program passport, RUP, syllabus structure, learning outcomes, topics, assessment, and literature.

The plugin is designed for Russian-language audits. The technical checks run in the background, while the final Markdown report is written as a human-readable expert audit:

- what must be fixed;
- where it must be fixed;
- the level of correction;
- evidence;
- recommended correction;
- final control form;
- literature notes;
- suggested final-control questions with Bloom level.

## Usage

Run from a Codex thread opened in the project folder:

```powershell
@sylabys-syllabus-checker Проверь силлабус "<path-to-syllabus.docx>" через 6 субагентов
```

This invokes the plugin-provided MCP tool `prepare_syllabus_audit`; Codex then spawns six real subagents (`STR`, `FMT`, `OP`, `RUP`, `INT`, `TXT`) and writes the final report.

If plugin MCP or custom Codex agents are not available in the current environment, use the local fallback:

```powershell
python scripts/run_check.py "<path-to-syllabus.docx>"
```

The fallback auto-detects OP and RUP fixtures in the project root when possible. You can also pass them explicitly:

```powershell
python scripts/run_check.py "<path-to-syllabus.docx>" --op "<op-passport.docx>" --rup "<rup.xlsx>"
```

For a portable run where the source files and report artifacts stay in one folder:

```powershell
python scripts/run_check.py "<path-to-syllabus.docx>" --output-root "<folder-with-syllabus-op-rup>"
```

The runtime is declarative:

- bundled defaults live in `config/syllabus-checker.json`;
- a local `sylabys-checker.json` in the working folder can override fixture search patterns, output folder names, and PDF browser candidates;
- `SYLABYS_CHECKER_CONFIG` can point to a custom JSON config;
- `SYLABYS_PDF_BROWSER` can point to a browser executable for PDF rendering;
- `SYLABYS_SKIP_PDF=1` skips PDF generation and still writes the HTML report.

## Outputs

The audit writes:

- `reports/final-report.md` - human-readable audit;
- `reports/final-report.pdf` - PDF version of the audit;
- `reports/final-report.html` - printable HTML source for the PDF;
- `reports/final-report.json` - structured final report;
- `reports/str.json`, `fmt.json`, `op.json`, `rup.json`, `int.json`, `txt.json` - suite-level reports;
- `build/syllabus.json`, `op.json`, `rup.json` - extracted data.

When `--output-root` is used, `build/` and `reports/` are written under that folder.

## Install From Marketplace Repository

From the Sylabys Codex plugins marketplace repository:

```powershell
codex plugin marketplace add https://github.com/<org>/sylabys-codex-plugins.git --ref main
codex plugin add sylabys-syllabus-checker@sylabys-codex-plugins
```

Start a new Codex thread after installing so Codex picks up the plugin prompt and agents.
