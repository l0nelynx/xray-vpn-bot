import { useEffect, useState } from "react";
import {
  Typography,
  Table,
  Tag,
  Input,
  Select,
  Space,
  Drawer,
  Button,
  message,
  Spin,
} from "antd";
import { api } from "../api/client";
import {
  PaginatedResponse,
  SupportTicketDetail,
  SupportTicketSummary,
} from "../api/types";

const STATUS_COLOR: Record<string, string> = {
  open: "blue",
  in_progress: "orange",
  closed: "default",
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
  const [items, setItems] = useState<SupportTicketSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SupportTicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(perPage),
        status,
        search,
      });
      const data = await api.get<PaginatedResponse<SupportTicketSummary>>(
        `/support/tickets?${params}`
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (e: any) {
      message.error(e?.message || "Failed to load tickets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [page, perPage, status]);

  const loadDetail = async (id: number) => {
    setDetailLoading(true);
    setDetail(null);
    try {
      const d = await api.get<SupportTicketDetail>(`/support/tickets/${id}`);
      setDetail(d);
    } catch (e: any) {
      message.error(e?.message || "Failed to load ticket");
    } finally {
      setDetailLoading(false);
    }
  };

  const openTicket = (id: number) => {
    setOpenId(id);
    setReply("");
    loadDetail(id);
  };

  const closeDrawer = () => {
    setOpenId(null);
    setDetail(null);
    setReply("");
  };

  const sendReply = async () => {
    if (!openId || !reply.trim()) return;
    setSending(true);
    try {
      await api.post(`/support/tickets/${openId}/reply`, { text: reply.trim() });
      setReply("");
      await loadDetail(openId);
      await load();
    } catch (e: any) {
      message.error(e?.message || "Failed to send reply");
    } finally {
      setSending(false);
    }
  };

  const changeStatus = async (newStatus: string) => {
    if (!openId) return;
    try {
      await api.patch(`/support/tickets/${openId}`, { status: newStatus });
      await loadDetail(openId);
      await load();
    } catch (e: any) {
      message.error(e?.message || "Failed to update status");
    }
  };

  const columns = [
    { title: "ID", dataIndex: "id", width: 70 },
    {
      title: "Subject",
      dataIndex: "subject",
      ellipsis: true,
      render: (v: string, r: SupportTicketSummary) => (
        <a onClick={() => openTicket(r.id)}>{v}</a>
      ),
    },
    {
      title: "User",
      dataIndex: "username",
      width: 180,
      render: (v: string | null, r: SupportTicketSummary) =>
        v ? `@${v}` : r.tg_id ? String(r.tg_id) : "—",
    },
    {
      title: "Status",
      dataIndex: "status",
      width: 130,
      render: (v: string) => (
        <Tag color={STATUS_COLOR[v] || "default"}>{STATUS_LABEL[v] || v}</Tag>
      ),
    },
    { title: "Created", dataIndex: "created_at", width: 170 },
    { title: "Updated", dataIndex: "updated_at", width: 170 },
  ];

  return (
    <div>
      <Typography.Title
        level={4}
        style={{ marginBottom: 20, color: "rgba(255,255,255,0.88)" }}
      >
        Support
      </Typography.Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          value={status}
          options={STATUS_OPTIONS}
          onChange={(v) => {
            setPage(1);
            setStatus(v);
          }}
          style={{ width: 160 }}
        />
        <Input.Search
          placeholder="Search by subject"
          allowClear
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
            load();
          }}
          style={{ width: 280 }}
        />
        <Button onClick={load}>Refresh</Button>
      </Space>

      <Table
        rowKey="id"
        columns={columns as any}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize: perPage,
          total,
          showSizeChanger: true,
          onChange: (p, ps) => {
            setPage(p);
            setPerPage(ps);
          },
        }}
      />

      <Drawer
        title={detail ? `#${detail.id} — ${detail.subject}` : "Loading…"}
        open={openId !== null}
        onClose={closeDrawer}
        width={560}
        extra={
          detail && (
            <Select
              value={detail.status}
              style={{ width: 160 }}
              onChange={changeStatus}
              options={[
                { value: "open", label: "Open" },
                { value: "in_progress", label: "In progress" },
                { value: "closed", label: "Closed" },
              ]}
            />
          )
        }
      >
        {detailLoading && <Spin />}
        {detail && (
          <>
            <div style={{ marginBottom: 8, color: "rgba(255,255,255,0.6)" }}>
              {detail.username ? `@${detail.username}` : detail.tg_id} ·{" "}
              {detail.created_at}
            </div>

            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                marginBottom: 16,
              }}
            >
              {detail.messages.map((m) => (
                <div
                  key={m.id}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 8,
                    background:
                      m.sender === "admin"
                        ? "rgba(24,144,255,0.12)"
                        : "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      color: "rgba(255,255,255,0.5)",
                      marginBottom: 4,
                    }}
                  >
                    {m.sender === "admin" ? "Admin" : "User"} · {m.created_at}
                  </div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
                </div>
              ))}
            </div>

            <Input.TextArea
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              rows={4}
              maxLength={4000}
              placeholder="Reply to user…"
            />
            <Button
              type="primary"
              loading={sending}
              disabled={!reply.trim()}
              onClick={sendReply}
              style={{ marginTop: 12 }}
            >
              Send reply
            </Button>
          </>
        )}
      </Drawer>
    </div>
  );
}
