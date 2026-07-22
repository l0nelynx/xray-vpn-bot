import { en } from "./en";
import { ru } from "./ru";
import type { Locale, Messages } from "./types";

export type { Locale, Messages } from "./types";

export const messages: Record<Locale, Messages> = { ru, en };

export function normalizeLocale(raw: string | null | undefined): Locale {
  if (raw === "en" || raw === "ru") return raw;
  return "ru";
}

export function localeTag(locale: Locale): string {
  return locale === "en" ? "en-US" : "ru-RU";
}

export function translate(
  locale: Locale,
  key: string,
  vars?: Record<string, string | number>
): string {
  const dict = messages[locale] ?? messages.ru;
  let text = dict[key] ?? messages.ru[key] ?? key;
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}
