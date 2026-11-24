# DealMind · Web UI

## 1. Frontend Overview

System Overview на `/` показывает доступность FastAPI, готовность PostgreSQL, общий результат readiness и способность Next.js выдавать диагностику. Для корреляции с журналом API служат два независимых Request ID. [Приёмка и скриншоты](../../docs/tasks/DM-008.md)

## 2. Technology Stack

Next.js 16.4.6 App Router, React 19.3.1, TypeScript 6.0.3 (strict), Tailwind 4.3.5 с PostCSS и Lucide React 1.79.0. Схемы Zod 4.6.7 дают типы и проверяют входные данные во время исполнения. Точные версии фиксирует `package-lock.json`.

## 3. Node.js Requirements

Используйте Node.js 24 LTS и npm 11. Приёмка выполнена на 24.22.3 / 11.19.1. Из `apps/web` можно выполнить `nvm use` в оболочке с поддержкой `.nvmrc`. Версии проверяются командами `node --version` и `npm --version`.

## 4. Installation

Из корня выполните

```shell
cd apps/web
npm ci
```

Для локальных настроек скопируйте здесь `.env.example` в `.env.local` и укажите опубликованный порт API. Посмотреть его из корня можно командой `docker compose port api 8000`.

## 5. Development Server

Из `apps/web` запустите `npm run dev` и откройте `http://127.0.0.1:3000`. Если этот порт уже занят Docker, используйте `npm run dev -- --port 3001`. Для состояния Operational также запустите API и БД по инструкции в корневом README.

## 6. Project Structure

| Путь внутри apps/web | Ответственность |
| --- | --- |
| `src/app/` | Layout, страница, стили, error boundary и два HTTP-обработчика |
| `src/components/` | Шапка, кнопка, индикатор и карточка статуса |
| `src/features/system-status/` | Страница обзора, интерактивная панель, публичный контракт и сводка проверок |
| `src/lib/api/`, `src/lib/config/` | Контракты FastAPI, HTTP-клиент и настройки сервера |
| `public/`, `scripts/` | Локальная иконка и упаковка статических ресурсов для standalone |
| `tests/unit/`, `tests/components/` | Контрактные и компонентные тесты |

## 7. Environment Variables

| Переменная | По умолчанию локально | В Compose |
| --- | --- | --- |
| `API_BASE_URL` | `http://127.0.0.1:8000` | `http://api:8000` |
| `API_REQUEST_TIMEOUT_MS` | `8000` | `8000`, переопределяется в корневом `.env` |
| `WEB_HOST_PORT` | Используется только Compose | `3000` на loopback хоста |

Укажите HTTP(S) origin. Путь, query, fragment и встроенные учётные данные приводят к CONFIGURATION_ERROR. Таймаут задаётся целым числом от 1 до 60000 мс. Дайте FastAPI время вернуть диагностический 503. По умолчанию API ждёт БД до 5 секунд, Next.js ждёт API до 8 секунд.

## 8. Server and Client Components

Root Layout, структура страницы, шапка и сведения о проекте рендерятся на сервере. Клиентская панель управляет загрузкой и кнопкой Refresh Status. Она получает только проверенный JSON с текущего origin. Версия в шапке берётся из package.json.

## 9. Backend Integration

При открытии страницы и нажатии Refresh браузер вызывает `GET /api/system/status`. Обработчик читает runtime-настройки и параллельно запрашивает два фиксированных пути FastAPI. Каждый запрос имеет свой timeout, включает `no-store` и проверяет HTTP-код, тип содержимого и JSON. Таймаут охватывает и чтение тела ответа. Автоматические повторы и polling отсутствуют.

## 10. System Status Contract

`GET /api/health` возвращает HTTP 200 с `{"status":"ok","service":"dealmind-web"}`. Этот маршрут отвечает за liveness web.

`GET /api/system/status` возвращает HTTP 200 с диагностическим снимком и `Cache-Control: no-store`. Поля `checkedAt` (UTC) и `overallStatus` относятся ко всей проверке. Объекты `backend` и `readiness` содержат `status`, `httpStatus`, `requestId`, `durationMs`, `error`. При отсутствии HTTP-ответа код и ID равны null. `database.status` следует из валидного readiness при готовом приложении.

| Health / readiness | Backend | Database | Overall |
| --- | --- | --- | --- |
| 200 / готова | Operational | Operational | Operational |
| 200 / 503, сбой БД | Operational | Not ready | Degraded |
| 200 / приложение не готово, таймаут или невалидный JSON | Operational | Unknown | Degraded |
| Невалидный health / валидная readiness | Degraded | По readiness | Degraded |
| Обе проверки без соединения | Unavailable | Unknown | Unavailable |
| Два неподтверждённых ответа | Unknown | Unknown | Unknown |

## 11. Loading and Error Handling

До первого ответа отображается Checking. Во время обновления остаётся предыдущий снимок с его временем. Кнопка блокирует повторный запрос и снова доступна после завершения. Ошибка самого диагностического маршрута переводит карточки в Unknown. Ошибку рендера обрабатывает граница страницы с кнопкой Try again. При уходе со страницы активный запрос отменяется.

## 12. Testing

```shell
npm test
npm run test:watch
```

Vitest и React Testing Library работают со специально заданными ответами HTTP без Docker и БД. Реальные отказы PostgreSQL и API проверены отдельно на изолированном стенде. [Подробные результаты](../../docs/tasks/DM-008.md)

## 13. Linting and Typecheck

```shell
npm run lint
npm run typecheck
```

ESLint использует официальный flat config Next.js. Typecheck сначала создаёт типы маршрутов, затем запускает TypeScript без генерации JavaScript.

## 14. Production Build

```shell
npm run build
npm start
```

Сборка создаёт standalone server и помещает рядом с ним `.next/static` и `public`. Локальный preview слушает loopback. Порт задаётся переменной `PORT`. Компиляция работает без доступа к FastAPI и внешним шрифтам.

## 15. Docker Deployment

Из корня проекта после первичной настройки БД и миграций выполните

```shell
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
```

Для обновления только frontend используйте `docker compose up -d --build --no-deps --wait web`. Standalone работает под пользователем node. Доступность контейнера проверяется через `/api/health`. [Установка и локальные порты](../../README.md#local-development-with-docker)

## 16. Troubleshooting

| Симптом | Действие |
| --- | --- |
| Backend unavailable | Проверьте `docker compose ps`, опубликованный порт и `API_BASE_URL` в среде запуска Next.js. Нажмите Refresh после восстановления. |
| HTTP 200 / HTTP 503 | API отвечает. Проверьте готовность приложения и PostgreSQL по `/api/v1/ready`, затем найдите запрос в логах по Request ID. |
| Configuration error или timeout | Проверьте формат origin, единицы таймаута и соотношение с `APP_DB_HEALTH_TIMEOUT`. Перезапустите локальный Node либо пересоздайте web после изменения окружения. |
| Порт 3000 занят | Задайте `WEB_HOST_PORT` для Compose или используйте другой порт dev-сервера. |
| После сборки отсутствуют CSS или иконка | Повторите `npm run build` целиком. Для standalone нужны скопированные статические ресурсы. |

## 17. Current Limitations

Это локальная инфраструктурная диагностика по запросу. CRM Dashboard, сделки, аналитика продаж, визуализация риска, RAG, AI-рекомендации, аутентификация и публичное развёртывание относятся к последующим этапам. Состояние n8n в интерфейсе не проверяется.

## 18. Next Task

DM-009 — n8n Integration Bootstrap. [Roadmap](../../docs/ROADMAP.md)
