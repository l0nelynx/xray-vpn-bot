import { http, HttpResponse, type HttpHandler } from "msw";

const API = "/bot/miniapp/api";

const links = {
  bot_url: "https://t.me/mock_bot",
  policy_url: "/bot/miniapp/policy",
  agreement_url: "/bot/miniapp/agreement",
  news_url: "https://t.me/mock_news",
  branding_name: "MockVPN",
  support_bot_link: "https://t.me/mock_support",
};

const menuTree = {
  tree: [
    {
      id: 1,
      parent_id: null,
      text: "Subscription",
      action: "buttons" as const,
      invoice: null,
      children: [
        {
          id: 2,
          parent_id: 1,
          text: "1 month",
          action: "invoice" as const,
          invoice: {
            provider: "crypto" as const,
            amount: 299,
            currency: "RUB",
            days: 30,
            tariff_slug: "month",
            method: "crypto",
            points_cost: 300,
          },
          children: [],
        },
        {
          id: 3,
          parent_id: 1,
          text: "3 months",
          action: "invoice" as const,
          invoice: {
            provider: "platega" as const,
            amount: 799,
            currency: "RUB",
            days: 90,
            tariff_slug: "quarter",
            method: "platega",
          },
          children: [],
        },
      ],
    },
  ],
};

let ticketSeq = 2;
let mockLanguage = "en";
let mockOnboardingVersion = 1;
let mockHasEmail = false;
const transactionPolls = new Map<string, number>();
let connectionVerificationPolls = 0;
let mockSubscriptions = [
  {
    id: 1,
    rw_id: 1031,
    label: "Main",
    product_key: null,
    source: "telegram",
    is_primary: true,
    tariff: "Premium",
    status: "active",
    days_left: 18,
    expire_iso: new Date(Date.now() + 18 * 86400000).toISOString(),
    data_limit_gb: 200,
    traffic_used_gb: 42.5,
    devices_count: 2,
    subscription_url: "https://example.com/sub/mock-main",
    connection_state: "connected" as const,
  },
  {
    id: 2,
    rw_id: 2048,
    label: "",
    product_key: "marketplace",
    source: "marketplace",
    is_primary: false,
    tariff: "Premium",
    status: "active",
    days_left: 61,
    expire_iso: new Date(Date.now() + 61 * 86400000).toISOString(),
    data_limit_gb: null,
    traffic_used_gb: 9.2,
    devices_count: 1,
    subscription_url: "https://example.com/sub/mock-marketplace",
    connection_state: "connected" as const,
  },
];

function scenarioFrom(request: Request): { name: string; language: "ru" | "en" | null } {
  const raw = request.headers.get("X-Telegram-Init-Data")?.split("mock-scenario:")[1] || "";
  const language = raw.endsWith("-ru") ? "ru" : raw.endsWith("-en") ? "en" : null;
  return { name: raw.replace(/-(?:ru|en)$/, ""), language };
}
const tickets = [
  {
    id: 1,
    subject: "Can't connect",
    status: "open",
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T11:00:00Z",
    last_message_preview: "Need help with connection",
    messages: [
      {
        id: 1,
        sender: "user",
        text: "Need help with connection",
        created_at: "2026-07-18T10:00:00Z",
        attachments: [],
      },
      {
        id: 2,
        sender: "admin",
        text: "Please send a screenshot of the error.",
        created_at: "2026-07-18T11:00:00Z",
        attachments: [],
      },
    ],
  },
];

export const handlers: HttpHandler[] = [
  http.get(`${API}/me`, ({ request }) => {
    const { name: scenario, language } = scenarioFrom(request);
    const empty = (scenario === "onboarding" && !mockHasEmail) || scenario === "empty";
    const unknown = scenario === "connection-unknown";
    const never = scenario === "connection-never";
    const selectedSubscriptions = scenario === "single" ? mockSubscriptions.slice(0, 1) : mockSubscriptions;
    const availableSubscriptions = empty ? [] : selectedSubscriptions.map((item) => ({
      ...item,
      status: unknown ? "unavailable" : scenario === "expired" ? "expired" : item.status,
      days_left: scenario === "expired" ? 0 : item.days_left,
      connection_state: unknown ? "unknown" : never || scenario === "connection-progress" ? "never_connected" : item.connection_state,
    }));
    const primary = availableSubscriptions.find((item) => item.is_primary);
    return HttpResponse.json({
      registered: true,
      user: {
        tg_id: 424242, username: "jason_karker", language: language || mockLanguage,
        has_email: mockHasEmail, email: mockHasEmail ? "existing@example.com" : null,
        onboarding_version: scenario === "onboarding" ? 0 : mockOnboardingVersion,
      },
      subscription: primary ? { ...primary, subscription_id: primary.id } : null,
      subscriptions_count: availableSubscriptions.length,
      links,
    });
  }),

  http.get(`${API}/subscriptions`, ({ request }) => {
    const { name: scenario } = scenarioFrom(request);
    if ((scenario === "onboarding" && !mockHasEmail) || scenario === "empty") return HttpResponse.json({ subscriptions: [] });
    if (scenario === "connection-progress") connectionVerificationPolls += 1;
    const selectedSubscriptions = scenario === "single" ? mockSubscriptions.slice(0, 1) : mockSubscriptions;
    return HttpResponse.json({ subscriptions: selectedSubscriptions.map((item) => ({
      ...item,
      status: scenario === "connection-unknown" ? "unavailable" : scenario === "expired" ? "expired" : item.status,
      days_left: scenario === "expired" ? 0 : item.days_left,
      connection_state: scenario === "connection-unknown" ? "unknown" : scenario === "connection-never" ? "never_connected" : scenario === "connection-progress" && connectionVerificationPolls < 2 ? "never_connected" : item.connection_state,
    })) });
  }),
  http.post(`${API}/subscriptions/:id/primary`, ({ params }) => {
    const id = Number(params.id);
    if (!mockSubscriptions.some((item) => item.id === id)) {
      return HttpResponse.json(
        { detail: { code: "subscription_not_found" } },
        { status: 404 },
      );
    }
    mockSubscriptions = mockSubscriptions.map((item) => ({
      ...item,
      is_primary: item.id === id,
    }));
    return HttpResponse.json({ status: "ok", subscription_id: id });
  }),

  http.patch(`${API}/me/language`, async ({ request }) => {
    const body = (await request.json()) as { language: string };
    mockLanguage = body.language === "en" ? "en" : "ru";
    return HttpResponse.json({
      tg_id: 424242,
      username: "mock_user",
      language: mockLanguage,
      has_email: false,
      email: null,
      onboarding_version: mockOnboardingVersion,
    });
  }),

  http.patch(`${API}/me/onboarding`, async ({ request }) => {
    const body = (await request.json()) as { version: number };
    mockOnboardingVersion = Math.max(mockOnboardingVersion, body.version);
    return HttpResponse.json({ onboarding_version: mockOnboardingVersion });
  }),

  http.post(`${API}/link/email`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.password !== "correct") {
      return HttpResponse.json(
        { detail: { code: "invalid_credentials" } },
        { status: 401 },
      );
    }
    if (body.email === "taken@example.com") {
      return HttpResponse.json(
        { detail: { code: "telegram_conflict" } },
        { status: 409 },
      );
    }
    mockHasEmail = true;
    return HttpResponse.json({ result: "ok", survivor_id: 1 });
  }),

  http.post(`${API}/ux/events`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/menu/tree`, () => HttpResponse.json(menuTree)),

  http.get(`${API}/payments/providers`, () =>
    HttpResponse.json({
      providers: [
        { name: "crypto", payment_method: "crypto", currencies: ["USDT"] },
        { name: "platega", payment_method: "platega", currencies: ["RUB"] },
      ],
    }),
  ),
  http.get(`${API}/payments/balance`, () => HttpResponse.json({ balance: 150 })),
  http.post(`${API}/payments/invoice`, async ({ request }) => {
    const body = (await request.json()) as { node_id: number };
    return HttpResponse.json({
      provider: "crypto",
      invoice_id: "inv-mock-1",
      url: "https://example.com/pay/mock",
      amount: 299,
      currency: "RUB",
      transaction_id: `tx-${body.node_id}`,
      payment_method: "crypto",
    });
  }),
  http.post(`${API}/payments/pay-credits`, () =>
    HttpResponse.json({
      ok: true,
      transaction_id: "tx-credits-1",
      points_spent: 300,
      balance_after: 0,
      subscription_url: "https://example.com/sub/mock",
      message: "Paid with credits (mock)",
    }),
  ),
  http.get(`${API}/payments/transactions/:transactionId`, ({ params }) => {
    const transactionId = String(params.transactionId);
    if (transactionId === "tx-failed") {
      return HttpResponse.json({ transaction_id: transactionId, state: "failed", delivery_status: 0 });
    }
    if (transactionId === "tx-awaiting") {
      return HttpResponse.json({ transaction_id: transactionId, state: "awaiting_payment", delivery_status: 0 });
    }
    if (transactionId === "tx-processing") {
      return HttpResponse.json({ transaction_id: transactionId, state: "processing", delivery_status: 0 });
    }
    if (transactionId === "tx-credits-1") {
      return HttpResponse.json({ transaction_id: transactionId, state: "succeeded", delivery_status: 1 });
    }
    const polls = (transactionPolls.get(transactionId) || 0) + 1;
    transactionPolls.set(transactionId, polls);
    const state = polls <= 2 ? "awaiting_payment" : polls <= 4 ? "processing" : "succeeded";
    return HttpResponse.json({ transaction_id: transactionId, state, delivery_status: state === "succeeded" ? 1 : 0 });
  }),

  http.get(`${API}/devices`, () =>
    HttpResponse.json({
      total: 2,
      devices: [
        {
          hwid: "hwid-iphone",
          platform: "ios",
          os_version: "18.0",
          device_model: "iPhone 15",
          user_agent: "Stash/2",
          created_at: "2026-06-01T00:00:00Z",
          updated_at: "2026-07-20T00:00:00Z",
        },
        {
          hwid: "hwid-android",
          platform: "android",
          os_version: "15",
          device_model: "Pixel 8",
          user_agent: "v2rayNG",
          created_at: "2026-06-15T00:00:00Z",
          updated_at: "2026-07-21T00:00:00Z",
        },
      ],
    }),
  ),
  http.delete(`${API}/devices/:hwid`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${API}/support/tickets`, () =>
    HttpResponse.json(
      tickets.map(({ messages: _m, ...summary }) => summary),
    ),
  ),
  http.post(`${API}/support/tickets`, async ({ request }) => {
    const body = (await request.json()) as { subject: string; message: string };
    const id = ticketSeq++;
    const ticket = {
      id,
      subject: body.subject,
      status: "open",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      last_message_preview: body.message,
      messages: [
        {
          id: 1,
          sender: "user",
          text: body.message,
          created_at: new Date().toISOString(),
          attachments: [],
        },
      ],
    };
    tickets.unshift(ticket);
    return HttpResponse.json(ticket);
  }),
  http.get(`${API}/support/tickets/:id`, ({ params }) => {
    const ticket = tickets.find((t) => t.id === Number(params.id));
    if (!ticket) return HttpResponse.json({ detail: "Not found" }, { status: 404 });
    return HttpResponse.json(ticket);
  }),
  http.post(`${API}/support/tickets/:id/messages`, async ({ params, request }) => {
    const form = await request.formData();
    const text = String(form.get("text") || "");
    const ticket = tickets.find((t) => t.id === Number(params.id));
    const msg = {
      id: (ticket?.messages.length || 0) + 1,
      sender: "user",
      text,
      created_at: new Date().toISOString(),
      attachments: [],
    };
    ticket?.messages.push(msg);
    return HttpResponse.json(msg);
  }),
  http.get(`${API}/support/tickets/:id/attachments/:attachmentId`, () =>
    HttpResponse.arrayBuffer(new ArrayBuffer(8), {
      headers: { "Content-Type": "image/png" },
    }),
  ),

  http.get(`${API}/connect/app-config`, () =>
    HttpResponse.json({
      locales: ["ru", "en"],
      version: 1,
      platforms: {
        ios: {
          apps: [
            {
              name: "Stash",
              featured: true,
              blocks: [
                {
                  title: { ru: "Установка", en: "Install" },
                  description: { ru: "Скачайте приложение", en: "Download the app" },
                  buttons: [
                    {
                      link: "https://apps.apple.com",
                      text: { ru: "App Store", en: "App Store" },
                      type: "external",
                    },
                    {
                      link: "",
                      text: { ru: "Добавить подписку", en: "Add subscription" },
                      type: "subscriptionLink",
                    },
                  ],
                },
              ],
            },
          ],
        },
        android: {
          apps: [
            {
              name: "v2rayNG",
              featured: true,
              blocks: [
                {
                  title: { ru: "Установка", en: "Install" },
                  buttons: [
                    {
                      link: "https://play.google.com",
                      text: { ru: "Google Play", en: "Google Play" },
                      type: "external",
                    },
                    {
                      link: "",
                      text: { ru: "Скопировать ссылку", en: "Copy link" },
                      type: "copyButton",
                    },
                  ],
                },
              ],
            },
          ],
        },
      },
    }),
  ),

  http.get(`${API}/free/check`, () =>
    HttpResponse.json({ subscribed: true, news_url: links.news_url }),
  ),
  http.get(`${API}/free/vpn/status`, () =>
    HttpResponse.json({
      has_access: false,
      url: null,
      news_url: links.news_url,
    }),
  ),
  http.get(`${API}/free/telemt/status`, () =>
    HttpResponse.json({
      has_access: false,
      url: null,
      news_url: links.news_url,
    }),
  ),
  http.post(`${API}/free/claim`, () =>
    HttpResponse.json({
      ok: true,
      subscription_url: "https://example.com/sub/free",
      days: 1,
      detail: "Trial activated (mock)",
    }),
  ),
  http.post(`${API}/free/telemt`, () =>
    HttpResponse.json({
      ok: true,
      link: "https://t.me/proxy?server=mock",
      detail: "Telemt trial (mock)",
    }),
  ),

  http.get(`${API}/promo`, () =>
    HttpResponse.json({
      balance: 150,
      last_promo_code: "WELCOME",
      default_credit_grant: 50,
    }),
  ),
  http.post(`${API}/promo`, async ({ request }) => {
    const body = (await request.json()) as { promo_code: string };
    return HttpResponse.json({
      ok: true,
      promo_code: body.promo_code,
      credit_grant: 50,
      balance: 200,
    });
  }),
  http.get(`${API}/promo/referral`, () =>
    HttpResponse.json({
      code: "MOCKREF",
      deeplink: "https://t.me/mock_bot?start=ref_MOCKREF",
      credit_grant: 50,
      points_reward_per_30: 30,
      reward_cap_points: 300,
      days_purchased: 90,
      points_rewarded: 90,
    }),
  ),

  http.all(`${API}/*`, ({ request }) => {
    if (request.method === "GET") {
      return HttpResponse.json({});
    }
    return HttpResponse.json({ ok: true });
  }),
];
