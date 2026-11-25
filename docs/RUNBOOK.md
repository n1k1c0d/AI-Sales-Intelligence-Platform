# Эксплуатация локального DealMind

Все команды Docker и Git ниже выполняются в корне репозитория. Команды приложений имеют отдельную рабочую директорию. В Windows подходят PowerShell и Docker Desktop с Linux-контейнерами. Для `.sh` используйте Git Bash или WSL с доступом к тому же Engine.

## Первый запуск

Для Docker-only нужны Git, Engine и Compose с `up --wait`. Для изолированных проверок нужна поддержка `!override` (Compose 2.24.4+), Bash, curl и Python. Проверенные версии локальной разработки — Python 3.12.13 с uv 0.11.0 и Node.js 24.22.3 с npm 11.19.1. Dockerfiles содержат версии для контейнерной сборки.

1. В каталоге для проектов выполните `git clone --branch dev https://github.com/n1k1c0d/AI-Sales-Intelligence-Platform.git dealmind` и `cd dealmind`. В существующем checkout проверьте `git rev-parse --show-toplevel` и `git status --short --branch`.
2. В новом клоне создайте `.env` по `.env.example`. В PowerShell выполните `if (!(Test-Path .env)) { Copy-Item .env.example .env }`, в Bash — `cp -n .env.example .env`. Получите у генератора паролей два независимых случайных секрета и укажите их в `POSTGRES_PASSWORD` и `N8N_ENCRYPTION_KEY`. Для существующих томов используйте прежние значения.
3. Проверьте `docker version`, `docker compose version` и `docker compose config --quiet`. Если нужный loopback-порт занят, измените соответствующий `*_HOST_PORT` в `.env`. [Настройки и адреса](ENVIRONMENT.md)
4. Соберите образы, дождитесь базы, примените миграции и запустите остальные сервисы:

```shell
docker compose build api web
docker compose up -d --wait db
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait
docker compose ps
```

5. У четырёх сервисов ожидается healthy. Проверьте liveness, readiness и System Overview по адресам из `docker compose ps`. Из корня `bash scripts/smoke_infra.sh` проверит HTTP, SQL, pgvector, UI и Docker DNS. Если healthchecks не прошли, переходите к диагностике ниже.
6. При первой настройке n8n владелец открывает редактор по опубликованному порту и проходит локальный onboarding. Импортируйте workflow и выполните ручную проверку по разделу n8n.

## Ежедневная разработка

| Задача | Команды из корня | Эффект |
| --- | --- | --- |
| Запустить / проверить | `docker compose up -d --wait`, `docker compose ps` | Возвращаются сервисы этого проекта |
| Последние события | `docker compose logs --tail=100 api` | Подставьте также web, db или n8n; используйте --follow при наблюдении |
| Перезапустить процесс | `docker compose restart api` или `docker compose restart web` | Кратковременный перерыв. При изменении окружения нужен recreate через up |
| Подхватить изменённые исходники | `docker compose up -d --build --no-deps --wait api` или аналогично web | Обновляется только выбранный сервис |
| Приостановить | `docker compose stop` | Контейнеры, сеть и данные сохранены |
| Убрать контейнеры | `docker compose down` | Снимает контейнеры и сеть проекта, именованные тома сохраняются |

**Опасная операция.** Флаг `-v` у `docker compose down` удаляет именованные тома. Для обычной остановки и диагностики используйте команды из таблицы.

Для разработки на хосте из `apps/api` выполните `uv sync --locked` и `uv run --locked uvicorn dealmind.main:app --reload --no-access-log`. В Windows добавьте `--loop asyncio:SelectorEventLoop` к команде Uvicorn, чтобы Psycopg мог обслуживать асинхронное подключение. [Команда запуска API](../apps/api/README.md). Для готовности БД экспортируйте соответствующие `APP_DB_*` в процесс. Из `apps/web` — `npm ci` и `npm run dev`. Укажите `API_BASE_URL` с фактическим опубликованным портом API, если он отличается от 8000. Выберите свободные порты при одновременной работе с Compose. [Тесты и команды по компонентам](TEST_STRATEGY.md)

Если на Windows `uv sync --locked` завершается с `os error 396` при создании hardlink, выполните в `apps/api` команду `uv sync --locked --link-mode copy`. Она устанавливает те же версии из lockfile. Проверьте импорт командой `uv run --locked python -c "from dealmind.main import app; print(app.title)"`. Ожидаемый вывод — `DealMind API`. Если команда `python` в корне открывает Windows Store, запустите проверку путей через установленный uv: `uv run --no-project --python 3.12 python scripts/check_repository.py`.

## Миграции и pgvector

```shell
docker compose run --rm --no-deps api alembic current
docker compose run --rm --no-deps api alembic heads
docker compose exec db sh -c 'exec psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

В psql выполните `SELECT extversion FROM pg_extension WHERE extname = 'vector';` и `SELECT version_num FROM alembic_version;`. Для выхода — `\q`. На baseline ожидаются pgvector 0.8.7 и `0001 (head)` в Alembic. Перед обновлением проверьте целевую БД и историю миграций, при наличии ценных данных подготовьте резервную копию. Из корня `docker compose run --rm --no-deps api alembic upgrade head` приводит схему к текущей версии. Downgrade проверяется только в отдельной тестовой БД. Для основной БД он требует отдельного плана восстановления. [Модель данных](DATA_MODEL.md)

## HTTP и Request ID

В PowerShell из корня:

```powershell
$api = 'http://' + (docker compose port api 8000).Trim()
$web = 'http://' + (docker compose port web 3000).Trim()
curl.exe -i "$api/api/v1/health"
curl.exe -i "$api/api/v1/ready"
curl.exe -i "$web/api/health"
curl.exe -i "$web/api/system/status"
$requestId = [guid]::NewGuid().ToString()
curl.exe -i -H "X-Request-ID: $requestId" "$api/api/v1/health"
docker compose logs --tail=200 api | Select-String -SimpleMatch $requestId
```

В Bash получите адрес через `api="http://$(docker compose port api 8000)"` и вызовите `curl -i "$api/api/v1/ready"`. Сопоставьте ответный UUID с полями `http_route`, `status_code` и `duration_ms` в событии `http.request.completed`. Это событие уровня INFO. Web health подтверждает доступность Next.js, а ready проверяет реальное подключение API к БД. [Структуры ответов](API_CONTRACTS.md)

## n8n

Откройте адрес из `docker compose port n8n 5678` через HTTP. После входа сначала найдите **DealMind — System Health Check** в списке workflows. При первом импорте используйте Import from File и выберите `automations/n8n/workflows/system-health-check.json`. Для импорта через CLI см. [проверенные команды](../automations/n8n/workflows/system-health-check.md#13-import--export).

Запустите Manual Trigger через Execute Workflow. В Executions выберите запуск, затем конечный узел и OUTPUT → JSON. Проверьте `overall_status`, `services` и `errors`. Для связи с FastAPI найдите оба `services.*.request_id` по очереди в логах API. При экспорте изменённого графа проверьте IDs узлов, связи и фиксированные URL. Уберите pinData, внутренние поля владельца и credentials перед сохранением в Git. Запустите `python scripts/validate_n8n_workflow.py`. Повторный импорт переносимого файла может создать второй workflow с тем же именем. Храните прежний ключ шифрования для существующего тома.

## GitHub Actions

В репозитории откройте Actions → DealMind CI → запуск с нужными веткой и SHA. В Summary проверьте результаты шести jobs и `CI Gate`. При сбое откройте первый упавший step, скачайте соответствующий JUnit/XML или JSON в Artifacts и повторите команду локально. Срок хранения артефактов — семь дней. Re-run failed jobs подходит при временном сетевом сбое; дефект кода требует исправления и нового прогона. Права на перезапуск определяет GitHub. [Подтверждённый запуск DM-010](https://github.com/n1k1c0d/AI-Sales-Intelligence-Platform/actions/runs/45515913261) · [Матрица тестов](TEST_STRATEGY.md)

## Диагностика

| Признак | Первая проверка и безопасное исправление | Когда остановиться |
| --- | --- | --- |
| Docker CLI сообщает об отсутствии Engine | `docker info`, `docker context show`, запустите нужный Engine и снова проверьте ps | Контекст указывает на чужую машину |
| API не отвечает | `docker compose ps -a` → логи api → фактический port; пересоберите при изменении исходников | Повторяется startup error |
| Health 200, ready 503 | Прочитайте checks, логи db/api, pg_isready; поднимите штатную db и повторите запрос | Нужны смена роли, пароль или вмешательство в данные |
| PostgreSQL connection refused | Сверьте TCP-порт хоста и db:5432 из контейнера, состояние и сеть | Адрес ведёт в неожиданный кластер |
| Отсутствует vector | Проверьте pg_extension и current; используйте закреплённый образ pgvector и штатный upgrade на верной БД | Нужна замена БД или расширения с зависимостями |
| Ошибка миграции | Сверьте current, heads, history и выбранную БД с Git-версией | Неизвестная ревизия, несколько heads или требуется downgrade |
| Frontend показывает Unknown | Сравните /api/system/status с двумя пробами API, проверьте API_BASE_URL и схему | Валидный ответ стабильно отвергается клиентом |
| n8n не видит API | Сверьте общий Compose project и `http://api:8000` в Initialize Context; выполните smoke | Контейнеры принадлежат разным проектам по неизвестной причине |
| Импорт workflow завершается ошибкой | Сверьте n8n 2.48.8, JSON из Git, вывод валидатора и list:workflow | Для импорта запрашиваются посторонние credentials |
| Workflow timeout | Посмотрите последний узел, execution ID, HTTP Request IDs и длительность readiness | Продолжаются таймауты при доступных сервисах |
| CI красный | Откройте упавший job для нужного SHA, повторите команду с lockfile | Локальный результат расходится с повторным запуском runner |
| Python import error | Проверьте рабочую папку apps/api, Python 3.12, выполните `uv sync --locked` | Lockfile действительно требует изменения |
| npm ci не проходит | В apps/web сверяйте Node 24, npm 11 и пару package.json / package-lock.json, затем повторите установку | Манифест и lockfile расходятся в Git |
| Порт занят | Сверьте `docker compose ps` и слушателя (`Get-NetTCPConnection` в Windows); задайте свободный host port в .env, затем up | Порт принадлежит неизвестному сервису |
| После переноса пропали данные или импорты | Сверьте Git root, имя проекта, Engine и владельца томов; выполните порядок ниже | Видны пустые тома вместо ожидаемых |

## Перенос рабочей папки

1. Запишите `docker context show`, имя проекта, контейнеры и имена томов через `docker compose ps` и `docker volume ls`. Остановите текущий проект через `docker compose stop`.
2. Переместите папку целиком, включая скрытые `.git`, `.env` и незакоммиченные файлы. Откройте её новое расположение в Codex. Сверьте `git rev-parse --show-toplevel`, ветку и `git status`.
3. Из `apps/api` проверьте `uv run --locked python --version` и импорт пакета. Если виртуальная среда ссылается на старое место, закройте использующие процессы, переименуйте только локальную `.venv` в резервную папку вне Git, выполните `uv sync --locked` и проверьте импорт заново.
4. В `apps/web` проверьте Node и `npm run typecheck`. При проблемах восстановите зависимости через `npm ci`. Верните прежние `COMPOSE_PROJECT_NAME` и Docker context.
5. На том же Engine проверьте метки `com.docker.compose.project` и `com.docker.compose.volume` для сохранённых именованных томов через `docker volume inspect`. Запускайте сервисы лишь после сверки владельца и имени. Проверьте readiness и прежние workflows. На другом Engine тома автоматически не переезжают: используйте отдельно подготовленные резервные копии.

## Резервные копии и восстановление

PostgreSQL хранит данные в `postgres_data`, SQLite, настройки и историю n8n — в `n8n_data`. Именованный том переживает пересоздание контейнера, но остаётся на том же диске и Engine. Для PostgreSQL предусмотрите логическую копию через pg_dump и проверку pg_restore в отдельной пустой БД. Для n8n нужен согласованный снимок остановленного хранилища и исходный encryption key, защищённый отдельно. JSON-экспорт сохраняет определение графа. Credentials, настройки экземпляра и execution history требуют собственной копии. `.env` храните защищённо вне Git.

В DM-011 восстановление backups не репетировалось. Перед восстановлением ценных данных подтвердите источник копии и целевую изолированную среду. Владелец определит периодичность, сроки хранения и критерии восстановления на этапе deployment.
