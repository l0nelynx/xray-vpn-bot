# Connect page & app catalog

The **Connect** page (`/connect` in the Telegram MiniApp) is our own UI for the
"how to install & connect" flow — it replaces bouncing the user to the external
Remnawave subscription page. It renders a per-platform catalog of VPN apps with
install steps and one-tap "add subscription" deep-links.

The only per-user datum is the `subscription_url` (from the authenticated `/me`
response); everything else — the app catalog, install steps, deep-link templates
— comes from a single **app-config** document.

## Where the catalog lives

The catalog format is the upstream **Remnawave subscription-page
`app-config.json`** schema, so configs are portable between the two.

| | Path | Notes |
|---|---|---|
| Bundled default | `services/miniapp/backend/connect/app_config.default.json` | Shipped in the image. Used when no override is mounted. The page works out of the box. |
| Operator override (optional) | mounted to `/app/app-config.json` | If present, served instead of the default. |

Served by the miniapp backend:

```
GET /bot/miniapp/api/connect/app-config
```

The response is cached in-process and invalidated by file mtime, and carries
`Cache-Control: public, max-age=300` (the catalog is non-sensitive). A broken
override falls back to the bundled default (logged).

## Customising the catalog (no frontend rebuild)

1. Copy the bundled default as a starting point:
   ```bash
   cp services/miniapp/backend/connect/app_config.default.json ./app-config.json
   ```
2. Edit `app-config.json`.
3. Mount it into the **miniapp** service (it's already wired as a commented line
   in `docker-compose.yml`):
   ```yaml
   miniapp:
     volumes:
       - ./config.yml:/app/config.yml:ro
       - ./app-config.json:/app/app-config.json:ro   # ← uncomment
   ```
4. Restart only the miniapp container:
   ```bash
   docker compose up -d miniapp
   ```

No frontend image rebuild is needed — the SPA fetches the catalog at runtime.

The override path is configurable via `connect_app_config_path` in `config.yml`
(default `/app/app-config.json`) or the `CONNECT_APP_CONFIG_PATH` env var.

## Schema

```jsonc
{
  "locales": ["en", "ru", "zh", "fa", "fr"],   // languages used in localized strings
  "version": "1",
  "uiConfig": { "installationGuidesBlockType": "cards" },  // (informational)
  "platforms": {
    "ios": {                                    // ios | android | windows | macos | linux | appleTV | androidTV
      "apps": [
        {
          "name": "Happ",
          "featured": true,                     // featured apps sort first + get a badge
          "svgIconKey": "Happ",                 // brand icon key (see Icons)
          "blocks": [                           // ordered install steps
            {
              "title":       { "en": "Add Subscription", "ru": "Добавить подписку" },
              "description": { "en": "Tap the button…",  "ru": "Нажмите кнопку…" },
              "svgIconKey":  "CloudDownload",    // UI step icon
              "svgIconColor": "cyan",            // accent colour name or hex
              "buttons": [
                {
                  "text": { "en": "Add", "ru": "Добавить" },
                  "link": "happ://add/{{SUBSCRIPTION_LINK}}",
                  "type": "subscriptionLink",    // see Button types
                  "svgIconKey": "Plus"
                }
              ]
            }
          ]
        }
      ]
    }
  }
}
```

### Placeholders (substituted client-side, per user)

| Placeholder | Replaced with |
|---|---|
| `{{SUBSCRIPTION_LINK}}` | the user's `subscription_url` (raw) |
| `{{USERNAME}}` | the user's Telegram username |

### Button types

| `type` | Behaviour |
|---|---|
| `external` | Opens an `http(s)` link (e.g. App Store) in the external browser. |
| `subscriptionLink` | Custom-scheme deep-link (`happ://…`). Navigates directly so the OS opens the app. Rendered as the primary button. |
| `copyButton` | Copies the (substituted) link to the clipboard with a toast. |

> **Deep-link caveat.** Custom-scheme links fire reliably from mobile Telegram
> (iOS/Android). From Telegram Desktop/Web they may not — that's expected, the
> user installs on the device whose tab they pick. Test new schemes on a real
> device.

## Adding an app

Add an entry under the relevant `platforms.<os>.apps[]`. Reuse an existing
`svgIconKey` to get an icon immediately, set `featured: true` to surface it, and
provide at least `en` + `ru` strings (other locales fall back to `en`).

## Icons

Icons ship **inside the app-config** under the top-level `svgLibrary` map
(`svgIconKey` → raw SVG markup) — both brand logos and UI glyphs. The frontend
renders them inline (`LibIcon` in `web/apps/miniapp/src/connect/icons.tsx`),
sanitising `<script>`/`on*` handlers first. A missing app key falls back to a
coloured monogram of the app name.

```jsonc
"svgLibrary": {
  "Happ":     "<svg viewBox=\"0 0 24 24\" …>…</svg>",
  "Plus":     "<svg … stroke=\"currentColor\">…</svg>",   // UI glyphs use currentColor
  "FlClashX":  "<svg …>…</svg>"
}
```

Because icons live in the document, adding an app that references **any** key
already in `svgLibrary` (the bundled default ships ~40, far more than the
catalog uses) needs only a miniapp **restart** — no frontend rebuild. To add a
brand-new logo, add its SVG to `svgLibrary` keyed by the `svgIconKey` you
reference. (UI glyphs that use `stroke="currentColor"` inherit the accent colour;
multicolour brand logos keep their own colours.)

## Branding fields & the bundled default

The schema also carries `brandingSettings` (`title`, `logoUrl`, `supportUrl`) and
`baseSettings` (`metaTitle`, …). **Our MiniApp does not use these** — it renders
its own header and branding (`branding_name`). They exist for upstream
compatibility. The **bundled default ships them neutralised** (generic `"VPN"`,
empty URLs) so no operator branding leaks into the public image; set your own in
a mounted override if you serve the catalog elsewhere.

## Why served by the backend (not bundled in the SPA)

The `frontend` container is static-only and mounts no files. Only the backends
mount `config.yml`. Serving the catalog through the miniapp API is therefore the
only way to make it operator-configurable without rebuilding the SPA — the same
pattern as branding (`branding_name` flows through `/me`).
