# DealMind · Локальное окружение Docker

С DM-008 Compose запускает четыре Linux-контейнера. Web стартует независимо и читает диагностику FastAPI через общую сеть. Для API используется существующий пакет DM-004. С DM-007 Compose запускает API после успешного `pg_isready` сервиса db. n8n использует свою SQLite и стартует независимо. `docker compose up --wait` ждёт проверок каждого сервиса. [Подготовка .env и первый запуск](../../README.md#local-development-with-docker)

| Сервис / образ | Из контейнера в общей сети | С хоста по умолчанию | Постоянные данные и проверка |
| --- | --- | --- | --- |
| `web` · локальный `dealmind-web:0.1.0` | `http://web:3000` | `http://127.0.0.1:3000` | Standalone без тома. Node.js проверяет собственный `/api/health`. |
| `api` · локальный `dealmind-api:0.1.0` | `http://api:8000` | `http://127.0.0.1:8000/docs` | Контейнер без состояния. Health check делает HTTP GET через Python. |
| `db` · `pgvector/pgvector:0.8.7-pg17-trixie` | `db:5432` | `127.0.0.1:5433` | `postgres_data` в `/var/lib/postgresql/data`. Готовность проверяет `pg_isready` по TCP. |
| `n8n` · `n8nio/n8n:2.48.8` | `http://n8n:5678` | `http://127.0.0.1:5678` | `n8n_data` в `/home/node/.n8n`. Встроенный Node.js проверяет HTTP `/healthz/readiness`. |

## Запуск и обслуживание

Из корня проекта выполните команды ниже. Вместе с включённым Engine требуется Compose с поддержкой `--wait`. В корневом `.env` должны быть заданы пароль PostgreSQL и отдельный постоянный ключ n8n. Шаблон содержит пустые поля для обоих секретов. Вывод полной развёрнутой конфигурации может содержать их значения.

```shell
docker compose config --quiet
docker compose up -d --wait db
docker compose build api web
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait
docker compose ps
docker compose port web 3000
docker compose port api 8000
docker compose port db 5432
docker compose port n8n 5678
docker compose logs --tail 50 api
```

`docker compose stop` останавливает контейнеры. `docker compose down` также убирает контейнеры и сеть проекта. После обеих команд `docker compose up -d --wait` снова использует именованные тома. **Команда `docker compose down -v` удаляет тома и их содержимое.** Для проверки работоспособности и для обновления схемы она не требуется.

## PostgreSQL и pgvector

Для общей проверки HTTP, SQL и связи n8n → API из корня проекта выполните `bash scripts/smoke_infra.sh`. Нужны Bash, curl и Docker Compose. На Windows подойдёт Git Bash или WSL с доступом к Docker Desktop. Скрипт определяет опубликованные порты через Compose и только читает данные.

Подключитесь из корня проекта к БД с именами из среды контейнера. Одинарные кавычки в командах подходят для PowerShell и Bash.

```shell
docker compose exec db sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

В открывшемся psql выполните

```sql
SELECT 1;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT '[1,0,0]'::vector(3) <-> '[0,1,0]'::vector(3) AS distance;
```

Ожидаются одна строка с расширением `vector` и расстояние около `1.41421356`. Для выхода из psql введите `\q`. Внешнему SQL-клиенту укажите опубликованный порт, базу и учётные данные из `.env`.

Init-каталог смонтирован только для чтения. PostgreSQL выполняет `001-enable-vector.sql` при первоначальной инициализации пустого тома. При подключении ранее созданного тома сначала проверьте расширение в нужной базе. Если оно отсутствует, выполните там `CREATE EXTENSION IF NOT EXISTS vector;` пользователем с соответствующими правами. Переменные `POSTGRES_*` задают начальную конфигурацию пустого тома. Изменение пароля существующей роли выполняется средствами PostgreSQL.

## n8n и сеть

Откройте редактор по опубликованному адресу и создайте владельца через штатную форму n8n. В локальном режиме n8n использует свою SQLite. Ключ `N8N_ENCRYPTION_KEY` должен оставаться тем же после перезапуска и восстановления данных. Храните резервные копии тома и ключа. Сервисы находят друг друга по DNS Compose на bridge-сети `dealmind-network`. Смена порта хоста не меняет адрес назначения внутри сети.

Проверка сетевого запроса из n8n к API без создания workflow

```shell
docker compose exec -T n8n node -e "fetch('http://api:8000/api/v1/health').then(async r => { if (!r.ok) process.exit(1); console.log(await r.json()) })"
```

## Границы и обновление образов

Сеть и тома имеют префикс имени проекта (`dealmind` по умолчанию). Хост-порты привязаны к loopback IPv4, Docker socket не монтируется. Для API один базовый Python 3.12.13 slim используется в обеих стадиях сборки, uv 0.11.0 остаётся в builder. Runtime запускается с UID 10001. Реестр, тег и digest внешних образов закреплены в Compose и Dockerfile. При обновлении сверяйте официальный тег, digest multi-arch manifest и наличие платформы машины, затем повторяйте проверки HTTP, SQL и сохранности данных. [Образы pgvector](https://github.com/pgvector/pgvector#docker) · [uv в Docker](https://docs.astral.sh/uv/guides/integration/docker/) · [Образы n8n](https://docs.n8n.io/hosting/installation/docker/)

Окружение предназначено для локальной разработки. API подключается к `db:5432` по Psycopg 3. Compose передаёт ему имя БД, роль и пароль из `POSTGRES_*`. Для клиента на хосте адрес по умолчанию `127.0.0.1:5433`. `/api/v1/ready` выполняет `SELECT 1`, а ревизию проверяет отдельная команда `docker compose run --rm --no-deps api alembic current`. Для публичного доступа потребуются отдельные решения по TLS, доступу и резервным копиям.

## Отдельная PostgreSQL для тестов

Из корня запустите `docker compose -p dealmind-db-test -f infra/docker/postgres/compose.test.yml up -d --wait`. У проекта отдельные сеть, том `dealmind-db-test_test_postgres_data` и хост-порт `127.0.0.1:55433`. Запуск `pytest -m database` проверяет Docker labels, порт, том и идентификатор кластера перед транзакциями, миграциями и временной остановкой тестового контейнера. Завершив работу, можно остановить тестовую БД командой `docker compose -p dealmind-db-test -f infra/docker/postgres/compose.test.yml stop`. [Команды и правила изоляции](../../apps/api/README.md#database-architecture)

## Устранение ошибок

| Симптом | Что проверить |
| --- | --- |
| Нет связи с daemon | Запустите Docker Desktop, проверьте `docker context show` и `docker info`. Для этих образов нужен Linux Engine. |
| Порт занят | Измените соответствующий `*_HOST_PORT` в `.env`. Снова выполните `docker compose up -d --wait`. |
| Compose требует пароль или encryption key | Проверьте корневой `.env` и выполните `docker compose config --quiet`. При восстановлении существующего n8n используйте прежний ключ. |
| БД отвергает пароль или нет расширения | Проверьте целевую БД и возраст тома. Используйте действующую роль, а расширение включите вручную командой выше. |
| Ошибка mount или доступа к init-файлу | Проверьте путь `infra/docker/postgres/init` и доступ Docker Desktop к рабочему каталогу. В Docker не должны попадать локальные файлы данных PostgreSQL. |
| Сборка или pull завершились ошибкой | Проверьте доступ к реестрам и PyPI, платформу образа, свободное место и актуальность `uv.lock`. Полный лог сборки доступен через `docker compose --progress plain build api`. |
| Контейнер unhealthy или завершился с кодом 137 | Сверьте `docker compose ps -a`, последние логи сервиса, доступную Docker память и место на диске. Проверьте смонтированный том перед восстановлением. |
