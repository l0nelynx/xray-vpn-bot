declare global {
  interface Window {
    __WEB_BASE__?: string;
    __WEB_BRAND_NAME__?: string;
    __WEB_BRAND_LOGO__?: string;
  }
}

export const BRAND_NAME: string = window.__WEB_BRAND_NAME__ || "Cheeze Networks";
export const BRAND_LOGO: string = window.__WEB_BRAND_LOGO__ || "";
