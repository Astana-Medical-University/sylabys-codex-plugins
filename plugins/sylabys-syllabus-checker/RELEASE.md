# Release 0.1.5

## Что изменилось

- Skill `/check-syllabus` переведён на явный workflow с настоящими Codex subagents.
- Добавлен `scripts/run_suite.py`: переносимый запуск одного suite (`STR`, `FMT`, `OP`, `RUP`, `INT`, `TXT`) для отдельного субагента.
- Добавлен `scripts/write_final_report.py`: сбор итогового `final-report.md/html/pdf/json` после завершения шести субагентов.
- В prompt больше нет зависимости от относительного `scripts/...` в папке пользователя: всем субагентам передаются абсолютные пути к `plugin_root`, `build_dir` и `reports_dir`.
- `scripts/run_check.py` оставлен как fallback для окружений, где Codex subagents недоступны.

## Как использовать

1. Обновите marketplace в Codex App из GitHub-репозитория.
2. Установите/обновите `Sylabys Syllabus Checker`.
3. Откройте новый thread в проекте с силлабусом.
4. Попросите: `Используй плагин Sylabys Syllabus Checker и проверь силлабус ...`.

Codex должен поднять шесть субагентов для suite-проверок и затем собрать PDF-аудит в `reports\final-report.pdf`.
