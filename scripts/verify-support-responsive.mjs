import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
const output = path.join(os.tmpdir(), "support-responsive-qa");
fs.mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const errors = [];
try {
  for (const width of [320, 390, 530]) {
    const context = await browser.newContext({
      viewport: { width, height: 844 },
      isMobile: true,
      hasTouch: true,
    });
    const page = await context.newPage();
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(
      "http://127.0.0.1:5174/bot/miniapp/support/1?mock=default-ru",
    );
    await page.locator(".mini-support-bubble").first().waitFor();
    // Reproduce the short content in the reported notification screenshot.
    await page.evaluate(() => {
      document.querySelector(".mini-support-header h1").textContent =
        "Подключение · Android";
      document.querySelector(".mini-support-bubble p").textContent =
        "Не работает";
    });
    const sizes = await page.evaluate(() => ({
      chat: document.querySelector(".mini-support-chat").getBoundingClientRect()
        .width,
      shell: document.querySelector(".app").getBoundingClientRect().width,
      overflow: document.documentElement.scrollWidth > innerWidth,
    }));
    assert.ok(Math.abs(sizes.chat - sizes.shell) < 1, JSON.stringify(sizes));
    assert.equal(sizes.overflow, false);
    if (width === 390)
      await page.screenshot({
        path: path.join(output, "miniapp-short-chat.png"),
      });
    await context.close();
  }
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  await context.addInitScript(() =>
    localStorage.setItem("token", "mock-token"),
  );
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://127.0.0.1:5173/bot/dashboard/support");
  await page.getByRole("tab", { name: /Needs reply/ }).waitFor();
  for (const tab of await page.getByRole("tab").all()) {
    const r = await tab.boundingBox();
    assert.ok(r.x >= 0 && r.x + r.width <= 391, "Queue is outside viewport");
  }
  await page.screenshot({
    path: path.join(output, "dashboard-mobile-inbox.png"),
  });
  await page.goto("http://127.0.0.1:5173/bot/dashboard/support?ticket=1");
  await page
    .getByRole("textbox", { name: "Reply to customer", exact: true })
    .waitFor();
  const bounds = await page.locator(".support-conversation").boundingBox();
  assert.ok(
    bounds.x === 0 &&
      bounds.y === 0 &&
      Math.abs(bounds.width - 390) < 1 &&
      Math.abs(bounds.height - 844) < 1,
    JSON.stringify(bounds),
  );
  await page.getByText("Reply templates", { exact: true }).click();
  assert.ok(await page.getByRole("button", { name: /Здравствуйте!/ }).count());
  await page.getByText("Reply templates", { exact: true }).click();
  await page.getByRole("button", { name: "Note", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Internal note", exact: true })
    .fill("Draft note");
  await page
    .getByRole("button", { name: "Reply to customer", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Reply to customer", exact: true })
    .fill("Draft reply");
  await page.screenshot({
    path: path.join(output, "dashboard-mobile-chat.png"),
  });
  // A reduced viewport approximates the space left by the software keyboard.
  await page.setViewportSize({ width: 390, height: 500 });
  await page.waitForFunction(
    () =>
      Math.abs(
        document.querySelector(".support-conversation").getBoundingClientRect()
          .height - 500,
      ) < 1,
  );
  const composer = await page.locator(".support-composer").boundingBox();
  assert.ok(composer.y + composer.height <= 501, JSON.stringify(composer));
  await page
    .getByRole("button", { name: "Reply and close", exact: true })
    .scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(output, "dashboard-keyboard.png") });
  await page
    .getByRole("button", { name: "Back to inbox", exact: true })
    .click();
  await page.getByRole("tab", { name: /Needs reply/ }).waitFor();
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      checks: [
        "short notification chat width: 320/390/530",
        "visible mobile queues",
        "full-screen mobile conversation",
        "Russian templates retained",
        "note and reply editors",
        "reduced keyboard viewport",
        "back to inbox",
      ],
      output,
    }),
  );
} finally {
  await browser.close();
}
