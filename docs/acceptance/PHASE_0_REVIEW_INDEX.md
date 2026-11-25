# PHASE 0 · Индекс независимой проверки

Проверяйте ветку `dev` на коммите `382730ceee04b641f44a7fc77394778ae3bb2d87`. В дереве этого коммита 162 файла, 1 943 579 байт по `git ls-tree -rl HEAD`. Исходное рабочее дерево было чистым. Протокол и доказательства DM-012 подготовлены после этого коммита.

| Направление | Что открыть и как проверить |
| --- | --- |
| Управление | [AGENTS](../../AGENTS.md) задаёт границы изменений и Git. [README](../../README.md) содержит Quick Start. [Контекст](../PROJECT_CONTEXT.md), [roadmap](../ROADMAP.md), [спецификации и протоколы](../tasks/) определяют фазу и критерии. |
| Архитектура | [Топология](../ARCHITECTURE.md), [модульный монолит](../adr/0001-modular-monolith.md), [асинхронный доступ](../adr/0002-async-database-access.md), [HTTP-интеграция Next.js](../adr/0003-frontend-api-integration.md). Сверьте зависимости с фактическим направлением вызовов. |
| Backend | [Фабрика и lifespan](../../apps/api/src/dealmind/main.py), [маршруты](../../apps/api/src/dealmind/api/routes/health.py), [зависимости](../../apps/api/src/dealmind/api/dependencies.py), [Settings и логирование](../../apps/api/src/dealmind/core/), [middleware](../../apps/api/src/dealmind/api/middleware/request_context.py), [исключения](../../apps/api/src/dealmind/api/exception_handlers.py), [Pydantic-схемы](../../apps/api/src/dealmind/schemas/). Сопоставьте API с [контрактами](../API_CONTRACTS.md). |
| PostgreSQL | [Base](../../apps/api/src/dealmind/db/base.py), [engine](../../apps/api/src/dealmind/db/engine.py), [сессия и транзакции](../../apps/api/src/dealmind/db/session.py), [readiness](../../apps/api/src/dealmind/db/health.py), [Alembic env](../../apps/api/alembic/env.py), [ревизия 0001](../../apps/api/alembic/versions/0001_database_baseline.py), [текущая и планируемая схема](../DATA_MODEL.md). |
| Frontend | [npm scripts](../../apps/web/package.json), [layout](../../apps/web/src/app/layout.tsx), [System Overview и refresh](../../apps/web/src/features/system-status/), [компоненты](../../apps/web/src/components/), [серверный URL](../../apps/web/src/lib/config/server.ts), [HTTP-клиент и Zod](../../apps/web/src/lib/api/), [Route Handlers](../../apps/web/src/app/api/). Остановите API на отдельном стенде и сверьте ответ BFF с изображением. |
| n8n | [Переносимый граф](../../automations/n8n/workflows/system-health-check.json), [контракт и импорт](../../automations/n8n/workflows/system-health-check.md), [эталоны](../../automations/n8n/examples/system-health-check/), [валидатор](../../scripts/validate_n8n_workflow.py), [реальный CLI harness](../../scripts/ci_stack.py). Сопоставьте значения свежего запуска с [наблюдениями DM-012](evidence.json). |
| Инфраструктура | [Compose](../../docker-compose.yml), [шаблон окружения](../../.env.example), [API image](../../apps/api/Dockerfile), [исключения API](../../apps/api/.dockerignore), [web image](../../apps/web/Dockerfile), [исключения web](../../apps/web/.dockerignore), [тестовая БД](../../infra/docker/postgres/compose.test.yml), [pgvector init](../../infra/docker/postgres/init/001-enable-vector.sql), [CI overlay и HTTP fixture](../../infra/docker/ci/). |
| Качество | [Backend tests](../../apps/api/tests/), [реальная БД](../../apps/api/tests/integration/database/), [frontend tests](../../apps/web/tests/), [тесты валидатора](../../scripts/tests/), [smoke](../../scripts/smoke_infra.sh), [GitHub Actions](../../.github/workflows/ci.yml), [стратегия и команды](../TEST_STRATEGY.md). |
| Приёмка | [Сводка и полная матрица](PHASE_0_ACCEPTANCE.md), [дефекты, риск и проверка исправления](PHASE_0_DEFECTS.md), [карточка DM-012](../tasks/DM-012.md), [процедуры эксплуатации](../RUNBOOK.md). |

## Артефакты тестов

[GitHub Actions run 45577247614](https://github.com/n1k1c0d/AI-Sales-Intelligence-Platform/actions/runs/45577247614) сохраняет пять наборов. В `backend-reports` имеются `backend-junit.xml` и `backend-coverage.xml`. В `database-report` и `frontend-report` находятся соответствующие JUnit, в `n8n-report` и `smoke-report` — `n8n.json` и `smoke.json`. При локальном повторе XML создаются в `apps/api/reports/` и `apps/web/reports/` командами из workflow. Эти каталоги исключены из Git. Для независимой сверки HTTP, n8n и сохранности томов используйте [измерения](evidence.json) и [скриншоты браузера](assets/).

## Передача исходников

Из репозитория сначала сверьте `git rev-parse HEAD` и `git ls-tree -rl 382730ceee04b641f44a7fc77394778ae3bb2d87`. Для архива проверенного baseline по решению владельца выполните:

```shell
git archive --format=zip --output=../dealmind-phase0-382730c.zip 382730ceee04b641f44a7fc77394778ae3bb2d87
```

Команда включает только Git-дерево указанного коммита. Для полноценного ревью передайте отдельно перечисленные в отчёте файлы DM-012 либо используйте последующий коммит с ними после успешного CI для его SHA. Перед передачей проверьте состав архива. Локальные env, credentials, дампы, SQLite n8n, история Git, runtime-логи, тома и установленные зависимости в комплект не входят. В рамках DM-012 архив не создавался.

## Решения для ревьюера

Проверьте границу транзакции, соответствие ошибок BFF и n8n фактическому HTTP и условия безопасной изоляции Docker. Отдельного решения требуют дальнейшие обновления тестового HTTP-клиента и требования к языку UI. Ограничения эксплуатации перечислены в [реестре](PHASE_0_DEFECTS.md). Следующий этап — независимая оценка фундамента владельцем.

Implementation requires owner approval after external Phase 0 review.
