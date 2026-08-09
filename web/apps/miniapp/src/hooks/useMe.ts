import { useCallback, useEffect, useState } from "react";
import { api, MeResponse, UiLanguage } from "../api/client";

export function useMe() {
  const [data, setData] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = async (silent: boolean): Promise<MeResponse | null> => {
    if (!silent) setLoading(true);
    try {
      const me = await api.get<MeResponse>("/me");
      setData(me);
      setError(null);
      return me;
    } catch (e: any) {
      setError(e?.detail || String(e));
      if (!silent) setData(null);
      return null;
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const reload = () => fetchMe(false);
  const refresh = () => fetchMe(true);

  const setUserLanguage = useCallback((language: UiLanguage) => {
    setData((prev) => {
      if (!prev?.user) return prev;
      return {
        ...prev,
        user: { ...prev.user, language },
      };
    });
  }, []);

  useEffect(() => {
    fetchMe(false);
  }, []);

  return { data, loading, error, reload, refresh, setUserLanguage };
}
