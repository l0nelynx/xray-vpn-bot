# Frontend stack

Dashboard and MiniApp SPAs live under `web/apps/*` and share `@xray/ui` /
`@xray/api` via npm workspaces (root `package.json`). The browser web portal
(`xray-vpn-web`) is a **separate repo** that mirrors this stack and vendors
shadcn components locally — see its `docs/frontend-stack.md`.

## Pinned versions

| Package | Version | Notes |
|---|---|---|
| `react` / `react-dom` | `^19.1.0` | |
| `react-router` | `^7.7.1` | SPA library mode; import from `react-router` |
| `vite` | `^8.1.0` | Rolldown bundler; Node 22+ in `frontend.Dockerfile` |
| `@vitejs/plugin-react` | `^6.0.0` | Oxc transform |
| `typescript` | `^5.9.2` | |
| `tailwindcss` / `@tailwindcss/vite` | `^4.1.11` | CSS-first, no `tailwind.config.js` |
| `lucide-react` | `^0.525.0` | icons |
| `sonner` | `^2.0.7` | toasts |
| `react-hook-form` / `zod` | `^7.62.0` / `^4.0.17` | forms |
| `@tanstack/react-table` | `^8.21.3` | dashboard tables |
| `recharts` | `^3.1.0` | dashboard charts |
| `@dnd-kit/*` | existing | menu/tariff editors |

UI kit: **shadcn/ui** (New York, `neutral`, dark by default) in
[`web/packages/ui`](../web/packages/ui) — exported as `@xray/ui`.

## Local mock API

```bash
npm run dev:mock -w xray-vpn-dashboard   # :5173
npm run dev:mock -w xray-vpn-miniapp     # :5174
```

Uses MSW (`VITE_MOCK_API=1` via `.env.mock`). See
[local-development.md](local-development.md#mock-api-no-backend).

## Sync checklist vs `xray-vpn-web`

When bumping versions or changing `@xray/ui` tokens/components:

- [ ] Mirror the same dependency pins in `xray-vpn-web/package.json`
- [ ] Port changed files from `web/packages/ui/src/components/*` into
      `xray-vpn-web/src/components/ui/`
- [ ] Diff `web/packages/ui/src/styles/globals.css` vs portal `src/index.css`
- [ ] Rebuild both monorepo apps and the portal
