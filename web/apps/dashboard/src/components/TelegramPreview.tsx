import { CSSProperties, useMemo } from "react";
import { Bot, CornerDownRight, MessageSquareText } from "lucide-react";
import { Badge } from "@xray/ui/components/badge";
import { sanitizeTelegramHtml } from "../utils/sanitize";

interface PreviewButton {
  text: string;
  row: number;
  col?: number;
  destination?: string;
}

interface TelegramPreviewProps {
  messageText?: string;
  buttons: PreviewButton[];
  style?: CSSProperties;
}

export default function TelegramPreview({
  messageText,
  buttons,
  style,
}: TelegramPreviewProps) {
  const sanitizedHtml = useMemo(
    () => (messageText ? sanitizeTelegramHtml(messageText.replace(/\n/g, "<br/>")) : ""),
    [messageText],
  );

  const rows = useMemo(() => {
    const grouped = new Map<number, PreviewButton[]>();
    buttons.forEach((button) => {
      const row = grouped.get(button.row) ?? [];
      row.push(button);
      grouped.set(button.row, row);
    });
    return [...grouped.entries()]
      .sort(([left], [right]) => left - right)
      .map(([row, rowButtons]) => ({
        row,
        buttons: rowButtons.sort((left, right) => (left.col ?? 0) - (right.col ?? 0)),
      }));
  }, [buttons]);

  return (
    <div
      className="w-full overflow-hidden rounded-lg border border-border bg-background/45 shadow-sm"
      style={style}
    >
      <div className="flex items-center justify-between gap-3 border-b border-border bg-white/[0.025] px-3.5 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex h-9 w-9 flex-none items-center justify-center rounded-md border border-border bg-secondary text-secondary-foreground">
            <Bot className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-[13px] font-medium text-foreground">
              XRAY VPN Bot
            </div>
            <div className="text-[10px] text-muted-foreground">Menu response preview</div>
          </div>
        </div>
        <Badge variant="outline" className="flex-none border-border text-[10px] font-medium text-muted-foreground">
          Telegram
        </Badge>
      </div>

      <div className="space-y-4 p-3.5">
        <section className="space-y-1.5">
          <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
            <MessageSquareText className="h-3 w-3" />
            Message
          </div>
          {messageText ? (
            <div
              className="max-h-44 overflow-auto rounded-lg border border-border bg-card px-3.5 py-3 text-[13px] leading-5 text-foreground/85 shadow-sm"
              dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
            />
          ) : (
            <div className="rounded-lg border border-dashed border-border px-3.5 py-5 text-center text-xs text-muted-foreground">
              Add message text to preview this screen.
            </div>
          )}
        </section>

        <section className="space-y-1.5">
          <div className="flex items-center justify-between gap-2 text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
            <span>Inline keyboard</span>
            <span className="font-mono tracking-normal">
              {buttons.length} {buttons.length === 1 ? "action" : "actions"}
            </span>
          </div>
          {rows.length > 0 ? (
            <div className="space-y-1.5">
              {rows.map(({ row, buttons: rowButtons }) => (
                <div key={row} className="grid auto-cols-fr grid-flow-col gap-1.5">
                  {rowButtons.map((button, index) => (
                    <div
                      key={`${row}-${button.col ?? index}-${button.text}`}
                      className="flex min-w-0 flex-col items-center justify-center rounded-md border border-input bg-transparent px-2 py-2 text-center shadow-sm"
                    >
                      <span className="w-full truncate text-[12px] font-medium text-foreground/90">
                        {button.text || "Untitled button"}
                      </span>
                      {button.destination && (
                        <span className="mt-1 flex max-w-full items-center gap-1 text-[9px] text-muted-foreground">
                          <CornerDownRight className="h-2.5 w-2.5 flex-none" />
                          <span className="truncate">{button.destination}</span>
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border px-3.5 py-5 text-center text-xs text-muted-foreground">
              Active buttons will appear here.
            </div>
          )}
        </section>
      </div>

      <div className="flex items-center justify-between border-t border-border px-3.5 py-2 text-[10px] text-muted-foreground">
        <span>Rendered from saved menu data</span>
        <span className="font-mono">HTML</span>
      </div>
    </div>
  );
}
