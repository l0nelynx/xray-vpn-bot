import { CSSProperties } from "react";

interface PreviewButton {
  text: string;
  row: number;
  col?: number;
}

interface TelegramPreviewProps {
  messageText?: string;
  buttons: PreviewButton[];
  style?: CSSProperties;
}

export default function TelegramPreview({ messageText, buttons, style }: TelegramPreviewProps) {
  // Group buttons by row
  const rows: Record<number, PreviewButton[]> = {};
  buttons.forEach((btn) => {
    if (!rows[btn.row]) rows[btn.row] = [];
    rows[btn.row].push(btn);
  });
  const sortedRows = Object.keys(rows)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div
      style={{
        width: 320,
        margin: "0 auto",
        background: "#1a1a2e",
        borderRadius: 28,
        padding: "12px 8px",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        border: "2px solid rgba(255,255,255,0.08)",
        ...style,
      }}
    >
      {/* Phone notch */}
      <div
        style={{
          width: 100,
          height: 6,
          background: "rgba(255,255,255,0.1)",
          borderRadius: 3,
          margin: "0 auto 12px",
        }}
      />

      {/* Chat header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          marginBottom: 12,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 16,
            background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            color: "#fff",
            fontWeight: 700,
          }}
        >
          B
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.9)" }}>
            XRAY VPN Bot
          </div>
          <div style={{ fontSize: 10, color: "rgba(255,255,255,0.4)" }}>online</div>
        </div>
      </div>

      {/* Message bubble */}
      {messageText && (
        <div
          style={{
            background: "rgba(255,255,255,0.06)",
            borderRadius: "12px 12px 12px 4px",
            padding: "10px 14px",
            margin: "0 8px 8px",
            fontSize: 13,
            color: "rgba(255,255,255,0.85)",
            lineHeight: 1.5,
            whiteSpace: "pre-wrap",
            maxHeight: 120,
            overflow: "auto",
          }}
          dangerouslySetInnerHTML={{ __html: messageText.replace(/\n/g, "<br/>") }}
        />
      )}

      {/* Inline keyboard */}
      <div style={{ padding: "0 8px 8px" }}>
        {sortedRows.map((rowIdx) => (
          <div
            key={rowIdx}
            style={{
              display: "flex",
              gap: 4,
              marginBottom: 4,
            }}
          >
            {rows[rowIdx].map((btn, i) => (
              <div
                key={i}
                style={{
                  flex: 1,
                  textAlign: "center",
                  background: "rgba(100,149,237,0.15)",
                  color: "#6495ed",
                  borderRadius: 6,
                  padding: "8px 4px",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "default",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  border: "1px solid rgba(100,149,237,0.2)",
                }}
              >
                {btn.text}
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Bottom bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 12px",
          borderTop: "1px solid rgba(255,255,255,0.06)",
          marginTop: 4,
        }}
      >
        <div
          style={{
            flex: 1,
            height: 32,
            borderRadius: 16,
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        />
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 16,
            background: "rgba(100,149,237,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
          }}
        >
          🎤
        </div>
      </div>
    </div>
  );
}
