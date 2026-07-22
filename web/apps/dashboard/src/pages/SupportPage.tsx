import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { Paperclip, Trash2, User } from "lucide-react";
import { Card, CardContent } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { Badge } from "@xray/ui/components/badge";
import { Spinner } from "@xray/ui/components/spinner";
import { cn } from "@xray/ui/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@xray/ui/components/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { api } from "../api/client";
import {
  PaginatedResponse,
  SupportAttachmentOut,
  SupportTicketDetail,
  SupportTicketSummary,
} from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import { useAuthedImage } from "../hooks/useAuthedImage";
import MobileSortControl, { type SortOrder } from "../components/MobileSortControl";
import UserDrawer from "../components/UserDrawer";
import DataTable from "../components/DataTable";
import TablePagination from "../components/TablePagination";
import ConfirmButton from "../components/ConfirmButton";
import { makeSortToggle } from "../utils/tableChange";

const MAX_IMAGES = 3;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

function AttachmentThumb({ attachment }: { attachment: SupportAttachmentOut }) {
  const objectUrl = useAuthedImage(attachment.url);
  if (!objectUrl) {
    return <div className="h-20 w-20 rounded-md bg-white/5" />;
  }
  return (
    <a href={objectUrl} target="_blank" rel="noreferrer">
      <img src={objectUrl} className="h-20 w-20 rounded-md object-cover" alt="attachment" />
    </a>
  );
}

const SORT_OPTIONS = [
  { value: "updated_at", label: "Updated" },
  { value: "created_at", label: "Created" },
  { value: "id", label: "ID" },
  { value: "subject", label: "Subject" },
  { value: "username", label: "User" },
  { value: "status", label: "Status" },
];

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

const STATUS_VARIANT: Record<string, BadgeVariant> = {
  open: "default",
  in_progress: "warning",
  closed: "outline",
};

const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  closed: "Closed",
};

const STATUS_OPTIONS = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "closed", label: "Closed" },
];

export default function SupportPage() {
  const isMobile = useIsMobile();
  const [items, setItems] = useState<SupportTicketSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const perPage = 20;
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("updated_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [loading, setLoading] = useState(false);

  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SupportTicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reply, setReply] = useState("");
  const [pendingImages, setPendingImages] = useState<File[]>([]);
  const [sending, setSending] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const pendingPreviewUrls = useMemo(
    () => pendingImages.map((f) => URL.createObjectURL(f)),
    [pendingImages],
  );
  useEffect(() => {
    return () => pendingPreviewUrls.forEach((u) => URL.revokeObjectURL(u));
  }, [pendingPreviewUrls]);

  const [userDrawerId, setUserDrawerId] = useState<number | null>(null);
  const [userOpen, setUserOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
        status,
        search,
        sort,
        order,
      });
      const data = await api.get<PaginatedResponse<SupportTicketSummary>>(
        `/support/tickets?${params}`,
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      toast.error((e as Error)?.message || "Failed to load tickets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, status, sort, order]);

  const loadDetail = async (id: number) => {
    setDetailLoading(true);
    setDetail(null);
    try {
      const d = await api.get<SupportTicketDetail>(`/support/tickets/${id}`);
      setDetail(d);
    } catch (e) {
      toast.error((e as Error)?.message || "Failed to load ticket");
    } finally {
      setDetailLoading(false);
    }
  };

  const openTicket = (id: number) => {
    setOpenId(id);
    setReply("");
    setPendingImages([]);
    loadDetail(id);
  };

  const closeDrawer = () => {
    setOpenId(null);
    setDetail(null);
    setReply("");
    setPendingImages([]);
  };

  const onFilesSelected = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const incoming = Array.from(files);
    const combined = [...pendingImages, ...incoming];
    if (combined.length > MAX_IMAGES) {
      toast.error(`Up to ${MAX_IMAGES} images per message`);
      return;
    }
    for (const f of incoming) {
      if (f.size > MAX_IMAGE_BYTES) {
        toast.error(`File too large (max 5MB): ${f.name}`);
        return;
      }
    }
    setPendingImages(combined);
  };

  const removePendingImage = (idx: number) => {
    setPendingImages((prev) => prev.filter((_, i) => i !== idx));
  };

  const sendReply = async () => {
    if (!openId) return;
    const text = reply.trim();
    if (!text && pendingImages.length === 0) return;
    setSending(true);
    try {
      const form = new FormData();
      form.append("text", text);
      for (const img of pendingImages) form.append("images", img);
      await api.postForm(`/support/tickets/${openId}/reply`, form);
      setReply("");
      setPendingImages([]);
      await loadDetail(openId);
      await load();
    } catch (e) {
      toast.error((e as Error)?.message || "Failed to send reply");
    } finally {
      setSending(false);
    }
  };

  const deleteMessage = async (messageId: number) => {
    if (!openId) return;
    try {
      await api.delete(`/support/tickets/${openId}/messages/${messageId}`);
      toast.success("Message deleted");
      await loadDetail(openId);
      await load();
    } catch (e) {
      toast.error((e as Error)?.message || "Failed to delete message");
    }
  };

  const changeStatus = async (newStatus: string) => {
    if (!openId) return;
    try {
      await api.patch(`/support/tickets/${openId}`, { status: newStatus });
      await loadDetail(openId);
      await load();
    } catch (e) {
      toast.error((e as Error)?.message || "Failed to update status");
    }
  };

  const onSortChange = makeSortToggle({ sort, order, setSort, setOrder, setPage });

  const columns: ColumnDef<SupportTicketSummary, unknown>[] = [
    { id: "id", header: "ID", meta: { sortKey: "id" }, cell: ({ row }) => row.original.id },
    {
      id: "subject",
      header: "Subject",
      meta: { sortKey: "subject" },
      cell: ({ row }) => <span className="line-clamp-1">{row.original.subject}</span>,
    },
    {
      id: "username",
      header: "User",
      meta: { sortKey: "username" },
      cell: ({ row }) =>
        row.original.username
          ? `@${row.original.username}`
          : row.original.tg_id
            ? String(row.original.tg_id)
            : "—",
    },
    {
      id: "status",
      header: "Status",
      meta: { sortKey: "status" },
      cell: ({ row }) => (
        <Badge variant={STATUS_VARIANT[row.original.status] || "outline"}>
          {STATUS_LABEL[row.original.status] || row.original.status}
        </Badge>
      ),
    },
    {
      id: "created_at",
      header: "Created",
      meta: { sortKey: "created_at" },
      cell: ({ row }) => row.original.created_at,
    },
    {
      id: "updated_at",
      header: "Updated",
      meta: { sortKey: "updated_at" },
      cell: ({ row }) => row.original.updated_at,
    },
  ];

  const renderMobileCard = (t: SupportTicketSummary) => {
    const who = t.username ? `@${t.username}` : t.tg_id ? String(t.tg_id) : "—";
    return (
      <Card key={t.id} className="mb-2 cursor-pointer" onClick={() => openTicket(t.id)}>
        <CardContent className="flex items-start justify-between gap-2 p-3">
          <div className="min-w-0 flex-1">
            <div className="mb-1 line-clamp-2 font-semibold text-foreground/85">
              #{t.id} · {t.subject}
            </div>
            <div className="text-xs text-muted-foreground">
              {who} · {t.updated_at}
            </div>
          </div>
          <Badge variant={STATUS_VARIANT[t.status] || "outline"} className="flex-shrink-0">
            {STATUS_LABEL[t.status] || t.status}
          </Badge>
        </CardContent>
      </Card>
    );
  };

  return (
    <div>
      <h1 className="mb-5 text-lg font-semibold text-foreground md:text-xl">Support</h1>

      <div className="mb-4 flex flex-wrap gap-2">
        <Select
          value={status}
          onValueChange={(v: string) => {
            setPage(1);
            setStatus(v);
          }}
        >
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          placeholder="Search by subject"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              setPage(1);
              load();
            }
          }}
          className="w-full md:w-[280px]"
        />
        <Button
          variant="outline"
          onClick={() => {
            setPage(1);
            load();
          }}
          className="w-full md:w-auto"
        >
          Refresh
        </Button>
      </div>

      {isMobile ? (
        <>
          <MobileSortControl
            options={SORT_OPTIONS}
            sort={sort}
            order={order}
            onChange={(s, o) => {
              setSort(s);
              setOrder(o);
              setPage(1);
            }}
          />
          {loading ? (
            <div className="py-10 text-center text-muted-foreground">Loading…</div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">No tickets</div>
          ) : (
            items.map(renderMobileCard)
          )}
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      ) : (
        <>
          <DataTable
            columns={columns}
            data={items}
            loading={loading}
            rowKey={(r) => r.id}
            sort={sort}
            order={order}
            onSortChange={onSortChange}
            empty="No tickets"
            onRowClick={(r) => openTicket(r.id)}
          />
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      )}

      <Sheet open={openId !== null} onOpenChange={(o: boolean) => !o && closeDrawer()}>
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-[560px]">
          <SheetHeader className="flex-row items-center justify-between gap-2 space-y-0">
            <SheetTitle className="truncate">
              {detail ? `#${detail.id} — ${detail.subject}` : "Loading…"}
            </SheetTitle>
            {detail && (
              <Select value={detail.status} onValueChange={(v: string) => changeStatus(v)}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="open">Open</SelectItem>
                  <SelectItem value="in_progress">In progress</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            )}
          </SheetHeader>

          <div className="py-4">
            {detailLoading && <Spinner className="h-6 w-6" />}
            {detail && (
              <>
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="text-muted-foreground">
                    {detail.username ? `@${detail.username}` : detail.tg_id} · {detail.created_at}
                  </span>
                  {detail.user_id != null && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setUserDrawerId(detail.user_id);
                        setUserOpen(true);
                      }}
                    >
                      <User className="h-4 w-4" />
                      Карточка пользователя
                    </Button>
                  )}
                </div>

                <div className="mb-4 flex flex-col gap-2">
                  {detail.messages.map((m) => (
                    <div
                      key={m.id}
                      className={cn(
                        "rounded-lg border border-white/5 px-3 py-2",
                        m.sender === "admin" ? "bg-primary/15" : "bg-white/5",
                      )}
                    >
                      <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                        <span>
                          {m.sender === "admin" ? "Admin" : "User"} · {m.created_at}
                        </span>
                        {m.sender === "admin" && (
                          <ConfirmButton
                            title="Delete this reply?"
                            description="This cannot be undone."
                            destructive
                            confirmText="Delete"
                            onConfirm={() => deleteMessage(m.id)}
                          >
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              aria-label="Delete reply"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </ConfirmButton>
                        )}
                      </div>
                      {m.text && <div className="whitespace-pre-wrap">{m.text}</div>}
                      {m.attachments && m.attachments.length > 0 && (
                        <div className={cn("flex flex-wrap gap-2", m.text && "mt-2")}>
                          {m.attachments.map((a) => (
                            <AttachmentThumb key={a.id} attachment={a} />
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <Textarea
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                  rows={4}
                  maxLength={4000}
                  placeholder="Reply to user…"
                />
                {pendingImages.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {pendingImages.map((f, idx) => (
                      <div key={idx} className="relative">
                        <img
                          src={pendingPreviewUrls[idx]}
                          className="h-16 w-16 rounded-md object-cover"
                          alt={f.name}
                        />
                        <Button
                          variant="destructive"
                          size="icon"
                          className="absolute -right-2 -top-2 h-5 w-5 rounded-full"
                          onClick={() => removePendingImage(idx)}
                        >
                          ×
                        </Button>
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
                <div className="mt-3 flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={pendingImages.length >= MAX_IMAGES}
                  >
                    <Paperclip className="h-4 w-4" />
                    Attach
                  </Button>
                  <Button
                    className="flex-1 md:flex-none"
                    disabled={sending || (!reply.trim() && pendingImages.length === 0)}
                    onClick={sendReply}
                  >
                    Send reply
                  </Button>
                </div>
              </>
            )}
          </div>
        </SheetContent>
      </Sheet>

      <UserDrawer userId={userDrawerId} open={userOpen} onClose={() => setUserOpen(false)} />
    </div>
  );
}
