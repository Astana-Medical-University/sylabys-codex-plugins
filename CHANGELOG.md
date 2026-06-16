# Changelog

## 1.0.2 - 2026-06-16

- Закреплена инструкция для ППС на сценарии установки через Codex app + Git marketplace: без CLI-команд для преподавателей и без Share-сценария.
- Обновлена PDF-инструкция `PPS_USER_GUIDE.pdf` со всеми реальными скриншотами: добавление marketplace, подключение плагина, выбор папки дисциплины, запуск аудита, автоподтверждение и папка `reports`.
- Уточнено, что Git for Windows должен быть установлен как системная зависимость, но Git Bash и команды `codex plugin ...` ППС не нужны.
- README обновлён под версию `1.0.2` и app-first установку через GitHub marketplace.
- Исправлена команда запуска тестов в README: модульные тесты запускаются из корня `plugins/sylabys-syllabus-checker`.

## 1.0.1 - 2026-06-16

- Переписан экстрактор на table-first и только стандартную библиотеку (без python-docx/openpyxl): корректно извлекаются часы, преподаватели, тематический план, глоссарий, оценивание, согласование.
- Адресная сверка с ОП и РУП: из паспорта ОП и РУП берутся только данные нужной дисциплины/модуля; РУП-сверка учитывает «модуль = сумма дисциплин» и автоматически выбирает охват.
- Сверка с ОП сделана scope-aware (модуль vs дисциплина), убраны ложные FAIL по кредитам и матрице РО.
- Настоящие проверки вместо заглушек: КИС (INT-046), литература (INT-050), глоссарий (INT-051), график СРОП (INT-052), титул vs раздел 1 (INT-056), диагностичность РО (TXT-004).
- Поддержка вариативного шаблона силлабуса (комбинированная таблица РО/ПН/план с двухстрочной шапкой часов) + синтез РО/ПН из плана.
- Громкие ошибки вместо тихой пустой экстракции; убран кардио-хардкод из эвристики TXT-001.
- Проверено на трёх реальных силлабусах (анатомия, патология, кардио-респираторный); 8 модульных тестов зелёные.

## 0.1.8 - 2026-06-16

- Fixed course parsing so resource-card fields like `Курс ______` followed by `Всего контингент обучающихся 735` no longer produce `course=735`.
- Restricted course extraction to reliable syllabus passport/study-period context and valid course values 1-7.
- Updated module credit reporting so extracted credit values are marked as syllabus passport values requiring RUP verification, not calculated module totals.
- Added regression tests for the `course=735` parser bug and invalid `735, 2.0 кредитов` report string.

## 0.1.7 - 2026-06-16

- Added plugin-provided MCP server `sylabys` and callable tool `prepare_syllabus_audit`.
- Kept the workflow plugin-based rather than skill-based while making `@sylabys-syllabus-checker` discoverable as an active tool.
- The MCP tool returns the orchestration plan for six real Codex subagents instead of performing a non-subagent fallback.

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

