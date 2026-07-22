import { Card, CardContent } from "@xray/ui/components/card";
import { Badge } from "@xray/ui/components/badge";
import { TicketSummary } from "../api/client";
import { useT } from "../i18n/LocaleContext";

const STATUS_KEYS: Record<string, string> = {
  open: "tickets.status.open",
  in_progress: "tickets.status.inProgress",
  closed: "tickets.status.closed",
};

const STATUS_VARIANT: Record<string, "default" | "warning" | "secondary"> = {
  open: "default",
  in_progress: "warning",
  closed: "secondary",
};

interface Props {
  ticket: TicketSummary;
  onClick: () => void;
}

export default function TicketListItem({ ticket, onClick }: Props) {
  const { t, dateLocale } = useT();

  const formatDateTime = (iso: string): string => {
    try {
      const d = new Date(iso);
      return d.toLocaleString(dateLocale, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  return (
    <Card className="mb-3 cursor-pointer" onClick={onClick}>
      <CardContent className="p-4">
        <div className="text-base font-semibold text-foreground">{ticket.subject}</div>
        <p
          className="text-muted-foreground mt-1 mb-2 overflow-hidden"
          style={{
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
          }}
        >
          {ticket.last_message_preview}
        </p>
        <div className="flex justify-between items-center">
          <Badge variant={STATUS_VARIANT[ticket.status] || "secondary"}>
            {STATUS_KEYS[ticket.status]
              ? t(STATUS_KEYS[ticket.status])
              : ticket.status}
          </Badge>
          <span className="text-muted-foreground text-xs">
            {formatDateTime(ticket.updated_at)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
