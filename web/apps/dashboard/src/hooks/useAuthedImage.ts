import { useEffect, useState } from "react";
import { fetchAuthedBlob } from "../api/client";

/** A plain <img src> can't carry the Authorization header, so this fetches
 * the attachment with auth and hands back a blob object URL instead. */
export function useAuthedImage(url: string | null): string | null {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!url) {
      setObjectUrl(null);
      return;
    }
    let cancelled = false;
    let created: string | null = null;
    fetchAuthedBlob(url)
      .then((blob) => {
        if (cancelled) return;
        created = URL.createObjectURL(blob);
        setObjectUrl(created);
      })
      .catch(() => {
        if (!cancelled) setObjectUrl(null);
      });
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [url]);

  return objectUrl;
}
