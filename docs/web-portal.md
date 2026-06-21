# Web Portal

A public-facing SaaS-branded client portal served by the **miniapp** service alongside the Telegram MiniApp. Users register with an invite code, verify email, and manage their VPN subscription through a browser — no Telegram required.

Default branding: **Cheeze Networks** (configurable).

---

## Architecture

### Multi-page Vite build

`miniapp/frontend/vite.config.ts` declares two entry points:

| Entry | HTML | Entry TS | Built bundle |
|---|---|---|---|
| Telegram MiniApp | `index.html` | `src/main.tsx` | `assets/main-*.js` |
| Web Portal | `web.html` | `src/web/main.tsx` | `assets/web-*.js` |

Both are built with `base: "/bot/miniapp/"`, so all assets are served from `/bot/miniapp/assets/`.

### Runtime config injection

`miniapp/backend/main.py` reads `web.html` from disk and injects a `<script>` block before `</head>` on every request:

```python
snippet = (
    f"<script>"
    f"window.__WEB_BASE__={json.dumps(WEB_BASE)};"
    f"window.__WEB_BRAND_NAME__={json.dumps(WEB_BRAND_NAME)};"
    f"window.__WEB_BRAND_LOGO__={json.dumps(WEB_BRAND_LOGO)};"
    f"</script>"
)
html = html.replace("</head>", f"{snippet}</head>", 1)
```

This means branding and base-path changes take effect on container restart — no frontend rebuild required.

### React Router basename

`miniapp/frontend/src/web/main.tsx` reads the injected value:

```tsx
const webBase: string = window.__WEB_BASE__ ?? "/";
<BrowserRouter basename={webBase}>
```

---

## Config keys (`config.yml`)

All optional. Read in `miniapp/backend/config.py`.

| Key | Default | Description |
|---|---|---|
| `web_base_path` | `/` | URL prefix for all portal routes. Must match nginx `location` block. Example: `/bot/web`. |
| `web_brand_name` | `Cheeze Networks` | Brand name shown in header, logo area, page titles. |
| `web_brand_logo` | _(inline SVG)_ | URL to SVG/PNG logo. If empty, uses the built-in `CheezyLogo` component. |

---

## Nginx setup

The miniapp service runs on port 8001 (no host mapping — accessed via docker network).

Typical nginx configuration:

```nginx
upstream miniapp { server miniapp:8001; }

# Telegram MiniApp
location /bot/miniapp {
    proxy_pass http://miniapp;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# Web portal at /bot/web (when web_base_path = /bot/web)
location /bot/web {
    proxy_pass http://miniapp;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}

# Web portal at root (when web_base_path = /)
location / {
    proxy_pass http://miniapp;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Only add the location block that matches your `web_base_path`.

---

## Frontend structure

```
miniapp/frontend/src/web/
├── main.tsx              # BrowserRouter with dynamic basename
├── App.tsx               # LangProvider + ConfigProvider + Routes
├── branding.ts           # BRAND_NAME, BRAND_LOGO from window.__WEB_BRAND_*
├── locale.tsx            # i18n: LangProvider, useLang(), EN + RU translations
├── api/client.ts         # Typed API client
├── auth/AuthContext.tsx  # JWT auth context
├── components/
│   ├── BrandLogo.tsx     # <img> if BRAND_LOGO set, else <CheezyLogo>
│   └── CheezyLogo.tsx    # Inline SVG (yellow + white on dark background)
└── pages/
    ├── LandingPage.tsx
    ├── LoginPage.tsx
    ├── RegisterPage.tsx
    ├── VerifyEmailPage.tsx
    └── DashboardPage.tsx      # Sidebar layout + tab routing
        └── dashboard/
            ├── SubscriptionTab.tsx
            ├── BuyTab.tsx         # Tree navigation (mirrors MiniApp BuyMenuPage)
            ├── DevicesTab.tsx
            └── SettingsTab.tsx
```

---

## i18n

`locale.tsx` exports `LangProvider` and `useLang()`.

- Default language: **English**
- Available: `en` | `ru`
- Toggled via button in the dashboard header (`L.lang_toggle` shows opposite language code)
- Persisted in `localStorage` under key `"web_lang"`
- Russian `days()` function uses proper Slavic pluralization: "1 день / 2 дня / 5 дней"

Usage in any component:
```tsx
const { L, lang, toggle } = useLang();
// L.menu_subscription → "Subscription" / "Подписка"
// L.days(30) → "30 days" / "30 дней"
```

`LangProvider` must wrap the entire app (done in `App.tsx`).

---

## Branding

`miniapp/frontend/src/web/branding.ts`:
```ts
export const BRAND_NAME: string = window.__WEB_BRAND_NAME__ || "Cheeze Networks";
export const BRAND_LOGO: string = window.__WEB_BRAND_LOGO__ || "";
```

`BrandLogo` component:
- If `BRAND_LOGO` is set → renders `<img src={BRAND_LOGO}>` (sized to `size` prop)
- Otherwise → renders `CheezyLogo` (yellow `#ffed00` + white `#ffffff` paths; white was changed from black to be visible on the dark `#0B0B14` background)

---

## Backend API

All web API endpoints share the base path `/bot/miniapp/api/` (the miniapp API prefix). The web-specific router is at `miniapp/backend/web/web_router.py`.

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/web/validate-invite` | None | Validate invite code; returns `{ valid, discount_percent }` |
| `POST` | `/web/register` | None | Register with email + password + invite code; creates `PromoRedemption` with `tg_id = -user.id` |
| `GET` | `/web/payments/menu` | JWT | Dynamic button-tree menu with user's current discount applied |
| `POST` | `/web/payments/invoice` | JWT | Create payment invoice; returns payment URL |

Auth endpoints (shared with Android):
- `POST /android/auth/login`
- `POST /android/auth/refresh`
- `GET /android/me`
- `POST /android/auth/email/send-code`
- `POST /android/auth/email/verify`
- `GET /android/devices`
- `DELETE /android/devices/{hwid}`
- `POST /android/sessions/revoke-all`
- `POST /android/auth/change-password`

---

## Registration flow

1. User enters invite code → debounced `validate-invite` call shows validity + discount
2. User completes form (email, password, confirm) → `POST /web/register`
3. Backend creates `User` record + `PromoRedemption(tg_id=-user.id, promo_id=..., ...)`
4. JWT tokens returned → stored in `AuthContext`
5. Redirect to `/verify-email`

**Why negative tg_id for web users:** The promo/discount system keys discounts by `tg_id`. Web users have no Telegram account. Using `-user.id` (negative integer) guarantees no collision with real Telegram IDs (always positive). Discount lookup: `get_effective_discount(session, -user.id)`.

---

## Dashboard sidebar layout

`DashboardPage.tsx` uses antd `Layout` with these constraints to prevent sidebar scrolling:

```
Layout (height: 100vh; overflow: hidden)
├── Sider (height: 100vh; position: sticky; top: 0; overflow: hidden)
│   └── flex column (height: 100%)
│       ├── Logo/brand link (flexShrink: 0) → links to "/"
│       ├── Menu (flex: 1; overflowY: auto)
│       └── Logout button (flexShrink: 0; paddingBottom: 60px)
│           (60px avoids the antd collapse trigger, which is ~48px and position:fixed)
└── Layout (flex column; overflow: hidden)
    ├── Header (flexShrink: 0)
    └── Content (flex: 1; overflowY: auto)  ← only this scrolls
```

---

## BuyTab tree navigation

Mirrors `miniapp/frontend/src/App.tsx`'s `BuyMenuPage`. State: `path: number[]` (array of node IDs drilled into).

- `GroupCard` — renders nodes with `action === "buttons"` (folder, shows child count)
- `TariffCard` — renders nodes with `action === "invoice"` (price, discount strikethrough, pay button)
- Breadcrumb at top; back button when `path.length > 0`
- Both groups and invoices can coexist at the same tree level

**Do not flatten the tree** — the menu structure mirrors what admins configure in the admin dashboard.

---

## Security

- Rate limiting via `slowapi` (on `/web/validate-invite`, `/web/register`, and auth endpoints)
- `miniapp/backend/web/brute_force.py` — in-memory tracker: 20 failures/hour per IP → 24h block
- Email must be verified before payments are allowed (`email_not_verified` error code)
- JWT access + refresh token pair; `POST /android/sessions/revoke-all` invalidates all sessions
