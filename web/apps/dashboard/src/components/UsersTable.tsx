import { useState, useEffect, useCallback, useRef } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { Search, Ban, Check, Trash2, Eye, Crown, Copy } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Badge } from "@xray/ui/components/badge";
import { Card, CardContent } from "@xray/ui/components/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { toast } from "sonner";
import { api } from "../api/client";
import type { UserItem, PaginatedResponse } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import useDebounce from "../hooks/useDebounce";
import MobileSortControl, { type SortOrder } from "./MobileSortControl";
import UserDrawer from "./UserDrawer";
import DataTable from "./DataTable";
import TablePagination from "./TablePagination";
import ConfirmButton from "./ConfirmButton";
import { makeSortToggle } from "../utils/tableChange";

const SORT_OPTIONS = [
  { value: "id", label: "ID" },
  { value: "tg_id", label: "TG ID" },
  { value: "rw_id", label: "RW ID" },
  { value: "username", label: "Username" },
  { value: "api_provider", label: "Provider" },
  { value: "is_paid", label: "Paid status" },
  { value: "subscriptions_count", label: "Subscriptions" },
];

function StatusBadges({ user }: { user: UserItem }) {
  return (
    <div className="flex flex-wrap gap-1">
      {user.vip && <Badge variant="warning">VIP</Badge>}
      {user.is_banned && <Badge variant="destructive">Banned</Badge>}
      {user.is_paid ? <Badge variant="success">Paid</Badge> : <Badge variant="secondary">Free</Badge>}
    </div>
  );
}

export default function UsersTable() {
  const [data, setData] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("id");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [loading, setLoading] = useState(false);
  const [drawerUserId, setDrawerUserId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isMobile = useIsMobile();
  const debouncedSearch = useDebounce(search, 400);
  const abortRef = useRef<AbortController | null>(null);

  const fetchUsers = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    try {
      const res = await api.get<PaginatedResponse<UserItem>>(
        `/users?page=${page}&per_page=${perPage}&search=${encodeURIComponent(debouncedSearch)}&filter=${filter}&sort=${sort}&order=${order}`,
        controller.signal,
      );
      setData(res.items);
      setTotal(res.total);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      throw e;
    } finally {
      setLoading(false);
    }
  }, [page, perPage, debouncedSearch, filter, sort, order]);

  useEffect(() => {
    fetchUsers();
    return () => abortRef.current?.abort();
  }, [fetchUsers]);

  const handleBan = async (user_id: number) => {
    try {
      await api.post(`/users/${user_id}/ban`);
      fetchUsers();
    } catch {
      toast.error("Failed to ban user");
    }
  };

  const handleUnban = async (user_id: number) => {
    try {
      await api.post(`/users/${user_id}/unban`);
      fetchUsers();
    } catch {
      toast.error("Failed to unban user");
    }
  };

  const handleDelete = async (user_id: number) => {
    try {
      await api.delete(`/users/${user_id}`);
      fetchUsers();
    } catch {
      toast.error("Failed to delete user");
    }
  };

  const handleToggleVip = async (user_id: number, currentVip: boolean) => {
    try {
      await api.post(`/users/${user_id}/${currentVip ? "unvip" : "vip"}`);
      fetchUsers();
    } catch {
      toast.error("Failed to toggle VIP status");
    }
  };

  const openDrawer = (user_id: number) => {
    setDrawerUserId(user_id);
    setDrawerOpen(true);
  };

  const onSortChange = makeSortToggle({ sort, order, setSort, setOrder, setPage });

  const columns: ColumnDef<UserItem, unknown>[] = [
    { id: "id", header: "ID", accessorKey: "id", meta: { sortKey: "id", width: 60 } },
    {
      id: "tg_id",
      header: "TG ID",
      meta: { sortKey: "tg_id", width: 130 },
      cell: ({ row }) => row.original.tg_id ?? "—",
    },
    {
      id: "rw_id",
      header: "rw_id",
      meta: { sortKey: "rw_id", width: 90 },
      cell: ({ row }) => row.original.rw_id ?? "—",
    },
    {
      id: "subscriptions_count",
      header: "Subs",
      accessorKey: "subscriptions_count",
      meta: { sortKey: "subscriptions_count", width: 70 },
    },
    { id: "username", header: "Username", accessorKey: "username", meta: { sortKey: "username", width: 140 } },
    {
      id: "email",
      header: "Email",
      meta: { width: 180 },
      cell: ({ row }) => row.original.email || "—",
    },
    {
      id: "vless_uuid",
      header: "vless_uuid",
      meta: { width: 150 },
      cell: ({ row }) => {
        const v = row.original.vless_uuid;
        return v ? (
          <span className="flex items-center gap-1">
            <span className="max-w-[120px] truncate font-mono text-[11px]" title={v}>
              {v}
            </span>
            <button
              type="button"
              onClick={() => navigator.clipboard?.writeText(v).then(() => toast.success("Copied"))}
              className="text-muted-foreground hover:text-foreground"
            >
              <Copy className="h-3 w-3" />
            </button>
          </span>
        ) : (
          "—"
        );
      },
    },
    {
      id: "api_provider",
      header: "Provider",
      accessorKey: "api_provider",
      meta: { sortKey: "api_provider", width: 90 },
    },
    {
      id: "is_paid",
      header: "Status",
      meta: { sortKey: "is_paid", width: 120 },
      cell: ({ row }) => <StatusBadges user={row.original} />,
    },
    {
      id: "actions",
      header: "Actions",
      meta: { width: 200 },
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div className="flex gap-1">
            <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => openDrawer(r.id)}>
              <Eye className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="outline"
              className="h-8 w-8"
              onClick={() => handleToggleVip(r.id, r.vip)}
              title={r.vip ? "Remove VIP" : "Set VIP"}
              style={r.vip ? { color: "#faad14", borderColor: "#faad14" } : undefined}
            >
              <Crown className="h-4 w-4" />
            </Button>
            {r.is_banned ? (
              <Button
                size="icon"
                variant="outline"
                className="h-8 w-8"
                onClick={() => handleUnban(r.id)}
                title="Unban"
              >
                <Check className="h-4 w-4" />
              </Button>
            ) : (
              <ConfirmButton
                title="Ban this user?"
                confirmText="Ban"
                destructive
                onConfirm={() => handleBan(r.id)}
              >
                <Button size="icon" variant="destructive" className="h-8 w-8" title="Ban">
                  <Ban className="h-4 w-4" />
                </Button>
              </ConfirmButton>
            )}
            <ConfirmButton
              title="Delete this user and all transactions?"
              confirmText="Delete"
              destructive
              onConfirm={() => handleDelete(r.id)}
            >
              <Button size="icon" variant="destructive" className="h-8 w-8">
                <Trash2 className="h-4 w-4" />
              </Button>
            </ConfirmButton>
          </div>
        );
      },
    },
  ];

  const renderMobileCard = (user: UserItem) => (
    <Card key={user.id} className="mb-2">
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="mb-1 font-semibold text-foreground">{user.username || "—"}</div>
            <div className="mb-1 text-xs text-muted-foreground">
              TG: {user.tg_id ?? "—"}
              {user.rw_id != null ? ` · RW: ${user.rw_id}` : ""} · {user.subscriptions_count} subs · {user.api_provider}
            </div>
            {user.email && (
              <div className="mb-1.5 break-all text-[11px] text-muted-foreground">{user.email}</div>
            )}
            <StatusBadges user={user} />
          </div>
          <div className="flex gap-1">
            <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => openDrawer(user.id)}>
              <Eye className="h-4 w-4" />
            </Button>
            {user.is_banned ? (
              <Button
                size="icon"
                variant="outline"
                className="h-8 w-8"
                onClick={() => handleUnban(user.id)}
              >
                <Check className="h-4 w-4" />
              </Button>
            ) : (
              <ConfirmButton
                title="Ban this user?"
                confirmText="Ban"
                destructive
                onConfirm={() => handleBan(user.id)}
              >
                <Button size="icon" variant="destructive" className="h-8 w-8">
                  <Ban className="h-4 w-4" />
                </Button>
              </ConfirmButton>
            )}
            <ConfirmButton
              title="Delete user?"
              confirmText="Delete"
              destructive
              onConfirm={() => handleDelete(user.id)}
            >
              <Button size="icon" variant="destructive" className="h-8 w-8">
                <Trash2 className="h-4 w-4" />
              </Button>
            </ConfirmButton>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <>
      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative min-w-[220px] flex-1 md:max-w-[320px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by username, email, UUID, rw_id or TG ID"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Select
          value={filter}
          onValueChange={(v: string) => {
            setFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
            <SelectItem value="free">Free</SelectItem>
            <SelectItem value="vip">VIP</SelectItem>
            <SelectItem value="banned">Banned</SelectItem>
            <SelectItem value="multiple_subscriptions">2+ subscriptions</SelectItem>
          </SelectContent>
        </Select>
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
            <div className="py-10 text-center text-muted-foreground">Loading...</div>
          ) : (
            data.map(renderMobileCard)
          )}
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      ) : (
        <>
          <DataTable
            columns={columns}
            data={data}
            loading={loading}
            rowKey={(r) => r.id}
            sort={sort}
            order={order}
            onSortChange={onSortChange}
            minWidth={1050}
          />
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      )}

      <UserDrawer
        userId={drawerUserId}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onChanged={fetchUsers}
      />
    </>
  );
}
