import { useEffect, useState } from "react";
import { api, MeResponse } from "../api/client";

export function useMe() {
  const [data, setData] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = async () => {
    setLoading(true);
    try {
      const me = await api.get<MeResponse>("/me");
      setData(me);
      setError(null);
    } catch (e: any) {
      setError(e?.detail || String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  return { data, loading, error, reload };
}
