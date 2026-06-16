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

## How To Run

Resolve the plugin root from this skill file: the plugin root is two directories above `skills/syllabus-checker/`.

Run the bundled checker script from the plugin root:

```powershell
python scripts\run_check.py "<path-to-syllabus.docx>" --output-root "<folder-with-syllabus-op-rup>"
```

If OP or RUP auto-detection fails, run with explicit paths:

```powershell
python scripts\run_check.py "<path-to-syllabus.docx>" --op "<op.docx>" --rup "<rup.xlsx>" --output-root "<folder-with-syllabus-op-rup>"
```

The main output is:

```text
<folder-with-syllabus-op-rup>\reports\final-report.pdf
```

Also check:

```text
<folder-with-syllabus-op-rup>\reports\final-report.md
<folder-with-syllabus-op-rup>\reports\final-report.json
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
