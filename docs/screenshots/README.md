# Marketing screenshots

EN UI captures from mock MiniApp + Dashboard (no Cyrillic).

| App | Viewport | Files |
|-----|----------|-------|
| Dashboard | 1440×900 @2x | `dashboard-*.png` |
| MiniApp | iPhone 14 | `miniapp-*.png` |

## Regenerate

```bash
npm run dev:mock -w xray-vpn-dashboard   # :5173
npm run dev:mock -w xray-vpn-miniapp     # :5174
node scripts/capture-marketing-screenshots.mjs
```

Requires `playwright` (devDependency) and Chromium: `npx playwright install chromium`.
