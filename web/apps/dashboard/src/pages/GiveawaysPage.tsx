import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { Plus, RefreshCw, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { Label } from "@xray/ui/components/label";
import { Badge } from "@xray/ui/components/badge";
import { Checkbox } from "@xray/ui/components/checkbox";
import { cn } from "@xray/ui/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@xray/ui/components/sheet";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@xray/ui/components/table";
import { api } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";
import DataTable from "../components/DataTable";
import TablePagination from "../components/TablePagination";

type GiveawayStatus = "draft" | "active" | "closed" | "drawn";

interface GiveawayConfig {
  distribution: string[];
  entry_condition: "click_only" | "channel_sub";
  ticket_sources: string[];
  chance_mode: "static" | "dynamic";
  winner_selection: "random" | "most_tickets";
}

interface GiveawayItem {
  id: number;
  title: string;
  channel_text: string;
  status: GiveawayStatus;
  config: GiveawayConfig;
  winner_count: number;
  starts_at: string | null;
  ends_at: string | null;
  drawn_at: string | null;
  created_at: string;
  participants: number;
  tickets: number;
}

interface ParticipantItem {
  tg_id: number;
  username: string | null;
  joined_at: string;
  ticket_count: number;
}

interface WinnerItem {
  rank: number;
  tg_id: number;
  username: string | null;
  tickets: number;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

const STATUS_VARIANT: Record<GiveawayStatus, BadgeVariant> = {
  draft: "outline",
  active: "success",
  closed: "warning",
  drawn: "default",
};

const PER_PAGE = 20;

function statusBadge(status: GiveawayStatus) {
  return <Badge variant={STATUS_VARIANT[status]}>{status}</Badge>;
}

function formatShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface GiveawayForm {
  title: string;
  channel_text: string;
  winner_count: number;
  entry_condition: GiveawayConfig["entry_condition"];
  chance_mode: GiveawayConfig["chance_mode"];
  winner_selection: GiveawayConfig["winner_selection"];
  distribution_bot: boolean;
  distribution_channel: boolean;
  ticket_ref: boolean;
  ticket_purchase: boolean;
  starts_at: string;
  ends_at: string;
}

const emptyForm: GiveawayForm = {
  title: "",
  channel_text: "",
  winner_count: 1,
  entry_condition: "click_only",
  chance_mode: "static",
  winner_selection: "random",
  distribution_bot: true,
  distribution_channel: false,
  ticket_ref: false,
  ticket_purchase: false,
  starts_at: "",
  ends_at: "",
};

function RadioRow<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="flex flex-col gap-2">
      {options.map((o) => (
        <label key={o.value} className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="radio"
            checked={value === o.value}
            onChange={() => onChange(o.value)}
            className="accent-primary"
          />
          {o.label}
        </label>
      ))}
    </div>
  );
}

export default function GiveawaysPage() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<GiveawayItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<GiveawayItem | null>(null);
  const [detail, setDetail] = useState<GiveawayItem | null>(null);
  const [participants, setParticipants] = useState<ParticipantItem[]>([]);
  const [winners, setWinners] = useState<WinnerItem[]>([]);
  const [winnersOpen, setWinnersOpen] = useState(false);
  const [form, setForm] = useState<GiveawayForm>(emptyForm);

  const patchForm = (patch: Partial<GiveawayForm>) => setForm((f) => ({ ...f, ...patch }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: String(PER_PAGE) });
      if (statusFilter) params.set("status", statusFilter);
      const data = await api.get<{ items: GiveawayItem[]; total: number }>(`/giveaways?${params}`);
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      toast.error((e as Error).message || "Failed to load giveaways");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setDrawerOpen(true);
  };

  const openEdit = (item: GiveawayItem) => {
    setEditing(item);
    setForm({
      title: item.title,
      channel_text: item.channel_text,
      winner_count: item.winner_count,
      entry_condition: item.config.entry_condition,
      chance_mode: item.config.chance_mode,
      winner_selection: item.config.winner_selection,
      distribution_bot: item.config.distribution.includes("bot"),
      distribution_channel: item.config.distribution.includes("channel"),
      ticket_ref: item.config.ticket_sources.includes("invitee_ref_activation"),
      ticket_purchase: item.config.ticket_sources.includes("invitee_purchase"),
      starts_at: item.starts_at ? item.starts_at.slice(0, 16) : "",
      ends_at: item.ends_at ? item.ends_at.slice(0, 16) : "",
    });
    setDrawerOpen(true);
  };

  const buildConfig = (): GiveawayConfig => {
    const distribution: string[] = [];
    if (form.distribution_bot) distribution.push("bot");
    if (form.distribution_channel) distribution.push("channel");
    const ticketSources: string[] = [];
    if (form.chance_mode === "dynamic") {
      if (form.ticket_ref) ticketSources.push("invitee_ref_activation");
      if (form.ticket_purchase) ticketSources.push("invitee_purchase");
    }
    return {
      distribution: distribution.length ? distribution : ["bot"],
      entry_condition: form.entry_condition,
      ticket_sources: ticketSources,
      chance_mode: form.chance_mode,
      winner_selection: form.winner_selection,
    };
  };

  const onSave = async () => {
    if (!form.title.trim()) {
      toast.error("Title is required");
      return;
    }
    const payload = {
      title: form.title,
      channel_text: form.channel_text || "",
      winner_count: form.winner_count,
      starts_at: form.starts_at ? `${form.starts_at}:00` : null,
      ends_at: form.ends_at ? `${form.ends_at}:00` : null,
      config: buildConfig(),
    };
    try {
      if (editing) {
        await api.patch(`/giveaways/${editing.id}`, payload);
        toast.success("Giveaway updated");
      } else {
        await api.post("/giveaways", payload);
        toast.success("Giveaway created");
      }
      setDrawerOpen(false);
      load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to save");
    }
  };

  const runAction = async (id: number, action: string, successMsg: string) => {
    try {
      await api.post(`/giveaways/${id}/${action}`);
      toast.success(successMsg);
      load();
      if (detail?.id === id) {
        const updated = await api.get<GiveawayItem>(`/giveaways/${id}`);
        setDetail(updated);
      }
    } catch (e) {
      toast.error((e as Error).message || "Action failed");
    }
  };

  const openDetail = async (item: GiveawayItem) => {
    setDetail(item);
    try {
      const [pData, wData] = await Promise.all([
        api.get<{ items: ParticipantItem[] }>(`/giveaways/${item.id}/participants?per_page=100`),
        api.get<{ winners: WinnerItem[] }>(`/giveaways/${item.id}/winners`),
      ]);
      setParticipants(pData.items);
      setWinners(wData.winners);
    } catch (e) {
      toast.error((e as Error).message || "Failed to load details");
    }
  };

  const onDraw = async () => {
    if (!detail) return;
    try {
      const data = await api.post<{ winners: WinnerItem[] }>(`/giveaways/${detail.id}/draw`);
      setWinners(data.winners);
      setWinnersOpen(true);
      load();
      const updated = await api.get<GiveawayItem>(`/giveaways/${detail.id}`);
      setDetail(updated);
    } catch (e) {
      toast.error((e as Error).message || "Draw failed");
    }
  };

  const copyWinners = () => {
    const text = winners
      .map(
        (w) =>
          `#${w.rank}: ${w.username ? `@${w.username}` : "—"} (${w.tg_id}) — ${w.tickets} tickets`,
      )
      .join("\n");
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  const columns: ColumnDef<GiveawayItem, unknown>[] = [
    { id: "id", header: "ID", cell: ({ row }) => row.original.id },
    { id: "title", header: "Title", cell: ({ row }) => row.original.title },
    { id: "status", header: "Status", cell: ({ row }) => statusBadge(row.original.status) },
    { id: "participants", header: "Participants", cell: ({ row }) => row.original.participants },
    { id: "tickets", header: "Tickets", cell: ({ row }) => row.original.tickets },
    { id: "winner_count", header: "Winners", cell: ({ row }) => row.original.winner_count },
    {
      id: "actions",
      header: "Actions",
      cell: ({ row }) => (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => openDetail(row.original)}>
            Open
          </Button>
          {row.original.status === "draft" && (
            <Button size="sm" variant="outline" onClick={() => openEdit(row.original)}>
              Edit
            </Button>
          )}
        </div>
      ),
    },
  ];

  const renderMobileCard = (item: GiveawayItem) => (
    <Card key={item.id} className="mb-2 cursor-pointer" onClick={() => openDetail(item)}>
      <CardContent className="flex items-start justify-between gap-2 p-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 break-words font-semibold text-foreground/85">
            {item.title || `Giveaway #${item.id}`}
          </div>
          <div className="mb-1.5">{statusBadge(item.status)}</div>
          <div className="text-xs text-muted-foreground">
            #{item.id} · {item.participants} participants · {item.tickets} tickets
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground/70">
            Winners: {item.winner_count}
            {item.ends_at ? ` · Ends ${formatShort(item.ends_at)}` : ""}
          </div>
        </div>
        {item.status === "draft" && (
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              openEdit(item);
            }}
          >
            Edit
          </Button>
        )}
      </CardContent>
    </Card>
  );

  return (
    <div>
      <h1 className="mb-3 flex items-center gap-2 text-lg font-semibold text-foreground md:mb-5 md:text-xl">
        <Trophy className="h-5 w-5" /> Giveaways
      </h1>

      <div className="mb-4 flex flex-wrap gap-2">
        <Button onClick={openCreate} className="w-full md:w-auto">
          <Plus className="h-4 w-4" />
          New giveaway
        </Button>
        <Button variant="outline" onClick={load} disabled={loading} className="w-full md:w-auto">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
        <Select
          value={statusFilter || "all"}
          onValueChange={(v: string) => {
            setStatusFilter(v === "all" ? "" : v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="draft">draft</SelectItem>
            <SelectItem value="active">active</SelectItem>
            <SelectItem value="closed">closed</SelectItem>
            <SelectItem value="drawn">drawn</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isMobile ? (
        <>
          {loading ? (
            <div className="py-10 text-center text-muted-foreground">Loading...</div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">No giveaways</div>
          ) : (
            items.map(renderMobileCard)
          )}
          <TablePagination page={page} perPage={PER_PAGE} total={total} onPageChange={setPage} />
        </>
      ) : (
        <>
          <DataTable
            columns={columns}
            data={items}
            loading={loading}
            rowKey={(r) => r.id}
            empty="No giveaways"
          />
          <TablePagination page={page} perPage={PER_PAGE} total={total} onPageChange={setPage} />
        </>
      )}

      <Sheet open={drawerOpen} onOpenChange={(o: boolean) => setDrawerOpen(o)}>
        <SheetContent side="right" className="flex w-full flex-col overflow-y-auto sm:max-w-[520px]">
          <SheetHeader>
            <SheetTitle>{editing ? `Edit #${editing.id}` : "New giveaway"}</SheetTitle>
          </SheetHeader>

          <div className="flex-1 space-y-4 py-4">
            <div className="space-y-1.5">
              <Label>Title *</Label>
              <Input value={form.title} onChange={(e) => patchForm({ title: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Post / broadcast text (HTML)</Label>
              <Textarea
                rows={5}
                value={form.channel_text}
                onChange={(e) => patchForm({ channel_text: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Number of winners *</Label>
              <Input
                type="number"
                min={1}
                max={100}
                value={form.winner_count}
                onChange={(e) => patchForm({ winner_count: Number(e.target.value) || 1 })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Starts at (optional)</Label>
              <Input
                type="datetime-local"
                value={form.starts_at}
                onChange={(e) => patchForm({ starts_at: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Ends at (optional)</Label>
              <Input
                type="datetime-local"
                value={form.ends_at}
                onChange={(e) => patchForm({ ends_at: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Distribution</Label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={form.distribution_bot}
                  onCheckedChange={(c: boolean | "indeterminate") =>
                    patchForm({ distribution_bot: c === true })
                  }
                />
                Bot broadcast
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={form.distribution_channel}
                  onCheckedChange={(c: boolean | "indeterminate") =>
                    patchForm({ distribution_channel: c === true })
                  }
                />
                Channel post
              </label>
            </div>
            <div className="space-y-1.5">
              <Label>Entry requirement</Label>
              <RadioRow
                value={form.entry_condition}
                onChange={(v) => patchForm({ entry_condition: v })}
                options={[
                  { value: "click_only", label: "Click participate" },
                  { value: "channel_sub", label: "Channel subscription" },
                ]}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Ticket mode</Label>
              <RadioRow
                value={form.chance_mode}
                onChange={(v) => patchForm({ chance_mode: v })}
                options={[
                  { value: "static", label: "Static (1 ticket per participant)" },
                  { value: "dynamic", label: "Dynamic (extra tickets for invitees)" },
                ]}
              />
            </div>
            {form.chance_mode === "dynamic" && (
              <div className="space-y-2">
                <Label>Extra ticket sources</Label>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={form.ticket_ref}
                    onCheckedChange={(c: boolean | "indeterminate") =>
                      patchForm({ ticket_ref: c === true })
                    }
                  />
                  Invitee activated referral code
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={form.ticket_purchase}
                    onCheckedChange={(c: boolean | "indeterminate") =>
                      patchForm({ ticket_purchase: c === true })
                    }
                  />
                  Invitee purchased subscription
                </label>
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Winner selection</Label>
              <RadioRow
                value={form.winner_selection}
                onChange={(v) => patchForm({ winner_selection: v })}
                options={[
                  { value: "random", label: "Random (weighted by tickets)" },
                  { value: "most_tickets", label: "Most tickets" },
                ]}
              />
            </div>
          </div>

          <SheetFooter>
            <Button onClick={onSave} className="w-full">
              Save
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={!!detail} onOpenChange={(o: boolean) => !o && setDetail(null)}>
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-[640px]">
          <SheetHeader>
            <SheetTitle>{detail ? `${detail.title} (#${detail.id})` : "Giveaway"}</SheetTitle>
          </SheetHeader>
          {detail && (
            <div className="space-y-4 py-4">
              <div>
                {statusBadge(detail.status)}{" "}
                <span className="text-muted-foreground">
                  {detail.participants} participants · {detail.tickets} tickets
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {detail.status === "draft" && (
                  <Button
                    className={cn(isMobile && "w-full")}
                    onClick={() => runAction(detail.id, "activate", "Activated")}
                  >
                    Activate
                  </Button>
                )}
                {detail.status === "active" && (
                  <>
                    <Button
                      variant="outline"
                      className={cn(isMobile && "w-full")}
                      onClick={() => runAction(detail.id, "broadcast", "Broadcast queued")}
                    >
                      Bot broadcast
                    </Button>
                    <Button
                      variant="outline"
                      className={cn(isMobile && "w-full")}
                      onClick={() => runAction(detail.id, "channel-post", "Posted to channel")}
                    >
                      Channel post
                    </Button>
                    <Button
                      variant="outline"
                      className={cn(isMobile && "w-full")}
                      onClick={() => runAction(detail.id, "close", "Closed")}
                    >
                      Close
                    </Button>
                  </>
                )}
                {(detail.status === "active" || detail.status === "closed") && (
                  <Button
                    variant="destructive"
                    className={cn(isMobile && "w-full")}
                    onClick={onDraw}
                  >
                    Draw winners
                  </Button>
                )}
                {detail.status === "drawn" && winners.length > 0 && (
                  <Button
                    variant="outline"
                    className={cn(isMobile && "w-full")}
                    onClick={() => setWinnersOpen(true)}
                  >
                    Show winners
                  </Button>
                )}
              </div>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Participants</CardTitle>
                </CardHeader>
                <CardContent>
                  {participants.length === 0 ? (
                    <span className="text-muted-foreground">No participants yet</span>
                  ) : isMobile ? (
                    participants.map((p) => (
                      <div key={p.tg_id} className="border-b border-white/5 py-2">
                        <div className="font-medium text-foreground/85">
                          {p.username ? `@${p.username}` : p.tg_id}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {p.tg_id} · {p.ticket_count} tickets
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="overflow-auto rounded-lg border border-border">
                      <Table>
                        <TableHeader>
                          <TableRow className="hover:bg-transparent">
                            <TableHead>User</TableHead>
                            <TableHead>tg_id</TableHead>
                            <TableHead>Tickets</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {participants.map((p) => (
                            <TableRow key={p.tg_id}>
                              <TableCell>{p.username ? `@${p.username}` : String(p.tg_id)}</TableCell>
                              <TableCell>{p.tg_id}</TableCell>
                              <TableCell>{p.ticket_count}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={winnersOpen} onOpenChange={setWinnersOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Winners</DialogTitle>
          </DialogHeader>
          <pre className="m-0 whitespace-pre-wrap text-sm">
            {winners
              .map(
                (w) =>
                  `#${w.rank}: ${w.username ? `@${w.username}` : "—"} (${w.tg_id}) — ${w.tickets} tickets`,
              )
              .join("\n") || "No winners yet"}
          </pre>
          <DialogFooter>
            <Button variant="outline" onClick={copyWinners}>
              Copy list
            </Button>
            <Button onClick={() => setWinnersOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
