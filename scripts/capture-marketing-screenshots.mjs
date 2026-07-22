/**
 * Capture EN marketing screenshots from mock MiniApp + Dashboard.
 *
 * Usage (servers must already be running):
 *   npm run dev:mock -w xray-vpn-dashboard
 *   npm run dev:mock -w xray-vpn-miniapp
 *   node scripts/capture-marketing-screenshots.mjs
 */
import { chromium, devices } from "playwright";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "docs", "screenshots");

const DASHBOARD = "http://127.0.0.1:5173/bot/dashboard/";
const MINIAPP = "http://127.0.0.1:5174/bot/miniapp/";

const PHONE = {
  ...devices["iPhone 14"],
  locale: "en-US",
  colorScheme: "dark",
};

function assertNoCyrillic(label, text) {
  if (/[\u0400-\u04FF]/.test(text || "")) {
    console.warn(`[warn] Cyrillic detected on ${label}`);
  }
}

async function waitSettled(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(600);
}

async function shot(page, name, opts = {}) {
  // Hide chart tooltips / floating popovers that spoil marketing shots
  await page.addStyleTag({
    content: `
      .recharts-tooltip-wrapper { display: none !important; }
      [data-radix-popper-content-wrapper] { display: none !important; }
    `,
  }).catch(() => {});
  await page.mouse.move(0, 0);
  await page.waitForTimeout(150);
  const path = join(OUT, `${name}.png`);
  await page.screenshot({
    path,
    fullPage: opts.fullPage ?? false,
    animations: "disabled",
  });
  console.log("saved", path);
}

async function captureDashboard(browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
    colorScheme: "dark",
    locale: "en-US",
  });
  const page = await context.newPage();

  await page.goto(`${DASHBOARD}login`, { waitUntil: "domcontentloaded" });
  await waitSettled(page);

  // Mock accepts any non-empty credentials
  const inputs = page.locator("input");
  await inputs.nth(0).fill("admin");
  await inputs.nth(1).fill("admin");
  await page.getByRole("button", { name: /sign in|log in|login/i }).click();
  await page.waitForURL(/\/bot\/dashboard\/?$/).catch(() => {});
  await waitSettled(page);
  assertNoCyrillic("dashboard", await page.locator("body").innerText());
  await shot(page, "dashboard-overview");

  for (const [path, name] of [
    ["users", "dashboard-users"],
    ["transactions", "dashboard-transactions"],
    ["stats", "dashboard-stats"],
    ["support", "dashboard-support"],
    ["crm", "dashboard-crm"],
    ["promocodes", "dashboard-promocodes"],
    ["store", "dashboard-store"],
  ]) {
    await page.goto(`${DASHBOARD}${path}`, { waitUntil: "domcontentloaded" });
    await waitSettled(page);
    // Wait for table/cards to paint (avoid empty loading flash)
    await page.waitForTimeout(500);
    assertNoCyrillic(name, await page.locator("body").innerText());
    await shot(page, name);
  }

  await context.close();
}

async function captureMiniapp(browser) {
  const context = await browser.newContext(PHONE);
  const page = await context.newPage();

  // Soften Telegram WebApp absence — app still loads via mock /me
  await page.addInitScript(() => {
    window.Telegram = {
      WebApp: {
        initData: "mock",
        initDataUnsafe: { user: { id: 424242, username: "mock_user", language_code: "en" } },
        ready() {},
        expand() {},
        themeParams: {},
        colorScheme: "dark",
        platform: "ios",
        version: "8.0",
        HapticFeedback: { impactOccurred() {}, notificationOccurred() {} },
        openLink(url) {
          console.log("openLink", url);
        },
        showAlert(msg) {
          console.log("alert", msg);
        },
      },
    };
  });

  const routes = [
    ["", "miniapp-home"],
    ["buy", "miniapp-buy"],
    ["connect", "miniapp-connect"],
    ["devices", "miniapp-devices"],
    ["support", "miniapp-support"],
    ["support/1", "miniapp-support-ticket"],
    ["settings", "miniapp-settings"],
    ["invite", "miniapp-invite"],
  ];

  for (const [path, name] of routes) {
    await page.goto(`${MINIAPP}${path}`, { waitUntil: "domcontentloaded" });
    await waitSettled(page);
    // Wait until page content is ready (not just spinner)
    await page.waitForSelector(".page", { timeout: 20000 });
    await page.waitForFunction(() => !document.querySelector(".spinner-wrap"), null, {
      timeout: 15000,
    }).catch(() => {});
    await page.waitForTimeout(700);

    // Buy: drill into Subscription so plans are visible
    if (name === "miniapp-buy") {
      const sub = page.getByRole("button", { name: /subscription/i }).first();
      if (await sub.count()) {
        await sub.click();
        await page.waitForTimeout(500);
      }
    }

    assertNoCyrillic(name, await page.locator("body").innerText());
    await shot(page, name);
  }

  await context.close();
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  await captureDashboard(browser);
  await captureMiniapp(browser);
} finally {
  await browser.close();
}
console.log("Done →", OUT);
