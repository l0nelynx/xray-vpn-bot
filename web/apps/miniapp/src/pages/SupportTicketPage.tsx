import { ArrowLeft, Paperclip, Send, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent } from "@xray/ui/components/card";
import { Dialog, DialogContent } from "@xray/ui/components/dialog";
import { Textarea } from "@xray/ui/components/textarea";
import { AttachmentOut, MessageItem, TicketDetail, api, support } from "../api/client";
import { useAuthedImage } from "../hooks/useAuthedImage";

const STATUS_LABELS: Record<string, string> = {
  open: "Открыт",
  in_progress: "В работе",
  closed: "Закрыт",
};

const STATUS_VARIANT: Record<string, "default" | "warning" | "secondary"> = {
  open: "default",
  in_progress: "warning",
  closed: "secondary",
};

const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function AttachmentThumb({ attachment, onOpen }: { attachment: AttachmentOut; onOpen: (url: string) => void }) {
  const objectUrl = useAuthedImage(attachment.url);
  if (!objectUrl) {
    return <div className="w-24 h-24 bg-muted rounded-md" />;
  }
  return (
    <img
      src={objectUrl}
      width={96}
      height={96}
      className="object-cover rounded-md cursor-pointer"
      onClick={() => onOpen(objectUrl)}
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
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
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
      <Button variant="outline" onClick={() => navigate("/support")} className="mb-3">
        <ArrowLeft />
        Назад
      </Button>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{error}</AlertTitle>
        </Alert>
      )}

      {ticket && (
        <>
          <div className="text-xl font-bold text-foreground mb-4">
            {ticket.subject}
          </div>

          <Card className="mb-4">
            <CardContent className="p-3.5 flex flex-col gap-2">
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground text-[13px]">Статус</span>
                <Badge variant={STATUS_VARIANT[ticket.status] || "secondary"}>
                  {STATUS_LABELS[ticket.status] || ticket.status}
                </Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-muted-foreground text-[13px]">Создан</span>
                <span className="text-[13px] text-foreground">{formatDateTime(ticket.created_at)}</span>
              </div>
            </CardContent>
          </Card>

          <div className="thread">
            {ticket.messages.map((m) => (
              <Card key={m.id} className={`message-bubble ${m.sender}`}>
                <CardContent className="p-3">
                  {m.text && (
                    <p className="mb-1.5 whitespace-pre-wrap mt-0">{m.text}</p>
                  )}
                  {m.attachments && m.attachments.length > 0 && (
                    <div className="flex gap-2 flex-wrap mb-1.5">
                      {m.attachments.map((a) => (
                        <AttachmentThumb key={a.id} attachment={a} onOpen={setPreviewUrl} />
                      ))}
                    </div>
                  )}
                  <span className="message-bubble__meta text-xs opacity-60">
                    {m.sender === "admin" ? "Поддержка" : "Вы"} ·{" "}
                    {formatDateTime(m.created_at)}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>

          {isClosed ? (
            <Alert className="mt-4">
              <AlertTitle>Обращение закрыто. Создайте новое, если нужна помощь.</AlertTitle>
            </Alert>
          ) : (
            <Card className="mt-4">
              <CardContent className="p-3.5 flex flex-col gap-3">
                {sendError && (
                  <Alert variant="destructive">
                    <AlertTitle>{sendError}</AlertTitle>
                  </Alert>
                )}
                <div className="flex flex-col gap-1">
                  <Textarea
                    value={reply}
                    onChange={(e) => setReply(e.target.value.slice(0, 4000))}
                    placeholder="Ваше сообщение"
                    rows={4}
                    maxLength={4000}
                  />
                  <span className="text-[11px] text-muted-foreground text-right">
                    {reply.length}/4000
                  </span>
                </div>
                {pendingImages.length > 0 && (
                  <div className="flex gap-2 flex-wrap">
                    {pendingImages.map((_, idx) => (
                      <div key={idx} className="relative">
                        <img
                          src={previewUrls[idx]}
                          width={64}
                          height={64}
                          className="object-cover rounded-md"
                        />
                        <button
                          onClick={() => removePendingImage(idx)}
                          className="absolute -top-2 -right-2 w-[22px] h-[22px] rounded-full bg-destructive text-destructive-foreground border-0 cursor-pointer flex items-center justify-center"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    onFilesSelected(e.target.files);
                    e.target.value = "";
                  }}
                />
                <div className="flex gap-2 w-full">
                  <Button
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={pendingImages.length >= MAX_IMAGES}
                  >
                    <Paperclip />
                    Фото
                  </Button>
                  <Button
                    className="flex-1"
                    size="lg"
                    disabled={sending || (!reply.trim() && pendingImages.length === 0)}
                    onClick={sendReply}
                  >
                    <Send />
                    Отправить
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      <Dialog open={!!previewUrl} onOpenChange={(open: boolean) => !open && setPreviewUrl(null)}>
        <DialogContent className="max-w-[90vw] bg-transparent border-0 shadow-none p-0">
          {previewUrl && (
            <img src={previewUrl} className="w-full max-h-[80vh] object-contain rounded-xl" />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
