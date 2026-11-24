# DealMind · Python Backend

В `apps/api` находится локальный HTTP API DealMind. Установленный пакет `dealmind-api` предоставляет модуль `dealmind`, фабрику FastAPI и ASGI entrypoint `dealmind.main:app`. Версия в OpenAPI берётся из метаданных distribution.

## Технологии и версия Python

Базовая версия разработки — Python 3.12, её выбирает `.python-version`. В метаданных пакета указано `requires-python = ">=3.12"`. FastAPI обслуживает HTTP-запросы, Pydantic v2 задаёт контракты, Uvicorn запускает ASGI-приложение. uv управляет окружением, Hatchling собирает пакет. pytest, HTTPX, Ruff и Mypy входят в группу `dev`. Приёмка DM-004 выполнена на CPython 3.12.13 под Windows.

## Структура пакета

| Путь | Назначение |
| --- | --- |
| `src/dealmind/__init__.py` | Корень импортируемого пакета |
| `src/dealmind/py.typed` | Маркер типизации, который поставляется в wheel |
| `src/dealmind/main.py` | Фабрика приложения, lifespan и точка входа Uvicorn |
| `src/dealmind/api/` | Общий router с префиксом `/api/v1`, маршруты, dependency готовности и обработчики исключений |
| `src/dealmind/core/` | Модель настроек, JSON formatter и контекст запроса |
| `src/dealmind/schemas/` | Публичные Pydantic-модели системных ответов и ошибок |
| `tests/unit/test_package_import.py` | Smoke-тесты импорта пакета и установленных метаданных |
| `tests/integration/` | HTTP-тесты, изоляция состояния, коды ошибок и OpenAPI |
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

## Локальный запуск

```shell
uv run --locked uvicorn dealmind.main:app --reload --no-access-log --host 127.0.0.1 --port 8000
```

Оставьте процесс в терминале на время работы. Для остановки нажмите Ctrl+C. Если порт занят, укажите `--port 8001` и замените порт в адресах ниже. На 8001 проверены запуск с reload, реальные запросы curl и отображение Swagger UI.

| Метод и путь | Код | Результат |
| --- | --- | --- |
| GET `/api/v1/health` | 200 | `{"status":"ok","service":"dealmind-api"}` |
| GET `/api/v1/ready` | 200 | `{"status":"ready","checks":{"application":"ok"}}` после startup |
| GET `/api/v1/ready` | 503 | `{"status":"not_ready","checks":{"application":"not_ready"}}` при неготовности |
| GET `/openapi.json` | 200 | OpenAPI с моделями ответов, включая 503 для readiness |
| GET `/docs` | 200 | Swagger UI с обоими маршрутами |

```shell
curl -i http://127.0.0.1:8000/api/v1/health
curl -i http://127.0.0.1:8000/api/v1/ready
curl -i http://127.0.0.1:8000/api/v1/unknown
curl -i http://127.0.0.1:8000/openapi.json
```

Откройте `http://127.0.0.1:8000/docs` в браузере. Swagger UI использует стандартные браузерные ресурсы FastAPI с CDN. Liveness подтверждает способность HTTP-процесса ответить. Readiness читает только состояние текущего экземпляра приложения. Проверка обязательной БД запланирована в DM-007.

## Контракт ошибок

Запрос к неизвестному пути возвращает HTTP 404 и JSON

```json
{"error":{"code":"NOT_FOUND","message":"Resource not found","details":null}}
```

Для 405 используется `METHOD_NOT_ALLOWED`, для 422 — `VALIDATION_ERROR`, для неожиданного исключения — `INTERNAL_SERVER_ERROR` (500). Ошибка валидации содержит список деталей с полями `loc`, `message`, `type`. Ответ ограничен публичными описаниями и безопасной позицией поля. Метод, указанный в заголовке `Allow` при 405, сохраняется. Ответ 503 у readiness имеет собственную модель `ReadinessResponse`.

## Тесты и проверка установки

```shell
uv run --locked pytest -v
uv run --locked python -c "import dealmind; print(dealmind.__file__)"
uv run --locked python -c "from importlib.metadata import version; print(version('dealmind-api'))"
```

Unit-тесты проверяют импорт и метаданные. HTTP-тесты создают приложение через `create_app()` и отправляют запросы в память через TestClient. Проверяются lifespan до и после startup/shutdown, изоляция dependency overrides, статусы и тела ответов, Swagger и OpenAPI. Маршруты для искусственных ошибок создаются только в тестах. Внешние сервисы и ключи для проверок не требуются.

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

## Запуск в Docker

Из корня monorepo подготовьте локальный `.env` по шаблону. `docker compose build api` собирает Python 3.12.13 и runtime-зависимости из `uv.lock`. Сначала uv устанавливает зависимости, затем копируется исходный код и устанавливается пакет в обычном режиме. В финальный слой попадает только собранное окружение. Сервис запускает `dealmind.main:app` через Uvicorn от пользователя `dealmind` (UID 10001). Параметр `--reload` применяется при локальной разработке на хосте.

Команда `docker compose up -d --build --wait` запускает всё окружение. Docker проверяет `/api/v1/health` изнутри контейнера через стандартную библиотеку Python. `/api/v1/ready` по-прежнему проверяет lifespan приложения. PostgreSQL и n8n имеют собственные проверки. `API_HOST_PORT` выбирает порт хоста, внутри сети API всегда слушает `api:8000`. Пароль PostgreSQL и ключ n8n передаются только своим сервисам. [Инфраструктурный runbook](../../infra/docker/README.md)

## Configuration & Logging

| Переменная | Default | Допустимые значения |
| --- | --- | --- |
| `APP_ENV` | `local` | `local`, `test`, `production` |
| `APP_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `APP_CORS_ORIGINS` | `[]` | JSON-массив HTTP(S) origins, например `["http://localhost:3000"]` |

Фабрика создаёт один неизменяемый `Settings` для приложения. Для тестов можно передать `create_app(settings=Settings(env="test"))`. В маршруте зависимость `Depends(get_settings)` возвращает тот же объект. Pydantic Settings читает переменные процесса. Поиск dotenv-файлов выключен. В режиме `production` действуют те же правила валидации. [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

В PowerShell из `apps/api` можно запустить API с локальными переопределениями. В Bash те же значения задаются через `export`.

```powershell
$env:APP_ENV = 'local'
$env:APP_LOG_LEVEL = 'DEBUG'
$env:APP_CORS_ORIGINS = '["http://localhost:3000"]'
uv run --locked uvicorn dealmind.main:app --reload --no-access-log
```

При запуске через Docker Compose корневой `.env` используется для подстановки. Секция `api.environment` передаёт в контейнер три `APP_*`. После изменения значений выполните из корня `docker compose up -d --build --wait api`. Обычный `restart` использует прежнее окружение контейнера. При ошибке запуска проверьте написание режима, регистр уровня и синтаксис JSON. Пустое значение известной переменной вызывает ошибку. Для пустого списка origins используйте `[]`.

**Корреляция.** Каждый ответ содержит `X-Request-ID`. Можно передать свой UUID v4. Приложение канонизирует корректный UUID и создаёт новый при отсутствующем, неоднозначном или некорректном заголовке. После запроса найдите возвращённое значение в `docker compose logs --no-log-prefix api`. При локальном запуске идентификатор виден в терминале.

**Формат.** Прикладной logger доступен через `request.app.state.logger`. Он пишет в stderr по одному JSON-объекту на строку. Событие `http.request.completed` уровня INFO содержит время UTC, уровень, logger, сообщение, сервис, среду, ID, HTTP-метод, шаблон маршрута, код ответа и длительность в миллисекундах. Для неизвестного маршрута используется `<unmatched>`. У неожиданной ошибки отдельное событие `http.request.failed` уровня ERROR с типом исключения. При обрыве уже начатого ответа оно сохраняет отправленный статус. Для диагностики используйте статические сообщения и предусмотренные поля. Тела, cookies, заголовки авторизации, query и текст исключения в HTTP-лог не записываются. Порог WARNING и выше скрывает обычные INFO-записи. Служебные сообщения запуска Uvicorn используют собственный формат.

**CORS.** Укажите сериализованный origin браузера со схемой и при необходимости портом. Пути, завершающий слеш, параметры, фрагменты, userinfo и wildcard отклоняются. Для разрешённого origin браузер получает доступ к `X-Request-ID`. Preflight поддерживает GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS и заголовки Content-Type, Authorization, X-Request-ID. Отправка cookies с credentials отключена. Если браузер отклонил запрос, сравните его Origin со списком и проверьте ответ OPTIONS.

Для проверки конфигурации, ошибок, параллельных запросов и CORS выполните `uv run --locked pytest -v` из `apps/api`. [Результаты приёмки DM-006](../../docs/tasks/DM-006.md)

## Дальнейшая разработка

Подключение backend к БД относится к DM-007. Доменные модули CRM, аналитика и AI-сценарии запланированы на последующие этапы. [Архитектура](../../docs/ARCHITECTURE.md) · [Roadmap](../../docs/ROADMAP.md)
