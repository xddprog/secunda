# Тестовое задание в компанию Secunda

## Запуск

### Docker

Из корня проекта:

```bash
cp backend/.env.example backend/.env
docker compose up --build -d
```

Запускаются PostgreSQL, RabbitMQ, API и consumer. Миграции применяются автоматически.

### Локально одним скриптом

После установки зависимостей, активации `.venv` и настройки `.env`, из корня проекта:

```bash
./run_local.sh
```

Скрипт применяет миграции и запускает API и consumer в одном терминале.
`Ctrl+C` останавливает оба процесса. PostgreSQL и RabbitMQ должны быть запущены.

### Локально

Нужны Python 3.12, запущенные PostgreSQL и RabbitMQ, а также созданная БД.
Параметры подключений и `API_KEY` указываются в `backend/.env`.

Из корня проекта:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

После настройки `.env`:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Consumer запускается во втором терминале из корня проекта:

```bash
source .venv/bin/activate
cd backend
faststream run app.consumer:app
```

API: `http://localhost:8000`. Swagger: `http://localhost:8000/docs`.

## Тесты

```bash
pip install -r backend/requirements.txt
cd backend && pytest
```

Тестам нужна запущенная PostgreSQL. Ходят через реальное приложение и реальную БД; RabbitMQ и вебхуки замоканы. Покрытие считается автоматически, конфиг — в `pyproject.toml`.

## Что реализовано

- Создание и получение платежа; авторизация через `X-API-Key`
- Outbox: платёж и событие сохраняются одной транзакцией (граница транзакции — сервис), затем событие отправляется в RabbitMQ
- Retry

## Гарантии доставки

- **Атомарность**: запись платежа и события Outbox коммитятся одной транзакцией — не бывает платежа без события и наоборот.
- **Идемпотентность создания**: повторный запрос с тем же `Idempotency-Key` возвращает существующий платёж; событие не дублируется. Если событие для существующего платежа отсутствует (было потеряно), оно пересоздаётся.
- **Вебхуки**: доставка at-least-once. Отправка защищена проверкой `webhook_sent_at` под `SELECT ... FOR UPDATE`, поэтому при повторной обработке сообщения вебхук не отправляется повторно. Получатель должен быть идемпотентен по `payment_id` (защита от редкого случая падения между отправкой вебхука и фиксацией отметки).
- **Индексы**: уникальный индекс на `idempotency_key`, уникальный `outbox.payment_id` и частичный индекс по неопубликованным событиям (`WHERE published_at IS NULL`) для поллера Outbox.

## API и примеры

Все методы требуют `X-API-Key`

### POST /api/v1/payments

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'X-API-Key: test-api-key' \
  -H 'Idempotency-Key: order-123' \
  -H 'Content-Type: application/json' \
  -d '{
    "amount": "1500.50",
    "currency": "RUB",
    "description": "Заказ 123",
    "metadata": {"order_id": 123},
    "webhook_url": "https://example.com/webhook"
  }'
```

Ответ `202 Accepted`:

```json
{
  "payment_id": "c31eb4be-8a8b-47eb-b5bf-fc5d206804fd",
  "status": "pending",
  "created_at": "2026-10-07T12:00:00Z"
}
```

### GET /api/v1/payments/{payment_id}

Возвращает платёж

```bash
curl http://localhost:8000/api/v1/payments/PAYMENT_ID \
  -H 'X-API-Key: test-api-key'
```

Пример ответа `200 OK` после обработки:

```json
{
  "payment_id": "c31eb4be-8a8b-47eb-b5bf-fc5d206804fd",
  "amount": "1500.50",
  "currency": "RUB",
  "status": "succeeded",
  "description": "Заказ 123",
  "metadata": {"order_id": 123},
  "webhook_url": "https://example.com/webhook",
  "created_at": "2026-10-07T12:00:00Z",
  "processed_at": "2026-10-07T12:00:03Z"
}
```

Для `pending` поле `processed_at` равно `null`. Webhook содержит те же поля, что ответ GET.
Ошибки: `401` — неверный API-ключ, `404` — платёж не найден, `422` — ошибка валидации.

## Структура

```text
backend/
├── app/
│   ├── api/                 # HTTP-роуты и зависимости FastAPI
│   ├── core/
│   │   ├── dto/             # Pydantic-схемы
│   │   ├── repositories/    # Запросы к БД
│   │   └── services/        # Логика платежей и Outbox
│   ├── infrastructure/
│   │   ├── broker/          # RabbitMQ-брокер и очереди
│   │   ├── config/          # Настройки
│   │   ├── database/        # Подключение и ORM-модели
│   │   ├── errors/          # Исключения
│   │   └── interfaces/      # Интерфейс репозитория
│   ├── utils/               # Enum валют и статусов
│   ├── main.py              # FastAPI
│   └── consumer.py          # Consumer и публикация Outbox
├── migrations/              # Миграции Alembic
├── tests/                   # api/ service/ repository/ consumer/
├── .env.example
├── Dockerfile
├── pyproject.toml            # Конфиг pytest и coverage
└── requirements.txt
docker-compose.yml
run_local.sh                # Локальный запуск API и consumer
```
