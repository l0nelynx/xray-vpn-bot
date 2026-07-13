/**
 * Icon rendering for the connect-page app catalog.
 *
 * Icons ship *inside* the app-config under `svgLibrary` (svgIconKey -> raw SVG
 * markup), so brand logos and UI glyphs both come from the same document the
 * operator controls — no bundled asset set to keep in sync. We render the SVG
 * inline; a missing app key falls back to a coloured monogram.
 */
import type { CSSProperties } from "react";

export type SvgLibrary = Record<string, string>;

// svgIconColor name -> hex (Remnawave palette, close enough for accents).
const COLOR_MAP: Record<string, string> = {
  violet: "#B47CFF",
  cyan: "#4FD1FF",
  teal: "#2DD4BF",
  green: "#4ADE80",
  blue: "#7C9CFF",
  red: "#FF7C7C",
  orange: "#FFAE63",
  yellow: "#FFD86B",
  gray: "rgba(255,255,255,0.6)",
  grey: "rgba(255,255,255,0.6)",
};

export function resolveColor(name?: string): string {
  if (!name) return "#7C9CFF";
  return COLOR_MAP[name.toLowerCase()] ?? name; // allow raw hex too
}

// Defense-in-depth: the config is operator-trusted, but it renders into users'
// browsers, so strip <script> and inline event handlers before injecting.
function sanitizeSvg(markup: string): string {
  return markup
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/\son\w+\s*=\s*"[^"]*"/gi, "")
    .replace(/\son\w+\s*=\s*'[^']*'/gi, "")
    // Drop fixed width/height so the wrapper controls the size (viewBox stays).
    .replace(/(<svg\b[^>]*?)\swidth="[^"]*"/i, "$1")
    .replace(/(<svg\b[^>]*?)\sheight="[^"]*"/i, "$1");
}

/** Render an icon from the svgLibrary by key. Returns null if the key is absent. */
export function LibIcon({
  library,
  name,
  size = 20,
  color,
}: {
  library?: SvgLibrary;
  name?: string;
  size?: number;
  color?: string;
}) {
  const markup = name && library ? library[name] : undefined;
  if (!markup) return null;
  const style: CSSProperties = {
    width: size,
    height: size,
    color: color ?? "currentColor",
    flexShrink: 0,
  };
  return (
    <span
      className="lib-icon"
      style={style}
      dangerouslySetInnerHTML={{ __html: sanitizeSvg(markup) }}
    />
  );
}

// Deterministic accent per app name so monogram fallbacks differ.
const MONOGRAM_COLORS = ["#7C9CFF", "#B47CFF", "#2DD4BF", "#FFAE63", "#4FD1FF", "#FF7C9C"];
function monogramColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return MONOGRAM_COLORS[h % MONOGRAM_COLORS.length];
}
function initials(name: string): string {
  const parts = name.trim().split(/[\s-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

/** App brand icon from svgLibrary, falling back to a coloured monogram. */
export function AppIcon({
  library,
  name,
  iconKey,
  size = 38,
}: {
  library?: SvgLibrary;
  name: string;
  iconKey?: string;
  size?: number;
}) {
  if (iconKey && library?.[iconKey]) {
    return (
      <span
        style={{
          width: size,
          height: size,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#FFFFFF",
          flexShrink: 0,
        }}
      >
        <LibIcon library={library} name={iconKey} size={Math.round(size * 0.8)} />
      </span>
    );
  }
  const accent = monogramColor(name);
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.28,
        background: `${accent}22`,
        border: `1px solid ${accent}55`,
        color: accent,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: size * 0.36,
        fontWeight: 700,
        flexShrink: 0,
      }}
    >
      {initials(name)}
    </div>
  );
}
