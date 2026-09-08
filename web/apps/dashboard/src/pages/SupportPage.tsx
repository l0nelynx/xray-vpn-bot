import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import {
  ArrowLeft,
  Check,
  Copy,
  MessageSquare,
  RefreshCw,
  Search,
  User,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { SupportImages } from "@xray/ui/components/support-images";
import { useSupportPolling } from "@xray/ui/hooks/useSupportPolling";
import { useSupportDraft } from "@xray/ui/hooks/useSupportDraft";
import { api } from "../api/client";
import type {
  SupportTicketDetail,
  SupportTicketSummary,
  SupportAttachmentOut,
} from "../api/types";
import { useAuthedImage } from "../hooks/useAuthedImage";
import UserDrawer from "../components/UserDrawer";
import ConfirmButton from "../components/ConfirmButton";
import "./support.css";

const labels: Record<string, string> = {
  open: "Нужен ответ",
  in_progress: "Проверяем",
  waiting_user: "Ждём пользователя",
  closed: "Закрыт",
};
const categories: Record<string, string> = {
  connection: "Подключение",
  speed: "Скорость",
  payment: "Оплата",
  subscription: "Подписка",
  other: "Другое",
};
const queues = [
  ["needs_reply", "Нужен ответ"],
  ["waiting_user", "Ждём пользователя"],
  ["active", "Все активные"],
  ["closed", "Закрытые"],
  ["all", "Все"],
];
const date = (value: string) =>
  new Date(value).toLocaleString("ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
function waiting(value?: string | null) {
  if (!value) return "";
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 60000),
  );
  return minutes < 60
    ? `${minutes} мин`
    : minutes < 1440
      ? `${Math.floor(minutes / 60)} ч`
      : `${Math.floor(minutes / 1440)} д`;
}
function Thumb({ item }: { item: SupportAttachmentOut }) {
  const url = useAuthedImage(item.url);
  return url ? (
    <a href={url} target="_blank" rel="noreferrer">
      <img
        className="h-20 w-20 rounded-md object-cover"
        src={url}
        alt={item.filename}
      />
    </a>
  ) : (
    <span className="text-xs text-muted-foreground">Фото загружается…</span>
  );
}
type QueueResult = {
  items: SupportTicketSummary[];
  total: number;
  counts: Record<string, number>;
};

export default function SupportPage() {
  const [params, setParams] = useSearchParams();
  const id = Number(params.get("ticket")) || null;
  const [queue, setQueue] = useState("needs_reply");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("updated_at");
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  const { data, error, reload } = useSupportPolling<QueueResult>(
    `${queue}:${query}:${page}:${sort}`,
    () =>
      api.get(
        `/support/tickets?${new URLSearchParams({ queue, search: query, page: String(page), per_page: "20", sort, order: "desc" })}`,
      ),
  );
  const select = (ticket: number | null) => {
    const next = new URLSearchParams(params);
    if (ticket) next.set("ticket", String(ticket));
    else next.delete("ticket");
    setParams(next);
  };
  return (
    <div className="support-workspace">
      <div className="flex items-start justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-semibold">Поддержка</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.counts.needs_reply ?? "—"} обращений ждут вашего ответа
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void reload()}
          aria-label="Обновить"
        >
          <RefreshCw size={16} />
        </Button>
      </div>
      <div
        className="support-queues"
        role="tablist"
        aria-label="Очереди обращений"
      >
        {queues.map(([key, title]) => (
          <button
            key={key}
            role="tab"
            aria-selected={queue === key}
            className={queue === key ? "selected" : ""}
            onClick={() => {
              setQueue(key);
              setPage(1);
            }}
          >
            {title}
            {data?.counts[key] != null && <span>{data.counts[key]}</span>}
          </button>
        ))}
      </div>
      {error && (
        <div role="alert" className="text-destructive text-sm mb-2">
          Не удалось обновить обращения. {error}
        </div>
      )}
      <div className={`support-columns ${id ? "has-ticket" : ""}`}>
        <aside className="support-inbox">
          <div className="p-3 border-b border-border space-y-2">
            <div className="relative">
              <Search
                className="absolute left-3 top-3 text-muted-foreground"
                size={15}
              />
              <Input
                aria-label="Поиск обращений"
                placeholder="Тема, #номер, username или Telegram ID"
                className="pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <select
              aria-label="Сортировка"
              className="support-select w-full"
              disabled={queue === "needs_reply"}
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
            >
              <option value="updated_at">
                {queue === "needs_reply"
                  ? "Сначала самое долгое ожидание"
                  : "По последней активности"}
              </option>
              <option value="created_at">Сначала новые обращения</option>
              <option value="id">По номеру</option>
            </select>
          </div>
          <div className="support-inbox-list">
            {!data && !error && (
              <p className="p-5 text-muted-foreground">Загружаем обращения…</p>
            )}
            {data?.items.length === 0 && (
              <div className="p-8 text-center text-muted-foreground">
                <Check className="mx-auto mb-3" />
                {query
                  ? "Ничего не найдено. Измените запрос."
                  : "В этой очереди нет обращений"}
              </div>
            )}
            {data?.items.map((ticket) => (
              <button
                key={ticket.id}
                className={`support-inbox-item ${id === ticket.id ? "selected" : ""}`}
                onClick={() => select(ticket.id)}
              >
                <div className="flex justify-between gap-2 text-xs text-muted-foreground">
                  <span>
                    #{ticket.id} ·{" "}
                    {ticket.username
                      ? `@${ticket.username}`
                      : ticket.tg_id || "Пользователь"}
                  </span>
                  {ticket.unread && (
                    <span className="support-unread">Новое</span>
                  )}
                </div>
                <div className="font-medium mt-1 truncate">
                  {ticket.subject}
                </div>
                <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                  {ticket.last_sender === "admin" ? "Вы: " : ""}
                  {ticket.last_message_preview}
                </p>
                <div className="flex justify-between gap-2 mt-3 text-xs">
                  <span>{labels[ticket.status]}</span>
                  <span
                    className={
                      ticket.status === "open"
                        ? "text-amber-400"
                        : "text-muted-foreground"
                    }
                  >
                    {ticket.status === "open" || ticket.status === "in_progress"
                      ? `Ждёт ${waiting(ticket.waiting_since)}`
                      : date(ticket.updated_at)}
                  </span>
                </div>
                {ticket.assignee && (
                  <div className="text-xs text-muted-foreground mt-1">
                    Ответственный: {ticket.assignee}
                  </div>
                )}
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between p-3 border-t border-border text-xs">
            <Button
              variant="ghost"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Назад
            </Button>
            <span>
              {page} / {Math.max(1, Math.ceil((data?.total || 0) / 20))}
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={page * 20 >= (data?.total || 0)}
              onClick={() => setPage(page + 1)}
            >
              Далее
            </Button>
          </div>
        </aside>
        {id ? (
          <Conversation
            key={id}
            id={id}
            onClose={() => select(null)}
            onChange={() => void reload()}
          />
        ) : (
          <div className="support-empty">
            <MessageSquare size={32} />
            <p>Выберите обращение</p>
            <small>Переписка и данные пользователя появятся здесь</small>
          </div>
        )}
      </div>
    </div>
  );
}

function Conversation({
  id,
  onClose,
  onChange,
}: {
  id: number;
  onClose: () => void;
  onChange: () => void;
}) {
  const {
    data: ticket,
    error,
    reload,
  } = useSupportPolling<SupportTicketDetail>(String(id), () =>
    api.get(`/support/tickets/${id}`),
  );
  const [reply, setReply] = useSupportDraft(`dashboard:${id}:reply`);
  const [note, setNote] = useSupportDraft(`dashboard:${id}:note`);
  const [internal, setInternal] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [hasNew, setHasNew] = useState(false);
  const scroll = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const lastRead = useRef(0);
  const [templates, setTemplates] = useState<string[]>(() => {
    try {
      return (
        JSON.parse(localStorage.getItem("support-templates") || "null") || [
          "Здравствуйте! Уточните, пожалуйста, на каком устройстве возникает проблема и какое приложение вы используете. Пришлите скриншот ошибки.",
          "Попробуйте переключиться между Wi-Fi и мобильной сетью и подключиться повторно. Напишите, изменился ли результат.",
          "Уточните номер платежа и время оплаты. Проверим поступление и активацию подписки.",
        ]
      );
    } catch {
      return [];
    }
  });
  const text = internal ? note : reply;
  const setText = internal ? setNote : setReply;
  const markRead = () => {
    const cursor = ticket?.last_message_id || 0;
    if (cursor <= lastRead.current || document.hidden) return;
    lastRead.current = cursor;
    void api
      .post(`/support/tickets/${id}/read`, { message_id: cursor })
      .then(onChange)
      .catch(() => {
        lastRead.current = 0;
      });
  };
  useEffect(() => {
    if (!ticket) return;
    if (atBottom.current) {
      scroll.current?.scrollTo({ top: scroll.current.scrollHeight });
      markRead();
    } else setHasNew(true);
  }, [ticket?.messages.length, ticket?.last_message_id]);
  const jump = () => {
    atBottom.current = true;
    scroll.current?.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: "smooth",
    });
    setHasNew(false);
    markRead();
  };
  const mutate = async (action: () => Promise<unknown>) => {
    if (busy) return;
    setBusy(true);
    try {
      await action();
      await reload();
      onChange();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const send = async (close = false) => {
    const sent = text;
    await mutate(async () => {
      const form = new FormData();
      form.append("text", sent.trim());
      form.append("close", String(close));
      form.append("internal", String(internal));
      files.forEach((f) => form.append("images", f));
      await api.postForm(`/support/tickets/${id}/reply`, form);
      setText("");
      setFiles([]);
      atBottom.current = true;
    });
  };
  if (!ticket)
    return (
      <section className="p-5">
        <Button variant="ghost" onClick={onClose}>
          <ArrowLeft size={16} />
          Назад
        </Button>
        <p role={error ? "alert" : undefined}>
          {error || "Загружаем переписку…"}
        </p>
        <Button variant="outline" onClick={() => void reload()}>
          Повторить
        </Button>
      </section>
    );
  return (
    <section className="support-conversation">
      <header className="p-4 border-b border-border">
        <div className="flex items-start gap-2">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Закрыть обращение на экране"
            onClick={onClose}
          >
            <ArrowLeft size={18} />
          </Button>
          <div className="min-w-0 flex-1">
            <div className="text-xs text-muted-foreground">
              #{id} · {categories[ticket.category || "other"]}
            </div>
            <h2 className="font-semibold break-words">{ticket.subject}</h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Скопировать ссылку"
            onClick={() =>
              navigator.clipboard
                .writeText(location.href)
                .then(() => toast.success("Ссылка скопирована"))
                .catch(() => toast.error("Не удалось скопировать ссылку"))
            }
          >
            <Copy size={16} />
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <select
            aria-label="Статус обращения"
            className="support-select"
            disabled={busy}
            value={ticket.status}
            onChange={(e) =>
              void mutate(() =>
                api.patch(`/support/tickets/${id}`, { status: e.target.value }),
              )
            }
          >
            {Object.entries(labels).map(([k, v]) => (
              <option value={k} key={k}>
                {v}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              void mutate(() =>
                ticket.assignee
                  ? api.delete(`/support/tickets/${id}/claim`)
                  : api.post(`/support/tickets/${id}/claim`, {}),
              )
            }
          >
            {ticket.assignee ? `Снять: ${ticket.assignee}` : "Взять в работу"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setUserOpen(true)}>
            <User size={14} />
            {ticket.username || ticket.tg_id || "Пользователь"}
          </Button>
        </div>
        {Object.keys(ticket.context || {}).length > 0 && (
          <details className="mt-3 text-xs text-muted-foreground">
            <summary className="cursor-pointer">
              Устройство, подписка и платёж
            </summary>
            <div className="grid gap-1 mt-2">
              {Object.entries(ticket.context || {}).map(([key, value]) => (
                <div key={key}>
                  <strong>
                    {(
                      {
                        platform: "Устройство",
                        subscription: "Подписка",
                        payment: "Платёж",
                        language: "Язык",
                      } as Record<string, string>
                    )[key] || key}
                    :{" "}
                  </strong>
                  {typeof value === "object"
                    ? Object.entries(value as object)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(" · ")
                    : String(value)}
                </div>
              ))}
            </div>
          </details>
        )}
      </header>
      {error && (
        <div role="alert" className="text-xs text-destructive px-4 py-2">
          Обновление не удалось. Переписка сохранена на экране.
        </div>
      )}
      <div
        ref={scroll}
        className="support-messages"
        onScroll={() => {
          const el = scroll.current!;
          atBottom.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          if (atBottom.current) {
            setHasNew(false);
            markRead();
          }
        }}
      >
        {ticket.messages.map((m) => (
          <article key={m.id} className={`support-message ${m.sender}`}>
            <div className="flex justify-between gap-2 text-xs text-muted-foreground mb-2">
              <span>
                {m.sender === "note"
                  ? "Внутренняя заметка"
                  : m.sender === "admin"
                    ? m.author || "Поддержка"
                    : "Пользователь"}{" "}
                · {date(m.created_at)}
              </span>
              {m.sender === "admin" && (
                <ConfirmButton
                  title="Удалить ответ?"
                  description="Ответ исчезнет из переписки. Уже доставленное Telegram-уведомление останется."
                  destructive
                  confirmText="Удалить"
                  onConfirm={() =>
                    mutate(() =>
                      api.delete(`/support/tickets/${id}/messages/${m.id}`),
                    )
                  }
                >
                  <button aria-label="Удалить ответ" disabled={busy}>
                    <X size={12} />
                  </button>
                </ConfirmButton>
              )}
            </div>
            <p className="whitespace-pre-wrap break-words text-sm">{m.text}</p>
            <div className="flex gap-2 flex-wrap mt-2">
              {m.attachments?.map((a) => (
                <Thumb key={a.id} item={a} />
              ))}
            </div>
          </article>
        ))}
      </div>
      {hasNew && (
        <Button
          variant="secondary"
          size="sm"
          className="mx-auto"
          onClick={jump}
        >
          Новые сообщения ↓
        </Button>
      )}
      <footer className={`support-composer ${internal ? "is-note" : ""}`}>
        <div className="flex gap-2 mb-2">
          <Button
            size="sm"
            variant={internal ? "ghost" : "secondary"}
            disabled={busy}
            onClick={() => {
              setInternal(false);
              setFiles([]);
            }}
          >
            Ответ пользователю
          </Button>
          <Button
            size="sm"
            variant={internal ? "secondary" : "ghost"}
            disabled={busy}
            onClick={() => {
              setInternal(true);
              setFiles([]);
            }}
          >
            Заметка
          </Button>
        </div>
        {ticket.status === "closed" && !internal ? (
          <div className="text-sm text-muted-foreground">
            Обращение закрыто. Чтобы ответить, измените статус на «Нужен ответ».
          </div>
        ) : (
          <>
            {!internal && (
              <details className="mb-2 text-xs">
                <summary className="cursor-pointer text-muted-foreground">
                  Шаблоны ответов
                </summary>
                <div className="space-y-1 max-h-32 overflow-auto py-2">
                  {templates.map((value, i) => (
                    <div className="flex gap-2" key={i}>
                      <button
                        disabled={busy}
                        className="text-left truncate flex-1 hover:underline"
                        onClick={() =>
                          setReply(reply ? `${reply}\n\n${value}` : value)
                        }
                      >
                        {value}
                      </button>
                      <button
                        aria-label="Удалить шаблон"
                        onClick={() => {
                          const next = templates.filter((_, j) => i !== j);
                          setTemplates(next);
                          localStorage.setItem(
                            "support-templates",
                            JSON.stringify(next),
                          );
                        }}
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!reply.trim()}
                  onClick={() => {
                    const next = [...templates, reply.trim()];
                    setTemplates(next);
                    localStorage.setItem(
                      "support-templates",
                      JSON.stringify(next),
                    );
                    toast.success("Ответ сохранён как шаблон в этом браузере");
                  }}
                >
                  Сохранить текущий ответ
                </Button>
              </details>
            )}
            <Textarea
              aria-label={
                internal ? "Внутренняя заметка" : "Ответ пользователю"
              }
              disabled={busy}
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={3}
              maxLength={4000}
              placeholder={
                internal ? "Видно только администраторам" : "Напишите ответ…"
              }
              onKeyDown={(e) => {
                if (
                  (e.ctrlKey || e.metaKey) &&
                  e.key === "Enter" &&
                  (text.trim() || files.length)
                ) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <div className="flex justify-between text-xs text-muted-foreground my-2">
              <span>
                {text ? "Черновик сохранён" : "Ctrl / ⌘ + Enter — отправить"}
              </span>
              <span>{text.length}/4000</span>
            </div>
            <SupportImages
              files={files}
              onChange={setFiles}
              onError={toast.error}
              label="Фото"
              disabled={busy}
            />
            <div className="flex flex-wrap gap-2 mt-3">
              <Button
                disabled={busy || (!text.trim() && !files.length)}
                onClick={() => void send()}
              >
                {busy
                  ? "Отправляем…"
                  : internal
                    ? "Сохранить заметку"
                    : "Ответить"}
              </Button>
              {!internal && (
                <Button
                  variant="outline"
                  disabled={busy || (!text.trim() && !files.length)}
                  onClick={() => void send(true)}
                >
                  Ответить и закрыть
                </Button>
              )}
            </div>
          </>
        )}
      </footer>
      <UserDrawer
        userId={ticket.user_id}
        open={userOpen}
        onClose={() => setUserOpen(false)}
      />
    </section>
  );
}
