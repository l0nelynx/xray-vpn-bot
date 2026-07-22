import { useState, useEffect, useCallback, useRef } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { Trash2, Search } from "lucide-react";
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
import type { TransactionItem, PaginatedResponse } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import useDebounce from "../hooks/useDebounce";
import MobileSortControl, { type SortOrder } from "./MobileSortControl";
import { statusBadgeVariant } from "../utils/constants";
import { makeSortToggle } from "../utils/tableChange";
import DataTable from "./DataTable";
import TablePagination from "./TablePagination";
import ConfirmButton from "./ConfirmButton";

const SORT_OPTIONS = [
  { value: "created_at", label: "Date" },
  { value: "amount", label: "Amount" },
  { value: "username", label: "Username" },
  { value: "user_tg_id", label: "TG ID" },
  { value: "payment_method", label: "Method" },
  { value: "order_status", label: "Status" },
  { value: "days_ordered", label: "Days" },
  { value: "expire_date", label: "Expires" },
];

// "" means "all" — the Select primitive disallows empty string values.
const ALL = "__all__";

export default function TransactionsTable() {
  const [data, setData] = useState<TransactionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [status, setStatus] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [dateRange, setDateRange] = useState<[string, string]>(["", ""]);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const isMobile = useIsMobile();
  const debouncedSearch = useDebounce(search, 400);
  const abortRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    try {
      let url = `/transactions?page=${page}&per_page=${perPage}&sort=${sort}&order=${order}`;
      if (status) url += `&status=${status}`;
      if (paymentMethod) url += `&payment_method=${encodeURIComponent(paymentMethod)}`;
      if (dateRange[0]) url += `&date_from=${dateRange[0]}`;
      if (dateRange[1]) url += `&date_to=${dateRange[1]}`;
      if (debouncedSearch) url += `&search=${encodeURIComponent(debouncedSearch)}`;

      const res = await api.get<PaginatedResponse<TransactionItem>>(url, controller.signal);
      setData(res.items);
      setTotal(res.total);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      throw e;
    } finally {
      setLoading(false);
    }
  }, [page, perPage, status, paymentMethod, dateRange, debouncedSearch, sort, order]);

  useEffect(() => {
    fetchData();
    return () => abortRef.current?.abort();
  }, [fetchData]);

  const cleanupStale = async () => {
    setCleaning(true);
    try {
      const res = await api.post<{ deleted: number; hours: number }>(
        "/transactions/cleanup-stale?hours=168",
      );
      toast.success(`Deleted ${res.deleted} stale created transactions (older than 7 days)`);
      setPage(1);
      await fetchData();
    } catch {
      toast.error("Failed to clean up transactions");
    } finally {
      setCleaning(false);
    }
  };

  const onSortChange = makeSortToggle({ sort, order, setSort, setOrder, setPage });

  const setFrom = (v: string) => {
    setDateRange(([, to]) => [v ? v : "", to]);
    setPage(1);
  };
  const setTo = (v: string) => {
    setDateRange(([from]) => [from, v ? `${v}T23:59:59` : ""]);
    setPage(1);
  };

  const columns: ColumnDef<TransactionItem, unknown>[] = [
    {
      id: "transaction_id",
      header: "ID",
      meta: { sortKey: "transaction_id", width: 140 },
      cell: ({ row }) => (
        <span className="block max-w-[140px] truncate" title={row.original.transaction_id}>
          {row.original.transaction_id}
        </span>
      ),
    },
    { id: "username", header: "Username", accessorKey: "username", meta: { sortKey: "username", width: 120 } },
    {
      id: "user_tg_id",
      header: "TG ID",
      meta: { sortKey: "user_tg_id", width: 120 },
      cell: ({ row }) => row.original.user_tg_id ?? "—",
    },
    {
      id: "payment_method",
      header: "Method",
      meta: { sortKey: "payment_method", width: 100 },
      cell: ({ row }) => row.original.payment_method || "—",
    },
    {
      id: "amount",
      header: "Amount",
      meta: { sortKey: "amount", width: 90 },
      cell: ({ row }) => row.original.amount ?? "—",
    },
    {
      id: "order_status",
      header: "Status",
      meta: { sortKey: "order_status", width: 100 },
      cell: ({ row }) => (
        <Badge variant={statusBadgeVariant(row.original.order_status)}>
          {row.original.order_status}
        </Badge>
      ),
    },
    { id: "days_ordered", header: "Days", accessorKey: "days_ordered", meta: { sortKey: "days_ordered", width: 60 } },
    {
      id: "created_at",
      header: "Date",
      meta: { sortKey: "created_at", width: 160 },
      cell: ({ row }) => row.original.created_at || "—",
    },
    {
      id: "expire_date",
      header: "Expires",
      meta: { sortKey: "expire_date", width: 160 },
      cell: ({ row }) => row.original.expire_date ?? "—",
    },
  ];

  const renderMobileCard = (tx: TransactionItem) => (
    <Card key={tx.transaction_id} className="mb-2">
      <CardContent className="p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <Badge variant={statusBadgeVariant(tx.order_status)}>{tx.order_status}</Badge>
          <span className="text-sm font-semibold text-foreground">
            {tx.amount != null ? tx.amount : "—"}
          </span>
        </div>
        <div className="mb-0.5 text-xs text-muted-foreground">
          {tx.username || "—"} · {tx.payment_method || "—"}
        </div>
        <div className="mb-0.5 text-[11px] text-muted-foreground/70">
          {tx.days_ordered}d · {tx.created_at || "—"}
        </div>
        {tx.expire_date && (
          <div className="text-[11px] text-muted-foreground/70">Expires: {tx.expire_date}</div>
        )}
        <div className="mt-1 truncate text-[10px] text-muted-foreground/50">{tx.transaction_id}</div>
      </CardContent>
    </Card>
  );

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full md:w-[280px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by username, TG ID or transaction ID"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Select
          value={status || ALL}
          onValueChange={(v: string) => {
            setStatus(v === ALL ? "" : v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[calc(50%-4px)] md:w-[140px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            <SelectItem value="created">Created</SelectItem>
            <SelectItem value="confirmed">Confirmed</SelectItem>
            <SelectItem value="delivered">Delivered</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={paymentMethod || ALL}
          onValueChange={(v: string) => {
            setPaymentMethod(v === ALL ? "" : v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[calc(50%-4px)] md:w-[160px]">
            <SelectValue placeholder="Payment method" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All methods</SelectItem>
            <SelectItem value="TG_STARS">Telegram Stars</SelectItem>
            <SelectItem value="CRYPTOPAY">CryptoPay</SelectItem>
            <SelectItem value="CRYSTAL_PAY">Crystal Pay</SelectItem>
            <SelectItem value="SBP_APAY">SBP (A-Pay)</SelectItem>
            <SelectItem value="PLATEGA">Platega</SelectItem>
            <SelectItem value="PARITYPAY">ParityPay</SelectItem>
            <SelectItem value="FREE">Free</SelectItem>
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1">
          <Input
            type="date"
            className="w-[150px]"
            onChange={(e) => setFrom(e.target.value)}
            aria-label="Date from"
          />
          <span className="text-muted-foreground">–</span>
          <Input
            type="date"
            className="w-[150px]"
            onChange={(e) => setTo(e.target.value)}
            aria-label="Date to"
          />
        </div>
        <ConfirmButton
          title="Clean up stale transactions?"
          description="Delete all created transactions older than 7 days (or without a timestamp)."
          confirmText="Delete"
          destructive
          onConfirm={cleanupStale}
        >
          <Button variant="destructive" disabled={cleaning} className="md:ml-auto">
            <Trash2 className="h-4 w-4" />
            Clean stale
          </Button>
        </ConfirmButton>
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
            rowKey={(r) => r.transaction_id}
            sort={sort}
            order={order}
            onSortChange={onSortChange}
            minWidth={1060}
          />
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      )}
    </>
  );
}
