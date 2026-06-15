# Sylabys Codex Plugins

Repo marketplace для установки и обновления внутренних Codex-плагинов Sylabys.

## Marketplace

Текущий marketplace:

- name: `sylabys-codex-plugins`
- plugin: `sylabys-syllabus-checker`
- version: `0.1.3`

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

## Install From Git

После публикации репозитория в GitHub/GitLab:

```powershell
codex plugin marketplace add https://github.com/<org>/sylabys-codex-plugins.git --ref main
codex plugin add sylabys-syllabus-checker@sylabys-codex-plugins
```

Для приватного репозитория используйте SSH URL:

```powershell
codex plugin marketplace add git@github.com:<org>/sylabys-codex-plugins.git --ref main
codex plugin add sylabys-syllabus-checker@sylabys-codex-plugins
```

## Install Locally

```powershell
codex plugin marketplace add "D:\github\sylabys-codex-plugins"
codex plugin add sylabys-syllabus-checker@sylabys-codex-plugins
```

Если CLI недоступен, откройте deep link в Codex app:

```text
codex://plugins/sylabys-syllabus-checker?marketplacePath=D%3A%5Cgithub%5Csylabys-codex-plugins%5Cmarketplace.json
```

## Update Flow

1. Внесите изменения в `plugins/sylabys-syllabus-checker`.
2. Поднимите semver в `plugins/sylabys-syllabus-checker/.codex-plugin/plugin.json`.
3. Обновите корневой `VERSION` и `CHANGELOG.md`.
4. Проверьте плагин:

   ```powershell
   python C:\Users\User\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py plugins\sylabys-syllabus-checker
   python -m unittest discover -s plugins\sylabys-syllabus-checker\tests -v
   ```

5. Сделайте commit и tag:

   ```powershell
   git add .
   git commit -m "Release sylabys-syllabus-checker 0.1.4"
   git tag v0.1.4
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
