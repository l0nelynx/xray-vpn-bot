import { useEffect, useState } from "react";
import { api, MeResponse } from "../api/client";

export function useMe() {
  const [data, setData] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = async (silent: boolean) => {
    if (!silent) setLoading(true);
    try {
      const me = await api.get<MeResponse>("/me");
      setData(me);
      setError(null);
    } catch (e: any) {
      setError(e?.detail || String(e));
      if (!silent) setData(null);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const reload = () => fetchMe(false);
  const refresh = () => fetchMe(true);

  useEffect(() => {
    fetchMe(false);
  }, []);

  return { data, loading, error, reload, refresh };
}
