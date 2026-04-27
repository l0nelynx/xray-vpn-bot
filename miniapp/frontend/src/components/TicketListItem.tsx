import { Card, Tag, Typography } from "antd";
import dayjs from "dayjs";
import { TicketSummary } from "../api/client";

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

interface Props {
  ticket: TicketSummary;
  onClick: () => void;
}

export default function TicketListItem({ ticket, onClick }: Props) {
  return (
    <Card
      hoverable
      size="small"
      style={{ marginBottom: 12, cursor: "pointer" }}
      onClick={onClick}
    >
      <Typography.Text strong style={{ fontSize: 16, display: "block" }}>
        {ticket.subject}
      </Typography.Text>
      <Typography.Paragraph
        type="secondary"
        ellipsis={{ rows: 2 }}
        style={{ marginBottom: 8, marginTop: 4 }}
      >
        {ticket.last_message_preview}
      </Typography.Paragraph>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Tag color={STATUS_COLOR[ticket.status] || "default"}>
          {STATUS_LABELS[ticket.status] || ticket.status}
        </Tag>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {dayjs(ticket.updated_at).format("DD.MM.YYYY HH:mm")}
        </Typography.Text>
      </div>
    </Card>
  );
}
