# Android API

Сервер: `miniapp` (FastAPI). Все эндпоинты ниже примонтированы под общим префиксом и
требуют HTTPS — Bearer-токены и пароли уходят в заголовке `Authorization`.

- Base URL: `https://<host>/bot/miniapp`
- Swagger UI: `https://<host>/bot/miniapp/api/docs`
- OpenAPI JSON: `https://<host>/bot/miniapp/openapi.json`

В таблицах ниже поле «Auth» означает:

- `—` — публично
- `Bearer` — нужен access JWT в `Authorization: Bearer <token>`
- `Bearer + verified` — дополнительно требуется подтверждённый email

Ошибки возвращаются как `{"detail": {"code": "<machine_code>"}}` с понятным `code` —
клиент локализует сообщение на своей стороне.

---

## 1. Auth (`/api/android`)

| Метод | Путь | Auth | Rate | Назначение |
|---|---|---|---|---|
| POST | `/register` | — | 5/min | Создать пользователя по email + password |
| POST | `/login` | — | 10/min | Получить пару токенов |
| POST | `/refresh` | — | 60/min | Ротация refresh-семейства |
| POST | `/logout` | — | — | Отозвать одно семейство по refresh-токену |
| POST | `/logout-all` | Bearer | — | Отозвать все семейства пользователя |
| POST | `/password/change` | Bearer | — | Сменить пароль (нужен текущий) |

### POST /register

```json
{ "email": "user@example.com", "password": "min8chars" }
```
**201** → `AuthResponse { tokens, user }`. **409 `email_taken`** при дубликате.

### POST /login

```json
{ "email": "...", "password": "..." }
```
**200** → `AuthResponse`. **401 `invalid_credentials`**, **403 `banned`**.

### POST /refresh

```json
{ "refresh_token": "<raw>" }
```
**200** → `TokenPair` (новый access + новый refresh). Старый refresh инвалидируется.
При повторе использования отозванного — отзывается всё семейство (replay-detection).

### POST /logout

```json
{ "refresh_token": "<raw>" }
```
**200** → `{ "status": "ok" }`. Отзывает family_id текущего refresh-токена.

### POST /password/change

```json
{ "current_password": "...", "new_password": "min8" }
```
**200** → `{ "status": "ok" }`. **401** при неверном `current_password`.

### Схемы

```jsonc
// TokenPair
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque>",
  "token_type": "Bearer",
  "expires_in": 900            // сек, TTL access-токена
}

// UserSummary
{
  "id": 42,
  "email": "user@example.com",
  "email_verified": false,
  "has_password": true,
  "has_telegram": false
}

// AuthResponse
{ "tokens": <TokenPair>, "user": <UserSummary> }
```

Access — JWT HS256, TTL ≈ 15 мин (см. `android_access_ttl`).
Refresh — opaque, TTL по умолчанию 60 дней (`android_refresh_ttl`).

---

## 2. Email (`/api/android/auth`)

Все ручки шлют 6-значный код на email. TTL кода — 15 мин (`email_code_ttl`),
максимум 5 попыток (`email_code_max_attempts`).

| Метод | Путь | Auth | Rate | Назначение |
|---|---|---|---|---|
| POST | `/email/send-code` | Bearer | 3/min | Отправить код подтверждения текущего email |
| POST | `/email/verify` | Bearer | 10/min | Подтвердить код → выдаётся бесплатная подписка |
| POST | `/password/reset-request` | — | 3/min | Запросить код сброса пароля |
| POST | `/password/reset-confirm` | — | 10/min | Сбросить пароль по коду |
| POST | `/email/change-request` | Bearer + verified | 3/min | Запросить код смены email |
| POST | `/email/change-confirm` | Bearer | 10/min | Применить смену email |

### Тела запросов

```jsonc
// /email/send-code            — без тела
// /email/verify
{ "code": "123456" }

// /password/reset-request
{ "email": "user@example.com" }

// /password/reset-confirm
{ "email": "...", "code": "123456", "new_password": "min8chars" }

// /email/change-request
{ "new_email": "new@example.com" }

// /email/change-confirm
{ "code": "123456" }
```

Все возвращают `{ "status": "ok" }` (или `"already_verified"`).
Коды ошибок: `code_invalid`, `code_expired`, `code_exhausted`, `email_send_failed`,
`email_taken`, `email_missing`.

После успешного `/email/verify` сервер автоматически создаёт FREE-подписку в
Remnawave (`provisioning.ensure_free_subscription`) — клиент сразу может звать
`/api/android/me` и видеть `tariff: "Free"`.

---

## 3. Платежи (`/api/android/payments`)

Внешние провайдеры (A-Pay, Platega). Для IAP — раздел 4.

| Метод | Путь | Auth | Rate | Назначение |
|---|---|---|---|---|
| GET | `/providers` | — | — | Список доступных провайдеров |
| POST | `/invoice` | Bearer + verified | 10/min | Создать счёт, получить URL для оплаты |
| GET | `/transactions` | Bearer | — | Последние 50 транзакций пользователя |
| GET | `/transactions/{id}` | Bearer | — | Состояние конкретной транзакции |

### POST /invoice

```jsonc
{
  "provider": "apay",                  // apay | platega
  "amount": 199.0,
  "currency": "RUB",
  "days": 30,
  "squad_id": "<remnawave squad uuid>",
  "external_squad_id": "<remnawave external squad uuid>",
  "description": "30 days Premium",    // опционально
  "method": null                        // опционально, нужен только для Platega
}
```

**200**:
```jsonc
{
  "provider": "apay",
  "invoice_id": "...",
  "url": "https://...",                // открыть в WebView/браузере
  "amount": 199.0,
  "currency": "RUB",
  "transaction_id": "<uuid>",          // запомнить, опрашивать /transactions/{id}
  "payment_method": "card"
}
```
Ошибки: `provider_not_allowed`, `provider_unavailable`, `currency_unsupported`,
`invoice_failed` (502).

### GET /transactions/{id}

```jsonc
{
  "transaction_id": "...",
  "status": "pending|success|failed",
  "delivery_status": 0,                // 1 ⇒ подписка выдана в Remnawave
  "payment_method": "card",
  "amount": 199.0,
  "days_ordered": 30,
  "created_at": "2026-05-05T10:00:00+00:00"
}
```

Поллить с экспоненциальным бэкоффом до `delivery_status == 1`. После этого
дёрнуть `/api/android/me` — там подтянутся новый `expire_iso` и `tariff`.

---

## 4. Google Play IAP (`/api/android/iap`)

| Метод | Путь | Auth | Rate | Назначение |
|---|---|---|---|---|
| GET | `/skus` | — | — | Активные продукты (product_id ↔ дни/сквад) |
| POST | `/verify` | Bearer + verified | 10/min | Проверить чек у Google и применить |
| POST | `/rtdn` | query `?token=` | — | Pub/Sub push-callback (Real-Time Developer Notifications) |

### POST /verify

```jsonc
{ "purchase_token": "<from BillingClient>", "product_id": "premium_30d" }
```

**200**:
```jsonc
{
  "state": "ACTIVE|IN_GRACE_PERIOD|ON_HOLD|...",
  "expiry_time": "2026-06-04T10:00:00Z",
  "auto_renewing": true,
  "delivered": true                    // прошла ли провижинг в Remnawave
}
```

Идемпотентно по `(purchase_token, expiry_time)` — повтор не выдаст дни дважды.
Ошибки: `product_mismatch`, `purchase_owner_mismatch` (409), `verification_failed`.

### POST /rtdn

Принимает Pub/Sub-payload. Аутентификация — `?token=<google_play_rtdn_token>`
из `config.yml`. Всегда возвращает 200, чтобы Pub/Sub не повторял пуши.

---

## 5. Профиль и состояние (`/api/android`)

| Метод | Путь | Auth | Назначение |
|---|---|---|---|
| GET | `/me` | Bearer | Профиль + текущая подписка + публичные ссылки |
| GET | `/devices` | Bearer | Активные HWID-устройства из Remnawave |
| DELETE | `/devices/{hwid}` | Bearer | Снести устройство |
| GET | `/sessions` | Bearer | Список активных refresh-семейств |
| DELETE | `/sessions/{id}` | Bearer | Отозвать одно семейство |
| POST | `/sessions/revoke-all` | Bearer | Отозвать все (не убивает текущий access до истечения TTL) |

### GET /me

```jsonc
{
  "user": {
    "id": 42,
    "email": "user@example.com",
    "email_verified": true,
    "tg_id": null,                     // null если не привязан Telegram
    "language": "ru"
  },
  "subscription": {
    "tariff": "Free|Premium|—",
    "status": "active|expired|disabled|null",
    "days_left": 12,
    "expire_iso": "2026-05-17T10:00:00+00:00",
    "data_limit_gb": 0,                // 0 = безлимит
    "traffic_used_gb": 3,
    "devices_count": 1,
    "subscription_url": "https://...", // VLESS subscription URL
    "source": "remnawave"              // или "google_play" если IAP перебивает
  },
  "links": {
    "bot_url": "https://t.me/yourbot",
    "policy_url": "...",
    "agreement_url": "...",
    "news_url": "...",
    "branding_name": "...",
    "support_bot_link": "..."
  }
}
```

Если у пользователя нет email или Remnawave не нашёл его аккаунт — `subscription: null`.

### GET /devices

```jsonc
{
  "total": 2,
  "devices": [
    {
      "hwid": "...",
      "platform": "android",
      "os_version": "14",
      "device_model": "Pixel 8",
      "user_agent": "...",
      "created_at": "2026-04-30T...",
      "updated_at": "2026-05-04T..."
    }
  ]
}
```

DELETE `/devices/{hwid}` → **204**, либо **502 `device_delete_failed`**.

### GET /sessions

```jsonc
{
  "total": 1,
  "sessions": [
    {
      "id": 17,
      "issued_at": "2026-05-04T20:00:00",
      "expires_at": "2026-07-03T20:00:00",
      "user_agent": "okhttp/5.0.0",
      "ip": "1.2.3.4",
      "current": null                  // family_id пока не пробрасывается в JWT
    }
  ]
}
```

DELETE `/sessions/{id}` → **204** на своих, **404 `session_not_found`** на чужих/несуществующих.
POST `/sessions/revoke-all` → `{ "revoked": 3 }`.

---

## 6. Привязка Telegram (`/api/android/link`)

| Метод | Путь | Auth | Rate | Назначение |
|---|---|---|---|---|
| POST | `/start` | Bearer + verified | 3/min | Получить код и deep-link |
| DELETE | `/telegram` | Bearer | — | Снести привязку (`tg_id = NULL`) |

### POST /start

Без тела. **200**:
```jsonc
{
  "code": "ABCdef1234",
  "expires_in": 600,
  "deep_link": "https://t.me/yourbot?start=link_ABCdef1234"
}
```

**409 `already_linked`** — уже есть `tg_id`. Сначала DELETE `/telegram`, потом `/start` снова.

UX: открыть `deep_link` системным интентом → бот в `/start` распарсит payload,
свяжет `users.tg_id` с аккаунтом и ответит сообщением. Клиент после этого
просто ре-фетчит `/me` (там появится `tg_id`).

---

## Конвенции

- **Время** — ISO-8601 UTC (`...Z` или `+00:00`).
- **Деньги** — `float` + ISO-код валюты, без копеек/центов.
- **Идентификаторы Remnawave** (`squad_id`, `external_squad_id`) — UUID-строки,
  передаются как есть. Сервер сам клеит `tariff_slug = sid:<squad>:esid:<external>`.
- **Bearer-токен** в `Authorization: Bearer <jwt>`. На 401 с любым `code` —
  выкинуть access, дёрнуть `/refresh`. На 401 после refresh — разлогинить.
- **Rate limits** возвращают **429** с `{"detail": {"code": "rate_limited"}}`.

## Что нужно для запуска

В `config.yml`:

```yaml
# обязательно
android_jwt_secret: "<≥32 байта>"        # python -c "import secrets; print(secrets.token_urlsafe(48))"
smtp_host: "..."
smtp_port: 587
smtp_user: "..."
smtp_password: "..."
smtp_from: "noreply@yourdomain"          # опционально, иначе = smtp_user

# опционально, дефолты в скобках
android_access_ttl: 900                  # (15 мин)
android_refresh_ttl: 5184000             # (60 дней)
android_jwt_issuer: "xray-vpn-bot"
email_code_ttl: 900
email_code_max_attempts: 5

# нужно только для Google Play IAP
google_play_package_name: "com.example.app"
google_play_service_account_path: "/run/secrets/play-sa.json"
google_play_rtdn_token: "<random>"
```

Без Android-секции `/api/android/*` отвечает 500 на auth-ручках. Без SMTP —
`/email/send-code` возвращает **503 `email_send_failed`**.
