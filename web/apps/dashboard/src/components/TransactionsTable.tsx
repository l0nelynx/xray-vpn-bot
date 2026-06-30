import { Table, Select, DatePicker, Tag, Card, Button, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import type { TableProps } from "antd";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api/client";
import type { TransactionItem, PaginatedResponse } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import useDebounce from "../hooks/useDebounce";
import MobileSortControl, { SortOrder } from "./MobileSortControl";
import { STATUS_COLORS } from "../utils/constants";

const { RangePicker } = DatePicker;

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

  const sortOrderFor = (key: string) =>
    sort === key ? (order === "asc" ? "ascend" : "descend") : null;

  const columns: TableProps<TransactionItem>["columns"] = [
    { title: "ID", dataIndex: "transaction_id", key: "transaction_id", width: 140, ellipsis: true, sorter: true, sortOrder: sortOrderFor("transaction_id") },
    { title: "Username", dataIndex: "username", key: "username", width: 120, sorter: true, sortOrder: sortOrderFor("username") },
    { title: "TG ID", dataIndex: "user_tg_id", key: "user_tg_id", width: 120, sorter: true, sortOrder: sortOrderFor("user_tg_id") },
    { title: "Method", dataIndex: "payment_method", key: "payment_method", width: 100, sorter: true, sortOrder: sortOrderFor("payment_method") },
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      width: 90,
      sorter: true,
      sortOrder: sortOrderFor("amount"),
      render: (v: number | null) => v ?? "—",
    },
    {
      title: "Status",
      dataIndex: "order_status",
      key: "order_status",
      width: 100,
      sorter: true,
      sortOrder: sortOrderFor("order_status"),
      render: (s: string) => <Tag color={STATUS_COLORS[s] || "default"}>{s}</Tag>,
    },
    { title: "Days", dataIndex: "days_ordered", key: "days_ordered", width: 60, sorter: true, sortOrder: sortOrderFor("days_ordered") },
    { title: "Date", dataIndex: "created_at", key: "created_at", width: 160, sorter: true, sortOrder: sortOrderFor("created_at") },
    {
      title: "Expires",
      dataIndex: "expire_date",
      key: "expire_date",
      width: 160,
      sorter: true,
      sortOrder: sortOrderFor("expire_date"),
      render: (v: string | null) => v ?? "—",
    },
  ];

  const handleTableChange: TableProps<TransactionItem>["onChange"] = (_p, _f, sorter) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    if (s && s.order) {
      setSort(String(s.field));
      setOrder(s.order === "ascend" ? "asc" : "desc");
    }
    setPage(1);
  };

  const renderMobileCard = (tx: TransactionItem) => (
    <Card
      key={tx.transaction_id}
      size="small"
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: "12px" } }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <Tag color={STATUS_COLORS[tx.order_status] || "default"} style={{ margin: 0 }}>
          {tx.order_status}
        </Tag>
        <span style={{ fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.88)" }}>
          {tx.amount != null ? tx.amount : "—"}
        </span>
      </div>
      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.55)", marginBottom: 2 }}>
        {tx.username || "—"} · {tx.payment_method || "—"}
      </div>
      <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginBottom: 2 }}>
        {tx.days_ordered}d · {tx.created_at || "—"}
      </div>
      {tx.expire_date && (
        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
          Expires: {tx.expire_date}
        </div>
      )}
      <div
        style={{
          fontSize: 10,
          color: "rgba(255,255,255,0.25)",
          marginTop: 4,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {tx.transaction_id}
      </div>
    </Card>
  );

  return (
    <>
      <div style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", gap: 8 }}>
        <Input
          placeholder="Search by username, TG ID or transaction ID"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          style={{ width: isMobile ? "100%" : 280 }}
          allowClear
        />
        <Select
          value={status}
          onChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
          style={{ width: isMobile ? "calc(50% - 4px)" : 140 }}
          allowClear
          placeholder="Status"
          options={[
            { value: "", label: "All statuses" },
            { value: "created", label: "Created" },
            { value: "confirmed", label: "Confirmed" },
            { value: "delivered", label: "Delivered" },
            { value: "failed", label: "Failed" },
          ]}
        />
        <Select
          value={paymentMethod}
          onChange={(v) => {
            setPaymentMethod(v);
            setPage(1);
          }}
          style={{ width: isMobile ? "calc(50% - 4px)" : 160 }}
          allowClear
          placeholder="Payment method"
          options={[
            { value: "", label: "All methods" },
            { value: "TG_STARS", label: "Telegram Stars" },
            { value: "CRYPTOPAY", label: "CryptoPay" },
            { value: "CRYSTAL_PAY", label: "Crystal Pay" },
            { value: "SBP_APAY", label: "SBP (A-Pay)" },
            { value: "PLATEGA", label: "Platega" },
            { value: "FREE", label: "Free" },
          ]}
        />
        <RangePicker
          style={{ width: isMobile ? "100%" : undefined }}
          onChange={(dates) => {
            if (dates && dates[0] && dates[1]) {
              setDateRange([
                dates[0].format("YYYY-MM-DD"),
                dates[1].format("YYYY-MM-DD") + "T23:59:59",
              ]);
            } else {
              setDateRange(["", ""]);
            }
            setPage(1);
          }}
        />
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
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>Loading...</div>
          ) : (
            data.map(renderMobileCard)
          )}
          <div style={{ textAlign: "center", padding: "12px 0", color: "rgba(255,255,255,0.45)", fontSize: 12 }}>
            Page {page} · Total: {total}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
            <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Prev
            </Button>
            <Button size="small" disabled={page * perPage >= total} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        </>
      ) : (
        <Table
          rowKey="transaction_id"
          columns={columns}
          dataSource={data}
          loading={loading}
          onChange={handleTableChange}
          pagination={{
            current: page,
            pageSize: perPage,
            total,
            onChange: setPage,
            showSizeChanger: false,
            showTotal: (t) => `Total: ${t}`,
          }}
          size="small"
          scroll={{ x: 1060 }}
        />
      )}
    </>
  );
}
