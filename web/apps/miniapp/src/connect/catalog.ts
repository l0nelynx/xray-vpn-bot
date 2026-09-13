import type { ConnectApp, ConnectButton, ConnectPurpose, LocalizedText } from "../api/client";

export const PLATFORM_ORDER = ["ios", "android", "windows", "macos", "linux", "appleTV", "androidTV"];

export function tr(obj: LocalizedText | undefined, locale: string): string {
  return obj?.[locale] ?? obj?.en ?? Object.values(obj ?? {})[0] ?? "";
}

export function detectPlatform(available: string[], telegramPlatform: string, userAgent: string): string {
  if (["ios", "android"].includes(telegramPlatform) && available.includes(telegramPlatform)) return telegramPlatform;
  const ua = userAgent.toLowerCase();
  const match = /iphone|ipad|ipod/.test(ua) ? "ios" : /android/.test(ua) ? "android" :
    /mac os x|macintosh/.test(ua) ? "macos" : /windows/.test(ua) ? "windows" : /linux/.test(ua) ? "linux" : "";
  return available.includes(match) ? match : "";
}

export function recommendedApp(apps: ConnectApp[]): string | undefined {
  return apps.find((app) => app.recommended)?.name ??
    apps.find((app) => app.name === "CheezyVPN" && app.recommended !== false)?.name ??
    apps.find((app) => app.featured && app.recommended !== false)?.name;
}

/** Legacy catalogs keep their buttons. Semantics never depend on translated labels. */
export function buttonPurpose(button: ConnectButton): ConnectPurpose {
  if (button.purpose) return button.purpose;
  if (button.type !== "external") return "import";
  try {
    const url = new URL(button.link);
    if (url.pathname === "/claim") return "account";
  } catch { /* Custom schemes and malformed links are handled at execution. */ }
  if (button.link.includes("{{SUBSCRIPTION_LINK}}")) return "import";
  return "install";
}

export function fillLink(link: string, subUrl: string, username: string): string {
  const hashIdx = link.indexOf("#");
  const before = hashIdx >= 0 ? link.slice(0, hashIdx) : link;
  const after = hashIdx >= 0 ? link.slice(hashIdx) : "";
  return before
    .replace(/([?&][^=&#]+=)\{\{SUBSCRIPTION_LINK\}\}/g, (_m, prefix: string) => prefix + encodeURIComponent(subUrl))
    .replace(/([?&][^=&#]+=)\{\{USERNAME\}\}/g, (_m, prefix: string) => prefix + encodeURIComponent(username))
    .split("{{SUBSCRIPTION_LINK}}").join(subUrl)
    .split("{{USERNAME}}").join(username) + after
    .split("{{SUBSCRIPTION_LINK}}").join(encodeURIComponent(subUrl))
    .split("{{USERNAME}}").join(encodeURIComponent(username));
}

export function resolveStage(step: string | null, platform: string, app: ConnectApp | undefined) {
  if (!platform || step === "platform" || !step) return "platform";
  if (step === "guide" && app) return "guide";
  return "clients";
}

export function subscriptionState(
  id: number | null,
  items: { id: number; connection_state?: string }[],
  fallback?: { subscription_id?: number | null; connection_state?: string } | null,
): string {
  // Never verify a different (primary) subscription when the selected one is unavailable.
  return items.find((item) => item.id === id)?.connection_state ??
    (fallback?.subscription_id === id ? fallback?.connection_state : undefined) ?? "unknown";
}
