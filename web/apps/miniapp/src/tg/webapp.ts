declare global {
  interface Window {
    Telegram?: {
      WebApp: any;
    };
  }
}

export const tg = window.Telegram?.WebApp;

// Telegram native apps that support and benefit from fullscreen mode.
// Desktop clients (tdesktop, web, webk, webz) open in a popup — fullscreen
// is either unsupported or simply wraps the browser fullscreen API, which is
// not what we want. Restrict to iOS and Android.
function isMobileTelegram(): boolean {
  const p = tg?.platform ?? "";
  return p === "ios" || p === "android";
}

// Read safe-area inset values from the JS API and apply them as CSS custom
// properties. Telegram sets --tg-* variables automatically in some clients,
// but not all versions do so reliably. Forcing them here ensures the CSS
// calc() expressions in theme.css always work.
function applyInsets() {
  if (!tg) return;
  const csa = tg.contentSafeAreaInset ?? {};
  const sa  = tg.safeAreaInset ?? {};
  const root = document.documentElement;
  root.style.setProperty("--tg-content-safe-area-inset-top",    `${csa.top    ?? 0}px`);
  root.style.setProperty("--tg-content-safe-area-inset-bottom", `${csa.bottom ?? 0}px`);
  root.style.setProperty("--tg-content-safe-area-inset-left",   `${csa.left   ?? 0}px`);
  root.style.setProperty("--tg-content-safe-area-inset-right",  `${csa.right  ?? 0}px`);
  root.style.setProperty("--tg-safe-area-inset-top",    `${sa.top    ?? 0}px`);
  root.style.setProperty("--tg-safe-area-inset-bottom", `${sa.bottom ?? 0}px`);
  root.style.setProperty("--tg-safe-area-inset-left",   `${sa.left   ?? 0}px`);
  root.style.setProperty("--tg-safe-area-inset-right",  `${sa.right  ?? 0}px`);
}

export function initTelegram() {
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();

    // Apply safe-area insets from JS API immediately (CSS-variable fallback).
    applyInsets();
    // Re-apply whenever Telegram reports a change (orientation, fullscreen toggle).
    tg.onEvent?.("safeAreaChanged",        applyInsets);
    tg.onEvent?.("contentSafeAreaChanged", applyInsets);

    // Fullscreen mode intentionally disabled.
  } catch (e) {
    console.warn("tg init failed", e);
  }
}

export function isFullscreen(): boolean {
  return tg?.isFullscreen ?? false;
}

export function exitFullscreen() {
  try {
    if (tg?.exitFullscreen) tg.exitFullscreen();
  } catch {
    /* noop */
  }
}

export function onFullscreenChange(cb: (fullscreen: boolean) => void) {
  try {
    tg?.onEvent?.("fullscreenChanged", () => cb(tg?.isFullscreen ?? false));
  } catch {
    /* noop */
  }
}

/** True when running inside Telegram Desktop or a web-based Telegram client. */
export function isDesktopTelegram(): boolean {
  const p = tg?.platform ?? "";
  return p === "tdesktop" || p === "web" || p === "webk" || p === "webz";
}

export function getInitData(): string {
  // Browser mock mode: real Telegram initData is absent; MSW ignores the header.
  if (import.meta.env.VITE_MOCK_API === "1") {
    const scenario = new URLSearchParams(window.location.search).get("mock");
    if (scenario) return `mock-scenario:${scenario}`;
    return tg?.initData || "mock-telegram-init-data";
  }
  return tg?.initData || "";
}

export function openLink(url: string) {
  if (!url) return;
  if (tg?.openLink) {
    tg.openLink(url);
  } else {
    window.open(url, "_blank");
  }
}

export function openTelegramLink(url: string) {
  if (!url) return;
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(url);
  } else {
    window.open(url, "_blank");
  }
}

export function showAlert(text: string) {
  if (tg?.showAlert) {
    tg.showAlert(text);
  } else {
    alert(text);
  }
}

export function hapticImpact(style: "light" | "medium" | "heavy" = "light") {
  try {
    tg?.HapticFeedback?.impactOccurred(style);
  } catch {
    /* noop */
  }
}

export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false;
  // Telegram WebApp doesn't expose a clipboard write API; use the browser's.
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to legacy path */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export function shareToTelegram(url: string, text: string) {
  // Opens Telegram's native "Share to…" sheet pre-filled with the invite
  // link + message. Falls back to a normal link open outside Telegram.
  if (!url) return;
  const shareUrl =
    "https://t.me/share/url?url=" +
    encodeURIComponent(url) +
    "&text=" +
    encodeURIComponent(text || "");
  openTelegramLink(shareUrl);
}
