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
| POST | `/check-uuid` | — | 10/min | Проверить short_uuid+identifier → полный SDK-DTO Remnawave |
| POST | `/migrate` | — | 5/min | Привязать Android-учётку к существующей Remnawave-подписке |
| POST | `/claim/resolve` | — | 5/min | ShortID-first онбординг: статус + email-hint + claim_token |
| POST | `/claim/otp-request` | — | 3/min | Отправить OTP-код на email владельца подписки |
| POST | `/claim/complete` | — | 10/min | OTP + пароль (+ acc_email) → `AuthResponse` |
| POST | `/register` | — | 5/min | Создать пользователя по email + password |
| POST | `/login` | — | 10/min | Получить пару токенов |
| POST | `/refresh` | — | 60/min | Ротация refresh-семейства |
| POST | `/logout` | — | — | Отозвать одно семейство по refresh-токену |
| POST | `/logout-all` | Bearer | — | Отозвать все семейства пользователя |
| POST | `/auth/app-login/create` | Bearer | 5/min | One-time токен для входа приложения (web → app) |
| POST | `/auth/app-login/exchange` | — | 10/min | Обменять one-time токен на `AuthResponse` |
| POST | `/password/change` | Bearer | — | Сменить пароль (нужен текущий) |

### POST /check-uuid

Доступен до регистрации (без Bearer-токена). Используется для онбординга:
клиент извлекает `short_uuid` из subscription-ссылки Remnawave и
**подтверждает владение** этой подпиской, передавая в `identifier` либо
email (содержит `@`), либо username, прописанные в Remnawave.

```jsonc
// request
{
  "short_uuid": "<remnawave short uuid>",
  "identifier": "user@example.com"   // или "user_at_example_com" (username)
}
```

**200** — `identifier` совпал с email/username в Remnawave. Возвращается
**сырой DTO** из `RemnawaveSDK.users.get_user_by_short_uuid`,
сериализованный через `model_dump(mode="json", by_alias=True)`. Бекенд
**ничего не интерпретирует** и не вырезает поля — клиент видит весь
набор атрибутов, который отдаёт upstream-API (uuid, expire_at,
subscription_url, status, traffic_limit_bytes, used_traffic_bytes,
active_internal_squads, hwid_devices, email и т.д.).

Правила сравнения: при наличии `@` сравнивается с `email` Remnawave
(case-insensitive); иначе — с `username` (точное совпадение).

**400 `bad_short_uuid`** — формат не похож на slug (`[A-Za-z0-9_-]{6,64}`).
**403 `identifier_mismatch`** — short_uuid существует, но identifier не
совпал с email/username владельца.
**404 `not_found`** — Remnawave не знает такого пользователя.

### POST /migrate

Создаёт Android-учётку поверх **уже существующей** Remnawave-подписки.
Используется, когда пользователь пришёл с готовым `short_uuid` (например,
бот выдал подписку до появления Android-приложения) и хочет завести
email/password для входа.

Доказательство владения — то же, что в `/check-uuid`: пара
`short_uuid` + `identifier` должна совпасть с данными Remnawave.

```jsonc
// request
{
  "short_uuid": "<remnawave short uuid>",
  "identifier": "user@example.com",   // существующий email/username в Remnawave
  "acc_email":  "new@example.com",    // email для логина в Android (может отличаться)
  "password":   "min8chars"
}
```

**201** → `AuthResponse { tokens, user }`. Полностью эквивалентен ответу
`/register`. Сразу можно использовать access-токен.

`email_verified_at` **не выставляется** — клиент должен дальше пройти
`/email/send-code` + `/email/verify`. При этом верификация email на
аккаунте с уже заполненным `vless_uuid` **не перезаписывает** подписку
бесплатной (free-provisioning пропускается).

Логика выбора локальной строки `users`:
1. `vless_uuid == rw.uuid` (panel user UUID; legacy имя колонки)
2. `users.email`-derived username совпал с `rw.username`
3. `users.email == rw.email`

Если строка найдена и у неё уже есть **и** email, **и** password —
аккаунт считается полностью зарегистрированным, возвращается `409`.
Иначе строка догружается: записывается `acc_email`, `password_hash`,
`vless_uuid`. Если ни одной строки не найдено — создаётся новая,
сразу привязанная к `vless_uuid`.

Ошибки:
- **400 `bad_short_uuid`** — формат slug невалиден.
- **403 `identifier_mismatch`** — identifier не совпал с DTO Remnawave.
- **404 `not_found`** — Remnawave не знает `short_uuid`.
- **409 `already_registered`** — нашли локальную строку с уже заполненной
  парой email+password (вход через `/login`).
- **409 `email_taken`** — `acc_email` принадлежит другому пользователю.
- **502 `upstream_invalid`** — DTO Remnawave без `uuid` (не должно
  случаться, защитный код).

### Claim flow (`/claim/*`) — shortID-first онбординг

Эволюция `/check-uuid` + `/migrate`: клиенту больше не нужно заранее знать
Remnawave-identifier. По shortID из subscription-ссылки сервер сам решает,
какая ветка онбординга применима. **Сессионные токены по одному shortID не
выдаются никогда** — любая мутация требует либо пароль
(`ready_login` → `/claim/login`), либо OTP на owner-email (когда он есть),
либо (для Remnawave-only без mailbox) регистрацию с привязкой по владению
ссылкой подписки.

#### POST /claim/resolve

```jsonc
// request — одно из двух полей
{ "short_uuid": "<remnawave short uuid>" }
{ "url": "https://<subscription_host>/<short_uuid>" }
```

**200:**

```jsonc
{
  "status": "ready_login | needs_password | rw_only",
  "email_hint": "u***@ex***.com",   // null, если deliverable email неизвестен
  "has_telegram": false,
  "claim_token": "<jwt, TTL 15 мин>",
  "subscription_url": "https://...",
  "email_verified": false
}
```

Статусы:

- `ready_login` — в БД есть строка с email+password → `/claim/login`
  (hint + пароль; forgot → `password/reset-*`). Поле `email_verified`
  показывает, подтверждён ли mailbox; если `false`, клиент может
  предложить «указать другой email» (rebind через `/claim/complete` с
  `acc_email` без OTP).
- `needs_password` — строка с email, но без пароля → OTP на этот email →
  установка пароля.
- `rw_only` — подписка есть в Remnawave, credentials в БД нет → регистрация
  `acc_email` + password с привязкой `vless_uuid`. Если есть deliverable
  owner-email (не `@bot.local` / `@miniapp.xyz`) — сначала OTP на него;
  иначе OTP не нужен, новый email подтверждается обычным
  `/email/send-code` + `/verify`.

`claim_token` не содержит PII (только short_uuid) — каждый следующий вызов
заново резолвит состояние. Lookup локальной строки: сначала `vless_uuid`,
затем username/email **только если** у кандидата нет чужого `vless_uuid`
(иначе `ready_login` привязал бы не тот аккаунт). Ошибки: `400 bad_short_uuid`,
`422 invalid_url`, `404 not_found`, `403 banned`, `502 upstream_invalid`.

#### POST /claim/login

```jsonc
{ "claim_token": "<jwt>", "password": "..." }
```

Password-only вход для `ready_login`. **200** → `AuthResponse`.
Ошибки: `401 invalid_credentials`, `401 bad_claim_token`, `403 banned`.

#### POST /claim/otp-request

```jsonc
{ "claim_token": "<jwt>" }
```

Шлёт 6-значный код на канонический email владельца (БД-email, иначе
Remnawave-email). **200** `{"status": "ok"}`. Ошибки: `401 bad_claim_token`,
`409 already_registered` (для `ready_login`), `400 email_missing` (нет
deliverable mailbox — клиент идёт в регистрацию без OTP),
`503 email_send_failed`.

#### POST /claim/complete

```jsonc
{
  "claim_token": "<jwt>",
  "code": "123456",                 // обязателен, если resolve вернул email_hint
  "new_password": "min8chars",
  "acc_email": "login@example.com"  // обязателен для rw_only
}
```

**200** → `AuthResponse { tokens, user }`.

- `needs_password`: пароль установлен, email помечен подтверждённым (OTP на
  него и был доставлен).
- `rw_only` + owner-email: строка создана/дозаполнена как в `/migrate`. Если
  `acc_email` совпал с адресом OTP — email сразу подтверждён; иначе дальше
  обычный `/email/send-code` + `/verify`.
- `rw_only` без owner-email: то же связывание без OTP; email unverified.
  Повторный complete на ту же `vless_uuid` при незавершённом verify
  перезаписывает email/password (исправление опечатки).
- `ready_login` + `email_verified=false` + `acc_email`: overwrite без OTP
  (исправление опечатки с экрана login).

Ошибки: `401 bad_claim_token`, `400 code_invalid | code_expired |
acc_email_required`, `429 code_exhausted`,
`409 already_registered | email_taken`.

### One-time app login (`/auth/app-login/*`)

Хендофф web → приложение: авторизованная web-сессия чеканит короткоживущий
одноразовый токен, приложение получает его через deeplink
`cheezyvpn://login/<token>` (Desktop) или `cheezy://login/<token>` (Android /
legacy Desktop) и обменивает на обычную пару токенов.

- `POST /auth/app-login/create` (Bearer) → `{"token": "...", "expires_in": 90}`.
  В БД хранится только sha256 токена; новый token помечает предыдущий pending
  token того же пользователя как `superseded`.
- `POST /auth/app-login/exchange` — `{"token": "..."}` → `AuthResponse`.
  Атомарный consume-on-use: повторный или параллельный обмен →
  `401 bad_app_login_token`.
- `POST /auth/app-login/status` (Bearer) — `{"token": "..."}` →
  `{"status": "pending" | "exchanged" | "expired" | "superseded"}`.
  Проверять состояние может только владелец токена.

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
| POST | `/email/verify` | Bearer | 10/min | Подтвердить код → выдаётся бесплатная подписка (если ещё нет) |
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

**Исключение:** если у пользователя уже заполнен `vless_uuid` (например, после
`/migrate` или ручной привязки), FREE-provisioning **пропускается**, чтобы не
затереть существующую подписку.

---

## 3. Платежи (`/api/android/payments`)

Внешние провайдеры (A-Pay, Platega). Для IAP — раздел 4.

Источник тарифов — **Tariff Constructor** в дашборде (таблица `webapp_menu_nodes`,
тот же источник, что у miniapp `/api/menu/tree`). Клиент получает дерево через
`/menu` и передаёт в `/invoice` только `node_id` выбранного узла. Provider/
amount/currency/method/days и delivery squad сервер достаёт сам — клиент **не
передаёт** никаких ценовых параметров (на мобильном клиенте всё подменяемо).
Для Android фильтруем только узлы с провайдерами `apay`, `platega` и
`paritypay`; Telegram Stars отсекаются.

| Метод | Путь | Auth | Rate | Назначение |
|---|---|---|---|---|
| GET | `/menu` | Bearer | — | Дерево тарифов из Tariff Constructor (Android-фильтр) |
| GET | `/providers` | — | — | Список доступных провайдеров (apay, platega, paritypay) |
| POST | `/invoice` | Bearer + verified | 10/min | Создать счёт по `node_id`, получить URL |
| GET | `/transactions` | Bearer | — | Последние 50 транзакций пользователя |
| GET | `/transactions/{id}` | Bearer | — | Состояние конкретной транзакции |

### GET /menu

**200**:
```jsonc
{
  "tree": [
    {
      "id": 1,
      "parent_id": null,
      "text": "Premium",
      "action": "buttons",            // группа — раскрывает children
      "invoice": null,
      "children": [
        {
          "id": 7,
          "parent_id": 1,
          "text": "30 дней — 199 ₽",
          "action": "invoice",
          "invoice": {
            "provider": "apay",       // только для отображения цены/способа
            "amount": 199.0,          // в UI; в /invoice ничего из этого
            "currency": "RUB",        // не передаётся
            "method": null,
            "days": 30,
            "tariff_slug": "premium_30"
          },
          "children": []
        }
      ]
    }
  ]
}
```

Узлы с invoice-провайдерами не из `(apay, platega, paritypay)` отрезаются на сервере, как
и пустые ветки после фильтрации. Клиент рендерит дерево как есть; для покупки
ему нужен только `node.id`.

### POST /invoice

```jsonc
{
  "node_id": 7,                       // id узла из /menu (action=invoice)
  "description": "30 дней Premium"    // опционально, для отображения в банке
}
```

Сервер берёт provider/amount/currency/method/days и delivery squad из узла. Никаких
тарифных параметров от клиента не принимается — это защита от подмены цены и
сквада на стороне приложения.

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

Ошибки:
- **404 `node_not_found`** — узла с таким id нет или он деактивирован.
- **400 `node_not_invoice`** — узел существует, но это группа (`action != invoice`)
  или его провайдер не из Android-набора.
- **400 `node_misconfigured`** — узел инвойсный, но `amount` или `days` не
  заполнены (черновик в дашборде).
- **400 `provider_unavailable`**, **400 `currency_unsupported`**,
  **502 `invoice_failed`** — ошибки на стороне платёжного провайдера.

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
из `config.yml`. Если секрет не настроен, endpoint отключён и возвращает
**503 `iap_not_configured`**. После настройки корректные, но незначимые или
повреждённые Pub/Sub payload возвращают 200, чтобы Google не повторял их
бесконечно.

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

## 7. FCM push tokens (`/api/android/fcm`)

Регистрация Firebase Cloud Messaging токена для пушей из Dashboard
(страница **Push**). Email verify **не** требуется.

| Метод | Путь | Auth | Rate | Назначение |
|---|---|---|---|---|
| POST | `/token` | Bearer | 30/min | Зарегистрировать / обновить токен |
| DELETE | `/token` | Bearer | 30/min | Снять токен (logout) |

### POST /token

```jsonc
{
  "token": "<fcm-device-token>",
  "app_version": "1.2.3",   // optional
  "platform": "android"     // optional, default android
}
```

**200** `{"status":"ok"}`. Один физический токен привязывается к одному
`user_id` (при смене аккаунта на устройстве — перепривязка).

### DELETE /token

```jsonc
{ "token": "<fcm-device-token>" }
```

**200** `{"status":"ok"}` даже если токена уже нет.

Клиент: после login/refresh — `POST /token`; на logout — `DELETE /token`.
Рассылка создаётся в Dashboard → Push (не из Android API).

---

## Конвенции

- **Время** — ISO-8601 UTC (`...Z` или `+00:00`).
- **Деньги** — `float` + ISO-код валюты, без копеек/центов.
- **`node_id`** в `/payments/invoice` — id узла из `/payments/menu`. Это
  единственное, что клиент шлёт для покупки: цена, валюта, дни и slug тарифа
  определяются на сервере по узлу. Подмена цены/сквада со стороны приложения
  невозможна.
- **Bearer-токен** в `Authorization: Bearer <jwt>`. На 401 с любым `code` —
  выкинуть access, дёрнуть `/refresh`. На 401 после refresh — разлогинить.
- **Rate limits** возвращают **429** с `{"detail": {"code": "rate_limited"}}`.

## Что нужно для запуска

Предпочтительно: **Dashboard → Settings → Android / Email / Push·Play**
(секреты шифруются в `app_integrations`). YAML остаётся fallback до Save.

В `config.yml` (или Dashboard):

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

# Google Play IAP — package/rtdn в Dashboard; SA JSON предпочтительно вставить в UI
google_play_package_name: "com.example.app"
google_play_service_account_path: "/run/secrets/play-sa.json"  # fallback path
google_play_rtdn_token: "<random>"

# FCM push — project id + SA JSON в Dashboard → Push/Play (path = fallback)
fcm_project_id: "your-firebase-project-id"
fcm_service_account_path: "/app/fcm-sa.json"
```

Без Android-секции `/api/android/*` отвечает 500 на auth-ручках. Без SMTP —
`/email/send-code` возвращает **503 `email_send_failed`**.

## Event-log в Telegram

Если в `config.yml` заданы `admin_bot_token` и `logs_id` — сервер шлёт короткие
HTML-уведомления в указанный чат на ключевые события:

- 🆕 регистрация Android-пользователя
- ✅ подтверждение email (после `/email/verify`)
- 🧾 создание инвойса — для всех источников (Android, miniapp, бот)
- 📦 успешная доставка подписки в Remnawave
- ❌ неуспешная доставка (с краткой причиной)
- 🔗 привязка Telegram-аккаунта к Android

Уведомления не блокирующие: отвал Telegram не влияет на платежи и регистрацию,
ошибки логируются как `notify_log: send failed`. Если `logs_id` пустой или
`admin_bot_token` не задан — это silent no-op.

```yaml
admin_bot_token: "<token>"
logs_id: -1001234567890     # numeric chat id (channel/group/private)
```
