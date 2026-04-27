import { ArrowLeftOutlined, SendOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Input,
  Space,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, MessageItem, TicketDetail } from "../api/client";

const STATUS_LABELS: Record<string, string> = {
  open: "Открыт",
  in_progress: "В работе",
  closed: "Закрыт",
};

const STATUS_COLOR: Record<string, string> = {
  open: "processing",
  in_progress: "warning",
  closed: "default",
};

export default function SupportTicketPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .get<TicketDetail>(`/support/tickets/${id}`)
      .then(setTicket)
      .catch((e) => setError(e?.detail || String(e)));
  }, [id]);

  const sendReply = async () => {
    if (!id || !ticket) return;
    const text = reply.trim();
    if (!text) return;
    setSending(true);
    setSendError(null);
    try {
      const msg = await api.post<MessageItem>(
        `/support/tickets/${id}/messages`,
        { text },
      );
      setTicket({
        ...ticket,
        messages: [...ticket.messages, msg],
        updated_at: msg.created_at,
      });
      setReply("");
    } catch (e: any) {
      setSendError(e?.detail || String(e));
    } finally {
      setSending(false);
    }
  };

  const isClosed = ticket?.status === "closed";

  return (
    <div className="page">
      <Button
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate("/support")}
        style={{ marginBottom: 12 }}
      >
        Назад
      </Button>

      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

      {ticket && (
        <>
          <Typography.Title level={3} style={{ marginBottom: 16 }}>
            {ticket.subject}
          </Typography.Title>

          <Card size="small" style={{ marginBottom: 16 }}>
            <Descriptions column={1} size="small" colon={false}>
              <Descriptions.Item label="Статус">
                <Tag color={STATUS_COLOR[ticket.status] || "default"}>
                  {STATUS_LABELS[ticket.status] || ticket.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Создан">
                {dayjs(ticket.created_at).format("DD.MM.YYYY HH:mm")}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <div className="thread">
            {ticket.messages.map((m) => (
              <Card
                key={m.id}
                size="small"
                className={`message-bubble ${m.sender}`}
                styles={{ body: { padding: 12 } }}
              >
                <Typography.Paragraph style={{ marginBottom: 6, whiteSpace: "pre-wrap" }}>
                  {m.text}
                </Typography.Paragraph>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {m.sender === "admin" ? "Поддержка" : "Вы"} ·{" "}
                  {dayjs(m.created_at).format("DD.MM.YYYY HH:mm")}
                </Typography.Text>
              </Card>
            ))}
          </div>

          {isClosed ? (
            <Alert
              type="info"
              message="Обращение закрыто. Создайте новое, если нужна помощь."
              style={{ marginTop: 16 }}
            />
          ) : (
            <Card size="small" style={{ marginTop: 16 }}>
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {sendError && <Alert type="error" message={sendError} />}
                <Input.TextArea
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  placeholder="Ваше сообщение"
                  rows={4}
                  maxLength={4000}
                  showCount
                />
                <Button
                  type="primary"
                  size="large"
                  block
                  icon={<SendOutlined />}
                  loading={sending}
                  disabled={!reply.trim()}
                  onClick={sendReply}
                >
                  Отправить
                </Button>
              </Space>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
