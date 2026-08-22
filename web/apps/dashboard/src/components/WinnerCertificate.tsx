import { forwardRef, useEffect, useRef, useState } from "react";

export interface CertificateWinner {
  rank: number;
  username: string | null;
  tg_id: number;
  tickets: number;
  ticket_number: number | null;
}

interface WinnerCertificateProps {
  brandName: string;
  logoUrl: string;
  giveawayTitle: string;
  drawnAt: string | null;
  winners: CertificateWinner[];
  page: number;
  pageCount: number;
  showFull: boolean;
}

function maskValue(value: string, edge: number): string {
  if (value.length <= edge * 2) {
    return value ? `${value[0]}****${value[value.length - 1]}` : "****";
  }
  return `${value.slice(0, edge)}****${value.slice(-edge)}`;
}

export function formatWinnerUsername(username: string | null, showFull: boolean): string {
  if (!username) return "No username";
  return `@${showFull ? username : maskValue(username, 2)}`;
}

export function formatWinnerTgId(tgId: number, showFull: boolean): string {
  const value = String(tgId);
  return showFull ? value : maskValue(value, 3);
}

function formatDrawDate(value: string | null): string {
  if (!value) return "Draw complete";
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

const COLORS = {
  background: "#212121",
  foreground: "#fafafa",
  card: "#2b2b2b",
  secondary: "#383838",
  muted: "#adadad",
  border: "rgba(255,255,255,.14)",
  quietBorder: "rgba(255,255,255,.09)",
};

const WinnerCertificate = forwardRef<HTMLDivElement, WinnerCertificateProps>(
  ({ brandName, logoUrl, giveawayTitle, drawnAt, winners, page, pageCount, showFull }, ref) => (
    <div
      ref={ref}
      style={{
        width: 1080,
        height: 1350,
        overflow: "hidden",
        padding: 54,
        color: COLORS.foreground,
        background: COLORS.background,
        fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <div
        style={{
          display: "flex",
          height: "100%",
          flexDirection: "column",
          padding: "44px 48px 38px",
          border: `1px solid ${COLORS.border}`,
          borderRadius: 28,
          background: COLORS.card,
          boxShadow: "0 24px 80px rgba(0,0,0,.28)",
        }}
      >
        <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 28 }}>
          <div style={{ display: "flex", minWidth: 0, alignItems: "center", gap: 20 }}>
            <div
              style={{
                width: 68,
                height: 68,
                flex: "0 0 auto",
                overflow: "hidden",
                border: `1px solid ${COLORS.border}`,
                borderRadius: 16,
                background: COLORS.background,
              }}
            >
              <img src={logoUrl} alt="" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 28, fontWeight: 650, letterSpacing: "-.02em" }}>
                {brandName}
              </div>
              <div style={{ marginTop: 4, color: COLORS.muted, fontSize: 16 }}>Dashboard giveaway</div>
            </div>
          </div>
          <div
            style={{
              flex: "0 0 auto",
              border: `1px solid ${COLORS.border}`,
              borderRadius: 999,
              padding: "10px 16px",
              background: COLORS.secondary,
              fontSize: 15,
              fontWeight: 600,
            }}
          >
            Draw complete
          </div>
        </header>

        <div style={{ height: 1, margin: "28px 0", background: COLORS.border }} />

        <section>
          <div style={{ color: COLORS.muted, fontSize: 16, fontWeight: 600 }}>Giveaway winners</div>
          <div
            style={{
              maxWidth: 820,
              marginTop: 10,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              fontSize: 44,
              fontWeight: 650,
              letterSpacing: "-.035em",
              lineHeight: 1.08,
            }}
          >
            {giveawayTitle}
          </div>
          <div style={{ marginTop: 12, color: COLORS.muted, fontSize: 16 }}>{formatDrawDate(drawnAt)}</div>
        </section>

        <main style={{ display: "flex", flex: 1, flexDirection: "column", gap: 10, marginTop: 28 }}>
          {winners.map((winner) => (
            <div
              key={`${winner.rank}-${winner.tg_id}`}
              style={{
                display: "grid",
                minHeight: 92,
                gridTemplateColumns: "68px minmax(0,1fr) 218px",
                alignItems: "center",
                overflow: "hidden",
                border: `1px solid ${COLORS.quietBorder}`,
                borderRadius: 14,
                background: COLORS.secondary,
              }}
            >
              <div
                style={{
                  display: "flex",
                  width: 38,
                  height: 38,
                  alignItems: "center",
                  justifyContent: "center",
                  justifySelf: "center",
                  borderRadius: 10,
                  background: winner.rank === 1 ? COLORS.foreground : COLORS.card,
                  color: winner.rank === 1 ? COLORS.background : COLORS.foreground,
                  fontSize: 16,
                  fontWeight: 700,
                }}
              >
                {winner.rank}
              </div>
              <div style={{ minWidth: 0, padding: "0 22px", borderLeft: `1px solid ${COLORS.quietBorder}` }}>
                <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 22, fontWeight: 600 }}>
                  {formatWinnerUsername(winner.username, showFull)}
                </div>
                <div style={{ marginTop: 6, color: COLORS.muted, fontSize: 15 }}>
                  TG ID {formatWinnerTgId(winner.tg_id, showFull)} · {winner.tickets} {winner.tickets === 1 ? "ticket" : "tickets"}
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", paddingRight: 18 }}>
                <div
                  style={{
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: 10,
                    padding: "10px 14px",
                    background: COLORS.card,
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                    fontSize: 17,
                    fontWeight: 650,
                    whiteSpace: "nowrap",
                  }}
                >
                  Ticket #{winner.ticket_number == null ? "—" : String(winner.ticket_number).padStart(4, "0")}
                </div>
              </div>
            </div>
          ))}
        </main>

        <footer
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 28,
            paddingTop: 22,
            borderTop: `1px solid ${COLORS.border}`,
            color: COLORS.muted,
            fontSize: 14,
          }}
        >
          <span>Generated by {brandName}</span>
          <span>{pageCount > 1 ? `Page ${page} of ${pageCount}` : "Final result"}</span>
        </footer>
      </div>
    </div>
  ),
);

WinnerCertificate.displayName = "WinnerCertificate";

export default WinnerCertificate;

export function ScaledWinnerCertificate(props: WinnerCertificateProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.5);

  useEffect(() => {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;
    const update = () => setScale(wrapper.clientWidth / 1080);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(wrapper);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={wrapperRef} style={{ position: "relative", width: "100%", aspectRatio: "4 / 5", overflow: "hidden", borderRadius: 18 }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: 1350, transform: `scale(${scale})`, transformOrigin: "top left" }}>
        <WinnerCertificate {...props} />
      </div>
    </div>
  );
}
