import { Table, Tag, Button, Space, Popconfirm, Input, Select, Drawer, Descriptions, List } from "antd";
import { SearchOutlined, StopOutlined, CheckOutlined, DeleteOutlined, EyeOutlined } from "@ant-design/icons";
import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { UserItem, UserDetail, PaginatedResponse, TransactionItem } from "../api/types";

export default function UsersTable() {
  const [data, setData] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<UserDetail | null>(null);
  const [userTx, setUserTx] = useState<TransactionItem[]>([]);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<PaginatedResponse<UserItem>>(
        `/users?page=${page}&per_page=${perPage}&search=${encodeURIComponent(search)}&filter=${filter}`
      );
      setData(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [page, perPage, search, filter]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleBan = async (tg_id: number) => {
    await api.post(`/users/${tg_id}/ban`);
    fetchUsers();
  };

  const handleUnban = async (tg_id: number) => {
    await api.post(`/users/${tg_id}/unban`);
    fetchUsers();
  };

  const handleDelete = async (tg_id: number) => {
    await api.delete(`/users/${tg_id}`);
    fetchUsers();
  };

  const openDrawer = async (tg_id: number) => {
    const user = await api.get<UserDetail>(`/users/${tg_id}`);
    const tx = await api.get<TransactionItem[]>(`/users/${tg_id}/transactions`);
    setSelectedUser(user);
    setUserTx(tx);
    setDrawerOpen(true);
  };

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    { title: "TG ID", dataIndex: "tg_id", key: "tg_id", width: 140 },
    { title: "Username", dataIndex: "username", key: "username" },
    { title: "Provider", dataIndex: "api_provider", key: "api_provider", width: 100 },
    {
      title: "Status",
      key: "status",
      width: 120,
      render: (_: unknown, r: UserItem) => (
        <Space>
          {r.is_banned && <Tag color="red">Banned</Tag>}
          {r.is_paid ? <Tag color="green">Paid</Tag> : <Tag>Free</Tag>}
        </Space>
      ),
    },
    {
      title: "Actions",
      key: "actions",
      width: 180,
      render: (_: unknown, r: UserItem) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDrawer(r.tg_id)} />
          {r.is_banned ? (
            <Button size="small" icon={<CheckOutlined />} onClick={() => handleUnban(r.tg_id)} title="Unban" />
          ) : (
            <Button size="small" danger icon={<StopOutlined />} onClick={() => handleBan(r.tg_id)} title="Ban" />
          )}
          <Popconfirm title="Delete this user and all transactions?" onConfirm={() => handleDelete(r.tg_id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="Search by username or TG ID"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          value={filter}
          onChange={(v) => {
            setFilter(v);
            setPage(1);
          }}
          style={{ width: 120 }}
          options={[
            { value: "all", label: "All" },
            { value: "paid", label: "Paid" },
            { value: "free", label: "Free" },
            { value: "banned", label: "Banned" },
          ]}
        />
      </Space>

      <Table
        rowKey="id"
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
        scroll={{ x: 700 }}
      />

      <Drawer
        title={selectedUser ? `User: ${selectedUser.username || selectedUser.tg_id}` : "User"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={500}
      >
        {selectedUser && (
          <>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="TG ID">{selectedUser.tg_id}</Descriptions.Item>
              <Descriptions.Item label="Username">{selectedUser.username || "—"}</Descriptions.Item>
              <Descriptions.Item label="Email">{selectedUser.email || "—"}</Descriptions.Item>
              <Descriptions.Item label="Provider">{selectedUser.api_provider}</Descriptions.Item>
              <Descriptions.Item label="Banned">{selectedUser.is_banned ? "Yes" : "No"}</Descriptions.Item>
              <Descriptions.Item label="Language">{selectedUser.language || "—"}</Descriptions.Item>
              <Descriptions.Item label="Total Spent">{selectedUser.total_spent}</Descriptions.Item>
              <Descriptions.Item label="Transactions">{selectedUser.transactions_count}</Descriptions.Item>
            </Descriptions>

            <h4 style={{ marginTop: 24 }}>Transactions</h4>
            <List
              size="small"
              dataSource={userTx}
              renderItem={(t) => (
                <List.Item>
                  <List.Item.Meta
                    title={`${t.transaction_id} — ${t.order_status}`}
                    description={`${t.payment_method || "—"} | ${t.amount ?? 0} | ${t.days_ordered}d | ${t.created_at || "—"}`}
                  />
                </List.Item>
              )}
            />
          </>
        )}
      </Drawer>
    </>
  );
}
