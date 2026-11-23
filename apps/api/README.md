# DealMind · Python Backend

В `apps/api` находится самостоятельный uv-проект. Имя устанавливаемой distribution — `dealmind-api`, имя для импорта в Python — `dealmind`. Версия берётся из метаданных установленной distribution. Сейчас пакет предоставляет основу для разработки backend и два smoke-теста упаковки.

## Технологии и версия Python

Базовая версия разработки — Python 3.12, её выбирает `.python-version`. В метаданных пакета указано `requires-python = ">=3.12"`. DM-003 проверялась на CPython 3.12.13 под Windows. uv управляет окружением и зависимостями, Hatchling собирает пакет. pytest, Ruff и Mypy входят в группу `dev`. Список внешних runtime-зависимостей пока пуст.

## Структура пакета

| Путь | Назначение |
| --- | --- |
| `src/dealmind/__init__.py` | Корень импортируемого пакета |
| `src/dealmind/py.typed` | Маркер типизации, который поставляется в wheel |
| `tests/unit/test_package_import.py` | Smoke-тесты импорта пакета и установленных метаданных |
| `pyproject.toml` | Метаданные, Hatchling, зависимости и настройки проверок |
| `uv.lock` | Разрешённые версии зависимостей и хеши артефактов |
| `.python-version` | Выбор интерпретатора для локальной разработки |

## Установка и зависимости

Из корня monorepo перейдите в `apps/api`. Все последующие команды выполняются в этом каталоге. Понадобится uv. Если Python 3.12 ещё не установлен, его можно получить командой `uv python install 3.12`.

```shell
cd apps/api
uv sync
uv lock --check
```

`uv sync` создаёт локальное окружение `.venv`, устанавливает проект в editable-режиме и включает группу `dev`. Чтобы восстановить уже зафиксированное окружение с проверкой актуальности lock-файла, выполните `uv sync --locked`. Команды `uv run` используют это окружение без ручной активации. При добавлении инструмента разработки используйте `uv add --dev` и включайте изменения `pyproject.toml` и `uv.lock` в один коммит.

## Тесты и проверка установки

```shell
uv run --locked pytest
uv run --locked python -c "import dealmind; print(dealmind.__file__)"
uv run --locked python -c "from importlib.metadata import version; print(version('dealmind-api'))"
```

Первый тест проверяет импорт `dealmind`, второй читает имя и версию установленной distribution. Для editable-установки путь импорта ведёт в `src/dealmind/`. Проверки выполняются локально, в том числе без ключа OpenAI и подключения к БД.

## Lint и форматирование

```shell
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Ruff проверяет импорты и правила E4, E7, E9, F, I, B, UP для Python 3.12. Длина строки — 100 символов. Для применения форматирования используйте `uv run --locked ruff format .`, для исправимых замечаний линтера — `uv run --locked ruff check --fix .`. Изменения можно проверить в Git diff.

## Проверка типов

```shell
uv run --locked mypy src tests
```

Mypy работает в strict-режиме для кода и тестов. У новых функций указываются типы параметров и результата. Импорты разрешаются установленным пакетом. Размещение исходников в `src/` позволяет проверять упаковку без изменения `PYTHONPATH` или `sys.path`.

## Сборка пакета

```shell
uv build
```

Hatchling собирает source distribution (`.tar.gz`) и wheel (`.whl`) в локальном `dist/`. Wheel включает пакет `dealmind` с маркером `py.typed`. Содержимое окружения, кеши проверок и артефакты сборки исключены из Git.

## Дальнейшая разработка

DM-004 добавит FastAPI-приложение, OpenAPI и проверки health/ready. В следующих задачах REST routes будут передавать запросы в прикладные сервисы, а доменные модули — рассчитывать KPI и риск. Подключение к PostgreSQL, миграции Alembic и AI-сценарии имеют отдельные задачи. [Архитектура](../../docs/ARCHITECTURE.md) · [Roadmap](../../docs/ROADMAP.md)
