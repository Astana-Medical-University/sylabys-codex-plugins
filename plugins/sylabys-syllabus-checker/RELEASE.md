# Release 1.0.3

## Что изменилось

- Исправлен запуск MCP server `sylabys` после установки плагина через Git marketplace.
- `scripts/mcp_server.py` больше не зависит от внешнего пакета `mcp`: stdio MCP entrypoint реализован на стандартной библиотеке Python.
- `@sylabys-syllabus-checker` продолжает открывать workflow через tool `prepare_syllabus_audit`, который возвращает план для шести настоящих Codex-субагентов.
- Команды аудита используют Python-интерпретатор MCP server, а не системный `python` из PATH пользователя.
- В `.mcp.json` добавлены unbuffered запуск и явные таймауты для старта/работы сервера.

## Проверка

- Валидация плагина через `validate_plugin.py`.
- Модульные тесты `python -m unittest discover -s tests -v`.
- Ручная проверка stdio MCP: `initialize`, `tools/list`, `tools/call`.
