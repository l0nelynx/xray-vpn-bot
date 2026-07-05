import { ArrowLeftOutlined, PaperClipOutlined, SendOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Image,
  Input,
  Space,
  Tag,
  Typography,
} from "antd";
import dayjs from "dayjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AttachmentOut, MessageItem, TicketDetail, api, support } from "../api/client";
import { useAuthedImage } from "../hooks/useAuthedImage";

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

const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

function AttachmentThumb({ attachment }: { attachment: AttachmentOut }) {
  const objectUrl = useAuthedImage(attachment.url);
  if (!objectUrl) {
    return <div style={{ width: 96, height: 96, background: "#f0f0f0", borderRadius: 6 }} />;
  }
  return (
    <Image
      src={objectUrl}
      width={96}
      height={96}
      style={{ objectFit: "cover", borderRadius: 6 }}
    />
  );
}

export default function SupportTicketPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [pendingImages, setPendingImages] = useState<File[]>([]);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!id) return;
    api
      .get<TicketDetail>(`/support/tickets/${id}`)
      .then(setTicket)
      .catch((e) => setError(e?.detail || String(e)));
  }, [id]);

  const previewUrls = useMemo(
    () => pendingImages.map((f) => URL.createObjectURL(f)),
    [pendingImages],
  );
  useEffect(() => {
    return () => previewUrls.forEach((u) => URL.revokeObjectURL(u));
  }, [previewUrls]);

  const onFilesSelected = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setSendError(null);
    const incoming = Array.from(files);
    const combined = [...pendingImages, ...incoming];
    if (combined.length > MAX_IMAGES) {
      setSendError(`Можно прикрепить не более ${MAX_IMAGES} изображений`);
      return;
    }
    for (const f of incoming) {
      if (f.size > MAX_IMAGE_BYTES) {
        setSendError(`Файл слишком большой (макс. 5MB): ${f.name}`);
        return;
      }
    }
    setPendingImages(combined);
  };

  const removePendingImage = (idx: number) => {
    setPendingImages((prev) => prev.filter((_, i) => i !== idx));
  };

  const sendReply = async () => {
    if (!id || !ticket) return;
    const text = reply.trim();
    if (!text && pendingImages.length === 0) return;
    setSending(true);
    setSendError(null);
    try {
      const msg: MessageItem = await support.addMessage(Number(id), text, pendingImages);
      setTicket({
        ...ticket,
        messages: [...ticket.messages, msg],
        updated_at: msg.created_at,
      });
      setReply("");
      setPendingImages([]);
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

      {error && <Alert type="error" title={error} style={{ marginBottom: 16 }} />}

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
                {m.text && (
                  <Typography.Paragraph style={{ marginBottom: 6, whiteSpace: "pre-wrap" }}>
                    {m.text}
                  </Typography.Paragraph>
                )}
                {m.attachments && m.attachments.length > 0 && (
                  <Image.PreviewGroup>
                    <Space size={8} wrap style={{ marginBottom: 6 }}>
                      {m.attachments.map((a) => (
                        <AttachmentThumb key={a.id} attachment={a} />
                      ))}
                    </Space>
                  </Image.PreviewGroup>
                )}
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
              title="Обращение закрыто. Создайте новое, если нужна помощь."
              style={{ marginTop: 16 }}
            />
          ) : (
            <Card size="small" style={{ marginTop: 16 }}>
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                {sendError && <Alert type="error" title={sendError} />}
                <Input.TextArea
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  placeholder="Ваше сообщение"
                  rows={4}
                  maxLength={4000}
                  showCount
                />
                {pendingImages.length > 0 && (
                  <Space size={8} wrap>
                    {pendingImages.map((f, idx) => (
                      <div key={idx} style={{ position: "relative" }}>
                        <img
                          src={previewUrls[idx]}
                          width={64}
                          height={64}
                          style={{ objectFit: "cover", borderRadius: 6 }}
                        />
                        <Button
                          size="small"
                          danger
                          shape="circle"
                          style={{ position: "absolute", top: -8, right: -8 }}
                          onClick={() => removePendingImage(idx)}
                        >
                          ×
                        </Button>
                      </div>
                    ))}
                  </Space>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  style={{ display: "none" }}
                  onChange={(e) => {
                    onFilesSelected(e.target.files);
                    e.target.value = "";
                  }}
                />
                <Space style={{ width: "100%" }}>
                  <Button
                    icon={<PaperClipOutlined />}
                    onClick={() => fileInputRef.current?.click()}
                    disabled={pendingImages.length >= MAX_IMAGES}
                  >
                    Фото
                  </Button>
                  <Button
                    type="primary"
                    size="large"
                    icon={<SendOutlined />}
                    loading={sending}
                    disabled={!reply.trim() && pendingImages.length === 0}
                    onClick={sendReply}
                    style={{ flex: 1 }}
                  >
                    Отправить
                  </Button>
                </Space>
              </Space>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
