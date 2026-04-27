import { PlusOutlined } from "@ant-design/icons";
import { Alert, Empty, FloatButton, Spin, Typography } from "antd";
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
      <Typography.Title level={3} style={{ marginBottom: 20 }}>
        Поддержка
      </Typography.Title>

      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

      {tickets === null && !error && (
        <div className="spinner-wrap">
          <Spin />
        </div>
      )}

      {tickets && tickets.length === 0 && (
        <Empty
          description={
            <>
              У вас пока нет обращений.
              <br />
              Нажмите «+», чтобы создать.
            </>
          }
        />
      )}

      {tickets &&
        tickets.map((t) => (
          <TicketListItem
            key={t.id}
            ticket={t}
            onClick={() => navigate(`/support/${t.id}`)}
          />
        ))}

      <FloatButton
        icon={<PlusOutlined />}
        type="primary"
        onClick={() => navigate("/support/new")}
        style={{ right: 24, bottom: 88 }}
      />
    </div>
  );
}
