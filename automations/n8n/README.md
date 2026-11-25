# DealMind · n8n Integration Layer

## Автоматическая проверка System Health Check

В корне выполните `python scripts/validate_n8n_workflow.py` и `python -m unittest discover -s scripts/tests -v`. Для реального исполнения запустите `python scripts/ci_stack.py n8n`. Сценарий проверяет установленный CLI, импортирует экспорт через `n8n import:workflow`, получает внутренний ID из `list:workflow` и сверяет обратный экспорт с Git. Затем `n8n execute --id` выполняет граф при доступной и остановленной тестовой БД. Ещё два запуска проверяют отказ подключения к остановленному API и HTTP 200 с некорректным JSON или схемой. Для этих сценариев имя `api` получает служба `invalid-api` только в изолированной сети.

У каждого прогона собственные SQLite, ключ и сеть. В отчёте `reports/n8n.json` ожидаются ровно один итоговый item на запуск, четыре ожидаемых статуса, HTTP-коды, request IDs от настоящего API и точные коды ошибок. [Команды и артефакты](../../scripts/README.md)

## 1. Integration Layer Overview

n8n запускает ручную диагностику инфраструктуры DealMind. Оператор видит, ответил ли FastAPI, готова ли БД и какая проверка дала ошибку. Каждое выполнение оставляет один отчёт в истории редактора.

## 2. n8n Responsibilities

Workflow организует GET-запросы, нормализует HTTP-ответы и выбирает диагностическую ветку. PostgreSQL, SQL, транзакциями, авторизацией и бизнес-правилами управляет Python Backend. [Границы компонентов](../../docs/ARCHITECTURE.md)

## 3. Local Environment

Подготовьте корневой `.env` и запустите Compose по инструкции проекта. Узнайте порт редактора через `docker compose port n8n 5678`. По умолчанию это `http://127.0.0.1:5678`. На стенде приёмки — порт 5679. При первом входе владелец лично проходит Set up owner account. Для диагностики понадобятся доступ к редактору и импортированный workflow. [Локальное окружение](../../infra/docker/README.md)

## 4. Installed Version

Проверенная версия — n8n 2.48.8. Образ и digest зафиксированы в Compose. Команда `docker compose exec -T n8n n8n --version` показывает версию работающего экземпляра. Workflow, локальная учётная запись и история хранятся во встроенной SQLite в томе `n8n_data`. Сохраняйте том и текущий ключ шифрования вместе.

## 5. Docker Networking

Из контейнера n8n FastAPI доступен по `http://api:8000` в общей bridge-сети. Посмотреть readiness из той же сети можно из корня проекта

```shell
docker compose exec -T n8n node -e "fetch('http://api:8000/api/v1/ready').then(async r => console.log(r.status, await r.text()))"
```

## 6. Workflow Registry

| Workflow | Trigger | Purpose | Version |
| --- | --- | --- | --- |
| [System Health Check](workflows/system-health-check.md) | Manual | Диагностика FastAPI и PostgreSQL через health/readiness | 1.0.0 |

## 7. Naming Conventions

Имя в редакторе начинается с DealMind и описывает операцию. Имя экспортируемого файла записывается в kebab-case. Рядом с JSON хранится одноимённый Markdown с входом, результатом, поведением при ошибке и порядком проверки. Названия узлов на английском обозначают их действие.

## 8. Node Design Principles

Используйте встроенные узлы. Контекст создаётся один раз. HTTP Request отвечает за транспорт, нормализация проверяет внешний контракт, Switch выбирает единственное завершение. Code nodes выполняют небольшие преобразования данных на JavaScript. Ограничьте маршруты, типы узлов и побочные эффекты областью конкретной интеграции.

## 9. Error Handling

Посмотрите в финальном item поля `overall_status` и `errors`. Состояние n8n Succeeded означает, что отчёт сформирован. Проверяемая система при этом может быть degraded, unavailable или unknown. Ошибка преобразования либо непредусмотренная ошибка исполнения остаётся в истории как Error.

## 10. Retry Policy

Проверка делает максимум две попытки на endpoint с интервалом 1000 мс после транспортного отказа. На одну попытку отведено 8000 мс, на workflow — 60 с. Полученный HTTP 503, неожиданный статус и невалидный JSON передаются в нормализацию сразу.

## 11. Request ID Correlation

Откройте Executions, выберите запуск, дважды щёлкните конечный узел и выберите OUTPUT → JSON. В `services.backend.request_id` и `services.readiness.request_id` находятся два разных UUID. Ищите их в `docker compose logs --no-color api`, сверяя `http_route` и `status_code`. При отсутствии заголовка выводится null.

## 12. Export and Import

Для нового экземпляра откройте пустой workflow, выберите меню ⋯ → Import → From file и укажите файл из Git. После сохранения нажмите Execute. В работающем проекте сначала проверьте наличие текущей копии. Поиск и одиночный CLI-импорт описаны в [руководстве workflow](workflows/system-health-check.md#13-import--export). [Документация n8n по импорту и экспорту](https://docs.n8n.io/workflows/export-import/)

## 13. Credentials Policy

Эта интеграция читает два внутренних диагностических маршрута без credentials. В Git входят только переносимый JSON, документация и безопасные примеры. Перед публикацией проверяйте `credentials`, headers, pinned data, ownership, URL и содержимое Code nodes. Настройки учётных записей и архив SQLite остаются в локальном окружении.

## 14. Testing

Из корня выполните `python scripts/validate_n8n_workflow.py`. Затем запустите проверку из редактора, сопоставьте execution ID и Request IDs. Для проверок остановки сервисов используйте отдельный Docker-проект со своей сетью и БД. [Результаты DM-009](../../docs/tasks/DM-009.md)

## 15. Troubleshooting

| Симптом | Что проверить |
| --- | --- |
| Пустой редактор | Уточните порт, учётную запись, Personal project и наличие файла в Workflow Registry. |
| 200 / 503 | Посмотрите причину в readiness, затем найдите запись FastAPI по Request ID. |
| Оба HTTP-кода null | Проверьте сеть, DNS-имя api и доступность контейнера. Следующий запуск делает новую проверку. |
| Unknown | Посмотрите безопасные коды ошибок, ответ HTTP-узла и контракт текущей версии API. |
| В истории нет запуска | Убедитесь, что workflow сохранён и включено сохранение manual executions в его настройках. |

## 16. Current Limitations

Результат — моментальный снимок двух запросов. История доступна по правилам хранения экземпляра n8n. Проверка сообщает о БД только то, что подтвердил FastAPI. Внешний аудит бизнес-операций и непрерывный мониторинг запланированы отдельно.

## 17. Future Integrations

В следующих фазах появятся CRM webhooks, расписания, Telegram и выполнение подтверждённых действий. Область и контракты каждого workflow определит отдельная задача. [Roadmap](../../docs/ROADMAP.md)
