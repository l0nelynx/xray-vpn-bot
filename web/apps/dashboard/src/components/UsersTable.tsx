import { Table, Tag, Button, Space, Popconfirm, Input, Select, Card, App, Typography } from "antd";
import type { TableProps } from "antd";
import { SearchOutlined, StopOutlined, CheckOutlined, DeleteOutlined, EyeOutlined, CrownOutlined, SyncOutlined } from "@ant-design/icons";
import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../api/client";
import type { UserItem, PaginatedResponse } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";
import useDebounce from "../hooks/useDebounce";
import MobileSortControl, { SortOrder } from "./MobileSortControl";
import UserDrawer from "./UserDrawer";

const SORT_OPTIONS = [
  { value: "id", label: "ID" },
  { value: "tg_id", label: "TG ID" },
  { value: "username", label: "Username" },
  { value: "api_provider", label: "Provider" },
  { value: "is_paid", label: "Paid status" },
];

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
  const [backfillLoading, setBackfillLoading] = useState(false);
  const [drawerTgId, setDrawerTgId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isMobile = useIsMobile();
  const debouncedSearch = useDebounce(search, 400);
  const abortRef = useRef<AbortController | null>(null);
  const { message } = App.useApp();

  const fetchUsers = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    try {
      const res = await api.get<PaginatedResponse<UserItem>>(
        `/users?page=${page}&per_page=${perPage}&search=${encodeURIComponent(debouncedSearch)}&filter=${filter}&sort=${sort}&order=${order}`,
        controller.signal
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

  const handleBan = async (tg_id: number) => {
    try {
      await api.post(`/users/${tg_id}/ban`);
      fetchUsers();
    } catch {
      message.error("Failed to ban user");
    }
  };

  const handleUnban = async (tg_id: number) => {
    try {
      await api.post(`/users/${tg_id}/unban`);
      fetchUsers();
    } catch {
      message.error("Failed to unban user");
    }
  };

  const handleDelete = async (tg_id: number) => {
    try {
      await api.delete(`/users/${tg_id}`);
      fetchUsers();
    } catch {
      message.error("Failed to delete user");
    }
  };

  const handleToggleVip = async (tg_id: number, currentVip: boolean) => {
    try {
      await api.post(`/users/${tg_id}/${currentVip ? "unvip" : "vip"}`);
      fetchUsers();
    } catch {
      message.error("Failed to toggle VIP status");
    }
  };

  const handleBackfillRwIds = async () => {
    setBackfillLoading(true);
    try {
      const res = await api.post<{
        local_candidates: number;
        updated: number;
        not_found_on_panel: number;
        errors: number;
      }>("/users/backfill-rw-ids");
      message.success(
        `Synced Remnawave IDs: ${res.updated} updated, ` +
          `${res.not_found_on_panel} not on panel, ${res.errors} errors ` +
          `(of ${res.local_candidates} candidates)`
      );
      fetchUsers();
    } catch {
      message.error("Failed to sync Remnawave IDs");
    } finally {
      setBackfillLoading(false);
    }
  };

  const openDrawer = (tg_id: number) => {
    setDrawerTgId(tg_id);
    setDrawerOpen(true);
  };

  const sortOrderFor = (key: string) =>
    sort === key ? (order === "asc" ? "ascend" : "descend") : null;

  const columns: TableProps<UserItem>["columns"] = [
    { title: "ID", dataIndex: "id", key: "id", width: 60, sorter: true, sortOrder: sortOrderFor("id") },
    { title: "TG ID", dataIndex: "tg_id", key: "tg_id", width: 130, sorter: true, sortOrder: sortOrderFor("tg_id") },
    { title: "Username", dataIndex: "username", key: "username", width: 140, sorter: true, sortOrder: sortOrderFor("username") },
    {
      title: "Email",
      dataIndex: "email",
      key: "email",
      width: 180,
      render: (v: string | null) => v || "—",
    },
    {
      title: "vless_uuid",
      dataIndex: "vless_uuid",
      key: "vless_uuid",
      width: 150,
      render: (v: string | null) =>
        v ? (
          <Typography.Text copyable={{ text: v }} style={{ fontSize: 11 }} ellipsis={{ tooltip: v }}>
            {v}
          </Typography.Text>
        ) : (
          "—"
        ),
    },
    { title: "Provider", dataIndex: "api_provider", key: "api_provider", width: 90, sorter: true, sortOrder: sortOrderFor("api_provider") },
    {
      title: "Status",
      key: "is_paid",
      width: 120,
      sorter: true,
      sortOrder: sortOrderFor("is_paid"),
      render: (_: unknown, r: UserItem) => (
        <Space>
          {r.vip && <Tag color="gold">VIP</Tag>}
          {r.is_banned && <Tag color="red">Banned</Tag>}
          {r.is_paid ? <Tag color="green">Paid</Tag> : <Tag>Free</Tag>}
        </Space>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 200,
      fixed: "right",
      render: (_: unknown, r: UserItem) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDrawer(r.tg_id)} />
          <Button
            size="small"
            icon={<CrownOutlined />}
            onClick={() => handleToggleVip(r.tg_id, r.vip)}
            title={r.vip ? "Remove VIP" : "Set VIP"}
            style={r.vip ? { color: "#faad14", borderColor: "#faad14" } : undefined}
          />
          {r.is_banned ? (
            <Button size="small" icon={<CheckOutlined />} onClick={() => handleUnban(r.tg_id)} title="Unban" />
          ) : (
            <Popconfirm title="Ban this user?" onConfirm={() => handleBan(r.tg_id)}>
              <Button size="small" danger icon={<StopOutlined />} title="Ban" />
            </Popconfirm>
          )}
          <Popconfirm title="Delete this user and all transactions?" onConfirm={() => handleDelete(r.tg_id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const handleTableChange: TableProps<UserItem>["onChange"] = (_p, _f, sorter) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    if (s && s.order) {
      setSort(String(s.columnKey));
      setOrder(s.order === "ascend" ? "asc" : "desc");
    }
    setPage(1);
  };

  const renderMobileCard = (user: UserItem) => (
    <Card key={user.id} size="small" style={{ marginBottom: 8 }} styles={{ body: { padding: "12px" } }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: "rgba(255,255,255,0.88)", marginBottom: 4 }}>
            {user.username || "—"}
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 4 }}>
            TG: {user.tg_id} · {user.api_provider}
          </div>
          {user.email && (
            <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginBottom: 6, wordBreak: "break-all" }}>
              {user.email}
            </div>
          )}
          <Space size={4}>
            {user.vip && <Tag color="gold" style={{ margin: 0 }}>VIP</Tag>}
            {user.is_banned && <Tag color="red" style={{ margin: 0 }}>Banned</Tag>}
            {user.is_paid ? <Tag color="green" style={{ margin: 0 }}>Paid</Tag> : <Tag style={{ margin: 0 }}>Free</Tag>}
          </Space>
        </div>
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDrawer(user.tg_id)} />
          {user.is_banned ? (
            <Button size="small" icon={<CheckOutlined />} onClick={() => handleUnban(user.tg_id)} />
          ) : (
            <Popconfirm title="Ban this user?" onConfirm={() => handleBan(user.tg_id)}>
              <Button size="small" danger icon={<StopOutlined />} />
            </Popconfirm>
          )}
          <Popconfirm title="Delete user?" onConfirm={() => handleDelete(user.tg_id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      </div>
    </Card>
  );

  return (
    <>
      <div style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", gap: 8 }}>
        <Input
          placeholder="Search by username, email, UUID or TG ID"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          style={{ flex: 1, minWidth: isMobile ? "100%" : 220, maxWidth: isMobile ? "100%" : 320 }}
          allowClear
        />
        <Select
          value={filter}
          onChange={(v) => {
            setFilter(v);
            setPage(1);
          }}
          style={{ width: isMobile ? "100%" : 120 }}
          options={[
            { value: "all", label: "All" },
            { value: "paid", label: "Paid" },
            { value: "free", label: "Free" },
            { value: "vip", label: "VIP" },
            { value: "banned", label: "Banned" },
          ]}
        />
        <Popconfirm
          title="Fetch Remnawave panel IDs for all users with vless_uuid?"
          description="Temporary migration helper. Safe to re-run; only fills missing rw_id."
          onConfirm={handleBackfillRwIds}
        >
          <Button
            icon={<SyncOutlined />}
            loading={backfillLoading}
            title="Temporary: sync Remnawave numeric user IDs into rw_id"
          >
            Sync Remnawave IDs
          </Button>
        </Popconfirm>
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
          rowKey="id"
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
          scroll={{ x: 960 }}
        />
      )}

      <UserDrawer
        tgId={drawerTgId}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onChanged={fetchUsers}
      />
    </>
  );
}
