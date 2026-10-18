/** Run after building miniapp, against `npm run preview -w xray-vpn-miniapp -- --port 5178`. */
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "playwright";

const base = process.env.MINIAPP_PREVIEW_URL || "http://127.0.0.1:5178/bot/miniapp/";
const browser = await chromium.launch({ headless: true });
try {
  for (const language of ["ru", "en"]) {
    const context = await browser.newContext({ viewport: { width: 360, height: 800 } });
    const page = await context.newPage();
    await page.addInitScript((language) => {
      window.Telegram = { WebApp: { initDataUnsafe: { user: { language_code: language } },
        ready() {}, expand() {}, onEvent() {} } };
    }, language);
    await page.clock.install();
    let unavailable = true;
    let subscribed = false;
    let attempts = 0;
    let meRequests = 0;
    let failMe = false;
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await context.route("https://telegram.org/**", (route) => route.fulfill({ body: "", contentType: "text/javascript" }));
    await context.route("**/bot/miniapp/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let body = {};
      if (path.endsWith("/availability")) body = { unavailable, subscribed };
      else if (path.endsWith("/recovery-notification")) {
        attempts++;
        assert.equal(route.request().postDataJSON().language, language);
        if (attempts === 1) return route.fulfill({ status: 503, json: { detail: "temporary" } });
        subscribed = true;
        body = { unavailable, subscribed };
      } else if (path.endsWith("/me")) {
        meRequests++;
        if (failMe) return route.fulfill({ status: 503, json: { detail: "remnawave_unavailable" } });
        body = {
          registered: true,
          user: { tg_id: 123, username: "test", language, has_email: true, onboarding_version: 1 },
          subscription: { subscription_id: 1, label: "Main", tariff: "Premium", status: unavailable ? "unavailable" : "active",
            days_left: 18, expire_iso: null, data_limit_gb: null, traffic_used_gb: 0, devices_count: 0,
            subscription_url: null, connection_state: "unknown" },
          subscriptions_count: 1,
          links: { branding_name: "TestVPN", bot_url: "", support_bot_link: "", news_url: "", policy_url: "", agreement_url: "" },
        };
      } else if (path.endsWith("/promo")) body = { balance: 0 };
      else if (path.endsWith("/support/tickets")) body = [];
      else if (path.endsWith("/subscriptions")) body = { subscriptions: [] };
      return route.fulfill({ json: body });
    });
    await page.goto(base);
    const title = language === "ru" ? "Технические работы" : "Maintenance in progress";
    const notify = language === "ru" ? "Уведомить, когда всё заработает" : "Notify me when service is restored";
    const confirmation = language === "ru" ? "Сообщим в Telegram, когда всё снова заработает." : "We'll notify you in Telegram when service is restored.";
    await page.getByText(title, { exact: true }).waitFor();
    assert.equal(attempts, 0, "Notifications require an explicit user opt-in");
    assert.equal(await page.getByText(/Remnawave/).count(), 0);
    const buttonBox = await page.getByRole("button", { name: notify, exact: true }).boundingBox();
    assert.ok(buttonBox && buttonBox.x >= 0 && buttonBox.x + buttonBox.width <= 360);
    await page.getByRole("button", { name: notify, exact: true }).click();
    await page.getByText(language === "ru" ? "Не удалось включить уведомление. Попробуйте ещё раз." : "Could not enable the notification. Please try again.", { exact: true }).waitFor();
    await page.getByRole("button", { name: notify, exact: true }).click();
    await page.getByText(confirmation, { exact: true }).waitFor();
    await page.reload();
    await page.getByText(confirmation, { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: notify, exact: true }).count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    if (process.env.SCREENSHOT_DIR) {
      mkdirSync(process.env.SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/maintenance-${language}.png`, fullPage: true });
    }
    const before = meRequests;
    unavailable = false;
    await page.clock.runFor(16_000);
    await page.getByText(title, { exact: true }).waitFor({ state: "hidden" });
    assert.ok(meRequests > before, "Recovery refreshes subscription details");
    unavailable = true;
    subscribed = false;
    failMe = true;
    await page.reload();
    await page.getByRole("button", { name: notify, exact: true }).waitFor();
    assert.equal(await page.getByText("remnawave_unavailable", { exact: true }).count(), 0);
    await page.getByRole("button", { name: notify, exact: true }).click();
    await page.getByText(confirmation, { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`PASS ${language}: maintenance, explicit opt-in, retry, persistence, recovery, mobile layout`);
  }
} finally {
  await browser.close();
}
