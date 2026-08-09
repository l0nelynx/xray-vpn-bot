# Marketing screenshots

EN UI captures from mock MiniApp + Dashboard (no Cyrillic).

| App | Viewport | Files |
|-----|----------|-------|
| Dashboard | 1440×900 @2x | `dashboard-*.png` |
| MiniApp | iPhone 14 | `miniapp-*.png` |

UX review captures live in `miniapp-ux/`. The matrix covers RU/EN on iPhone 14,
Pixel 7, and a 478×790 Telegram Desktop webview for onboarding, email login,
contextual home states, every payment state, connection verification, and help.

## Regenerate

```bash
npm run dev:mock -w xray-vpn-dashboard   # :5173
npm run dev:mock -w xray-vpn-miniapp     # :5174
node scripts/capture-marketing-screenshots.mjs

# MiniApp UX review matrix (MiniApp mock server only)
node scripts/capture-miniapp-ux-previews.mjs

# Optional focused run
MINIAPP_PREVIEW_TARGETS=telegram-desktop \
MINIAPP_PREVIEW_LANGUAGES=ru \
MINIAPP_PREVIEW_CAPTURES=home-connected,subscriptions,settings,connect-wizard,help \
node scripts/capture-miniapp-ux-previews.mjs
```

Requires `playwright` (devDependency) and Chromium: `npx playwright install chromium`.
