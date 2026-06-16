# Release 0.1.6

## Что изменилось

- Плагин переведён в plugin-only режим запуска через `@sylabys-syllabus-checker`.
- Из manifest удалён `skills`: запуск больше не должен происходить как bundled skill.
- Plugin-level description и `/check-syllabus` теперь прямо требуют настоящий Codex subagent workflow.
- Fallback без субагентов убран из основного сценария: если subagents недоступны или закончились workspace credits, плагин должен остановиться и сообщить блокер.
- `.codex/agents/*.toml` и suite runner остаются основой проверки: один Codex-субагент выполняет один suite.

## Использование

В новом thread после обновления плагина напишите:

```text
@sylabys-syllabus-checker Проверь силлабус D:\path\to\syllabus.docx
```

Ожидаемый результат: шесть Codex-субагентов выполняют `STR`, `FMT`, `OP`, `RUP`, `INT`, `TXT`, затем главный тред собирает `reports\final-report.pdf`.
