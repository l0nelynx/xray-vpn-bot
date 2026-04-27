import dayjs from "dayjs";
import { TicketSummary } from "../api/client";

const STATUS_LABELS: Record<string, string> = {
  open: "Открыт",
  in_progress: "В работе",
  closed: "Закрыт",
};

interface Props {
  ticket: TicketSummary;
  onClick: () => void;
}

export default function TicketListItem({ ticket, onClick }: Props) {
  return (
    <div className="ticket-item" onClick={onClick}>
      <div className="ticket-subject">{ticket.subject}</div>
      <div className="ticket-preview">{ticket.last_message_preview}</div>
      <div className="ticket-meta">
        <span className={`badge ${ticket.status}`}>
          {STATUS_LABELS[ticket.status] || ticket.status}
        </span>
        <span>{dayjs(ticket.updated_at).format("DD.MM.YYYY HH:mm")}</span>
      </div>
    </div>
  );
}
