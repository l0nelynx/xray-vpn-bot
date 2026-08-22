import { ux, type UxEvent } from "./api/client";
import { tg } from "./tg/webapp";

const SESSION_KEY = "miniapp_ux_session";

function sessionId(): string {
  try {
    let value = sessionStorage.getItem(SESSION_KEY);
    if (!value) {
      value = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      sessionStorage.setItem(SESSION_KEY, value);
    }
    return value;
  } catch {
    return "session-unavailable";
  }
}

export function trackUx(event: UxEvent): void {
  const platform = event.platform || tg?.platform || (
    /android/i.test(navigator.userAgent) ? "android" :
    /iphone|ipad|ipod/i.test(navigator.userAgent) ? "ios" : "web"
  );
  void ux.track({ ...event, platform, session_id: sessionId() }).catch(() => {});
}
