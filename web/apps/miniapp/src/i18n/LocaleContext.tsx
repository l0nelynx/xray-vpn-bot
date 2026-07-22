import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  localeTag,
  normalizeLocale,
  translate,
  type Locale,
} from "./index";

type SetLocaleFn = (locale: Locale) => void | Promise<void>;

interface LocaleContextValue {
  locale: Locale;
  setLocale: SetLocaleFn;
  t: (key: string, vars?: Record<string, string | number>) => string;
  dateLocale: string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

interface ProviderProps {
  locale: Locale;
  onLocaleChange?: SetLocaleFn;
  children: ReactNode;
}

export function LocaleProvider({
  locale: localeProp,
  onLocaleChange,
  children,
}: ProviderProps) {
  const [locale, setLocaleState] = useState<Locale>(localeProp);

  useEffect(() => {
    setLocaleState(localeProp);
  }, [localeProp]);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback<SetLocaleFn>(
    async (next) => {
      const normalized = normalizeLocale(next);
      let previous: Locale = "ru";
      setLocaleState((prev) => {
        previous = prev;
        return normalized;
      });
      try {
        if (onLocaleChange) await onLocaleChange(normalized);
      } catch (err) {
        setLocaleState(previous);
        throw err;
      }
    },
    [onLocaleChange]
  );

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) =>
      translate(locale, key, vars),
    [locale]
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
      dateLocale: localeTag(locale),
    }),
    [locale, setLocale, t]
  );

  return createElement(LocaleContext.Provider, { value }, children);
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useLocale must be used within LocaleProvider");
  }
  return ctx;
}

export function useT() {
  const { t, locale, dateLocale } = useLocale();
  return { t, locale, dateLocale };
}
