/** Run against `npm run dev:mock -w xray-vpn-miniapp`. Node 22.18+ required. */
import assert from "node:assert/strict";
import { mkdirSync, readFileSync } from "node:fs";
import { chromium } from "playwright";
import jsQR from "jsqr";
import { buttonPurpose, detectPlatform, fillLink, recommendedApp, resolveStage, subscriptionState } from "../web/apps/miniapp/src/connect/catalog.ts";

const catalog = JSON.parse(readFileSync(new URL("../services/miniapp/backend/connect/app_config.default.json", import.meta.url), "utf8"));
const sourceUrl = "https://example.com/sub/long%20name?token=a%2Fb&value=кириллица#fragment";
assert.equal(new URL(fillLink("https://cheezyvpn.uk/claim?client=desktop&url={{SUBSCRIPTION_LINK}}", sourceUrl, "")).searchParams.get("url"), sourceUrl);
assert.equal(fillLink("cheezy://add/{{SUBSCRIPTION_LINK}}", sourceUrl, ""), `cheezy://add/${sourceUrl}`);
assert.equal(decodeURIComponent(fillLink("https://example.com/#{{SUBSCRIPTION_LINK}}", sourceUrl, "").split("#")[1]), sourceUrl);
assert.equal(buttonPurpose({ type: "external", link: "https://cheezyvpn.uk/claim?url={{SUBSCRIPTION_LINK}}" }), "account");
assert.equal(buttonPurpose({ type: "external", link: "https://example.com/help", purpose: "help" }), "help");
assert.equal(buttonPurpose({ type: "copyButton", link: "{{SUBSCRIPTION_LINK}}" }), "import");
assert.equal(detectPlatform(["ios", "android"], "tdesktop", "unknown"), "");
assert.equal(resolveStage("guide", "", undefined), "platform");
assert.equal(resolveStage("guide", "android", undefined), "clients");
assert.equal(subscriptionState(2, [], { subscription_id: 1, connection_state: "connected" }), "unknown");
assert.equal(recommendedApp([{ name: "Alternative", featured: true }, { name: "CheezyVPN", featured: true }]), "CheezyVPN");
for (const [platform, entry] of Object.entries(catalog.platforms)) {
  assert.equal(entry.apps.filter((app) => app.recommended).length, 1, platform);
  if (["android", "windows", "macos", "linux"].includes(platform)) assert.equal(recommendedApp(entry.apps), "CheezyVPN");
  for (const app of entry.apps) for (const block of app.blocks) for (const button of block.buttons) {
    assert.ok(button.purpose);
    assert.ok(fillLink(button.link, sourceUrl, "test").length);
  }
}
console.log("PASS catalog semantics, URL encoding, selection and subscription isolation");

const base = process.env.MINIAPP_PREVIEW_URL || "http://127.0.0.1:5174/bot/miniapp/";
const out = new URL("../docs/screenshots/miniapp-connect-redesign/", import.meta.url);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHANNEL ? { channel: process.env.PLAYWRIGHT_CHANNEL } : {}) });
try {
  for (const language of ["ru", "en"]) {
    const context = await browser.newContext({ viewport: { width: 360, height: 640 }, permissions: ["clipboard-read", "clipboard-write"], reducedMotion: "reduce" });
    await context.route("https://telegram.org/js/telegram-web-app.js", (route) => route.fulfill({ body: "", contentType: "application/javascript" }));
    await context.addInitScript(() => {
      window.__openedLinks = [];
      window.__uxEvents = [];
      window.__subscriptionRequests = 0;
      const originalFetch = window.fetch.bind(window);
      window.fetch = (input, options) => {
        const url = typeof input === "string" ? input : input.url;
        if (url?.endsWith("/ux/events") && options?.body) window.__uxEvents.push(JSON.parse(options.body));
        if (url?.endsWith("/subscriptions") && (!options?.method || options.method === "GET")) window.__subscriptionRequests++;
        return originalFetch(input, options);
      };
      let back;
      window.__telegramBack = () => back?.();
      window.Telegram = { WebApp: {
        platform: "android", ready() {}, expand() {}, onEvent() {},
        themeParams: {}, safeAreaInset: {}, contentSafeAreaInset: {},
        HapticFeedback: { impactOccurred() {} },
        openLink(url) { window.__openedLinks.push(url); },
        BackButton: { show() {}, hide() {}, onClick(callback) { back = callback; }, offClick(callback) { if (back === callback) back = undefined; } },
      } };
    });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const txt = (ru, en) => language === "ru" ? ru : en;
    const goto = async (scenario = "connection-never", extra = "") => {
      await page.goto(`${base}connect?mock=${scenario}-${language}&mock_platform=android&source=review${extra}`);
      await page.locator(".connect-page").waitFor();
    };
    const shot = async (name) => {
      await page.mouse.move(0, 0);
      await page.screenshot({ path: new URL(`${language}-${name}.png`, out).pathname.replace(/^\/([A-Z]:)/, "$1"), animations: "disabled" });
    };
    const decodeQr = async () => {
      const image = page.locator(".connect-qr-image img");
      await image.waitFor();
      const pixels = await image.evaluate((img) => {
        const canvas = document.createElement("canvas"); canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d"); ctx.drawImage(img, 0, 0);
        return { width: canvas.width, height: canvas.height, data: [...ctx.getImageData(0, 0, canvas.width, canvas.height).data] };
      });
      return jsQR(new Uint8ClampedArray(pixels.data), pixels.width, pixels.height)?.data;
    };
    await goto();
    await page.locator(".connect-platform-grid").waitFor();
    assert.equal(await page.locator("details, .platform-tabs, .connect-progress-card, .connect-guide").count(), 0);
    const copy = page.locator(".connect-subscription").getByRole("button", { name: txt("Скопировать ссылку", "Copy link"), exact: true });
    assert.ok((await copy.boundingBox()).y < 200);
    await copy.click();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), "https://example.com/sub/mock-main");
    await shot("platforms-360");
    await page.getByRole("button", { name: txt("Android Это устройство", "Android This device"), exact: true }).click();
    await page.locator(".connect-choice-list").waitFor();
    assert.equal(await page.locator(".connect-choice").count(), 3);
    assert.equal(await page.locator(".connect-recommendation").count(), 1);
    assert.match(await page.locator(".connect-choice").first().innerText(), /CheezyVPN/);
    const alternative = await page.locator(".connect-choice").nth(2).boundingBox();
    const tabs = await page.locator(".bottom-tabs").boundingBox();
    assert.ok(alternative.y + alternative.height < tabs.y, "Two alternatives must fit above bottom navigation");
    await shot("clients-360");
    await page.locator(".connect-choice").first().click();
    await page.locator(".connect-guide").waitFor();
    assert.equal(await page.locator(".connect-guide > li").count(), 3);
    assert.equal(await page.locator(".connect-verification").count(), 0);
    const requestsBefore = await page.evaluate(() => window.__subscriptionRequests);
    await page.locator(".connect-guide-buttons").first().getByRole("button").first().click();
    assert.equal(await page.locator(".connect-verification").count(), 0);
    assert.equal(await page.evaluate(() => window.__subscriptionRequests), requestsBefore);
    await shot("guide-360");
    await page.reload(); await page.locator(".connect-guide").waitFor();
    assert.match(await page.locator("h1").innerText(), /CheezyVPN/);
    await page.evaluate(() => window.__telegramBack());
    await page.locator(".connect-choice-list").waitFor();
    assert.equal(new URL(page.url()).searchParams.get("app"), "CheezyVPN");
    await page.locator(".connect-choice").first().click();
    await page.goBack(); await page.locator(".connect-choice-list").waitFor();
    await page.getByRole("button", { name: txt("Изменить платформу", "Change platform"), exact: true }).click();
    await page.getByRole("checkbox", { name: txt("Хочу настроить на другом устройстве", "I want to set up another device"), exact: true }).click();
    await page.waitForFunction(() => document.querySelector('input[type="checkbox"]')?.checked === true);
    await page.getByRole("button", { name: "Windows", exact: true }).click();
    await page.locator(".connect-choice").first().click();
    await page.locator(".connect-guide").waitFor();
    assert.equal(await page.locator(".connect-verification-section").count(), 0);
    assert.ok(await page.locator(".connect-transfer-resource").count() >= 3);
    await shot("other-windows-360");
    const qrButton = page.locator(".connect-subscription .connect-qr-button");
    await qrButton.click();
    const qrImage = page.locator(".connect-qr-image img");
    await qrImage.waitFor();
    assert.equal(await page.getByRole("dialog").evaluate((el) => el.scrollTop), 0);
    assert.ok(await page.getByRole("dialog").evaluate((el) => Number(getComputedStyle(el).zIndex) > Number(getComputedStyle(document.querySelector(".bottom-tabs")).zIndex)));
    const pixels = await qrImage.evaluate((img) => {
      const canvas = document.createElement("canvas"); canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d"); ctx.drawImage(img, 0, 0);
      return { width: canvas.width, height: canvas.height, data: [...ctx.getImageData(0, 0, canvas.width, canvas.height).data] };
    });
    assert.equal(jsQR(new Uint8ClampedArray(pixels.data), pixels.width, pixels.height)?.data, "https://example.com/sub/mock-main");
    await shot("subscription-qr");
    await page.getByRole("button", { name: txt("Закрыть", "Close"), exact: true }).click();
    assert.equal(await qrButton.evaluate((el) => el === document.activeElement), true);
    const install = page.locator(".connect-transfer-resource").first();
    await install.getByRole("button").first().click();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), catalog.platforms.windows.apps[0].blocks[0].buttons[0].link);
    await install.locator(".connect-qr-button").click(); await qrImage.waitFor();
    assert.equal(await page.locator(".connect-dialog-url textarea").inputValue(), catalog.platforms.windows.apps[0].blocks[0].buttons[0].link);
    assert.equal(await decodeQr(), catalog.platforms.windows.apps[0].blocks[0].buttons[0].link);
    await page.keyboard.press("Escape");
    const account = page.locator(".connect-transfer-resource").last();
    await account.locator(".connect-qr-button").click();
    const accountUrl = await decodeQr();
    assert.equal(new URL(accountUrl).pathname, "/claim");
    assert.equal(new URL(accountUrl).searchParams.get("url"), "https://example.com/sub/mock-main");
    await page.keyboard.press("Escape");
    await page.locator(".connect-subscription-picker").click();
    await page.getByRole("dialog").locator(".connect-choice").nth(1).click();
    assert.match(await page.locator(".connect-subscription-url").inputValue(), /mock-marketplace$/);
    assert.equal(new URL(page.url()).searchParams.get("source"), "review");
    await page.locator(".connect-subscription .connect-qr-button").click(); await qrImage.waitFor();
    assert.match(await page.locator(".connect-dialog-url textarea").inputValue(), /mock-marketplace$/);
    await page.keyboard.press("Escape");
    const events = await page.evaluate(() => window.__uxEvents);
    assert.ok(events.some((e) => e.name === "connect_qr_opened" && e.resource === "subscription" && e.device_mode === "other"));
    assert.ok(!JSON.stringify(events).includes("https://"));
    await goto("connected", "&platform=windows&app=CheezyVPN&step=guide");
    await page.getByRole("button", { name: txt("Подключить через браузер", "Connect via browser"), exact: true }).click();
    await page.locator(".connect-verification.connected").waitFor();
    const opened = await page.evaluate(() => window.__openedLinks.at(-1));
    assert.equal(new URL(decodeURIComponent(new URL(opened).hash.slice(1))).pathname, "/claim");
    for (const [scenario, state] of [["connected", "connected"], ["connection-unknown", "unknown"], ["connection-never", "timeout"]]) {
      await goto(scenario, "&platform=android&app=CheezyVPN&step=guide&preview_timeout=1");
      await page.locator(".connect-verification-section > button").click();
      await page.locator(`.connect-verification.${state}`).waitFor();
      await shot(state);
    }
    await goto("catalog-error"); await page.getByText(txt("Не удалось загрузить приложения", "Could not load the apps"), { exact: true }).waitFor();
    assert.equal(await page.locator(".connect-subscription").count(), 1);
    await goto("empty"); await page.locator(".connect-empty").waitFor();
    await goto("single", "&platform=missing&app=Missing&step=guide"); await page.locator(".connect-platform-grid").waitFor();
    assert.equal(await page.locator(".connect-subscription-picker").count(), 0);
    await goto("single", "&platform=appleTV&step=clients"); await page.locator(".connect-choice-list").waitFor();
    assert.equal(await page.locator(".connect-choice").count(), 1);
    await page.locator(".connect-choice").click(); await page.locator(".connect-guide").waitFor();
    await goto("long-link", "&device=other");
    const longUrl = await page.locator(".connect-subscription-url").inputValue();
    assert.ok(longUrl.length > 1000);
    await page.locator(".connect-subscription .connect-qr-button").click();
    assert.equal(await decodeQr(), longUrl);
    await page.keyboard.press("Escape");
    await goto("qr-overflow", "&device=other");
    await page.locator(".connect-subscription .connect-qr-button").click();
    await page.locator(".connect-qr-image [role=alert]").waitFor();
    await page.getByRole("dialog").getByRole("button", { name: txt("Скопировать ссылку", "Copy link"), exact: true }).click();
    assert.ok((await page.evaluate(() => navigator.clipboard.readText())).length > 5000);
    await page.keyboard.press("Escape");
    await goto("single");
    await page.evaluate(() => {
      Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => { throw new Error("Denied"); } } });
      document.execCommand = () => false;
    });
    await page.locator(".connect-subscription").getByRole("button").first().click();
    await page.locator(".connect-dialog-url textarea").waitFor();
    assert.equal(await page.locator(".connect-dialog-url textarea").inputValue(), "https://example.com/sub/mock-main");
    assert.equal(await page.evaluate(() => document.activeElement?.tagName), "TEXTAREA");
    await shot("clipboard-fallback");
    await page.keyboard.press("Escape");
    await goto("single", "&platform=android&app=CheezyVPN&step=guide"); await page.locator(".connect-guide").waitFor();
    await page.setViewportSize({ width: 390, height: 844 }); await shot("guide-390");
    await page.addStyleTag({ content: ".connect-page { zoom: 1.5; }" });
    await shot("large-text");
    assert.ok(await page.evaluate(() => document.querySelector(".connect-page").scrollWidth <= document.querySelector(".connect-page").clientWidth + 1));
    assert.deepEqual(errors, []);
    await context.close();
    console.log(`PASS ${language}: navigation, clipboard, QR decoding, subscription change, verification, errors, layout`);
  }
} finally { await browser.close(); }
console.log("PASS complete ru/en browser matrix plus catalog assertions");
