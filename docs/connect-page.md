# Connect page & app catalog

The **Connect** page (`/connect` in the Telegram MiniApp) is our own UI for the
"how to install & connect" flow. Users explicitly choose a platform, then a
client, then see that client's short instruction. There are no platform
carousels, app accordions or decorative installation progress rails.

The subscription URL and its copy action are visible at the top of every
screen, including while the catalog is unavailable. A clipboard failure opens
a selectable full URL. Multiple subscriptions use a separate selection dialog.
The home action for an already-used subscription reads “How to connect?”.

The optional **another device** mode has a visible checkbox on every selection
and instruction screen. Toggling it preserves the current screen, platform and
client, and immediately updates the link/QR actions. It follows the same choices and offers copy
and QR actions for subscription, installation and browser-account links. QR
generation runs locally in a lazy-loaded module; personal URLs are never sent
to a QR service. Each QR identifies its resource. A subscription QR must be
imported by a compatible VPN client; scanning it with a camera does not
necessarily import it. TV guides retain their phone-transfer instructions.

Selection is represented by `step=platform|clients|guide`, `platform`, `app`,
and `device=other` in the route query. `subscription_id` and `source` survive
navigation. Invalid selections return to the relevant chooser. No personal
URL is stored in route parameters. Telegram BackButton and in-page back return
to the previous choice; browser history and reload retain the route's choices.

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
          "featured": true,                     // legacy recommendation hint
          "recommended": true,                  // optional explicit MiniApp preference
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

### Optional MiniApp metadata

Existing catalogs without these fields continue to render all their blocks
and buttons. MiniApp adds the following optional fields to the bundled catalog:

- `apps[].recommended`: explicit preference. Otherwise CheezyVPN wins when
  present, followed by the first `featured` app. Explicit `false` opts out.
  Only the chosen recommendation receives a compact badge; all clients remain
  visible in the same list, with equal row heights.
- `blocks[].purpose`: `install`, `account`, `import`, `manual`, `enable`, or
  `help`. Necessary client-specific actions (HWID, TUN, routing, TV transfer)
  remain in the instruction.
- `blocks[].otherDescription`: optional localized text for another-device mode.
- `buttons[].purpose`: `install`, `account`, `import`, or `help`, independent
  of how the button executes. This distinguishes browser sign-in from download.
- `buttons[].secondary`: optional lower visual emphasis, e.g. “All releases”.

The legacy adapter identifies account links by `/claim`, subscription actions
by placeholders or button type, and otherwise treats external links as
installation. For accurate help/download analytics, annotate legacy external
help buttons with `purpose: "help"`. No behavior depends on translated labels.
Consumers with a strict upstream schema can remove these optional metadata
fields when exporting the catalog to Remnawave; MiniApp's legacy adapter still
supports the original format. MiniApp currently supports Russian and English;
upstream locales retain existing translations where unchanged and use English
fallback for edited content.

### Verification and analytics

Downloading, copying or showing QR does not start verification. On the current
device, import/account actions or the explicit “Check subscription” button may
check the selected subscription. Another-device mode does not claim to verify
that device. `connected` means the subscription has a connection history; it is
not proof that this specific device is connected. Unknown status is shown only
after a requested check. Changing the selection cancels pending polling.

Events `connect_platform_selected`, `connect_app_selected`,
`connect_guide_opened`, `connect_link_copied`, and `connect_qr_opened` use the
existing UX endpoint. Optional `device_mode` and `resource` are finite categories
stored in event metadata. URL contents are never included. Historical checks
use `connection_verified` with `outcome: "subscription_history"`; do not treat
that event as proof of a new-device conversion.

> **Deep-link / query handling.** The Mini App webview can't launch custom
> schemes (`happ://…`) directly — `tg.openLink` only opens `http(s)`. Telegram's
> `openLink` also **strips URL fragments** on external https, and Remnawave
> often does **not** substitute `{{SUBSCRIPTION_LINK}}` inside a `#fragment`.
> Desktop claim buttons therefore use **query** params
> (`https://cheezyvpn.uk/claim?client=desktop&url={{SUBSCRIPTION_LINK}}`). Custom-scheme
> buttons and any https URL that still carries `?`/`#` with the subscription
> open a static redirector, `web/apps/miniapp/public/connect-open.html`
> (served at `/bot/miniapp/connect-open.html`); the real target rides in the
> redirector's own `#fragment` (same-origin) and `connect-open.html` then
> validates the destination against known HTTPS hosts and custom schemes before
> calling `location.replace`. It uses distinct browser/app copy. Plain
> `external` buttons without query/fragment
> (App Store / Google Play / GitHub) still open directly. Adding the
> redirector file needs a `frontend` image rebuild (it's a build-time asset).

## Adding an app

Add an entry under the relevant `platforms.<os>.apps[]`. Reuse an existing
`svgIconKey` to get an icon immediately, set `featured: true` to surface it, and
provide at least `en` + `ru` strings (other locales fall back to `en`).

## CheezyVPN / CheezyClash entries

The bundled default ships our own clients as `featured` on four platforms:

| Platform | App | Key buttons |
|---|---|---|
| `android` | CheezyVPN | APK download + `cheezy://add/{{SUBSCRIPTION_LINK}}` (subscriptionLink) |
| `windows` / `macos` / `linux` | CheezyVPN | GitHub Releases + browser claim page (`external`) + copy-link fallback |

Notes:

- For CheezyVPN on desktop, installation comes first, followed by browser
  account connection and enabling VPN. The browser connection is a primary
  action. Manual import is a short fallback beside it, using the always-visible
  subscription link. Download labels identify x64/arm64/AppImage restrictions.
- `cheezy://add/…` expects the **raw** subscription URL after the host segment.
  The client's deep-link parser percent-decodes `%XX` only when present, so the
  raw substitution `fillLink` performs is parsed correctly. Senders that build
  the link by hand may percent-encode; both forms work.
- The desktop "Connect via browser" button points at the web portal `/claim`
  with the subscription in a **query** param
  (`https://cheezyvpn.uk/claim?client=desktop&url={{SUBSCRIPTION_LINK}}`) so Remnawave
  substitutes the placeholder (it often skips `#fragment`s). The portal
  resolves the claim status via `POST /api/android/claim/resolve`
  (see [android-api.md](android-api.md)) and, after auth, hands the session to
  CheezyVPN via `cheezyvpn://login/<one-time token>`. Android keeps
  `cheezy://`; CheezyClash Desktop uses `cheezyclash://add` for import only.

## Using the catalog on the Remnawave subscription page

The format is the upstream Remnawave subscription-page `app-config.json`, so
the same document can be uploaded as-is: in the Remnawave panel open the
**Subscription Page** template settings and paste the catalog JSON (or point
the subscription-page container at the file, depending on your deployment).
Remnawave performs the same `{{SUBSCRIPTION_LINK}}` substitution, so the
CheezyVPN deep-link buttons work identically there. Remember to fill
`brandingSettings` / `baseSettings` in the copy you upload — the bundled
default ships them neutralised.

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

## Local preview and regression checks

Run `npm run dev:mock -w xray-vpn-miniapp` and open
`http://127.0.0.1:5174/bot/miniapp/connect?mock=connection-never-ru`.
The MSW mock imports the real bundled app catalog, with fictitious subscription
URLs. Run `node scripts/support-mock-server.mjs` alongside it for the support
tab and unread badge API. Neither command needs production credentials.

`node scripts/test-miniapp-connect.mjs` checks catalog semantics and the ru/en
browser matrix: navigation, visible alternatives at 360×640, copy and manual
fallback, QR decoding (including long URLs), QR overflow, subscription changes,
desktop redirects, verification outcomes, missing catalog, single subscription,
single client and enlarged text. It writes review screenshots to
`docs/screenshots/miniapp-connect-redesign/`. Requires Node 22.18+ and a
Playwright browser; `PLAYWRIGHT_CHANNEL=chrome` selects installed Chrome.
The standard MiniApp build checks TypeScript. Server telemetry checks live in
`services/miniapp/tests/test_connect_ux_events.py`.

Additional mock scenarios: `catalog-error`, `catalog-empty`, `long-link`,
`qr-overflow`, `single`, `empty`, `connected`, `connection-unknown`, and
`connection-never`, with `-ru` / `-en` suffixes. `preview_timeout=1` shortens
verification only in mock mode.
