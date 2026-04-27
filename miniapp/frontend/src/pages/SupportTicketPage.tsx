import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, TicketDetail } from "../api/client";

const STATUS_LABELS: Record<string, string> = {
  open: "Открыт",
  in_progress: "В работе",
  closed: "Закрыт",
};

export default function SupportTicketPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .get<TicketDetail>(`/support/tickets/${id}`)
      .then(setTicket)
      .catch((e) => setError(e?.detail || String(e)));
  }, [id]);

  return (
    <div className="page">
      <button
        className="btn secondary"
        style={{ marginTop: 0, marginBottom: 12 }}
        onClick={() => navigate("/support")}
      >
        ← Назад к списку
      </button>

      {error && <div className="error-banner">{error}</div>}

      {ticket && (
        <>
          <div className="page-title">{ticket.subject}</div>
          <div className="section">
            <div className="row">
              <span className="row-label">Статус</span>
              <span className={`badge ${ticket.status}`}>
                {STATUS_LABELS[ticket.status] || ticket.status}
              </span>
            </div>
            <div className="row">
              <span className="row-label">Создан</span>
              <span className="row-value">
                {dayjs(ticket.created_at).format("DD.MM.YYYY HH:mm")}
              </span>
            </div>
          </div>

          <div className="thread">
            {ticket.messages.map((m) => (
              <div key={m.id} className={`message-bubble ${m.sender}`}>
                <div>{m.text}</div>
                <div className="message-time">
                  {dayjs(m.created_at).format("DD.MM.YYYY HH:mm")}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
