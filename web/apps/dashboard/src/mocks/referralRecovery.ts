import { http, HttpResponse } from "msw";

const base = "/bot/dashboard/api/tg-admin/referral-recovery";
let executed = false;
let snapshot: ReturnType<typeof makeSnapshot> | null = null;

function makeSnapshot(adjustments: Record<string, number> = {}) {
  const manual = adjustments["1"] ?? 20;
  const missing = Math.max(0, 90 - 30 - manual);
  const bonus = Math.ceil(missing / 10);
  return {
    id: "mock-recovery", adjustments,
    plan: {
      rate: 30, cap: 1800, purchases_checked: 3, recipients: missing ? 1 : 0,
      missing, bonus, total: missing + bonus, manual, issues: [],
      rows: [{ user_id: 1, tg_id: 100001, username: "demo_inviter", promo_code: "DEMOREF",
        expected: 90, automatic: 30, paid: 30, admin_grants: 20, manual, spent: 50,
        balance: 0, missing, bonus, total: missing + bonus, warnings: [] }],
    },
  };
}

export const referralRecoveryHandlers = [
  http.get(base, () => HttpResponse.json({ status: executed ? "executed" : "ready", snapshot,
    messages: { pending: 0, sending: 0, sent: executed ? 1 : 0, failed: 0, unknown: 0, unavailable: 0 }, message_details: [] })),
  http.post(`${base}/preview`, async ({ request }) => {
    const body = await request.json() as { manual_adjustments?: Record<string, number> };
    snapshot = makeSnapshot(body.manual_adjustments);
    return HttpResponse.json(snapshot);
  }),
  http.post(`${base}/execute`, () => { executed = true; return HttpResponse.json(snapshot); }),
  http.post(`${base}/retry-messages`, () => HttpResponse.json({ queued: 0 })),
];
