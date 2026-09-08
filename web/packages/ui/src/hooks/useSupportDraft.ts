import { useState } from "react";

/** Mount the editor with key=ticketId. Session storage avoids cross-tab drafts. */
export function useSupportDraft(key: string) {
  const storageKey = `support-draft:${key}`;
  const [value, setValue] = useState(() => {
    try { return sessionStorage.getItem(storageKey) || ""; } catch { return ""; }
  });
  const update = (next: string) => {
    setValue(next);
    try { if (next) sessionStorage.setItem(storageKey, next); else sessionStorage.removeItem(storageKey); } catch { /* Storage unavailable: retain in memory. */ }
  };
  return [value, update] as const;
}
