import { http, HttpResponse, type HttpHandler } from "msw";
import type { ApiAlertSettings, ManagedSubscription } from "../api/types";

const API = "/bot/dashboard/api";

let mockBranding = {
  branding_name: "MockVPN",
  branding_logo_url: "",
  has_custom_logo: false,
  updated_at: "2026-08-15T10:00:00Z",
};

const mockGiveaway = {
  id: 42,
  title: "Summer Connection Giveaway",
  channel_text: "",
  status: "drawn",
  config: {
    distribution: ["bot"],
    entry_condition: "click_only",
    ticket_sources: [],
    chance_mode: "static",
    winner_selection: "random",
  },
  winner_count: 9,
  starts_at: "2026-08-01T10:00:00",
  ends_at: "2026-08-14T20:00:00",
  drawn_at: "2026-08-15T09:30:00",
  created_at: "2026-08-01T08:00:00",
  participants: 24,
  tickets: 47,
};

const mockWinners = Array.from({ length: 9 }, (_, index) => ({
  rank: index + 1,
  tg_id: 7123456700 + index,
  username: index === 4 ? null : `winner_${index + 1}_telegram`,
  tickets: index + 2,
  ticket_number: 101 + index * 3,
}));

const mockParticipants = Array.from({ length: 18 }, (_, index) => ({
  tg_id: 7123456700 + index,
  username: `participant_${index + 1}`,
  joined_at: "2026-08-02T12:00:00",
  ticket_count: index + 1,
}));

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
    subscriptions_count: 2,
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
    subscriptions_count: 0,
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
    subscriptions_count: 1,
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

let mockUserSubscriptions: ManagedSubscription[] = [
  {
    id: 1,
    rw_id: 10,
    label: "Main",
    product_key: null,
    source: "telegram",
    is_primary: true,
    tariff: "Premium",
    status: "active",
    days_left: 18,
    expire_iso: "2026-08-13T00:00:00Z",
    data_limit_gb: 200,
    traffic_used_gb: 42.5,
    devices_count: 2,
    subscription_url: "https://example.com/sub/main",
  },
  {
    id: 2,
    rw_id: 12,
    label: "Marketplace",
    product_key: "marketplace",
    source: "marketplace",
    is_primary: false,
    tariff: "Premium",
    status: "active",
    days_left: 61,
    expire_iso: "2026-09-25T00:00:00Z",
    data_limit_gb: null,
    traffic_used_gb: 9.2,
    devices_count: 1,
    subscription_url: "https://example.com/sub/marketplace",
  },
];

let apiAlertSettings: ApiAlertSettings = {
  enabled: true,
  server_error_threshold: 20,
  latency_p95_ms: 2000,
  latency_min_requests: 20,
  health_failures: 3,
  cooldown_minutes: 30,
};

const apiHealthSeries = Array.from({ length: 24 }, (_, index) => {
  const date = new Date(Date.now() - (23 - index) * 60 * 60 * 1000);
  const incident = index === 17 || index === 18;
  return {
    bucket: date.toISOString(), requests: 90 + index * 4,
    status_2xx: 82 + index * 4, status_3xx: 2,
    status_4xx: 5 + (index % 3), status_5xx: incident ? 14 : index === 19 ? 3 : 0,
    error_rate: incident ? 12.4 : 2.1, p50_ms: 68 + index,
    p95_ms: incident ? 2380 : 320 + index * 7, p99_ms: incident ? 6100 : 760 + index * 11,
  };
});

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
  http.get(`${API}/users/:id/subscriptions`, ({ params }) =>
    HttpResponse.json({ subscriptions: Number(params.id) === 1 ? mockUserSubscriptions : [] }),
  ),
  http.post(`${API}/users/:id/subscriptions`, async ({ request }) => {
    const body = (await request.json()) as { rw_id: number; label?: string; make_primary?: boolean };
    const next = {
      ...mockUserSubscriptions[0],
      id: Math.max(0, ...mockUserSubscriptions.map((item) => item.id)) + 1,
      rw_id: body.rw_id,
      label: body.label || null,
      source: "dashboard",
      is_primary: Boolean(body.make_primary),
    };
    if (next.is_primary) {
      mockUserSubscriptions = mockUserSubscriptions.map((item) => ({ ...item, is_primary: false }));
    }
    mockUserSubscriptions.push(next);
    return HttpResponse.json(next);
  }),
  http.patch(`${API}/users/:id/subscriptions/:subscriptionId`, async ({ params, request }) => {
    const body = (await request.json()) as { label?: string | null };
    const id = Number(params.subscriptionId);
    mockUserSubscriptions = mockUserSubscriptions.map((item) =>
      item.id === id ? { ...item, label: body.label || null } : item,
    );
    return HttpResponse.json(mockUserSubscriptions.find((item) => item.id === id));
  }),
  http.post(`${API}/users/:id/subscriptions/:subscriptionId/primary`, ({ params }) => {
    const id = Number(params.subscriptionId);
    mockUserSubscriptions = mockUserSubscriptions.map((item) => ({ ...item, is_primary: item.id === id }));
    return HttpResponse.json(mockUserSubscriptions.find((item) => item.id === id));
  }),
  http.delete(`${API}/users/:id/subscriptions/:subscriptionId`, ({ params }) => {
    mockUserSubscriptions = mockUserSubscriptions.filter((item) => item.id !== Number(params.subscriptionId));
    return HttpResponse.json({ ok: true });
  }),

  http.post(`${API}/users/:id/ban`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/users/:id/unban`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/users/:id/vip`, () => HttpResponse.json({ ok: true })),
  http.post(`${API}/users/:id/unvip`, () => HttpResponse.json({ ok: true })),
  http.delete(`${API}/users/:id`, () => new HttpResponse(null, { status: 204 })),
  http.patch(`${API}/users/:id/identifiers`, () => HttpResponse.json({ ok: true })),
  http.patch(`${API}/users/:id/email`, () =>
    HttpResponse.json({ ok: true, rw_id: 99 }),
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
  http.get(`${API}/branding`, () =>
    HttpResponse.json({
      branding_name: mockBranding.branding_name,
      logo_url: `${API}/branding/logo`,
      favicon_url: `${API}/branding/icon/64.png`,
      manifest_url: `${API}/branding/manifest.webmanifest`,
    }),
  ),
  http.get(`${API}/branding/logo`, () =>
    HttpResponse.text(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="24" fill="#7c6cff"/><path d="M25 32h14l11 32 11-32h14L57 76H43z" fill="white"/></svg>',
      { headers: { "Content-Type": "image/svg+xml" } },
    ),
  ),
  http.get(`${API}/settings/branding`, () => HttpResponse.json(mockBranding)),
  http.put(`${API}/settings/branding`, async ({ request }) => {
    const body = (await request.json()) as { branding_name: string; branding_logo_url: string | null };
    mockBranding = {
      branding_name: body.branding_name,
      branding_logo_url: body.branding_logo_url || "",
      has_custom_logo: !!body.branding_logo_url,
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json(mockBranding);
  }),
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
    HttpResponse.json(paginate([mockGiveaway], new URL(request.url))),
  ),
  http.get(`${API}/giveaways/:id`, () => HttpResponse.json(mockGiveaway)),
  http.get(`${API}/giveaways/:id/participants`, () =>
    HttpResponse.json({ items: mockParticipants, total: mockParticipants.length, page: 1, per_page: 100 }),
  ),
  http.get(`${API}/giveaways/:id/winners`, () => HttpResponse.json({ winners: mockWinners })),
  http.post(`${API}/giveaways/:id/redraw`, () =>
    HttpResponse.json({
      winners: mockWinners.map((winner, index) => ({
        ...winner,
        tg_id: 7123456800 + index,
        username: `replacement_${index + 1}`,
        ticket_number: 201 + index,
      })),
    }),
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

  // ── API Health ────────────────────────────────────────
  http.get(`${API}/api-health/summary`, () =>
    HttpResponse.json({
      requests: 3248, avg_rps: 0.038, success_rate: 97.84, client_errors: 38,
      server_errors: 32, error_rate: 2.16, avg_ms: 142, p50_ms: 100,
      p95_ms: 500, p99_ms: 2000, max_ms: 6284, client_error_rate: 1.17,
      server_error_rate: .99, slow_requests: 18, dropped_events: 0,
      last_telemetry_at: new Date().toISOString(),
      services: [
        { service: "miniapp", is_healthy: true, checked_at: new Date().toISOString(), last_ok_at: new Date().toISOString(), last_error: null, consecutive_failures: 0, response_time_ms: 24 },
        { service: "bot", is_healthy: true, checked_at: new Date().toISOString(), last_ok_at: new Date().toISOString(), last_error: null, consecutive_failures: 0, response_time_ms: 18 },
        { service: "dashboard", is_healthy: true, checked_at: new Date().toISOString(), last_ok_at: new Date().toISOString(), last_error: null, consecutive_failures: 0, response_time_ms: 12 },
      ],
    }),
  ),
  http.get(`${API}/api-health/series`, () => HttpResponse.json(apiHealthSeries)),
  http.get(`${API}/api-health/endpoints`, () => HttpResponse.json([
    { service: "miniapp", method: "GET", route: "/bot/miniapp/api/me", requests: 1240, success_rate: 99.4, client_errors: 5, server_errors: 2, error_rate: .56, client_error_rate: .4, server_error_rate: .16, slow_requests: 0, avg_ms: 118, p50_ms: 100, p95_ms: 500, p99_ms: 1000, max_ms: 1844, dropped_events: 0, last_error_at: new Date(Date.now() - 7200000).toISOString() },
    { service: "miniapp", method: "POST", route: "/bot/miniapp/api/payments/invoice", requests: 284, success_rate: 92.3, client_errors: 8, server_errors: 14, error_rate: 7.74, client_error_rate: 2.82, server_error_rate: 4.93, slow_requests: 18, avg_ms: 740, p50_ms: 500, p95_ms: 2000, p99_ms: 5000, max_ms: 6284, dropped_events: 0, last_error_at: new Date(Date.now() - 1800000).toISOString() },
    { service: "bot", method: "POST", route: "/bot/remnawave_webhook", requests: 604, success_rate: 98.7, client_errors: 4, server_errors: 4, error_rate: 1.32, client_error_rate: .66, server_error_rate: .66, slow_requests: 0, avg_ms: 94, p50_ms: 100, p95_ms: 250, p99_ms: 1000, max_ms: 1310, dropped_events: 0, last_error_at: new Date(Date.now() - 3600000).toISOString() },
    { service: "dashboard", method: "GET", route: "/bot/dashboard/api/users", requests: 420, success_rate: 100, client_errors: 0, server_errors: 0, error_rate: 0, client_error_rate: 0, server_error_rate: 0, slow_requests: 0, avg_ms: 72, p50_ms: 50, p95_ms: 250, p99_ms: 500, max_ms: 612, dropped_events: 0, last_error_at: null },
  ])),
  http.get(`${API}/api-health/errors/:id`, ({ params }) => HttpResponse.json({
    id: Number(params.id), occurred_at: new Date(Date.now() - 1800000).toISOString(), request_id: "e1703e7c-7f0f-49cd-8725-c868bfce2183",
    service: "miniapp", method: "POST", route: "/bot/miniapp/api/payments/invoice", status_code: 500, duration_ms: 2384,
    user_id: 1, tg_id: 100001, actor: null, client_ip: "203.0.113.42", client_channel: "telegram", user_agent: "TelegramBot (Android)", app_version: "2.4.1",
    exception_type: "UpstreamTimeout", error_message: "Payment provider did not respond before the request deadline",
    error_fingerprint: "78418ca69c7b5ae884b5e2c9beea8920", traceback: "Traceback (most recent call last):\n  File \"routers/payments.py\", line 224, in create_invoice\n    response = await provider.create_invoice(...)\nUpstreamTimeout: provider request timed out",
  })),
  http.get(`${API}/api-health/errors`, () => HttpResponse.json({
    items: [
      { id: 1, occurred_at: new Date(Date.now() - 1800000).toISOString(), request_id: "e1703e7c-7f0f-49cd-8725-c868bfce2183", service: "miniapp", method: "POST", route: "/bot/miniapp/api/payments/invoice", status_code: 500, duration_ms: 2384, user_id: 1, tg_id: 100001, actor: null, client_ip: "203.0.113.42", client_channel: "telegram", user_agent: "TelegramBot (Android)", app_version: "2.4.1", exception_type: "UpstreamTimeout", error_message: "Payment provider did not respond before the request deadline", error_fingerprint: "78418ca69c7b5ae884b5e2c9beea8920" },
      { id: 2, occurred_at: new Date(Date.now() - 4200000).toISOString(), request_id: "07c445a0-e56f-4df7-8ce7-22af85ccda97", service: "bot", method: "POST", route: "/bot/remnawave_webhook", status_code: 502, duration_ms: 1304, user_id: null, tg_id: null, actor: null, client_ip: "198.51.100.17", client_channel: "webhook", user_agent: "Remnawave/3.0", app_version: null, exception_type: "HTTPStatusError", error_message: "Upstream returned HTTP 502", error_fingerprint: "529405b615a947377dcbdad13f18b3c2" },
      { id: 3, occurred_at: new Date(Date.now() - 6300000).toISOString(), request_id: "1dbbda16-297b-481e-b5ca-2fae0d786acb", service: "miniapp", method: "GET", route: "/bot/miniapp/api/me", status_code: 401, duration_ms: 18, user_id: null, tg_id: null, actor: null, client_ip: "192.0.2.88", client_channel: "telegram", user_agent: "TelegramBot (iOS)", app_version: "2.4.1", exception_type: null, error_message: "HTTP 401", error_fingerprint: "b61812508515003f6d1e8f33551537a9" },
    ],
    groups: [
      { fingerprint: "78418ca69c7b5ae884b5e2c9beea8920", service: "miniapp", route: "/bot/miniapp/api/payments/invoice", status_code: 500, exception_type: "UpstreamTimeout", message: "Payment provider did not respond", count: 21, affected_users: 14, last_seen_at: new Date(Date.now() - 1800000).toISOString() },
      { fingerprint: "529405b615a947377dcbdad13f18b3c2", service: "bot", route: "/bot/remnawave_webhook", status_code: 502, exception_type: "HTTPStatusError", message: "Upstream returned HTTP 502", count: 7, affected_users: 0, last_seen_at: new Date(Date.now() - 4200000).toISOString() },
    ],
    total: 32, page: 1, per_page: 25,
  })),
  http.get(`${API}/api-health/settings`, () => HttpResponse.json(apiAlertSettings)),
  http.put(`${API}/api-health/settings`, async ({ request }) => {
    apiAlertSettings = await request.json() as ApiAlertSettings;
    return HttpResponse.json(apiAlertSettings);
  }),

  // ── Catch-all: keep unknown endpoints from crashing the UI ─
  http.all(`${API}/*`, ({ request }) => {
    if (request.method === "GET") {
      return HttpResponse.json({ items: [], total: 0, page: 1, per_page: 20 });
    }
    return HttpResponse.json({ ok: true });
  }),
];
