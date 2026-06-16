# Release 0.1.7

## Что изменилось

- Добавлен plugin-provided MCP server `sylabys`.
- Добавлен MCP tool `prepare_syllabus_audit`, чтобы `@sylabys-syllabus-checker` был активным callable-инструментом в новом thread.
- Skill-компонент не возвращался: запуск остаётся plugin + MCP tool + настоящие Codex subagents.
- MCP tool не выполняет аудит вместо агентов. Он возвращает точный orchestration plan: extraction, шесть suite-команд, prompts для subagents и final arbitration command.

## Использование

В новом thread после обновления плагина напишите:

```text
@sylabys-syllabus-checker Проверь силлабус D:\path\to\syllabus.docx
```

Ожидаемый результат: Codex вызывает MCP tool `prepare_syllabus_audit`, затем поднимает шесть Codex-субагентов для `STR`, `FMT`, `OP`, `RUP`, `INT`, `TXT`, после чего главный тред собирает `reports\final-report.pdf`.
