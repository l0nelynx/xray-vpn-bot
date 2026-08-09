/**
 * Capture the MiniApp UX review matrix from the MSW dev server.
 *
 * Start first:
 *   npm run dev:mock -w xray-vpn-miniapp
 * Then:
 *   node scripts/capture-miniapp-ux-previews.mjs
 */
import { chromium, devices } from "playwright";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "docs", "screenshots", "miniapp-ux");
const base = "http://127.0.0.1:5174/bot/miniapp/";

const targets = [
  { name: "iphone", device: devices["iPhone 14"], platform: "ios" },
  { name: "android", device: devices["Pixel 7"], platform: "android" },
  {
    name: "telegram-desktop",
    platform: "tdesktop",
    device: {
      viewport: { width: 478, height: 790 },
      screen: { width: 478, height: 790 },
      deviceScaleFactor: 1,
      isMobile: false,
      hasTouch: false,
      userAgent: "Mozilla/5.0 TelegramDesktop MiniApp",
    },
  },
];

const captures = [
  ["onboarding-identity", "onboarding", "onboarding?step=0"],
  ["onboarding-access", "onboarding", "onboarding?step=1"],
  ["onboarding-connect", "onboarding", "onboarding?step=2"],
  ["onboarding-help", "onboarding", "onboarding?step=3"],
  ["email-login", "onboarding", "account/link?returnTo=%2Fonboarding%3Fstep%3D1"],
  ["home-empty", "empty", ""],
  ["home-never-connected", "connection-never", ""],
  ["home-connected", "connected", ""],
  ["home-promo", "connected", ""],
  ["home-expired", "expired", ""],
  ["devices", "connected", "devices"],
  ["settings", "connected", "settings"],
  ["telegram-proxy", "connected", "free/telemt"],
  ["invite", "connected", "invite"],
  ["subscriptions", "connected", "subscriptions"],
  ["payment-awaiting", "connected", "buy/success?transaction_id=tx-awaiting"],
  ["payment-processing", "connected", "buy/success?transaction_id=tx-processing"],
  ["payment-succeeded", "connected", "buy/success?transaction_id=tx-credits-1&preview_success=1"],
  ["payment-failed", "connected", "buy/success?transaction_id=tx-failed"],
  ["payment-timeout", "connected", "buy/success?transaction_id=tx-awaiting&preview_timeout=1"],
  ["connect-wizard", "connection-never", "connect?subscription_id=1&source=preview"],
  ["connect-timeout", "connection-never", "connect?subscription_id=1&source=preview&preview_timeout=1"],
  ["connect-verified", "connected", "connect?subscription_id=1&source=preview"],
  ["connect-unavailable", "connection-unknown", "connect?subscription_id=1&source=preview"],
  ["help", "connected", "support"],
];

const requestedTargets = new Set((process.env.MINIAPP_PREVIEW_TARGETS || "").split(",").filter(Boolean));
const requestedCaptures = new Set((process.env.MINIAPP_PREVIEW_CAPTURES || "").split(",").filter(Boolean));
const requestedLanguages = new Set((process.env.MINIAPP_PREVIEW_LANGUAGES || "").split(",").filter(Boolean));
const selectedTargets = requestedTargets.size ? targets.filter((target) => requestedTargets.has(target.name)) : targets;
const selectedCaptures = requestedCaptures.size ? captures.filter(([name]) => requestedCaptures.has(name)) : captures;
const selectedLanguages = requestedLanguages.size ? ["ru", "en"].filter((language) => requestedLanguages.has(language)) : ["ru", "en"];

function withScenario(path, scenario, language) {
  const url = new URL(path, base);
  url.searchParams.set("mock", `${scenario}-${language}`);
  return url.href;
}

async function waitForApp(page) {
  await page.waitForSelector(".page, .onboarding-shell", { timeout: 20_000 });
  await page.waitForFunction(() => !document.querySelector(".spinner-wrap"), null, { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(500);
}

mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  for (const target of selectedTargets) {
    for (const language of selectedLanguages) {
      const context = await browser.newContext({
        ...target.device,
        locale: language === "ru" ? "ru-RU" : "en-US",
        colorScheme: "dark",
        reducedMotion: "reduce",
      });
      await context.addInitScript(({ language, platform }) => {
        window.Telegram = { WebApp: {
          initData: "mock", initDataUnsafe: { user: { id: 424242, username: "mock_user", language_code: language } },
          ready() {}, expand() {}, onEvent() {}, themeParams: {}, colorScheme: "dark", platform, version: "8.0",
          safeAreaInset: { top: 0, right: 0, bottom: 24, left: 0 },
          contentSafeAreaInset: { top: 8, right: 0, bottom: 0, left: 0 },
          HapticFeedback: { impactOccurred() {}, notificationOccurred() {} },
          openLink() {}, openTelegramLink() {}, showAlert() {},
        }};
      }, { language, platform: target.platform });
      const page = await context.newPage();
      for (const [name, scenario, path] of selectedCaptures) {
        await page.goto(withScenario(path, scenario, language), { waitUntil: "domcontentloaded" });
        await waitForApp(page);
        if (name === "connect-timeout") {
          await page.locator(".connect-verification + button").click();
          await page.waitForTimeout(500);
        }
        if (name === "home-promo") {
          await page.locator(".home-promo-trigger").click();
          await page.waitForTimeout(250);
        }
        const image = join(out, `${language}-${target.name}-${name}.png`);
        await page.screenshot({ path: image, fullPage: true, animations: "disabled" });
        console.log("saved", image);
      }
      await context.close();
    }
  }
} finally {
  await browser.close();
}
