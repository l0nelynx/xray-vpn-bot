import { http, HttpResponse, type HttpHandler } from "msw";

const API = "/bot/dashboard/api";

function paginate<T>(items: T[], url: URL) {
  const page = Number(url.searchParams.get("page") || 1);
  const perPage = Number(url.searchParams.get("per_page") || 20);
  const start = (page - 1) * perPage;
  return {
    items: items.slice(start, start + perPage),
    total: items.length,
    page,
    per_page: perPage,
  };
}

function okEnvelope<T>(data: T) {
  return { ok: true, data, revision: "mock-1" };
}

const users = [
  {
    id: 1,
    tg_id: 100001,
    username: "alice",
    vless_uuid: "11111111-1111-1111-1111-111111111111",
    rw_id: 10,
    api_provider: "remnawave",
    is_banned: false,
    is_paid: true,
    vip: false,
    email: "alice@example.com",
    language: "ru",
  },
  {
    id: 2,
    tg_id: 100002,
    username: "bob",
    vless_uuid: null,
    rw_id: null,
    api_provider: "remnawave",
    is_banned: false,
    is_paid: false,
    vip: true,
    email: null,
    language: "en",
  },
  {
    id: 3,
    tg_id: 100003,
    username: "carol",
    vless_uuid: "22222222-2222-2222-2222-222222222222",
    rw_id: 11,
    api_provider: "remnawave",
    is_banned: true,
    is_paid: true,
    vip: false,
    email: "carol@example.com",
    language: "ru",
  },
];

const transactions = [
  {
    transaction_id: "tx-mock-001",
    username: "alice",
    user_tg_id: 100001,
    payment_method: "crypto",
    amount: 299,
    order_status: "paid",
    delivery_status: 1,
    days_ordered: 30,
    created_at: "2026-07-01T12:00:00Z",
    expire_date: "2026-07-31T12:00:00Z",
  },
  {
    transaction_id: "tx-mock-002",
    username: "carol",
    user_tg_id: 100003,
    payment_method: "platega",
    amount: 799,
    order_status: "pending",
    delivery_status: 0,
    days_ordered: 90,
    created_at: "2026-07-20T09:30:00Z",
    expire_date: null,
  },
];

const revenue = Array.from({ length: 14 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - (13 - i));
  return { date: d.toISOString().slice(0, 10), revenue: 1200 + i * 85 };
});

const growth = revenue.map((p, i) => ({ date: p.date, count: 40 + i * 3 }));

const menuTree = [
  {
    id: 1,
    parent_id: null,
    text_ru: "Тарифы",
    text_en: "Plans",
    action: "buttons",
    sort_order: 0,
    is_active: true,
    invoice_provider: null,
    invoice_amount: null,
    invoice_currency: null,
    invoice_method: null,
    invoice_days: null,
    invoice_internal_squad_ids: null,
    invoice_external_squad_id: null,
    invoice_traffic_limit_bytes: null,
    invoice_traffic_limit_strategy: null,
    invoice_remnawave_description: null,
    invoice_remnawave_tag: null,
    needs_attention: false,
    children: [
      {
        id: 2,
        parent_id: 1,
        text_ru: "1 месяц",
        text_en: "1 month",
        action: "invoice",
        sort_order: 0,
        is_active: true,
        invoice_provider: "crypto",
        invoice_amount: 10,
        invoice_currency: "USDT",
        invoice_method: "default",
        invoice_days: 30,
        invoice_internal_squad_ids: ["11111111-1111-4111-8111-111111111111"],
        invoice_external_squad_id: "22222222-2222-4222-8222-222222222222",
        invoice_traffic_limit_bytes: 107374182400,
        invoice_traffic_limit_strategy: "MONTH",
        invoice_remnawave_description: "Premium subscription",
        invoice_remnawave_tag: "PREMIUM",
        needs_attention: false,
        children: [],
      },
      {
        id: 3,
        parent_id: 1,
        text_ru: "100 звёзд",
        text_en: "100 Stars",
        action: "invoice",
        sort_order: 1,
        is_active: true,
        invoice_provider: "stars",
        invoice_amount: 100,
        invoice_currency: "XTR",
        invoice_method: "default",
        invoice_days: 30,
        invoice_internal_squad_ids: ["11111111-1111-4111-8111-111111111111"],
        invoice_external_squad_id: "22222222-2222-4222-8222-222222222222",
        invoice_traffic_limit_bytes: 0,
        invoice_traffic_limit_strategy: "NO_RESET",
        invoice_remnawave_description: null,
        invoice_remnawave_tag: null,
        needs_attention: false,
        children: [],
      },
    ],
  },
];

export const handlers: HttpHandler[] = [
  // ── Auth ──────────────────────────────────────────────
  http.post(`${API}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { login?: string; password?: string };
    if (!body.login || !body.password) {
      return HttpResponse.json({ detail: "Enter login and password" }, { status: 400 });
    }
    // Any non-empty credentials work in mock mode
    return HttpResponse.json({ access_token: "mock-dashboard-jwt" });
  }),

  // ── Users ─────────────────────────────────────────────
  http.get(`${API}/users`, ({ request }) => {
    const url = new URL(request.url);
    const search = (url.searchParams.get("search") || "").toLowerCase();
    const filtered = search
      ? users.filter(
          (u) =>
            u.username?.toLowerCase().includes(search) ||
            u.email?.toLowerCase().includes(search) ||
            String(u.tg_id).includes(search),
        )
      : users;
    return HttpResponse.json(paginate(filtered, url));
  }),

  http.get(`${API}/users/:id`, ({ params }) => {
    const user = users.find((u) => u.id === Number(params.id));
    if (!user) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return HttpResponse.json({
      ...user,
      transactions_count: 2,
      total_spent: 1098,
      promo_code: "ALICE10",
      tickets_count: 1,
      bonus_credits: 150,
    });
  }),

  http.get(`${API}/users/:id/transactions`, () => HttpResponse.json(transactions)),

  http.post(`${API}/users/:id/ban`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/users/:id/unban`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/users/:id/vip`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/users/:id/unvip`, () => HttpResponse.json({ ok: true })),
  http.delete(`${API}/users/:id`, () => new HttpResponse(null, { status: 204 })),
  http.patch(`${API}/users/:id/identifiers`, () => HttpResponse.json({ ok: true })),
  http.patch(`${API}/users/:id/email`, () =>
    HttpResponse.json({ ok: true, rw_uuid: "mock-uuid", rw_id: 99 }),
  ),
  http.post(`${API}/users/:id/credits`, () => HttpResponse.json({ ok: true, balance: 250 })),
  http.post(`${API}/users/:id/send-message`, () => HttpResponse.json({ ok: true })),

  // ── Transactions ──────────────────────────────────────
  http.get(`${API}/transactions`, ({ request }) =>
    HttpResponse.json(paginate(transactions, new URL(request.url))),
  ),
  http.get(`${API}/transactions/recent`, () => HttpResponse.json(transactions)),
  http.post(`${API}/transactions/cleanup-stale`, () =>
    HttpResponse.json({ deleted: 0, hours: 24 }),
  ),

  // ── Stats ─────────────────────────────────────────────
  http.get(`${API}/stats/summary`, () =>
    HttpResponse.json({
      period: "30d",
      revenue: { value: 45200, prev: 38100 },
      orders: { value: 128, prev: 110 },
      new_users: { value: 64, prev: 51 },
      avg_order: { value: 353, prev: 346 },
      totals: {
        total_users: 1840,
        active_subs: 920,
        conversion: 18.4,
        revenue_all_time: 890000,
      },
    }),
  ),
  http.get(`${API}/stats/revenue`, () => HttpResponse.json(revenue)),
  http.get(`${API}/stats/user-growth`, () => HttpResponse.json(growth)),
  http.get(`${API}/stats/payment-methods`, () =>
    HttpResponse.json([
      { method: "crypto", count: 80, total: 24000 },
      { method: "platega", count: 40, total: 16000 },
      { method: "crystal", count: 8, total: 5200 },
    ]),
  ),
  http.get(`${API}/stats/order-statuses`, () =>
    HttpResponse.json([
      { status: "paid", count: 110 },
      { status: "pending", count: 12 },
      { status: "failed", count: 6 },
    ]),
  ),

  // ── Telegram menus ─────────────────────────────────────
  http.get(`${API}/menus/screens`, () =>
    HttpResponse.json([
      {
        id: 1,
        slug: "main_new",
        name: "Main · New user",
        message_text_ru: "Выберите подходящий тариф",
        message_text_en: "Choose a subscription plan",
        is_system: true,
        is_active: true,
        buttons: [
          {
            id: 1,
            screen_id: 1,
            text_ru: "Купить Premium",
            text_en: "Buy Premium",
            callback_data: null,
            url: null,
            row: 0,
            col: 0,
            sort_order: 0,
            button_type: "tariff",
            is_active: true,
          },
        ],
      },
    ]),
  ),
  http.post(`${API}/menus/screens`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ id: 1, ...(body as object), buttons: [] });
  }),

  // ── Webapp menu / settings ────────────────────────────
  http.get(`${API}/webapp-menu/tree`, () => HttpResponse.json(menuTree)),
  http.get(`${API}/webapp-menu/remnawave-squads`, () =>
    HttpResponse.json({
      internal: [
        { uuid: "11111111-1111-4111-8111-111111111111", name: "Premium" },
      ],
      external: [
        { uuid: "22222222-2222-4222-8222-222222222222", name: "Default external" },
      ],
    }),
  ),
  http.get(`${API}/webapp-menu/providers`, () =>
    HttpResponse.json({
      providers: [
        {
          name: "crypto",
          payment_method: "CRYPTOPAY",
          currencies: ["USDT", "TON"],
          methods: [{ value: "default", label: "Default" }],
          surfaces: ["bot", "miniapp", "web"],
          webhook_key: "provider",
        },
        {
          name: "stars",
          payment_method: "TG_STARS",
          currencies: ["XTR"],
          methods: [{ value: "default", label: "Default" }],
          surfaces: ["bot", "miniapp"],
          webhook_key: "merchant",
        },
      ],
    }),
  ),
  http.post(`${API}/webapp-menu/nodes`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ id: 100, children: [], ...(body as object) });
  }),
  http.put(`${API}/webapp-menu/nodes/:id`, async ({ request, params }) => {
    const body = await request.json();
    return HttpResponse.json({ id: Number(params.id), children: [], ...(body as object) });
  }),
  http.delete(`${API}/webapp-menu/nodes/:id`, () => new HttpResponse(null, { status: 204 })),
  http.put(`${API}/webapp-menu/reorder`, () => HttpResponse.json({ ok: true })),

  http.get(`${API}/settings/features`, () =>
    HttpResponse.json({ legacy_bot_constructor: false }),
  ),
  http.put(`${API}/settings/features`, () => HttpResponse.json({ ok: true })),
  http.get(`${API}/settings/runtime`, () =>
    HttpResponse.json({
      maintenance: { enabled: false, message: "" },
      values: {},
      sources: {},
    }),
  ),
  http.put(`${API}/settings/runtime`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json(body);
  }),
  http.get(`${API}/settings/payments`, () =>
    HttpResponse.json({
      providers: [
        { name: "crypto", enabled: true, configured: true },
        { name: "platega", enabled: true, configured: true },
      ],
    }),
  ),
  http.put(`${API}/settings/payments/:provider`, async ({ request, params }) => {
    const body = (await request.json()) as object;
    return HttpResponse.json({
      provider: params.provider,
      managed: true,
      source: "dashboard",
      field_meta: [],
      fields: {},
      enabled: true,
      ...body,
    });
  }),
  http.get(`${API}/settings/integrations`, () =>
    HttpResponse.json({
      providers: [
        {
          provider: "smtp",
          enabled: true,
          managed: false,
          source: "yaml",
          fields: {},
          field_meta: [{ name: "smtp_password", secret: true }],
        },
        {
          provider: "android",
          enabled: true,
          managed: false,
          source: "none",
          fields: {},
          field_meta: [{ name: "android_jwt_secret", secret: true }],
        },
        {
          provider: "telemt",
          enabled: true,
          managed: false,
          source: "yaml",
          fields: {},
          field_meta: [{ name: "telemt_header", secret: true }],
        },
        {
          provider: "store",
          enabled: false,
          managed: false,
          source: "none",
          fields: {},
          field_meta: [{ name: "store_api_token", secret: true }],
        },
        {
          provider: "fcm",
          enabled: false,
          managed: false,
          source: "none",
          fields: {},
          field_meta: [{ name: "fcm_sa_json", secret: true }],
        },
        {
          provider: "google_play",
          enabled: false,
          managed: false,
          source: "none",
          fields: {},
          field_meta: [
            { name: "google_play_rtdn_token", secret: true },
            { name: "google_play_sa_json", secret: true },
          ],
        },
        {
          provider: "web",
          enabled: false,
          managed: false,
          source: "none",
          fields: {},
          field_meta: [{ name: "tg_client_secret", secret: true }],
        },
      ],
    }),
  ),
  http.put(`${API}/settings/integrations/:provider`, async ({ request, params }) => {
    const body = (await request.json()) as object;
    return HttpResponse.json({
      provider: params.provider,
      managed: true,
      source: "dashboard",
      field_meta: [],
      fields: {},
      enabled: true,
      ...body,
    });
  }),

  // ── Promos / giveaways / store ────────────────────────
  http.get(`${API}/promos`, ({ request }) =>
    HttpResponse.json(
      paginate(
        [
          {
            promo_code: "WELCOME",
            promo_type: "credit",
            owner_username: null,
            owner_tg_id: 0,
            usage_count: 12,
            days_purchased: 0,
            points_rewarded: 0,
            credit_grant: 50,
          },
        ],
        new URL(request.url),
      ),
    ),
  ),
  http.get(`${API}/promos/settings`, () =>
    HttpResponse.json({
      default_credit_grant: 50,
      points_reward_per_30: 30,
      reward_cap_points: 300,
    }),
  ),
  http.put(`${API}/promos/settings`, () => HttpResponse.json({ ok: true })),
  http.get(`${API}/promos/referral-stats`, ({ request }) =>
    HttpResponse.json(paginate([], new URL(request.url))),
  ),
  http.post(`${API}/promos`, () => HttpResponse.json({ ok: true })),
  http.delete(`${API}/promos/:code`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/giveaways`, ({ request }) =>
    HttpResponse.json(paginate([], new URL(request.url))),
  ),
  http.get(`${API}/store/order-params`, () => HttpResponse.json([])),

  // ── Support ───────────────────────────────────────────
  http.get(`${API}/support/tickets`, ({ request }) =>
    HttpResponse.json(
      paginate(
        [
          {
            id: 1,
            user_id: 1,
            tg_id: 100001,
            username: "alice",
            subject: "Cannot connect",
            status: "open",
            created_at: "2026-07-18T10:00:00Z",
            updated_at: "2026-07-18T11:00:00Z",
          },
        ],
        new URL(request.url),
      ),
    ),
  ),
  http.get(`${API}/support/tickets/:id`, ({ params }) =>
    HttpResponse.json({
      id: Number(params.id),
      user_id: 1,
      tg_id: 100001,
      username: "alice",
      subject: "Cannot connect",
      status: "open",
      created_at: "2026-07-18T10:00:00Z",
      updated_at: "2026-07-18T11:00:00Z",
      messages: [
        {
          id: 1,
          sender: "user",
          text: "Hello, need help with connection",
          created_at: "2026-07-18T10:00:00Z",
          attachments: [],
        },
      ],
    }),
  ),
  http.patch(`${API}/support/tickets/:id`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/support/tickets/:id/reply`, () => HttpResponse.json({ ok: true })),
  http.delete(`${API}/support/tickets/:id/messages/:messageId`, () =>
    new HttpResponse(null, { status: 204 }),
  ),
  http.get(`${API}/support/tickets/:id/attachments/:attachmentId`, () =>
    HttpResponse.arrayBuffer(new ArrayBuffer(8), {
      headers: { "Content-Type": "image/png" },
    }),
  ),

  // ── CRM / Push (minimal) ──────────────────────────────
  http.get(`${API}/crm/segments`, () => HttpResponse.json({ segments: [] })),
  http.post(`${API}/crm/conditions/evaluate`, () =>
    HttpResponse.json({ segment_id: "mock", total: 0, users: [], warning: null }),
  ),
  http.get(`${API}/crm/campaigns`, () => HttpResponse.json({ campaigns: [] })),
  http.post(`${API}/crm/campaigns/launch`, () =>
    HttpResponse.json({ id: 1, status: "queued", queue_status: "ok" }),
  ),
  http.get(`${API}/crm/events`, () => HttpResponse.json({ events: [] })),
  http.get(`${API}/crm/webhooks/catalog`, () => HttpResponse.json({ scopes: [] })),
  http.get(`${API}/crm/webhooks`, () => HttpResponse.json({ rules: [] })),
  http.get(`${API}/crm/actions/types`, () => HttpResponse.json({ action_types: [] })),
  http.get(`${API}/crm/variables`, () => HttpResponse.json({ variables: [] })),
  http.get(`${API}/crm/templates`, () => HttpResponse.json({ templates: [] })),
  http.get(`${API}/crm/remnawave/internal-squads`, () => HttpResponse.json({ squads: [] })),

  http.get(`${API}/push/stats`, () =>
    HttpResponse.json({ token_count: 42, fcm_configured: false }),
  ),
  http.post(`${API}/push/preview-count`, () =>
    HttpResponse.json({ count: 42, audience: "all_tokens" }),
  ),
  http.get(`${API}/push/campaigns`, () => HttpResponse.json({ campaigns: [] })),
  http.post(`${API}/push/campaigns/launch`, () =>
    HttpResponse.json({ id: 1, status: "queued" }),
  ),

  // ── TG admin / Telemt stubs ───────────────────────────
  http.post(`${API}/tg-admin/channel-post`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/tg-admin/sub-clean/scan`, () =>
    HttpResponse.json({ total_checked: 0, to_disable: 0, errors: [] }),
  ),
  http.post(`${API}/tg-admin/sub-clean/execute`, () =>
    HttpResponse.json({ disabled: 0, notified: 0, errors: [] }),
  ),
  http.post(`${API}/tg-admin/telemt-clean/scan`, () =>
    HttpResponse.json({ total_checked: 0, to_delete: 0, errors: [] }),
  ),
  http.post(`${API}/tg-admin/telemt-clean/execute`, () =>
    HttpResponse.json({ deleted: 0, notified: 0, errors: [] }),
  ),

  http.get(`${API}/telemt/system/info`, () =>
    HttpResponse.json(okEnvelope({ version: "mock", uptime_secs: 3600 })),
  ),
  http.get(`${API}/telemt/stats/summary`, () =>
    HttpResponse.json(okEnvelope({ users: 3, connections: 1 })),
  ),
  http.get(`${API}/telemt/health`, () => HttpResponse.json(okEnvelope({ status: "ok" }))),
  http.get(`${API}/telemt/health/ready`, () =>
    HttpResponse.json(okEnvelope({ ready: true, status: "ready" })),
  ),
  http.get(`${API}/telemt/runtime/gates`, () => HttpResponse.json(okEnvelope({}))),
  http.get(`${API}/telemt/runtime/connections/summary`, () =>
    HttpResponse.json(okEnvelope({ enabled: true, data: { totals: { current_connections: 1 } } })),
  ),
  http.get(`${API}/telemt/runtime/events/recent`, () =>
    HttpResponse.json(okEnvelope({ enabled: true, events: [] })),
  ),
  http.get(`${API}/telemt/runtime/tls-fingerprints`, () => HttpResponse.json(okEnvelope({}))),
  http.get(`${API}/telemt/security/posture`, () => HttpResponse.json(okEnvelope({}))),
  http.get(`${API}/telemt/security/whitelist`, () => HttpResponse.json(okEnvelope({ entries: [] }))),
  http.get(`${API}/telemt/limits/effective`, () => HttpResponse.json(okEnvelope({}))),
  http.get(`${API}/telemt/config`, () => HttpResponse.json(okEnvelope({}))),
  http.patch(`${API}/telemt/config`, () => HttpResponse.json(okEnvelope({ applied: true }))),
  http.get(`${API}/telemt/users`, () => HttpResponse.json(okEnvelope([]))),
  http.get(`${API}/telemt/free-params`, () =>
    HttpResponse.json({ enabled: false, days: 1, news_required: true }),
  ),
  http.put(`${API}/telemt/free-params`, () => HttpResponse.json({ ok: true })),

  // ── Catch-all: keep unknown endpoints from crashing the UI ─
  http.all(`${API}/*`, ({ request }) => {
    if (request.method === "GET") {
      return HttpResponse.json({ items: [], total: 0, page: 1, per_page: 20 });
    }
    return HttpResponse.json({ ok: true });
  }),
];
