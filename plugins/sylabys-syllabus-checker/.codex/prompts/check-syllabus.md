# /check-syllabus

Plugin entrypoint for `@sylabys-syllabus-checker`.

Запусти полную проверку силлабуса именно как plugin workflow через настоящих Codex-субагентов. Не запускай bundled skills и не подменяй workflow обычным локальным `run_check.py`.

Аргумент: путь к `.docx` силлабуса. Папка с силлабусом обычно также содержит ОП/паспорт ОП и РУП/учебный план.

## Жёсткое правило

Используй real Codex subagents. Главный тред делает только подготовку, запуск, ожидание и арбитраж. Шесть проверочных suite должны выполняться шестью отдельными Codex-субагентами.

Если в текущем окружении нет subagent capability, закончились workspace credits, или Codex не может spawn/wait subagents, остановись и объясни блокер. Не используй fallback без субагентов, если пользователь отдельно не попросил аварийный локальный запуск.

## Порядок

1. Найди `plugin_root`: корень установленного плагина `sylabys-syllabus-checker`.
2. Определи:
   - `source_root` = папка с силлабусом, ОП и РУП;
   - `build_dir` = `<source_root>\build`;
   - `reports_dir` = `<source_root>\reports`.
3. Пересоздай `build_dir` и `reports_dir`, не трогая исходные `.docx`/`.xlsx`.
4. В главном треде выполни extraction:

   ```powershell
   python "<plugin_root>/scripts/extract.py" "<docx>" --build "<build_dir>"
   ```

   Если ОП/РУП не найдены автоматически, повтори с `--op` и `--rup`.

5. Spawn six Codex subagents in parallel. Если доступны custom agent names, используй:
   `syllabus-str`, `syllabus-fmt`, `syllabus-op`, `syllabus-rup`, `syllabus-int`, `syllabus-txt`.
   Если custom names не видны, используй стандартный `worker`/`default` subagent type, но строго с suite-specific prompt.

6. Каждому субагенту передай абсолютные пути `plugin_root`, `build_dir`, `reports_dir`, путь к исходному силлабусу, путь к ОП/РУП при наличии и ровно один suite. Команда для suite:

   ```powershell
   python "<plugin_root>/scripts/run_suite.py" --suite "<SUITE>" --build "<build_dir>" --reports "<reports_dir>"
   ```

   Где `<SUITE>` один из `STR`, `FMT`, `OP`, `RUP`, `INT`, `TXT`.

7. Wait for all six subagents. Проверь наличие:
   `str.json`, `fmt.json`, `op.json`, `rup.json`, `int.json`, `txt.json` в `reports_dir`.
   Если файл отсутствует, перезапусти только соответствующий suite один раз через subagent.

8. Арбитраж выполни сам в главном треде:

   ```powershell
   python "<plugin_root>/scripts/write_final_report.py" --build "<build_dir>" --reports "<reports_dir>"
   ```

9. Финальный вывод пользователю: понятный аудит на русском, без сырого JSON. Обязательно укажи:
   - итоговый статус;
   - что исправить;
   - где исправить;
   - уровень исправления;
   - доказательство;
   - как исправить;
   - форму итогового контроля;
   - замечания по литературе;
   - вопросы для итогового контроля;
   - путь к `final-report.pdf`.

Настройки поиска ОП/РУП, названий папок вывода и PDF-движка берутся из `config/syllabus-checker.json`, локального `sylabys-checker.json` или файла из `SYLABYS_CHECKER_CONFIG`.
