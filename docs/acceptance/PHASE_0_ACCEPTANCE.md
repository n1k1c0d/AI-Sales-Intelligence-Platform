# PHASE 0 · Техническая приёмка DealMind

**Вердикт — ACCEPTED. DM-012 — DONE.** Из удалённого клона `dev` собраны API и web, применена миграция и запущены четыре сервиса. Все восемь сценариев интеграции прошли. PostgreSQL сохранил контрольную запись, n8n — исходный workflow и историю после пересоздания контейнеров. Для этого же коммита GitHub подтвердил `CI Gate`. Следующий шаг — независимое ревью. [Численные результаты](evidence.json) · [Индекс для ревьюера](PHASE_0_REVIEW_INDEX.md)

## Проверяемая версия и среда

| Параметр | Наблюдение |
| --- | --- |
| Дата | 25 ноября 2026 года. В HTTP, логах и execution reports используется UTC. |
| Baseline | `382730ceee04b641f44a7fc77394778ae3bb2d87`, ветка `dev`. До начала работы основной checkout был чистым и совпадал с `origin/dev`. |
| Удалённый источник | [Репозиторий](https://github.com/n1k1c0d/AI-Sales-Intelligence-Platform), 162 отслеживаемых файла, 1 943 579 байт содержимого. `git fsck` и проверка путей прошли. |
| Среда | Windows, Git 2.53.0.windows.2, Docker Engine 29.6.2, Compose 5.3.1, Linux-контейнеры. CPython 3.12.13, uv 0.11.0, Node 24.22.3, npm 11.19.1, Next.js 16.4.6, Edge 158.0.4370.33. |
| Граница проверки | Исполняемый код, lockfiles, Docker и CI взяты из baseline. Отчёт, снимки и правки руководств созданы позже и проверены в рабочей копии `dev`. У этого набора пока нет отдельного CI run. |

## Прослеживаемость задач

| Задача | Ожидаемый результат | Свидетельство и граница | Итог |
| --- | --- | --- | --- |
| [DM-001](../tasks/DM-001.md) | Фундамент и границы MVP | Три ADR, [архитектура](../ARCHITECTURE.md), фактическая цепочка web/n8n → API → БД | PASS |
| [DM-002](../tasks/DM-002.md) | Структура репозитория | `git ls-files`, 162 пути baseline, [проверка структуры](../../scripts/check_repository.py) | PASS |
| [DM-003](../tasks/DM-003.md) | Python package | uv lock, чистая установка, импорт, wheel/sdist с 23 файлами пакета | PASS |
| [DM-004](../tasks/DM-004.md) | API и ошибки | Реальные health, ready, 404, 405 и [ASGI tests](../../apps/api/tests/integration/test_errors.py) для 422/500 | PASS |
| [DM-005](../tasks/DM-005.md) | Контейнерный стек | Compose config/build, 4 healthy, SQL, HTTP, [smoke](../../scripts/smoke_infra.sh) | PASS |
| [DM-006](../tasks/DM-006.md) | Настройки, логирование | Валидный и неверный ID, допустимый и запрещённый origin, событие запроса, тест неверного пароля | PASS |
| [DM-007](../tasks/DM-007.md) | Async DB и миграции | 4 реальных DB tests, один head `0001`, pgvector, commit/rollback и pool recovery | PASS |
| [DM-008](../tasks/DM-008.md) | Диагностика Next.js | Edge, реальные пробы BFF, refresh, три ширины, четыре PNG | PASS |
| [DM-009](../tasks/DM-009.md) | Ручной workflow n8n | Свежий импорт, исполнения 1–13, независимые UUID, повторный импорт, сохранение истории | PASS |
| [DM-010](../tasks/DM-010.md) | Quality gates | Локальные suites, семь успешных jobs и пять наборов артефактов для `382730c` | PASS |
| [DM-011](../tasks/DM-011.md) | Руководства разработчика | Пройдены startup, миграции, диагностика, импорт и shutdown. Уточнены две особенности запуска Windows | PASS |
| [DM-012](../tasks/DM-012.md) | Комплексная интеграция и передача | Матрица ниже, реестр дефектов, результаты и индекс ревью | PASS |

## Чистое клонирование и воспроизводимость

`git clone --branch dev --single-branch` из GitHub создал новый каталог за пределами основного checkout. До установки в нём отсутствовали `.env`, `.venv`, `node_modules` и `.next`. После проверок `git status --porcelain` в клоне остался пустым. Настройки получены из шаблона, пароль БД и ключ n8n сгенерированы отдельно. [Переменные](../ENVIRONMENT.md)

`uv lock --check` прошёл. Первый `uv sync --locked` остановился из-за Windows hardlinks. С режимом `copy` установились все 43 пакета. В другой пустой виртуальной среде повторены установка и импорт по исправленной инструкции. `npm ci` добавил 432 пакета. Оба lockfile сохранились. Локальная production-сборка Next.js прошла с недоступным адресом backend. [Разбор первоначальной ошибки](PHASE_0_DEFECTS.md)

## Архитектура и инфраструктура

FastAPI создаёт engine в lifespan и освобождает его при завершении. Сессия выделяется на сценарий, границу транзакции выбирает вызывающий код. HTTP routes передают инфраструктурные пробы слою БД. Миграции выполняет Alembic. Серверный клиент Next.js проверяет ответы FastAPI по Zod, клиентский компонент читает same-origin BFF. n8n вызывает два фиксированных HTTP endpoint. У frontend и workflow нет собственного SQL-доступа к прикладной БД. В PostgreSQL только миграционный baseline. Интерфейсы CRM, аналитики, Risk Engine, RAG и AI Agent запланированы на следующие фазы. [ADR и точки входа](PHASE_0_REVIEW_INDEX.md)

Проект `dealmind-acceptance-b79724bc3` использовал один собственный bridge и именованные `postgres_data` и `n8n_data` с префиксом проекта. Сверены Docker labels проекта, контейнеров, сети и томов, а также реальный mount destination и имя БД. Порты на `127.0.0.1` — API 18000, PostgreSQL 15433, web 13000, n8n 15678. Базовый Compose объединялся с CI overlay и временным переопределением опубликованных портов. Образы API и web имели отдельные теги.

Последовательность запуска — `config --quiet`, `build api web`, `up -d --wait db`, `run --rm --no-deps api alembic upgrade head`, запуск остальных сервисов и ожидание healthchecks. Все четыре достигли `healthy`. Контексты сборки получены из клона, кеш Docker разрешён. Образы закреплены digest: Python 3.12.13 slim trixie, Node 24.22.3 bookworm slim, uv 0.11.0, pgvector 0.8.7 на PostgreSQL 17, n8n 2.48.8. UID процессов API/web/n8n — 10001/1000/1000. В runtime подтверждены миграции API и standalone web. [Smoke и наблюдения](evidence.json)

## PostgreSQL, миграции и сохранность

PostgreSQL 17.12, БД `dealmind_test`, `SELECT 1` → 1, расширение `vector` версии 0.8.7. Евклидово расстояние между ортогональными единичными векторами — `1.4142135623730951`. Вывод `alembic heads` и `current` совпал — `0001 (head)`. Повторный upgrade успешен. Отдельный DB suite проверил downgrade/upgrade с сохранением расширения, видимость commit независимой сессии, rollback при ошибке и возвращение соединений в пул. [Database tests](../../apps/api/tests/integration/database/)

На изолированном стенде одна синтетическая строка пережила отдельный рестарт БД, остановку и запуск всего Compose и принудительное пересоздание db/n8n. Изменились container IDs, сохранились имена томов и PostgreSQL system identifier `7712026996257427494`. Контрольный объект удалён после проверки. Итоговый список public-таблиц — `alembic_version`. В n8n до рестартов сохранились executions 1–11, после дополнительных запусков и пересоздания — 1–13. [Идентификаторы и история](evidence.json)

## Backend и наблюдаемость

| Запрос или условие | Фактический результат |
| --- | --- |
| `GET /api/v1/health` | 200, `{"status":"ok","service":"dealmind-api"}`, включая время отказа PostgreSQL |
| `GET /api/v1/ready`, БД доступна | 200, `{"status":"ready","checks":{"application":"ok","database":"ok"}}` |
| Тот же запрос, БД остановлена | 503, `{"status":"not_ready","checks":{"application":"ok","database":"not_ready"}}` |
| Неверный пароль | Реальный Windows Uvicorn с SelectorEventLoop вернул 503, с верным получил 200. |
| OpenAPI и Swagger | HTTP 200 для обоих. `DealMind API` версии `0.1.0`, две операции GET и шесть компонентных схем. Readiness объявляет 503. |
| Ошибки | 404 `NOT_FOUND` и 405 `METHOD_NOT_ALLOWED` с `details:null`. Действующие ASGI-тесты подтвердили 422/500, заголовки и безопасный ответ. |
| CORS и UUID | Разрешённый origin получил preflight 200 и точный allow-origin, посторонний — 400 без него. Клиентский UUID возвращён, неправильный заменён. |

В исполнении n8n №1 запрос health `f908e1c5-0439-4aa2-aa0b-55405e839b74` и запрос ready `6189a8f2-c8de-4e0e-8a43-283d795a51c2` по одному разу обнаружены в JSON-событиях `http.request.completed`. Сверены route, статус, метод и длительность. Оба запроса для исполнения с 503 также сопоставлены. Синтетические значения Authorization, Cookie, тела запроса и тестовые секреты отсутствовали в проверенных логах. [HTTP-ответы и события](evidence.json)

## Frontend и браузер

В Edge открывалась реальная страница System Overview. При нажатии Enter на `Refresh Status` сервер получил один новый запрос, кнопка на время проверки отключилась, обновились `checkedAt` и доступные Request IDs. Для наблюдения состояния загрузки браузер замедлял отправку одного реального запроса. При возврате API и БД панель обновилась до operational. На ширинах 375/768/1440 px отображались 1/2/4 колонки, ширина документа совпала с viewport. Зафиксированы четыре карточки, видимый клавиатурный фокус, загрузка статических ресурсов и отсутствие ошибок console/pageerror в проверенных состояниях. Действующий интерфейс англоязычный. [Desktop](assets/operational-1440.png) · [Отказ БД](assets/degraded-1440.png) · [Отказ API](assets/unavailable-1440.png) · [Mobile](assets/operational-375.png)

## n8n и классификация ошибок

В пустом n8n CLI импортировал неактивный System Health Check. Экспорт обратно подтвердил узлы, версии, связи и настройки, валидатор проверил отсутствие credentials и pinned data. Исходный workflow ID — `jFggox10NQHWv5uR`. Реальные исполнения №1 и №2 дали разные UUID и execution IDs. Для каждого исполнения провал или успех интеграции отражён в диагностическом результате. Отдельно код узла Normalize Responses был исполнен в Node с тремя синтетическими нарушениями контракта. Неизвестная ошибка, отсутствие HTTP-статуса и пустой список items вызвали ожидаемые исключения. [Граф и контракт](../../automations/n8n/workflows/system-health-check.md)

На HTTP-узел настроено максимум две попытки, 1000 мс между ними и 8000 мс на запрос. Лимит workflow — 60 с. Контролируемый timeout обоих endpoint дал два `TIMEOUT` за 34 157 мс. Повторный импорт того же переносимого файла создал второй ID `0PYMFWBStQekmdoJ`, исходный сохранился. [Все 13 структурированных результатов](evidence.json)

## Сквозная приёмка

| Сценарий | Ожидание | Наблюдение | Итог |
| --- | --- | --- | --- |
| E2E-001 · Штатный запуск | Обе пробы 200, UI и n8n operational | Два последовательных исполнения №1/2, новые UUID, browser refresh, корреляция | PASS |
| E2E-002 · Отказ БД | Liveness 200, ready 503, degraded | Web продолжил отвечать, браузер и исполнение №3 подтвердили отказ database | PASS |
| E2E-003 · Возврат БД | Восстановление без рестарта API | Та же идентичность процесса API, маркер на месте, ready 200, UI и №4 operational | PASS |
| E2E-004 · Отказ API | Web доступен, БД unknown | API остановлен, TCP на 8000 закрыт. BFF и №5 unavailable, два NETWORK_ERROR, 2203 мс | PASS |
| E2E-005 · Возврат API | UI и workflow восстанавливаются | Без рестарта web и n8n получены HTTP 200, реальный refresh и №6 operational | PASS |
| E2E-006 · Отказ web | API, SQL и n8n независимы | Web остановлен, SQL 1, обе API-пробы 200, №7 operational. После запуска web вернул operational | PASS |
| E2E-007 · Отказ n8n | Web и API продолжают работать | При остановленном n8n BFF operational, ready 200. После запуска исходный граф выполнился, №8 | PASS |
| E2E-008 · Ошибочный upstream | Корректная классификация и ограниченное ожидание | Некорректный JSON и схема → INVALID_RESPONSE / unknown (№9). HTTP 502 → HTTP_ERROR / unknown (№10). Истечение обоих таймаутов → TIMEOUT / unavailable (№11). BFF и n8n совпали | PASS |

Ошибочный upstream работал только на изолированной сети. При остановленном API для воспроизводимого отказа TCP отдельный контейнер сохранял DNS-имя `api` без слушателя на 8000. Для проверки malformed/status/timeout использованы тестовые HTTP-ответы. В приложении отсутствуют добавленные для приёмки маршруты.

### Как повторить сценарии на отдельном стенде

1. Из свежего клона подготовьте временный env по [шаблону](../../.env.example), новые пароль и ключ, свободные loopback-порты и уникальный Compose project. Сверьте `docker compose config --quiet`, project labels, network, реальные mount names и `SELECT current_database()`. Для сборки используйте отдельные теги из [CI overlay](../../infra/docker/ci/compose.yml). Один набор параметров `--env-file`, `-p` и `-f` нужен для каждой команды.
2. Соберите api/web, запустите db, примените `alembic upgrade head`, затем запустите стек с `up -d --wait`. Передайте те же параметры в `bash scripts/smoke_infra.sh`. Импортируйте переносимый workflow по [инструкции](../../automations/n8n/workflows/system-health-check.md), получите внутренний ID через `n8n list:workflow --onlyId`.
3. Сверяйте `/api/v1/health`, `/api/v1/ready`, `/api/system/status` и результат ручного исполнения. В браузере используйте Refresh Status. Останавливайте по одному db, api, web и n8n исключительно в этом проекте, каждый раз восстанавливайте сервис и ожидайте healthcheck. По Request IDs найдите события завершения в логах api.
4. Для E2E-008 при остановленном api используйте тестовую сеть и alias `api`. Существующий [fixture](../../infra/docker/ci/invalid_api.py) отдаёт невалидный JSON и пустую схему. Для остальных двух случаев тестовый HTTP-сервер возвращал 502 с JSON или задерживал ответ на 16 секунд при таймауте клиента 8 секунд. После проверки восстановите настоящий api.
5. Для сохранности сравните один синтетический маркер, ID n8n и executions до и после `stop`, `up -d --wait` и `up -d --no-deps --force-recreate --wait db n8n`. Удалите только созданный маркер. Остановите выделенный проект командой `down` с прежними параметрами, сохранив тома. [Результат контрольного прогона](evidence.json)

## Тесты и quality gates

| Компонент | Прошли | Упали | Пропущены | Дополнительные проверки |
| --- | ---: | ---: | ---: | --- |
| Backend, кроме DB suite | 65 | 0 | 0 | Ruff check и format (47 файлов), Mypy strict (44 файла), wheel и sdist |
| Отдельный PostgreSQL DM-007 | 4 | 0 | 0 | JUnit подтвердил выполнение всех четырёх обязательных тестов |
| Frontend Vitest | 29 | 0 | 0 | 19 проверок контракта, 10 UI, ESLint, TypeScript strict и production build |
| n8n workflow validator | 9 | 0 | 0 | Статическая проверка экспорта и четырёх эталонов, реальные исполнения отдельно |
| **Всего автоматических тестов** | **107** | **0** | **0** | Отдельно выполнены 8 сквозных сценариев |

Backend line coverage — **94,75%**, покрыто 325 из 343 строк. В двух прогонах pytest метки `database` и `not database` делили один набор из 69 тестов. Команды для воспроизведения, каталоги JUnit и coverage перечислены в [стратегии](../TEST_STRATEGY.md) и [индексе](PHASE_0_REVIEW_INDEX.md).

## GitHub Actions

`DealMind CI`, ветка `dev`, указанный выше полный SHA. Статус `completed`, заключение `success`. Успешны `repository-checks`, `backend-quality`, `database-integration`, `frontend-quality`, `n8n-validation`, `docker-smoke` и `ci-gate` (отображается как `CI Gate`). Обязательные jobs выполнились, в YAML для них отсутствует `continue-on-error`. Проверены пять артефактов и шесть ожидаемых XML/JSON внутри них. Локальные документы и PNG текущей задачи проверены отдельно. [Запуск 45577247614](https://github.com/n1k1c0d/AI-Sales-Intelligence-Platform/actions/runs/45577247614)

## Безопасность и ограничения

Проверены Git index и достижимая история клона `dev`. Для 252 исторических blobs просмотрены признаки приватных ключей, типичных provider tokens, URL с credentials и нежелательных путей. Совпадений по этим правилам не было. Пять артефактов CI сверены по именам и проверены на сигнатуры секретов. В 12 публичных ресурсах web не обнаружены тестовые секреты и внутренний базовый URL. У четырёх контейнеров проверены loopback-порты, отсутствие privileged и Docker socket. Для 42 зафиксированных PyPI-зависимостей и npm audit известных advisories на дату проверки не найдено. Область проверки ограничена известными сигнатурами и доступными базами. [Измерения](evidence.json)

У основного проекта четыре healthy-сервиса и прежние тома. Их время старта предшествует приёмке. У acceptance project после штатной остановки осталось ноль контейнеров, два его тома сохранены. Выделенный postgres-test проекта DM-007 возвращён в исходное остановленное состояние. Пользовательские данные не считывались для побайтового сравнения.

Публичная эксплуатация потребует auth/RBAC, HTTPS, rate limiting, управления секретами и проверенной backup/restore-процедуры. Нагрузочная проверка, полный аудит безопасности и WCAG, restore на другом Docker Engine, приватные недостижимые Git-объекты и история других веток за пределами baseline в этот прогон не входили. Полное отключение Docker build cache не требовалось. Наименование `n8n · prepared` в карточке проекта является статической подписью и не измеряет доступность n8n. [Реестр дефектов](PHASE_0_DEFECTS.md)

## Дефекты и решение по фазе

Открытых P0/P1 нет. Исправлены и повторно проверены два P2 в Windows-инструкции. Открыто три P3 — язык UI в формулировке проверки, предупреждение Starlette TestClient и срок поддержки ESLint. [Шаги воспроизведения и результаты](PHASE_0_DEFECTS.md)

## Состав изменений и передача

Созданы этот отчёт, [реестр](PHASE_0_DEFECTS.md), [индекс ревью](PHASE_0_REVIEW_INDEX.md), [протокол задачи](../tasks/DM-012.md), [измерения JSON](evidence.json) и четыре PNG в [assets](assets/). Обновлены [README](../../README.md), [CHANGELOG](../../CHANGELOG.md), [PROJECT_CONTEXT](../PROJECT_CONTEXT.md), [ROADMAP](../ROADMAP.md) и [RUNBOOK](../RUNBOOK.md). Рабочие изменения документации и доказательств находятся в `dev`. Итоговый Git status содержит пять изменённых и девять новых файлов. Проверка репозитория прошла для 171 пути. Создание коммита, публикация и PR остаются у владельца. Индекс содержит инструкцию передачи `git archive` для проверенного SHA и порядок добавления более позднего отчёта.

**PHASE 0 — TECHNICALLY ACCEPTED.** Следующий шаг — независимый аудит. Следующая задача разработки — DM-101, CRM Domain Model.

Implementation requires owner approval after external Phase 0 review.

## Матрица проверок фундамента

| ID | Проверка | Статус | Основание |
| --- | --- | --- | --- |
| FND-001 | Repository structure соответствует документации | PASS | [Валидатор путей и Markdown-ссылок](../../scripts/check_repository.py) · пройден на baseline и отчёте |
| FND-002 | Git history и repository integrity проверены | PASS | [Git baseline и clean clone](evidence.json) · `git fsck`, `git ls-tree -rl HEAD` |
| FND-003 | Проверяемый commit зафиксирован | PASS | [Git baseline и clean clone](evidence.json) · `git fsck`, `git ls-tree -rl HEAD` |
| FND-004 | Fresh remote clone выполнен | PASS | [Git baseline и clean clone](evidence.json) · `git fsck`, `git ls-tree -rl HEAD` |
| FND-005 | Нет зависимости от основной рабочей папки | PASS | [Git baseline и clean clone](evidence.json) · `git fsck`, `git ls-tree -rl HEAD` |
| FND-006 | `.env.example` корректен | PASS | [Шаблон](../../.env.example) · [сверенные порты, project и изоляция](evidence.json) |
| FND-007 | Environment configuration воспроизводима | PASS | [Шаблон](../../.env.example) · [сверенные порты, project и изоляция](evidence.json) |
| FND-008 | Реальные секреты не используются | PASS | [Шаблон](../../.env.example) · [сверенные порты, project и изоляция](evidence.json) |
| FND-009 | Acceptance environment полностью изолирована | PASS | [Измерения](evidence.json) · `persistence.volumes`, `cleanup.retainedVolumes` и `cleanup.mainVolumes` |
| FND-010 | Python dependencies устанавливаются | PASS | [uv.lock](../../apps/api/uv.lock) · `uv lock --check`, чистый `uv sync --locked --link-mode copy` и импорт |
| FND-011 | uv.lock актуален | PASS | [uv.lock](../../apps/api/uv.lock) · `uv lock --check`, чистый `uv sync --locked --link-mode copy` и импорт |
| FND-012 | npm ci проходит | PASS | [package-lock](../../apps/web/package-lock.json) · `npm ci`, 432 пакета установлены, Git tree клона чист |
| FND-013 | package-lock.json не требует обновления | PASS | [package-lock](../../apps/web/package-lock.json) · `npm ci`, 432 пакета установлены, Git tree клона чист |
| FND-014 | Docker images собираются | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| FND-015 | Compose configuration валидна | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| FND-016 | PostgreSQL запускается | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| FND-017 | FastAPI запускается | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| FND-018 | Next.js запускается | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| FND-019 | n8n запускается | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| FND-020 | Docker networking работает | PASS | [Smoke](../../scripts/smoke_infra.sh) · `serviceChecks.smoke` и `portsOnIPv4Loopback` в [измерениях](evidence.json) |
| FND-021 | Persistent volumes изолированы | PASS | [Измерения](evidence.json) · `persistence.volumes`, `cleanup.retainedVolumes` и `cleanup.mainVolumes` |
| FND-022 | PostgreSQL connectivity подтверждена | PASS | [SQL и pgvector](evidence.json) · `database.facts` и `serviceChecks.smoke` |
| FND-023 | SELECT 1 выполняется | PASS | [SQL и pgvector](evidence.json) · `database.facts` и `serviceChecks.smoke` |
| FND-024 | pgvector extension доступен | PASS | [SQL и pgvector](evidence.json) · `database.facts` и `serviceChecks.smoke` |
| FND-025 | Vector operation работает | PASS | [SQL и pgvector](evidence.json) · `database.facts` и `serviceChecks.smoke` |
| FND-026 | AsyncSession работает | PASS | [Реальная проверка сессий и пула](../../apps/api/tests/integration/database/test_sessions.py) · database JUnit, 4/4 |
| FND-027 | Transaction commit работает | PASS | [Реальная проверка сессий и пула](../../apps/api/tests/integration/database/test_sessions.py) · database JUnit, 4/4 |
| FND-028 | Transaction rollback работает | PASS | [Реальная проверка сессий и пула](../../apps/api/tests/integration/database/test_sessions.py) · database JUnit, 4/4 |
| FND-029 | Connection cleanup работает | PASS | [Реальная проверка сессий и пула](../../apps/api/tests/integration/database/test_sessions.py) · database JUnit, 4/4 |
| FND-030 | Alembic upgrade проходит | PASS | [Миграции на отдельной БД](../../apps/api/tests/integration/database/test_migrations.py) · `database.alembic` в [наблюдениях](evidence.json) |
| FND-031 | Alembic current соответствует head | PASS | [Миграции на отдельной БД](../../apps/api/tests/integration/database/test_migrations.py) · `database.alembic` в [наблюдениях](evidence.json) |
| FND-032 | Повторный upgrade безопасен | PASS | [Миграции на отдельной БД](../../apps/api/tests/integration/database/test_migrations.py) · `database.alembic` в [наблюдениях](evidence.json) |
| FND-033 | Liveness возвращает 200 | PASS | [Реальные HTTP-ответы](evidence.json) · `http`, `serviceChecks.openapi` |
| FND-034 | Readiness возвращает 200 | PASS | [Реальные HTTP-ответы](evidence.json) · `http`, `serviceChecks.openapi` |
| FND-035 | Readiness возвращает 503 при недоступной БД | PASS | [При отказе БД](evidence.json) · `bff.db-outage`, исполнение №3, [скриншот](assets/degraded-1440.png) |
| FND-036 | OpenAPI доступен | PASS | [Реальные HTTP-ответы](evidence.json) · `http`, `serviceChecks.openapi` |
| FND-037 | Error contract корректен | PASS | [ASGI-тесты 404/405/422/500](../../apps/api/tests/integration/test_errors.py) · [HTTP и коды](evidence.json) |
| FND-038 | Request ID работает | PASS | [Два совпадающих события](evidence.json) · `http`, `correlation.operational`, `correlation.degraded` |
| FND-039 | CORS работает | PASS | [Preflight](evidence.json) · `http.allowed/denied`, [CORS tests](../../apps/api/tests/integration/test_cors.py) |
| FND-040 | Structured logs корректны | PASS | [Два совпадающих события](evidence.json) · `http`, `correlation.operational`, `correlation.degraded` |
| FND-041 | Главная страница доступна | PASS | [Операционный экран](assets/operational-1440.png) · [реальные ответы BFF и браузера](evidence.json) |
| FND-042 | Frontend liveness работает | PASS | [Реальные HTTP-ответы](evidence.json) · `http`, `serviceChecks.openapi` |
| FND-043 | System status получает реальные данные | PASS | [Операционный экран](assets/operational-1440.png) · [реальные ответы BFF и браузера](evidence.json) |
| FND-044 | Operational state корректен | PASS | [Операционный экран](assets/operational-1440.png) · [реальные ответы BFF и браузера](evidence.json) |
| FND-045 | Degraded state корректен | PASS | [При отказе БД](evidence.json) · `bff.db-outage`, исполнение №3, [скриншот](assets/degraded-1440.png) |
| FND-046 | Unavailable state корректен | PASS | [При отказе API](evidence.json) · `bff.api-outage`, исполнение №5, [скриншот](assets/unavailable-1440.png) |
| FND-047 | Database unknown корректен | PASS | [При отказе API](evidence.json) · `bff.api-outage`, исполнение №5, [скриншот](assets/unavailable-1440.png) |
| FND-048 | Refresh работает | PASS | [Браузер](evidence.json) · `browser.operational`, `refreshRequests = 1`, новые UUID и `checkedAt` |
| FND-049 | Responsive layout проверен | PASS | [375 px](assets/operational-375.png) · [измерения 375/768/1440 и console](evidence.json) |
| FND-050 | Browser console не содержит критических ошибок | PASS | [375 px](assets/operational-375.png) · [измерения 375/768/1440 и console](evidence.json) |
| FND-051 | Workflow JSON валиден | PASS | [Граф и валидатор](../../scripts/validate_n8n_workflow.py) · 9/9, [реальный импорт и исполнения](evidence.json) |
| FND-052 | Fresh import успешен | PASS | [Граф и валидатор](../../scripts/validate_n8n_workflow.py) · 9/9, [реальный импорт и исполнения](evidence.json) |
| FND-053 | Manual execution успешен | PASS | [Структурированные результаты](evidence.json) · `workflowRuns.operational`, `workflowRuns.repeat`, `serviceChecks.workflowSettingsMatch` |
| FND-054 | Operational result корректен | PASS | [Структурированные результаты](evidence.json) · `workflowRuns.operational`, `workflowRuns.repeat`, `serviceChecks.workflowSettingsMatch` |
| FND-055 | Readiness 503 обрабатывается | PASS | [При отказе БД](evidence.json) · `bff.db-outage`, исполнение №3, [скриншот](assets/degraded-1440.png) |
| FND-056 | Network failure обрабатывается | PASS | [При отказе API](evidence.json) · `bff.api-outage`, исполнение №5, [скриншот](assets/unavailable-1440.png) |
| FND-057 | Retry ограничен | PASS | [Настройки и фактическая длительность](evidence.json) · `serviceChecks.retries`, `workflowRuns.timeout` |
| FND-058 | Request IDs коррелируются | PASS | [Два совпадающих события](evidence.json) · `http`, `correlation.operational`, `correlation.degraded` |
| FND-059 | Execution report соответствует контракту | PASS | [Структурированные результаты](evidence.json) · `workflowRuns.operational`, `workflowRuns.repeat`, `serviceChecks.workflowSettingsMatch` |
| FND-060 | Workflow сохраняется после restart | PASS | [Восстановление n8n](evidence.json) · №8 и 13, сохранённые executions и исходный workflow ID |
| FND-061 | Database recovery подтверждена | PASS | [Восстановление БД](evidence.json) · №4, `browser.db-recovery`, контрольное значение |
| FND-062 | Backend recovery подтверждён | PASS | [Восстановление API](evidence.json) · №6, `browser.api-recovery`, HTTP 200 |
| FND-063 | Frontend restart подтверждён | PASS | [Независимость при отказе web](evidence.json) · №7, `serviceChecks.smoke` |
| FND-064 | n8n restart подтверждён | PASS | [Восстановление n8n](evidence.json) · №8 и 13, сохранённые executions и исходный workflow ID |
| FND-065 | PostgreSQL persistence подтверждена | PASS | [Сохранность](evidence.json) · `persistence`, `database.finalPublicTables`, исполнения №12–13 |
| FND-066 | Compose stop/start безопасен | PASS | [Сохранность](evidence.json) · `persistence`, `database.finalPublicTables`, исполнения №12–13 |
| FND-067 | Ruff lint проходит | PASS | [Backend quality](../../.github/workflows/ci.yml) · Ruff check/format и Mypy strict в клоне и CI |
| FND-068 | Ruff format проходит | PASS | [Backend quality](../../.github/workflows/ci.yml) · Ruff check/format и Mypy strict в клоне и CI |
| FND-069 | Mypy strict проходит | PASS | [Backend quality](../../.github/workflows/ci.yml) · Ruff check/format и Mypy strict в клоне и CI |
| FND-070 | Backend tests проходят | PASS | [JUnit и coverage](evidence.json) · `tests.backend`, 65/65 |
| FND-071 | Real database tests проходят | PASS | [Database JUnit](evidence.json) · `tests.database`, 4/4 на отдельном PostgreSQL |
| FND-072 | ESLint проходит | PASS | [Frontend quality](../../.github/workflows/ci.yml) · `npm run lint`, `npm run typecheck` |
| FND-073 | TypeScript strict проходит | PASS | [Frontend quality](../../.github/workflows/ci.yml) · `npm run lint`, `npm run typecheck` |
| FND-074 | Vitest проходит | PASS | [Vitest JUnit](evidence.json) · `tests.frontend`, 29/29 |
| FND-075 | Python build проходит | PASS | [Состав дистрибутивов](../../scripts/check_package.py) · `uv build`, 23 файла пакета в wheel/sdist |
| FND-076 | Next.js build проходит | PASS | [Web Dockerfile](../../apps/web/Dockerfile) · production build без backend, standalone smoke |
| FND-077 | n8n validator проходит | PASS | [Граф и валидатор](../../scripts/validate_n8n_workflow.py) · 9/9, [реальный импорт и исполнения](evidence.json) |
| FND-078 | Remote CI подтверждён | PASS | [GitHub Actions](https://github.com/n1k1c0d/AI-Sales-Intelligence-Platform/actions/runs/45577247614) · `382730c`, 7/7 |
| FND-079 | Нет добавленных секретов | PASS | [Безопасность](evidence.json) · `security.history`, `artifacts`, `publicAssetsExamined` |
| FND-080 | Порты привязаны к localhost | PASS | [Smoke](../../scripts/smoke_infra.sh) · `serviceChecks.smoke` и `portsOnIPv4Loopback` в [измерениях](evidence.json) |
| FND-081 | Архитектурные границы соблюдены | PASS | [Три ADR и соответствующие модули](PHASE_0_REVIEW_INDEX.md) · HTTP-топология, ownership БД |
| FND-082 | Основная инфраструктура не повреждена | PASS | [Контейнеры и тома после тестов](evidence.json) · `cleanup`, основной стек healthy |
| FND-083 | Production limitations задокументированы | PASS | [Ограничения публичной эксплуатации](PHASE_0_DEFECTS.md) |
| FND-084 | README воспроизводим | PASS | [Quick Start](../../README.md) · чистый clone, миграции и штатный smoke |
| FND-085 | AGENTS.md актуален | PASS | [Правила разработки и Git](../../AGENTS.md) · сверены пути, роли, проверки и текущая ветка |
| FND-086 | Architecture documentation актуальна | PASS | [Три ADR и соответствующие модули](PHASE_0_REVIEW_INDEX.md) · HTTP-топология, ownership БД |
| FND-087 | API contracts актуальны | PASS | [Контракты](../API_CONTRACTS.md) · сопоставлены с `http` и `serviceChecks.openapi` в [замере](evidence.json) |
| FND-088 | Runbook актуален | PASS | [Сценарии запуска, миграций, логов и остановки](../RUNBOOK.md) · [проверка исправлений](PHASE_0_DEFECTS.md) |
| FND-089 | Roadmap согласован | PASS | [Статус и внешний gate](../ROADMAP.md) |
| FND-090 | Defect register создан | PASS | [Реестр, уровень и статус](PHASE_0_DEFECTS.md) |
| FND-091 | Acceptance report создан | PASS | [Итоговый отчёт](PHASE_0_ACCEPTANCE.md) · сценарии, измерения и матрица |
| FND-092 | Review index создан | PASS | [Индекс независимого ревью](PHASE_0_REVIEW_INDEX.md) · источники, отчёты, передача |
| FND-093 | DM-012 задокументирована | PASS | [Карточка задачи DM-012](../tasks/DM-012.md) |
| FND-094 | Нет нерешённых P0/P1 blockers | PASS | [Реестр, уровень и статус](PHASE_0_DEFECTS.md) |
| FND-095 | PHASE 0 готова к независимому аудиту | PASS | [Индекс независимого ревью](PHASE_0_REVIEW_INDEX.md) · источники, отчёты, передача |

## Критерии приёмки задачи

| ID | Проверка | Статус | Основание |
| --- | --- | --- | --- |
| AC-01 | Проверяемый commit SHA зафиксирован | PASS | [Git baseline и clean clone](evidence.json) · `git fsck`, `git ls-tree -rl HEAD` |
| AC-02 | Выполнено чистое клонирование | PASS | [Git baseline и clean clone](evidence.json) · `git fsck`, `git ls-tree -rl HEAD` |
| AC-03 | Установка не зависит от основной папки проекта | PASS | [Git baseline и clean clone](evidence.json) · `git fsck`, `git ls-tree -rl HEAD` |
| AC-04 | Python dependencies воспроизводимы | PASS | [uv.lock](../../apps/api/uv.lock) · `uv lock --check`, чистый `uv sync --locked --link-mode copy` и импорт |
| AC-05 | Frontend dependencies воспроизводимы | PASS | [package-lock](../../apps/web/package-lock.json) · `npm ci`, 432 пакета установлены, Git tree клона чист |
| AC-06 | README позволяет запустить проект | PASS | [Quick Start](../../README.md) · чистый clone, миграции и штатный smoke |
| AC-07 | Acceptance environment изолирована | PASS | [Измерения](evidence.json) · `persistence.volumes`, `cleanup.retainedVolumes` и `cleanup.mainVolumes` |
| AC-08 | Docker Compose валиден | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| AC-09 | API image собирается | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| AC-10 | Web image собирается | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| AC-11 | Все четыре сервиса запускаются | PASS | [Compose](../../docker-compose.yml) · `config --quiet`, сборка из клона, `serviceChecks.healthy` в [измерениях](evidence.json) |
| AC-12 | Internal networking работает | PASS | [Smoke](../../scripts/smoke_infra.sh) · `serviceChecks.smoke` и `portsOnIPv4Loopback` в [измерениях](evidence.json) |
| AC-13 | Основные пользовательские volumes сохранены | PASS | [Контейнеры и тома после тестов](evidence.json) · `cleanup`, основной стек healthy |
| AC-14 | PostgreSQL connectivity подтверждена | PASS | [SQL и pgvector](evidence.json) · `database.facts` и `serviceChecks.smoke` |
| AC-15 | pgvector работает | PASS | [SQL и pgvector](evidence.json) · `database.facts` и `serviceChecks.smoke` |
| AC-16 | Alembic migrations выполняются | PASS | [Миграции на отдельной БД](../../apps/api/tests/integration/database/test_migrations.py) · `database.alembic` в [наблюдениях](evidence.json) |
| AC-17 | Current revision соответствует head | PASS | [Миграции на отдельной БД](../../apps/api/tests/integration/database/test_migrations.py) · `database.alembic` в [наблюдениях](evidence.json) |
| AC-18 | Async database layer работает | PASS | [Реальная проверка сессий и пула](../../apps/api/tests/integration/database/test_sessions.py) · database JUnit, 4/4 |
| AC-19 | Commit и rollback проверены | PASS | [Реальная проверка сессий и пула](../../apps/api/tests/integration/database/test_sessions.py) · database JUnit, 4/4 |
| AC-20 | Database persistence подтверждена | PASS | [Сохранность](evidence.json) · `persistence`, `database.finalPublicTables`, исполнения №12–13 |
| AC-21 | Health endpoint работает | PASS | [Реальные HTTP-ответы](evidence.json) · `http`, `serviceChecks.openapi` |
| AC-22 | Database readiness работает | PASS | [Реальные HTTP-ответы](evidence.json) · `http`, `serviceChecks.openapi` |
| AC-23 | HTTP 503 возвращается корректно | PASS | [При отказе БД](evidence.json) · `bff.db-outage`, исполнение №3, [скриншот](assets/degraded-1440.png) |
| AC-24 | OpenAPI доступен | PASS | [Реальные HTTP-ответы](evidence.json) · `http`, `serviceChecks.openapi` |
| AC-25 | Error contract сохраняется | PASS | [ASGI-тесты 404/405/422/500](../../apps/api/tests/integration/test_errors.py) · [HTTP и коды](evidence.json) |
| AC-26 | Structured logging работает | PASS | [Два совпадающих события](evidence.json) · `http`, `correlation.operational`, `correlation.degraded` |
| AC-27 | Request ID correlation работает | PASS | [Два совпадающих события](evidence.json) · `http`, `correlation.operational`, `correlation.degraded` |
| AC-28 | CORS проверен | PASS | [Preflight](evidence.json) · `http.allowed/denied`, [CORS tests](../../apps/api/tests/integration/test_cors.py) |
| AC-29 | Frontend запускается | PASS | [Операционный экран](assets/operational-1440.png) · [реальные ответы BFF и браузера](evidence.json) |
| AC-30 | System Overview получает реальные данные | PASS | [Операционный экран](assets/operational-1440.png) · [реальные ответы BFF и браузера](evidence.json) |
| AC-31 | Operational state корректен | PASS | [Операционный экран](assets/operational-1440.png) · [реальные ответы BFF и браузера](evidence.json) |
| AC-32 | Degraded state корректен | PASS | [При отказе БД](evidence.json) · `bff.db-outage`, исполнение №3, [скриншот](assets/degraded-1440.png) |
| AC-33 | Unavailable state корректен | PASS | [При отказе API](evidence.json) · `bff.api-outage`, исполнение №5, [скриншот](assets/unavailable-1440.png) |
| AC-34 | Refresh работает | PASS | [Браузер](evidence.json) · `browser.operational`, `refreshRequests = 1`, новые UUID и `checkedAt` |
| AC-35 | Browser verification выполнена | PASS | [375 px](assets/operational-375.png) · [измерения 375/768/1440 и console](evidence.json) |
| AC-36 | Текущий frontend design сохранён | PASS | [Операционный экран](assets/operational-1440.png) · [реальные ответы BFF и браузера](evidence.json) |
| AC-37 | Workflow импортируется в чистый n8n | PASS | [Граф и валидатор](../../scripts/validate_n8n_workflow.py) · 9/9, [реальный импорт и исполнения](evidence.json) |
| AC-38 | Workflow реально выполняется | PASS | [Структурированные результаты](evidence.json) · `workflowRuns.operational`, `workflowRuns.repeat`, `serviceChecks.workflowSettingsMatch` |
| AC-39 | Structured result соответствует контракту | PASS | [Структурированные результаты](evidence.json) · `workflowRuns.operational`, `workflowRuns.repeat`, `serviceChecks.workflowSettingsMatch` |
| AC-40 | HTTP 503 обрабатывается | PASS | [При отказе БД](evidence.json) · `bff.db-outage`, исполнение №3, [скриншот](assets/degraded-1440.png) |
| AC-41 | Network errors обрабатываются | PASS | [При отказе API](evidence.json) · `bff.api-outage`, исполнение №5, [скриншот](assets/unavailable-1440.png) |
| AC-42 | Retry ограничен | PASS | [Настройки и фактическая длительность](evidence.json) · `serviceChecks.retries`, `workflowRuns.timeout` |
| AC-43 | Request IDs найдены в backend logs | PASS | [Два совпадающих события](evidence.json) · `http`, `correlation.operational`, `correlation.degraded` |
| AC-44 | Workflow persistence подтверждена | PASS | [Восстановление n8n](evidence.json) · №8 и 13, сохранённые executions и исходный workflow ID |
| AC-45 | Database failure scenario проверен | PASS | [При отказе БД](evidence.json) · `bff.db-outage`, исполнение №3, [скриншот](assets/degraded-1440.png) |
| AC-46 | Database recovery подтверждена | PASS | [Восстановление БД](evidence.json) · №4, `browser.db-recovery`, контрольное значение |
| AC-47 | Backend failure scenario проверен | PASS | [При отказе API](evidence.json) · `bff.api-outage`, исполнение №5, [скриншот](assets/unavailable-1440.png) |
| AC-48 | Backend recovery подтверждён | PASS | [Восстановление API](evidence.json) · №6, `browser.api-recovery`, HTTP 200 |
| AC-49 | Frontend failure independence подтверждена | PASS | [Независимость при отказе web](evidence.json) · №7, `serviceChecks.smoke` |
| AC-50 | n8n failure independence подтверждена | PASS | [Восстановление n8n](evidence.json) · №8 и 13, сохранённые executions и исходный workflow ID |
| AC-51 | Invalid response handling проверен | PASS | [Управляемый upstream](evidence.json) · №9–11, INVALID_RESPONSE, HTTP_ERROR и TIMEOUT |
| AC-52 | Ruff check проходит | PASS | [Backend quality](../../.github/workflows/ci.yml) · Ruff check/format и Mypy strict в клоне и CI |
| AC-53 | Ruff format проходит | PASS | [Backend quality](../../.github/workflows/ci.yml) · Ruff check/format и Mypy strict в клоне и CI |
| AC-54 | Mypy strict проходит | PASS | [Backend quality](../../.github/workflows/ci.yml) · Ruff check/format и Mypy strict в клоне и CI |
| AC-55 | Backend tests проходят | PASS | [JUnit и coverage](evidence.json) · `tests.backend`, 65/65 |
| AC-56 | Database integration tests проходят | PASS | [Database JUnit](evidence.json) · `tests.database`, 4/4 на отдельном PostgreSQL |
| AC-57 | ESLint проходит | PASS | [Frontend quality](../../.github/workflows/ci.yml) · `npm run lint`, `npm run typecheck` |
| AC-58 | TypeScript typecheck проходит | PASS | [Frontend quality](../../.github/workflows/ci.yml) · `npm run lint`, `npm run typecheck` |
| AC-59 | Vitest проходит | PASS | [Vitest JUnit](evidence.json) · `tests.frontend`, 29/29 |
| AC-60 | Python build проходит | PASS | [Состав дистрибутивов](../../scripts/check_package.py) · `uv build`, 23 файла пакета в wheel/sdist |
| AC-61 | Next.js build проходит | PASS | [Web Dockerfile](../../apps/web/Dockerfile) · production build без backend, standalone smoke |
| AC-62 | n8n validation проходит | PASS | [Граф и валидатор](../../scripts/validate_n8n_workflow.py) · 9/9, [реальный импорт и исполнения](evidence.json) |
| AC-63 | GitHub Actions подтверждён на проверяемой версии | PASS | [GitHub Actions](https://github.com/n1k1c0d/AI-Sales-Intelligence-Platform/actions/runs/45577247614) · `382730c`, 7/7 |
| AC-64 | Нет добавленных секретов | PASS | [Безопасность](evidence.json) · `security.history`, `artifacts`, `publicAssetsExamined` |
| AC-65 | Acceptance ports доступны только локально | PASS | [Smoke](../../scripts/smoke_infra.sh) · `serviceChecks.smoke` и `portsOnIPv4Loopback` в [измерениях](evidence.json) |
| AC-66 | Test data полностью изолированы | PASS | [Измерения](evidence.json) · `persistence.volumes`, `cleanup.retainedVolumes` и `cleanup.mainVolumes` |
| AC-67 | Архитектурные ограничения соблюдены | PASS | [Три ADR и соответствующие модули](PHASE_0_REVIEW_INDEX.md) · HTTP-топология, ownership БД |
| AC-68 | Основные пользовательские данные не повреждены | PASS | [Контейнеры и тома после тестов](evidence.json) · `cleanup`, основной стек healthy |
| AC-69 | Production limitations задокументированы | PASS | [Ограничения публичной эксплуатации](PHASE_0_DEFECTS.md) |
| AC-70 | README воспроизводим | PASS | [Quick Start](../../README.md) · чистый clone, миграции и штатный smoke |
| AC-71 | AGENTS.md актуален | PASS | [Правила разработки и Git](../../AGENTS.md) · сверены пути, роли, проверки и текущая ветка |
| AC-72 | ARCHITECTURE соответствует реализации | PASS | [Три ADR и соответствующие модули](PHASE_0_REVIEW_INDEX.md) · HTTP-топология, ownership БД |
| AC-73 | API_CONTRACTS актуален | PASS | [Контракты](../API_CONTRACTS.md) · сопоставлены с `http` и `serviceChecks.openapi` в [замере](evidence.json) |
| AC-74 | RUNBOOK проверен | PASS | [Сценарии запуска, миграций, логов и остановки](../RUNBOOK.md) · [проверка исправлений](PHASE_0_DEFECTS.md) |
| AC-75 | ROADMAP актуализирован | PASS | [Статус и внешний gate](../ROADMAP.md) |
| AC-76 | PHASE_0_DEFECTS.md создан | PASS | [Реестр, уровень и статус](PHASE_0_DEFECTS.md) |
| AC-77 | PHASE_0_ACCEPTANCE.md создан | PASS | [Итоговый отчёт](PHASE_0_ACCEPTANCE.md) · сценарии, измерения и матрица |
| AC-78 | PHASE_0_REVIEW_INDEX.md создан | PASS | [Индекс независимого ревью](PHASE_0_REVIEW_INDEX.md) · источники, отчёты, передача |
| AC-79 | DM-012.md создан | PASS | [Карточка задачи DM-012](../tasks/DM-012.md) |
| AC-80 | Нет открытых P0/P1 blockers | PASS | [Реестр, уровень и статус](PHASE_0_DEFECTS.md) |
| AC-81 | Проект готов к независимому аудиту PHASE 0 | PASS | [Индекс независимого ревью](PHASE_0_REVIEW_INDEX.md) · источники, отчёты, передача |
| AC-82 | Реализация DM-101 не начата | PASS | [Roadmap](../ROADMAP.md) · только внешняя проверка и согласование, в diff документация и свидетельства |
