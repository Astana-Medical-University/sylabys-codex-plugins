# Sylabys Codex Plugins

Repo marketplace для установки и обновления внутренних Codex-плагинов Sylabys.

## Marketplace

Текущий marketplace:

- name: `sylabys-codex-plugins`
- plugin: `sylabys-syllabus-checker`
- version: `1.0.3`

Структура:

```text
marketplace.json
.agents/plugins/marketplace.json
plugins/
  sylabys-syllabus-checker/
    .codex-plugin/plugin.json
    .codex/
    config/
    docs/
    scripts/
    src/
    tests/
```

Корневой `marketplace.json` нужен для установки как marketplace root или Git marketplace. Файл `.agents/plugins/marketplace.json` нужен, чтобы Codex видел marketplace при открытии этого репозитория как проекта.

## Инструкция Для ППС

Подробная инструкция без командной строки, со скриншотами и пошаговым запуском аудита:

[PPS_USER_GUIDE.md](PPS_USER_GUIDE.md)

PDF-версия для отправки ППС:

[PPS_USER_GUIDE.pdf](PPS_USER_GUIDE.pdf)


## Установка Для ППС Через Codex App + Git Marketplace

Основной способ распространения: преподаватель устанавливает `Git for Windows`, открывает Codex app и добавляет GitHub marketplace через интерфейс `Плагины`.

ППС не нужно открывать Git Bash, PowerShell, CMD или выполнять команды `codex plugin ...`.

В Codex app:

1. Открыть `Плагины`.
2. В правом верхнем углу открыть выпадающее меню со стрелкой.
3. Нажать `Добавить маркетплейс`.
4. В поле `Источник` вставить:

   ```text
   https://github.com/Astana-Medical-University/sylabys-codex-plugins
   ```

5. В `Git ref` оставить `main`.
6. Нажать `Добавить маркетплейс`.
7. Открыть вкладку `Sylabys Codex Plugins`.
8. Рядом с `Sylabys Syllabus Checker` нажать `Подключить`.

Подробная инструкция со скриншотами находится в `PPS_USER_GUIDE.md` и `PPS_USER_GUIDE.pdf`.

## CLI Только Для Администраторов

Если администратору нужно проверить установку через CLI:

```powershell
codex plugin marketplace add https://github.com/Astana-Medical-University/sylabys-codex-plugins --ref main
codex plugin add sylabys-syllabus-checker@sylabys-codex-plugins
```

## Update Flow

1. Внесите изменения в `plugins/sylabys-syllabus-checker`.
2. Поднимите semver в `plugins/sylabys-syllabus-checker/.codex-plugin/plugin.json`.
3. Обновите корневой `VERSION` и `CHANGELOG.md`.
4. Проверьте плагин:

   ```powershell
   python C:\Users\User\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\sylabys-syllabus-checker
   Push-Location plugins\sylabys-syllabus-checker
   python -m unittest discover -s tests -v
   Pop-Location
   ```

5. Сделайте commit и tag:

   ```powershell
   git add .
   git commit -m "Release sylabys-syllabus-checker 1.0.3"
   git tag v1.0.3
   git push origin main --tags
   ```

6. Пользователи обновляют marketplace:

   ```powershell
   codex plugin marketplace upgrade sylabys-codex-plugins
   ```

## Branching

- `main` - стабильная версия для пользователей.
- `dev` - тестирование изменений перед релизом.
- tags `vX.Y.Z` - зафиксированные версии релиза.


