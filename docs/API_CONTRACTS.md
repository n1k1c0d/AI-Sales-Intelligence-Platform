# HTTP-контракты PHASE 0

## FastAPI Backend

Базовый путь `/api/v1`. Системные маршруты принимают GET без тела и возвращают `application/json`. OpenAPI доступен на `/openapi.json`, Swagger UI — на `/docs` того же сервиса. Для опубликованного порта выполните в корне `docker compose port api 8000`. [Фабрика приложения](../apps/api/src/dealmind/main.py) · [Роутер](../apps/api/src/dealmind/api/routes/health.py)

| Маршрут и состояние | HTTP | Тело |
| --- | --- | --- |
| `GET /api/v1/health`, процесс обслуживает запросы | 200 | `{"status":"ok","service":"dealmind-api"}` |
| `GET /api/v1/ready`, приложение готово, `SELECT 1` успешен | 200 | `{"status":"ready","checks":{"application":"ok","database":"ok"}}` |
| Lifecycle готов, БД недоступна, пароль отсутствует в local/test или истёк таймаут | 503 | `{"status":"not_ready","checks":{"application":"ok","database":"not_ready"}}` |
| Lifecycle ещё не готов | 503 | `{"status":"not_ready","checks":{"application":"not_ready","database":"not_ready"}}` |

В OpenAPI `200` health использует `HealthResponse`, `200/503` ready используют `ReadinessResponse`. Общие ответы `422/500` ссылаются на `ErrorResponse`. Readiness проверяет соединение, но актуальность миграций нужно отдельно проверить через Alembic.

## Ошибки и корреляция

Пример ответа для неизвестного ресурса:

```json
{"error":{"code":"NOT_FOUND","message":"Resource not found","details":null}}
```

| HTTP | Код в envelope | Когда возникает |
| --- | --- | --- |
| 404 | NOT_FOUND | Маршрут отсутствует |
| 405 | METHOD_NOT_ALLOWED | Метод не разрешён, заголовок Allow сохраняется |
| 422 | VALIDATION_ERROR | Ошибка схемы. В details возможны элементы с `loc`, `message`, `type` и безопасными сведениями о поле |
| 500 | INTERNAL_SERVER_ERROR | Непредусмотренное исключение, клиент получает общее сообщение |
| 503 | DATABASE_UNAVAILABLE | Ошибка DB-зависимости. У штатного `/ready` при отказе БД своё типизированное тело выше |

Каждый HTTP-ответ FastAPI, включая ошибки, получает `X-Request-ID`. Подходит один UUIDv4 из 32 hex-символов или стандартной записи с дефисами, регистр несущественен. Сервер нормализует его в строчную запись с дефисами. При пропуске, неверном значении или нескольких заголовках создаёт новый UUIDv4. ID доступен в JSON-логе `request_id`, контекст сбрасывается после запроса. [Обработчики ошибок](../apps/api/src/dealmind/api/exception_handlers.py) · [Поиск по ID](RUNBOOK.md)

## Next.js Frontend

`GET /api/health` возвращает HTTP 200 и `{"status":"ok","service":"dealmind-web"}`. `GET /api/system/status` — динамический same-origin Route Handler. Он параллельно запрашивает две пробы backend, возвращает JSON со статусом наблюдений и `Cache-Control: no-store`. HTTP 200 от обработчика возможен при деградации зависимостей. Пример структуры с синтетическими значениями:

```json
{
  "checkedAt": "2026-11-25T08:00:00.000Z",
  "overallStatus": "degraded",
  "backend": {"status":"operational","httpStatus":200,"requestId":"00000000-0000-4000-8000-000000000001","durationMs":12,"error":null},
  "database": {"status":"degraded"},
  "readiness": {"status":"degraded","httpStatus":503,"requestId":"00000000-0000-4000-8000-000000000002","durationMs":20,"error":null}
}
```

Статусы — `operational`, `degraded`, `unavailable`, `unknown`. Каждая проба содержит `httpStatus`, `requestId`, `durationMs` и `error`, все четыре поля допускают null. При отсутствии подтверждённой readiness БД имеет статус unknown. Поле error может содержать NETWORK_ERROR, TIMEOUT, INVALID_RESPONSE, HTTP_ERROR или CONFIGURATION_ERROR. Валидный ответ readiness 503 обрабатывается как диагностика приложения. [Схема frontend](../apps/web/src/features/system-status/contract.ts) · [Правила агрегации](../apps/web/src/features/system-status/snapshot.ts)

## Workflow и будущие API

Результат ручного workflow использует snake_case, собственный execution ID, статусы сервисов и список errors. [Вход, выход и примеры n8n](../automations/n8n/workflows/system-health-check.md)

Для последующих фаз рассматриваются группы `deals`, `contacts`, `activities`, `analytics`, `risks`, `integrations`, `knowledge`, `recommendations`, `approvals` под `/api/v1`. Для будущих CRM-команд DM-104 должен учитывать границу организации, строгую десятичную сумму и время с явным смещением. Для изменения этапа DM-105 должен учитывать ожидаемый номер перехода и повтор внешнего события. HTTP-пути, payload и коды ответов будут определены в соответствующих задачах. [Логическая CRM-модель](DATA_MODEL.md)
