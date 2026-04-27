import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TicketSummary } from "../api/client";
import TicketListItem from "../components/TicketListItem";

export default function SupportPage() {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState<TicketSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TicketSummary[]>("/support/tickets")
      .then(setTickets)
      .catch((e) => setError(e?.detail || String(e)));
  }, []);

  return (
    <div className="page">
      <div className="page-title">Поддержка</div>

      {error && <div className="error-banner">{error}</div>}

      {tickets === null && !error && <div className="spinner-wrap">Загрузка…</div>}

      {tickets && tickets.length === 0 && (
        <div className="empty">
          У вас пока нет обращений.
          <br />
          Нажмите «+», чтобы создать.
        </div>
      )}

      {tickets &&
        tickets.map((t) => (
          <TicketListItem
            key={t.id}
            ticket={t}
            onClick={() => navigate(`/support/${t.id}`)}
          />
        ))}

      <button className="fab" onClick={() => navigate("/support/new")}>
        +
      </button>
    </div>
  );
}
