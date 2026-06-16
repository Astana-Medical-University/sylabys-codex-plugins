# /check-syllabus

Plugin entrypoint for `@sylabys-syllabus-checker`.

Запусти полную проверку силлабуса именно как plugin workflow: сначала вызови MCP tool `prepare_syllabus_audit`, затем подними настоящих Codex-субагентов по плану, который вернул tool. Не запускай bundled skills и не подменяй workflow обычным локальным `run_check.py`.

Аргумент: путь к `.docx` силлабуса. Папка с силлабусом обычно также содержит ОП/паспорт ОП и РУП/учебный план.

## Жёсткое правило

1. Сначала используй MCP tool плагина `prepare_syllabus_audit` с путём к силлабусу.
2. Затем используй real Codex subagents. Главный тред делает только подготовку, запуск, ожидание и арбитраж.
3. Шесть проверочных suite должны выполняться шестью отдельными Codex-субагентами: `STR`, `FMT`, `OP`, `RUP`, `INT`, `TXT`.
4. Если MCP tool или subagent capability недоступны, закончились workspace credits, или Codex не может spawn/wait subagents, остановись и объясни блокер. Не используй fallback без субагентов, если пользователь отдельно не попросил аварийный локальный запуск.

## Порядок

1. Вызови `prepare_syllabus_audit`:
   - `syllabus_path`: путь к `.docx` силлабуса;
   - `output_root`: папка с силлабусом, ОП и РУП, если пользователь указал её отдельно;
   - `op_path`: путь к ОП, если пользователь указал явно;
   - `rup_path`: путь к РУП, если пользователь указал явно.

2. Выполни `extractCommand`, который вернул MCP tool, в главном треде.

3. Spawn six Codex subagents in parallel. Если доступны custom agent names, используй:
   `syllabus-str`, `syllabus-fmt`, `syllabus-op`, `syllabus-rup`, `syllabus-int`, `syllabus-txt`.
   Если custom names не видны, используй стандартный `worker`/`default` subagent type, но строго с suite-specific prompt из `subagentPrompts`.

4. Каждому субагенту передай только его suite prompt и соответствующую команду из `suiteCommands`. Субагент не должен спавнить других агентов и не должен редактировать исходные `.docx`/`.xlsx`.

5. Wait for all six subagents. Проверь наличие всех файлов из `suiteReports`. Если файл отсутствует, перезапусти только соответствующий suite один раз через subagent.

6. Арбитраж выполни сам в главном треде: запусти `finalCommand`, который вернул MCP tool.

7. Финальный вывод пользователю: понятный аудит на русском, без сырого JSON. Обязательно укажи:
   - итоговый статус;
   - что исправить;
   - где исправить;
   - уровень исправления;
   - доказательство;
   - как исправить;
   - форму итогового контроля;
   - замечания по литературе;
   - вопросы для итогового контроля;
   - путь к `finalReportPdf`.

Настройки поиска ОП/РУП, названий папок вывода и PDF-движка берутся из `config/syllabus-checker.json`, локального `sylabys-checker.json` или файла из `SYLABYS_CHECKER_CONFIG`.
