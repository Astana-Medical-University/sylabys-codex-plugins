---
name: syllabus-checker
description: Используй, когда нужно сделать аудит силлабуса, сверить силлабус с ОП/РУП, проверить цели, результаты обучения, темы, часы Л/ПЗ/СРОП/СРО, литературу, итоговый контроль и подготовить понятный PDF-аудит на русском.
---

# Sylabys Syllabus Checker

Use this skill for Russian-language syllabus audits for Astana Medical University or similar medical university programs.

The output must be a human-readable audit for a non-technical reviewer. Technical checks may run in the background, but the final answer should explain:

- что исправить;
- где исправить;
- уровень исправления;
- доказательство;
- как исправить;
- форму итогового контроля;
- замечания по литературе;
- вопросы для итогового контроля;
- где лежит PDF-отчёт.

## Inputs

Expected source folder contains:

- syllabus `.docx`;
- OP/passport/application `.docx` with a name like `Приложение 6`, `паспорт ОП`, or `стандарта ОП`;
- RUP/curriculum `.xlsx` with a name like `РУП` or `учебный план`.

## Required Codex Subagent Workflow

This plugin is designed to use real Codex subagents. When the Codex subagent capability is available, do not replace it with a single Python run. The main thread should orchestrate, while six subagents perform the six checking suites.

Resolve the plugin root from this skill file: the plugin root is two directories above `skills/syllabus-checker/`.

1. Resolve paths:
   - `plugin_root`: absolute path to this plugin root;
   - `source_root`: folder containing syllabus, OP and RUP;
   - `build_dir`: `<source_root>\build` unless the user requested another output root;
   - `reports_dir`: `<source_root>\reports` unless the user requested another output root.

2. Prepare extraction in the main thread:

   ```powershell
   python "<plugin_root>\scripts\extract.py" "<path-to-syllabus.docx>" --build "<build_dir>"
   ```

   If OP or RUP auto-detection fails, rerun extraction with explicit paths:

   ```powershell
   python "<plugin_root>\scripts\extract.py" "<path-to-syllabus.docx>" --op "<op.docx>" --rup "<rup.xlsx>" --build "<build_dir>"
   ```

3. Spawn six true Codex subagents in parallel. Use named/custom agents when Codex exposes them; otherwise use the standard worker/default subagent type with the suite-specific prompt below. Each subagent must run exactly one suite and write exactly one JSON file into `reports_dir`:

   - STR: structure and required syllabus sections;
   - FMT: DOCX formatting, margins, comments, tracked changes and template hygiene;
   - OP: aim, learning outcomes and OP alignment;
   - RUP: credits, period and hour distribution alignment with curriculum;
   - INT: internal consistency of topics, Bloom levels, outcomes, practical skills, assessment and hours;
   - TXT: language quality, bibliography and final-control wording.

   Suite command for each subagent:

   ```powershell
   python "<plugin_root>\scripts\run_suite.py" --suite "<SUITE>" --build "<build_dir>" --reports "<reports_dir>"
   ```

   The parent prompt to every subagent must include the absolute `plugin_root`, `build_dir`, `reports_dir`, syllabus path, OP path when known, RUP path when known, and the assigned suite. The subagent must not spawn other agents.

4. Wait for all six subagents. Check that these files exist:

   ```text
   <reports_dir>\str.json
   <reports_dir>\fmt.json
   <reports_dir>\op.json
   <reports_dir>\rup.json
   <reports_dir>\int.json
   <reports_dir>\txt.json
   ```

   If one suite file is missing, rerun only that suite once. If it is still missing, continue and let the final report show it as a critical incident.

5. In the main thread, run final arbitration and PDF generation:

   ```powershell
   python "<plugin_root>\scripts\write_final_report.py" --build "<build_dir>" --reports "<reports_dir>"
   ```

6. Report the main output:

   ```text
   <reports_dir>\final-report.pdf
   ```

   Also check:

   ```text
   <reports_dir>\final-report.md
   <reports_dir>\final-report.json
   <reports_dir>\agent-run.json
   ```

## Fallback When Codex Subagents Are Not Available

Use this only when the current Codex environment does not expose a subagent capability. State clearly that fallback was used.

```powershell
python "<plugin_root>\scripts\run_check.py" "<path-to-syllabus.docx>" --output-root "<folder-with-syllabus-op-rup>"
```

If OP or RUP auto-detection fails:

```powershell
python "<plugin_root>\scripts\run_check.py" "<path-to-syllabus.docx>" --op "<op.docx>" --rup "<rup.xlsx>" --output-root "<folder-with-syllabus-op-rup>"
```

## Audit Rules

1. First verify that the folder contains the right files.
2. Check syllabus structure against the current DAR template.
3. Compare aim and learning outcomes against OP and syllabus discipline content.
4. Compare thematic plan, topics, practical skills, and learning outcomes.
5. Check Bloom taxonomy wording.
6. Check hour distribution by lecture, practical classes, SROP, SRO.
7. Check final assessment form and write it separately.
8. Check literature and recommend updates if needed.
9. Generate or verify the PDF report.
10. In the final message, summarize status and link to `final-report.pdf`.

Do not present raw JSON as the main answer. Use the PDF/Markdown audit as the source of the human-readable conclusion.
