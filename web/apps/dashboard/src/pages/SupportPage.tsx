import { useEffect, useState } from "react";
import {
  Typography,
  Table,
  Tag,
  Input,
  Select,
  Drawer,
  Button,
  App,
  Spin,
  Popconfirm,
  Card,
} from "antd";
import type { TableProps } from "antd";
import { DeleteOutlined, UserOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import {
  PaginatedResponse,
  SupportTicketDetail,
  SupportTicketSummary,
} from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import MobileSortControl, { SortOrder } from "../components/MobileSortControl";
import UserDrawer from "../components/UserDrawer";

const SORT_OPTIONS = [
  { value: "updated_at", label: "Updated" },
  { value: "created_at", label: "Created" },
  { value: "id", label: "ID" },
  { value: "subject", label: "Subject" },
  { value: "username", label: "User" },
  { value: "status", label: "Status" },
];

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
  const isMobile = useIsMobile();
  const { message } = App.useApp();
  const [items, setItems] = useState<SupportTicketSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("updated_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [loading, setLoading] = useState(false);

  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SupportTicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);

  // Nested user card (opened from within a ticket)
  const [userTgId, setUserTgId] = useState<number | null>(null);
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
  }, [page, perPage, status, sort, order]);

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

  const deleteMessage = async (messageId: number) => {
    if (!openId) return;
    try {
      await api.delete(`/support/tickets/${openId}/messages/${messageId}`);
      message.success("Message deleted");
      await loadDetail(openId);
      await load();
    } catch (e: any) {
      message.error(e?.message || "Failed to delete message");
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

  const sortOrderFor = (key: string) =>
    sort === key ? (order === "asc" ? "ascend" : "descend") : null;

  const columns: TableProps<SupportTicketSummary>["columns"] = [
    { title: "ID", dataIndex: "id", key: "id", width: 70, sorter: true, sortOrder: sortOrderFor("id") },
    {
      title: "Subject",
      dataIndex: "subject",
      key: "subject",
      ellipsis: true,
      sorter: true,
      sortOrder: sortOrderFor("subject"),
    },
    {
      title: "User",
      dataIndex: "username",
      key: "username",
      width: 180,
      sorter: true,
      sortOrder: sortOrderFor("username"),
      render: (v: string | null, r: SupportTicketSummary) =>
        v ? `@${v}` : r.tg_id ? String(r.tg_id) : "—",
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 130,
      sorter: true,
      sortOrder: sortOrderFor("status"),
      render: (v: string) => (
        <Tag color={STATUS_COLOR[v] || "default"}>{STATUS_LABEL[v] || v}</Tag>
      ),
    },
    { title: "Created", dataIndex: "created_at", key: "created_at", width: 170, sorter: true, sortOrder: sortOrderFor("created_at") },
    { title: "Updated", dataIndex: "updated_at", key: "updated_at", width: 170, sorter: true, sortOrder: sortOrderFor("updated_at") },
  ];

  const handleTableChange: TableProps<SupportTicketSummary>["onChange"] = (_p, _f, sorter) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    if (s && s.order) {
      setSort(String(s.columnKey));
      setOrder(s.order === "ascend" ? "asc" : "desc");
    }
    setPage(1);
  };

  const renderMobileCard = (t: SupportTicketSummary) => {
    const who = t.username ? `@${t.username}` : t.tg_id ? String(t.tg_id) : "—";
    return (
      <Card
        key={t.id}
        size="small"
        hoverable
        onClick={() => openTicket(t.id)}
        style={{ marginBottom: 8 }}
        styles={{ body: { padding: 12 } }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontWeight: 600,
                color: "rgba(255,255,255,0.88)",
                marginBottom: 4,
                overflow: "hidden",
                textOverflow: "ellipsis",
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
              }}
            >
              #{t.id} · {t.subject}
            </div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 6 }}>
              {who} · {t.updated_at}
            </div>
          </div>
          <Tag color={STATUS_COLOR[t.status] || "default"} style={{ margin: 0, flexShrink: 0 }}>
            {STATUS_LABEL[t.status] || t.status}
          </Tag>
        </div>
      </Card>
    );
  };

  return (
    <div>
      <Typography.Title
        level={4}
        style={{ marginBottom: 20, color: "rgba(255,255,255,0.88)" }}
      >
        Support
      </Typography.Title>

      <div
        style={{
          marginBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Select
          value={status}
          options={STATUS_OPTIONS}
          onChange={(v) => {
            setPage(1);
            setStatus(v);
          }}
          style={{ width: isMobile ? "100%" : 160 }}
        />
        <Input.Search
          placeholder="Search by subject"
          allowClear
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
            load();
          }}
          style={{
            flex: isMobile ? "1 1 100%" : "0 0 280px",
            width: isMobile ? "100%" : 280,
          }}
        />
        <Button onClick={load} style={{ width: isMobile ? "100%" : undefined }}>
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
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
              Loading…
            </div>
          ) : items.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
              No tickets
            </div>
          ) : (
            items.map(renderMobileCard)
          )}
          <div
            style={{
              textAlign: "center",
              padding: "12px 0",
              color: "rgba(255,255,255,0.45)",
              fontSize: 12,
            }}
          >
            Page {page} · Total: {total}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
            <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Prev
            </Button>
            <Button
              size="small"
              disabled={page * perPage >= total}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </>
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          onChange={handleTableChange}
          onRow={(record) => ({
            onClick: () => openTicket(record.id),
            style: { cursor: "pointer" },
          })}
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
      )}

      <Drawer
        title={detail ? `#${detail.id} — ${detail.subject}` : "Loading…"}
        open={openId !== null}
        onClose={closeDrawer}
        width={isMobile ? "100%" : 560}
        extra={
          detail && (
            <Select
              value={detail.status}
              style={{ width: isMobile ? 140 : 160 }}
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
            <div
              style={{
                marginBottom: 12,
                display: "flex",
                alignItems: "center",
                gap: 8,
                flexWrap: "wrap",
              }}
            >
              <span style={{ color: "rgba(255,255,255,0.6)" }}>
                {detail.username ? `@${detail.username}` : detail.tg_id} · {detail.created_at}
              </span>
              {detail.tg_id != null && (
                <Button
                  size="small"
                  icon={<UserOutlined />}
                  onClick={() => {
                    setUserTgId(detail.tg_id);
                    setUserOpen(true);
                  }}
                >
                  Карточка пользователя
                </Button>
              )}
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
                        ? "rgba(124, 156, 255, 0.16)"
                        : "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      fontSize: 12,
                      color: "rgba(255,255,255,0.5)",
                      marginBottom: 4,
                    }}
                  >
                    <span>
                      {m.sender === "admin" ? "Admin" : "User"} · {m.created_at}
                    </span>
                    {m.sender === "admin" && (
                      <Popconfirm
                        title="Delete this reply?"
                        description="This cannot be undone."
                        okText="Delete"
                        okButtonProps={{ danger: true }}
                        cancelText="Cancel"
                        onConfirm={() => deleteMessage(m.id)}
                      >
                        <Button
                          type="text"
                          size="small"
                          icon={<DeleteOutlined />}
                          aria-label="Delete reply"
                        />
                      </Popconfirm>
                    )}
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
              block={isMobile}
              style={{ marginTop: 12 }}
            >
              Send reply
            </Button>
          </>
        )}
      </Drawer>

      <UserDrawer
        tgId={userTgId}
        open={userOpen}
        onClose={() => setUserOpen(false)}
      />
    </div>
  );
}
