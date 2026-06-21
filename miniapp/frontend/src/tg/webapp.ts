declare global {
  interface Window {
    Telegram?: {
      WebApp: any;
    };
  }
}

export const tg = window.Telegram?.WebApp;

export function initTelegram() {
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    // Bot API 8.0+: request fullscreen mode.
    // Telegram then sets --tg-content-safe-area-inset-* CSS variables so the
    // app can offset content below the floating header.
    if (tg.requestFullscreen) tg.requestFullscreen();
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

export function getInitData(): string {
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
