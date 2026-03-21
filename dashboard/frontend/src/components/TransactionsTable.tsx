import { Table, Space, Select, DatePicker, Tag, Card, Button } from "antd";
import { useState, useEffect, useCallback } from "react";
import dayjs from "dayjs";
import { api } from "../api/client";
import type { TransactionItem, PaginatedResponse } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

const { RangePicker } = DatePicker;

const statusColor: Record<string, string> = {
  created: "blue",
  confirmed: "green",
  delivered: "cyan",
  failed: "red",
  cancelled: "orange",
};

export default function TransactionsTable() {
  const [data, setData] = useState<TransactionItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [status, setStatus] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [dateRange, setDateRange] = useState<[string, string]>(["", ""]);
  const [loading, setLoading] = useState(false);
  const isMobile = useIsMobile();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      let url = `/transactions?page=${page}&per_page=${perPage}`;
      if (status) url += `&status=${status}`;
      if (paymentMethod) url += `&payment_method=${encodeURIComponent(paymentMethod)}`;
      if (dateRange[0]) url += `&date_from=${dateRange[0]}`;
      if (dateRange[1]) url += `&date_to=${dateRange[1]}`;

      const res = await api.get<PaginatedResponse<TransactionItem>>(url);
      setData(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, status, paymentMethod, dateRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const columns = [
    { title: "ID", dataIndex: "transaction_id", key: "transaction_id", width: 140, ellipsis: true },
    { title: "Username", dataIndex: "username", key: "username", width: 120 },
    { title: "TG ID", dataIndex: "user_tg_id", key: "user_tg_id", width: 120 },
    { title: "Method", dataIndex: "payment_method", key: "payment_method", width: 100 },
    {
      title: "Amount",
      dataIndex: "amount",
      key: "amount",
      width: 90,
      render: (v: number | null) => v ?? "—",
    },
    {
      title: "Status",
      dataIndex: "order_status",
      key: "order_status",
      width: 100,
      render: (s: string) => <Tag color={statusColor[s] || "default"}>{s}</Tag>,
    },
    { title: "Days", dataIndex: "days_ordered", key: "days_ordered", width: 60 },
    { title: "Date", dataIndex: "created_at", key: "created_at", width: 160 },
    {
      title: "Expires",
      dataIndex: "expire_date",
      key: "expire_date",
      width: 160,
      render: (v: string | null) => v ?? "—",
    },
  ];

  const renderMobileCard = (tx: TransactionItem) => (
    <Card
      key={tx.transaction_id}
      size="small"
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: "12px" } }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <Tag color={statusColor[tx.order_status] || "default"} style={{ margin: 0 }}>
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
            { value: "stars", label: "Stars" },
            { value: "cryptobot", label: "CryptoBot" },
            { value: "crystal", label: "Crystal Pay" },
            { value: "apay", label: "A-Pays" },
            { value: "platega", label: "Platega" },
            { value: "free", label: "Free" },
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
