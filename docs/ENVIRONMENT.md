# Настройки окружения

## Загрузка и адреса

Из корня Compose подставляет переменные процесса и корневого `.env` в [docker-compose.yml](../docker-compose.yml). Для одного имени экспортированное значение оболочки имеет приоритет перед dotenv. В контейнер передаются значения, перечисленные у сервиса. `docker compose config --quiet` проверяет подстановки без печати секретов. Начальный образец — [.env.example](../.env.example).

Вне Docker FastAPI читает `APP_*` из окружения процесса. У Pydantic Settings задано `env_file=None`, явно переданные поля модели имеют приоритет. Разбор выполняется при создании приложения. Next.js читает серверные runtime-настройки при обработке статуса. Для запуска на хосте можно заполнить `apps/web/.env.local` по [шаблону frontend](../apps/web/.env.example). Переменные процесса имеют приоритет. Браузер вызывает same-origin Route Handler. В тестовой инфраструктуре отдельный dotenv и временные ключи. [Settings](../apps/api/src/dealmind/core/config.py) · [Frontend config](../apps/web/src/lib/config/server.ts)

| Сервис | С хоста по шаблону | В сети Compose |
| --- | --- | --- |
| Next.js | `127.0.0.1:3000` | `web:3000` |
| FastAPI | `127.0.0.1:8000` | `api:8000` |
| PostgreSQL | `127.0.0.1:5433` | `db:5432` |
| n8n | `127.0.0.1:5678` | `n8n:5678` |

Фактическая привязка после запуска — `docker compose port api 8000` и аналогично для остальных. На проверенном стенде API опубликован на 8001, n8n на 5679. Внутренние адреса одинаковы для обоих вариантов.

## Параметры запуска

| Переменная | Потребитель | По умолчанию | Обязательность / секрет | Назначение |
| --- | --- | --- | --- | --- |
| COMPOSE_PROJECT_NAME | Compose | dealmind | Опция | Имя проекта, сеть и префикс томов. При переносе сохраните имя |
| API_HOST_PORT | Compose | 8000 | Опция | Публикация FastAPI |
| POSTGRES_HOST_PORT | Compose | 5433 | Опция | Публикация PostgreSQL |
| WEB_HOST_PORT | Compose | 3000 | Опция | Публикация Next.js |
| N8N_HOST_PORT | Compose | 5678 | Опция | Порт редактора и база публичных локальных URL n8n |
| APP_ENV | FastAPI | local | Опция | local, test или production |
| APP_LOG_LEVEL | FastAPI | INFO | Опция | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| APP_CORS_ORIGINS | FastAPI | `[]` в Settings и Compose fallback | Опция | JSON-массив полных origins. Шаблон разрешает localhost и 127.0.0.1 на 3000 |
| POSTGRES_DB | PostgreSQL / Compose | dealmind | Опция | Имя начальной БД и источник APP_DB_NAME |
| POSTGRES_USER | PostgreSQL / Compose | dealmind | Опция | Начальная роль и источник APP_DB_USER |
| POSTGRES_PASSWORD | PostgreSQL / Compose | отсутствует | Обязательна в Compose, секрет | Пароль и источник APP_DB_PASSWORD. Смена .env не меняет пароль существующей роли |
| APP_DB_HOST | FastAPI / Alembic | 127.0.0.1 на хосте, db в Compose | Явно в production | Хост PostgreSQL |
| APP_DB_PORT | FastAPI / Alembic | 5433 на хосте, 5432 в Compose | Явно в production | Порт 1–65535 |
| APP_DB_NAME | FastAPI / Alembic | dealmind | Явно в production | База подключения |
| APP_DB_USER | FastAPI / Alembic | dealmind | Явно в production | Роль подключения |
| APP_DB_PASSWORD | FastAPI / Alembic | отсутствует вне Compose | Секрет, обязателен в production и для подключения | В local/test без пароля API обслуживает health и сообщает not_ready для БД |
| APP_DB_POOL_SIZE | FastAPI | 5 | Опция | Размер пула, >0 |
| APP_DB_MAX_OVERFLOW | FastAPI | 5 | Опция | Дополнительные соединения, ≥0 |
| APP_DB_POOL_TIMEOUT | FastAPI | 5 с | Опция | Положительный срок ожидания места в пуле |
| APP_DB_CONNECT_TIMEOUT | FastAPI | 3 с | Опция | Положительный целый таймаут соединения |
| APP_DB_HEALTH_TIMEOUT | FastAPI | 5 с | Опция | Общий предел пробы readiness |
| API_BASE_URL | Next.js server | http://127.0.0.1:8000 вне Docker, http://api:8000 в Compose | Опция | HTTP(S) origin без пути, query или credentials |
| API_REQUEST_TIMEOUT_MS | Next.js server | 8000 мс | Опция | Целое число от 1 до 60000, действует до чтения тела |
| N8N_ENCRYPTION_KEY | n8n | отсутствует | Обязательна в Compose, секрет | Устойчивый ключ шифрования credentials, сохраните для восстановления |
| N8N_HOST / N8N_PORT / N8N_PROTOCOL | n8n | 127.0.0.1 / 5678 / http | Заданы в Compose | Настройки локального редактора |
| N8N_EDITOR_BASE_URL / WEBHOOK_URL | n8n | http://127.0.0.1:5678 и тот же URL с завершающим / | Вычисляются Compose | Используют фактический N8N_HOST_PORT |
| N8N_DIAGNOSTICS_ENABLED | n8n | false в Compose | Задана | Отключает отправку диагностики n8n |
| GENERIC_TIMEZONE / TZ | n8n | UTC | Опции | Часовой пояс n8n и процесса |

## Инструменты сборки и тестов

| Переменная | Где и когда используется | Значение и назначение |
| --- | --- | --- |
| DEALMIND_TEST_DB_HOST / DEALMIND_TEST_DB_PORT | Выделенный проект DM-007 | По умолчанию 127.0.0.1 / 55433. Fixture сверяет порт с Docker |
| DEALMIND_TEST_DB_NAME / DEALMIND_TEST_DB_USER | DB suite | Стандартное имя и роль dealmind_test, проверяются защитной fixture |
| DEALMIND_TEST_DB_PASSWORD | Тестовый PostgreSQL и pytest | Секрет при переопределении. Только отдельная база, публичный тестовый fallback задан в test Compose |
| CI_FIXTURE_PORT | CI-профиль invalid-response | 8000 по умолчанию, 8001 для сценария отказа TCP |
| N8N_RUNNERS_BROKER_PORT | Отдельное исполнение n8n CLI | Скрипт задаёт 5680, чтобы второй broker не занял порт основного процесса |
| GITHUB_ACTIONS / GITHUB_RUN_ID / GITHUB_RUN_ATTEMPT | GitHub runner | Метаданные попытки определяют тестовый проект. При локальном прогоне создаётся уникальное имя |
| RUNNER_TEMP / RESULTS | CI | Временный каталог runner и JSON результатов зависимостей у итогового gate |
| NEXT_TELEMETRY_DISABLED | Web build / CI | 1 для сборки и тестов |
| NODE_ENV / HOSTNAME / PORT | Web runtime image | production / 0.0.0.0 / 3000 для standalone-сервера |
| UV_PYTHON_DOWNLOADS / UV_LINK_MODE | API builder image | never / copy, используются установленный Python и копирование зависимостей |
| PYTHONDONTWRITEBYTECODE / PYTHONUNBUFFERED | API runtime image | 1 / 1 для байткода и вывода процесса |
| MSYS_NO_PATHCONV / MSYS2_ARG_CONV_EXCL | Тестовый shell на Windows | Скрипт Compose отключает преобразование путей внутри аргументов контейнера |

Тестовый dotenv формируется программно из шаблона. Для `POSTGRES_PASSWORD` и `N8N_ENCRYPTION_KEY` нужны независимые значения. Права внешней CRM, Telegram и LLM появятся со своими интеграциями. [Изолированная топология](../infra/docker/README.md) · [Реализация CI](../scripts/ci_stack.py)
