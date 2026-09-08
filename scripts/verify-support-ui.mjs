import { chromium } from "playwright";
import fs from "node:fs";
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1050 },
});
await context.addInitScript(() => localStorage.setItem("token", "mock-token"));
const dashboard = await context.newPage();
const errors = [];
dashboard.on("pageerror", (e) => errors.push(e.message));
await dashboard.goto("http://127.0.0.1:5173/bot/dashboard/support?ticket=1");
await dashboard
  .getByRole("textbox", { name: "Ответ пользователю", exact: true })
  .waitFor();
fs.mkdirSync("docs/screenshots/support-workflow", { recursive: true });
await dashboard.screenshot({
  path: "docs/screenshots/support-workflow/dashboard.png",
  fullPage: true,
});
const miniContext = await browser.newContext({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
});
const mini = await miniContext.newPage();
mini.on("pageerror", (e) => errors.push(e.message));
await mini.goto("http://127.0.0.1:5174/bot/miniapp/support/1");
await mini.getByRole("textbox").waitFor();
await mini.screenshot({
  path: "docs/screenshots/support-workflow/miniapp-chat.png",
  fullPage: true,
});
await mini.goto(
  "http://127.0.0.1:5174/bot/miniapp/support/new?category=connection",
);
await mini.getByRole("textbox").first().waitFor();
await mini.screenshot({
  path: "docs/screenshots/support-workflow/miniapp-create.png",
  fullPage: true,
});
// Draft survives navigation and full reload.
await dashboard
  .getByRole("textbox", { name: "Ответ пользователю", exact: true })
  .fill("QA draft preserved");
await dashboard.reload();
await dashboard
  .getByRole("textbox", { name: "Ответ пользователю", exact: true })
  .waitFor();
if (
  (await dashboard
    .getByRole("textbox", { name: "Ответ пользователю", exact: true })
    .inputValue()) !== "QA draft preserved"
)
  throw new Error("Lost dashboard draft");
await mini.goto("http://127.0.0.1:5174/bot/miniapp/support/1");
await mini.getByRole("textbox").waitFor();
await dashboard
  .getByRole("textbox", { name: "Ответ пользователю", exact: true })
  .fill("QA live reply");
await dashboard.getByRole("button", { name: "Ответить", exact: true }).click();
await mini
  .getByText("QA live reply", { exact: true })
  .waitFor({ timeout: 15000 });
await mini.getByRole("textbox").fill("QA user reply");
await mini.getByRole("button", { name: "Send", exact: true }).click();
await dashboard
  .locator(".support-messages")
  .getByText("QA user reply", { exact: true })
  .waitFor({ timeout: 15000 });
await dashboard.getByRole("button", { name: "Заметка", exact: true }).click();
await dashboard
  .getByRole("textbox", { name: "Внутренняя заметка", exact: true })
  .fill("QA private note");
await dashboard
  .getByRole("button", { name: "Сохранить заметку", exact: true })
  .click();
await dashboard.getByText("QA private note", { exact: true }).waitFor();
await mini.reload();
await mini.getByRole("textbox").waitFor();
if (await mini.getByText("QA private note", { exact: true }).count())
  throw new Error("Private note leaked");
await dashboard
  .getByRole("button", { name: "Ответ пользователю", exact: true })
  .click();
await dashboard
  .getByRole("textbox", { name: "Ответ пользователю", exact: true })
  .fill("QA resolved");
await dashboard
  .getByRole("button", { name: "Ответить и закрыть", exact: true })
  .click();
await mini
  .getByText("Request closed", { exact: true })
  .waitFor({ timeout: 15000 });
await mini
  .getByRole("button", { name: "Still need help", exact: true })
  .click();
await mini.getByRole("textbox").waitFor();
// Create a ticket with the first screenshot attached.
await mini.goto("http://127.0.0.1:5174/bot/miniapp/support/new");
await mini.getByRole("textbox").first().fill("QA initial screenshot");
await mini
  .locator("input[type=file]")
  .setInputFiles("docs/screenshots/support-workflow/miniapp-chat.png");
await mini.getByRole("button", { name: "Send request", exact: true }).click();
await mini.getByText("QA initial screenshot", { exact: true }).waitFor();
await mini.getByRole("img").first().waitFor();
await dashboard.setViewportSize({ width: 390, height: 844 });
await dashboard.screenshot({
  path: "docs/screenshots/support-workflow/dashboard-mobile.png",
  fullPage: true,
});
for (const page of [mini, dashboard]) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  if (overflow) throw new Error("Horizontal overflow");
}
console.log(
  JSON.stringify({
    errors,
    checks: [
      "draft persistence",
      "live admin reply",
      "live user reply",
      "private notes",
      "close and reopen",
      "initial photo upload",
      "mobile overflow",
    ],
    dashboard: await dashboard.title(),
    miniapp: await mini.title(),
  }),
);
if (errors.length) throw new Error(errors.join("\n"));
await browser.close();
