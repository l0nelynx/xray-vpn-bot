import { createContext, useContext, useEffect, useMemo, useState } from "react";

export interface PublicBranding {
  branding_name: string;
  logo_url: string;
  favicon_url: string;
  manifest_url: string;
}

const FALLBACK: PublicBranding = {
  branding_name: "VPN Admin",
  logo_url: "/bot/dashboard/api/branding/logo",
  favicon_url: "/bot/dashboard/api/branding/icon/64.png",
  manifest_url: "/bot/dashboard/api/branding/manifest.webmanifest",
};

const BrandingContext = createContext<PublicBranding>(FALLBACK);

function updateHead(branding: PublicBranding) {
  document.title = `${branding.branding_name} Dashboard`;
  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (favicon) favicon.href = branding.favicon_url;
  const manifest = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
  if (manifest) manifest.href = branding.manifest_url;
}

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<PublicBranding>(FALLBACK);

  useEffect(() => {
    let active = true;
    const refresh = () => fetch("/bot/dashboard/api/branding", { cache: "no-cache" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<PublicBranding>;
      })
      .then((data) => {
        if (!active) return;
        const next = {
          ...FALLBACK,
          ...data,
          branding_name: data.branding_name?.trim() || FALLBACK.branding_name,
        };
        setBranding(next);
        updateHead(next);
      })
      .catch(() => updateHead(FALLBACK));
    void refresh();
    window.addEventListener("branding-updated", refresh);
    return () => {
      active = false;
      window.removeEventListener("branding-updated", refresh);
    };
  }, []);

  const value = useMemo(() => branding, [branding]);
  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>;
}

export function useBranding() {
  return useContext(BrandingContext);
}
