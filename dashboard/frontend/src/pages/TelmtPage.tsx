import { useEffect, useState, useCallback } from "react";
import {
  Typography,
  Card,
  Row,
  Col,
  Table,
  Tag,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  DatePicker,
  message,
  Descriptions,
  Space,
  Tabs,
  Tooltip,
  Popconfirm,
  Spin,
  Badge,
} from "antd";
import {
  ReloadOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  LinkOutlined,
  CopyOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudServerOutlined,
  UserOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import type {
  TelmtEnvelope,
  TelmtSystemInfo,
  TelmtSummary,
  TelmtHealth,
  TelmtRuntimeGates,
  TelmtUser,
  TelmtSecurityPosture,
} from "../api/types";
import StatsCard from "../components/StatsCard";
import useIsMobile from "../hooks/useIsMobile";

function formatUptime(secs: number): string {
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(" ");
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
  message.success("Copied to clipboard");
}

// ======================== Server Tab ========================

function ServerTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [sysInfo, setSysInfo] = useState<TelmtSystemInfo | null>(null);
  const [summary, setSummary] = useState<TelmtSummary | null>(null);
  const [health, setHealth] = useState<TelmtHealth | null>(null);
  const [gates, setGates] = useState<TelmtRuntimeGates | null>(null);
  const [security, setSecurity] = useState<TelmtSecurityPosture | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get<TelmtEnvelope<TelmtSystemInfo>>("/telemt/system/info"),
      api.get<TelmtEnvelope<TelmtSummary>>("/telemt/stats/summary"),
      api.get<TelmtEnvelope<TelmtHealth>>("/telemt/health"),
      api.get<TelmtEnvelope<TelmtRuntimeGates>>("/telemt/runtime/gates"),
      api.get<TelmtEnvelope<TelmtSecurityPosture>>("/telemt/security/posture"),
    ])
      .then(([si, st, h, g, sec]) => {
        setSysInfo(si.data);
        setSummary(st.data);
        setHealth(h.data);
        setGates(g.data);
        setSecurity(sec.data);
      })
      .catch(() => message.error("Failed to load telemt data"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading && !sysInfo) {
    return <div style={{ textAlign: "center", padding: 60 }}><Spin size="large" /></div>;
  }

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "flex-end" }}>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
          Refresh
        </Button>
      </div>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Connections"
            value={summary?.connections_total ?? 0}
            loading={loading}
            color="#4f8cff"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Bad Connections"
            value={summary?.connections_bad_total ?? 0}
            loading={loading}
            color={summary?.connections_bad_total ? "#ff4d4f" : "#36cfc9"}
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Users"
            value={summary?.configured_users ?? 0}
            loading={loading}
            color="#b37feb"
          />
        </Col>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Uptime"
            value={summary ? formatUptime(summary.uptime_seconds) : "..."}
            loading={loading}
            color="#ffc53d"
          />
        </Col>
      </Row>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginTop: isMobile ? 8 : 16 }}>
        <Col xs={24} lg={12}>
          <Card title={<span style={{ color: "rgba(255,255,255,0.85)" }}>System Info</span>}>
            {sysInfo && (
              <Descriptions column={1} size="small" labelStyle={{ color: "rgba(255,255,255,0.5)" }} contentStyle={{ color: "rgba(255,255,255,0.85)" }}>
                <Descriptions.Item label="Version">{sysInfo.version}</Descriptions.Item>
                <Descriptions.Item label="Architecture">{sysInfo.target_arch}</Descriptions.Item>
                <Descriptions.Item label="OS">{sysInfo.target_os}</Descriptions.Item>
                <Descriptions.Item label="Build Profile">{sysInfo.build_profile}</Descriptions.Item>
                {sysInfo.git_commit && <Descriptions.Item label="Git Commit">{sysInfo.git_commit}</Descriptions.Item>}
                <Descriptions.Item label="Config Path">{sysInfo.config_path}</Descriptions.Item>
                <Descriptions.Item label="Config Reloads">{sysInfo.config_reload_count}</Descriptions.Item>
                <Descriptions.Item label="Started">
                  {dayjs.unix(sysInfo.process_started_at_epoch_secs).format("YYYY-MM-DD HH:mm:ss")}
                </Descriptions.Item>
              </Descriptions>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Runtime & Security</span>}>
            <Row gutter={[8, 8]}>
              {health && (
                <Col span={24}>
                  <Space>
                    <span style={{ color: "rgba(255,255,255,0.5)" }}>Status:</span>
                    <Badge status={health.status === "ok" ? "success" : "error"} text={<span style={{ color: "rgba(255,255,255,0.85)" }}>{health.status}</span>} />
                    {health.read_only && <Tag color="orange">Read-Only</Tag>}
                  </Space>
                </Col>
              )}
              {gates && (
                <>
                  <Col span={24} style={{ marginTop: 12 }}>
                    <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 12, textTransform: "uppercase", letterSpacing: 1 }}>Runtime Gates</span>
                  </Col>
                  <Col span={24}>
                    <Space wrap>
                      <Tag color={gates.accepting_new_connections ? "green" : "red"}>
                        {gates.accepting_new_connections ? <CheckCircleOutlined /> : <CloseCircleOutlined />} Accepting Connections
                      </Tag>
                      <Tag color={gates.me_runtime_ready ? "green" : "orange"}>
                        ME {gates.me_runtime_ready ? "Ready" : "Not Ready"}
                      </Tag>
                      <Tag color="blue">Startup: {gates.startup_status}</Tag>
                      {gates.startup_progress_pct < 100 && (
                        <Tag color="gold">{gates.startup_progress_pct.toFixed(0)}%</Tag>
                      )}
                      <Tag>{gates.use_middle_proxy ? "Middle Proxy" : "Direct"}</Tag>
                    </Space>
                  </Col>
                </>
              )}
              {security && (
                <>
                  <Col span={24} style={{ marginTop: 12 }}>
                    <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 12, textTransform: "uppercase", letterSpacing: 1 }}>Security</span>
                  </Col>
                  <Col span={24}>
                    <Space wrap>
                      <Tag color={security.api_auth_header_enabled ? "green" : "red"}>
                        Auth: {security.api_auth_header_enabled ? "ON" : "OFF"}
                      </Tag>
                      <Tag color={security.api_whitelist_enabled ? "green" : "default"}>
                        Whitelist: {security.api_whitelist_enabled ? `${security.api_whitelist_entries} entries` : "OFF"}
                      </Tag>
                      <Tag>Log: {security.log_level}</Tag>
                      <Tag color={security.telemetry_core_enabled ? "green" : "default"}>
                        Core Telemetry: {security.telemetry_core_enabled ? "ON" : "OFF"}
                      </Tag>
                    </Space>
                  </Col>
                </>
              )}
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

// ======================== Users Tab ========================

function UsersTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<TelmtUser[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<TelmtUser | null>(null);
  const [linksUser, setLinksUser] = useState<TelmtUser | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<TelmtEnvelope<TelmtUser[]>>("/telemt/users")
      .then((r) => setUsers(r.data))
      .catch(() => message.error("Failed to load telemt users"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (values: any) => {
    try {
      const body: any = { username: values.username };
      if (values.secret) body.secret = values.secret;
      if (values.user_ad_tag) body.user_ad_tag = values.user_ad_tag;
      if (values.max_tcp_conns != null) body.max_tcp_conns = values.max_tcp_conns;
      if (values.max_unique_ips != null) body.max_unique_ips = values.max_unique_ips;
      if (values.data_quota_bytes != null) body.data_quota_bytes = values.data_quota_bytes;
      if (values.expiration) body.expiration_rfc3339 = values.expiration.toISOString();
      await api.post("/telemt/users", body);
      message.success("User created");
      setCreateOpen(false);
      createForm.resetFields();
      load();
    } catch (e: any) {
      message.error(e.message || "Failed to create user");
    }
  };

  const handleEdit = async (values: any) => {
    if (!editUser) return;
    try {
      const body: any = {};
      if (values.secret) body.secret = values.secret;
      if (values.user_ad_tag) body.user_ad_tag = values.user_ad_tag;
      if (values.max_tcp_conns != null) body.max_tcp_conns = values.max_tcp_conns;
      if (values.max_unique_ips != null) body.max_unique_ips = values.max_unique_ips;
      if (values.data_quota_bytes != null) body.data_quota_bytes = values.data_quota_bytes;
      if (values.expiration) body.expiration_rfc3339 = values.expiration.toISOString();
      await api.patch(`/telemt/users/${editUser.username}`, body);
      message.success("User updated");
      setEditUser(null);
      editForm.resetFields();
      load();
    } catch (e: any) {
      message.error(e.message || "Failed to update user");
    }
  };

  const handleDelete = async (username: string) => {
    try {
      await api.delete(`/telemt/users/${username}`);
      message.success(`User ${username} deleted`);
      load();
    } catch (e: any) {
      message.error(e.message || "Failed to delete user");
    }
  };

  const openEdit = (user: TelmtUser) => {
    setEditUser(user);
    editForm.setFieldsValue({
      user_ad_tag: user.user_ad_tag || undefined,
      max_tcp_conns: user.max_tcp_conns,
      max_unique_ips: user.max_unique_ips,
      data_quota_bytes: user.data_quota_bytes,
      expiration: user.expiration_rfc3339 ? dayjs(user.expiration_rfc3339) : undefined,
    });
  };

  const columns = [
    {
      title: "Username",
      dataIndex: "username",
      key: "username",
      width: 140,
      render: (v: string, r: TelmtUser) => (
        <Space>
          <span>{v}</span>
          <Badge status={r.in_runtime ? "success" : "default"} />
        </Space>
      ),
    },
    {
      title: "Connections",
      dataIndex: "current_connections",
      key: "conns",
      width: 100,
      sorter: (a: TelmtUser, b: TelmtUser) => a.current_connections - b.current_connections,
    },
    {
      title: "Unique IPs",
      dataIndex: "active_unique_ips",
      key: "ips",
      width: 90,
    },
    {
      title: "Traffic",
      dataIndex: "total_octets",
      key: "traffic",
      width: 100,
      render: (v: number) => formatBytes(v),
      sorter: (a: TelmtUser, b: TelmtUser) => a.total_octets - b.total_octets,
    },
    {
      title: "Limits",
      key: "limits",
      width: 180,
      render: (_: any, r: TelmtUser) => (
        <Space wrap size={4}>
          {r.max_tcp_conns != null && <Tag>TCP: {r.max_tcp_conns}</Tag>}
          {r.max_unique_ips != null && <Tag>IPs: {r.max_unique_ips}</Tag>}
          {r.data_quota_bytes != null && <Tag>Quota: {formatBytes(r.data_quota_bytes)}</Tag>}
          {r.expiration_rfc3339 && (
            <Tag color={dayjs(r.expiration_rfc3339).isBefore(dayjs()) ? "red" : "blue"}>
              Exp: {dayjs(r.expiration_rfc3339).format("DD.MM.YY")}
            </Tag>
          )}
          {!r.max_tcp_conns && !r.max_unique_ips && !r.data_quota_bytes && !r.expiration_rfc3339 && (
            <span style={{ color: "rgba(255,255,255,0.3)" }}>No limits</span>
          )}
        </Space>
      ),
    },
    {
      title: "",
      key: "actions",
      width: 120,
      render: (_: any, r: TelmtUser) => (
        <Space size={4}>
          <Tooltip title="Links">
            <Button type="text" size="small" icon={<LinkOutlined />} onClick={() => setLinksUser(r)} />
          </Tooltip>
          <Tooltip title="Edit">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          </Tooltip>
          <Popconfirm title={`Delete ${r.username}?`} onConfirm={() => handleDelete(r.username)} okText="Delete" okButtonProps={{ danger: true }}>
            <Button type="text" size="small" icon={<DeleteOutlined />} danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const renderUserMobile = (user: TelmtUser) => (
    <Card
      key={user.username}
      size="small"
      style={{ marginBottom: 8 }}
      title={
        <Space>
          <Badge status={user.in_runtime ? "success" : "default"} />
          <span>{user.username}</span>
        </Space>
      }
      extra={
        <Space size={4}>
          <Button type="text" size="small" icon={<LinkOutlined />} onClick={() => setLinksUser(user)} />
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(user)} />
          <Popconfirm title={`Delete ${user.username}?`} onConfirm={() => handleDelete(user.username)} okText="Delete" okButtonProps={{ danger: true }}>
            <Button type="text" size="small" icon={<DeleteOutlined />} danger />
          </Popconfirm>
        </Space>
      }
    >
      <Row gutter={8}>
        <Col span={8}><span style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>Conns</span><div>{user.current_connections}</div></Col>
        <Col span={8}><span style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>IPs</span><div>{user.active_unique_ips}</div></Col>
        <Col span={8}><span style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>Traffic</span><div>{formatBytes(user.total_octets)}</div></Col>
      </Row>
    </Card>
  );

  const userFormFields = (isCreate: boolean) => (
    <>
      {isCreate && (
        <Form.Item name="username" label="Username" rules={[{ required: true, pattern: /^[A-Za-z0-9_.\-]{1,64}$/, message: "Letters, digits, _ . - (1-64)" }]}>
          <Input placeholder="username" />
        </Form.Item>
      )}
      <Form.Item name="secret" label="Secret" rules={[{ pattern: /^[0-9a-fA-F]{32}$/, message: "32 hex chars" }]}>
        <Input placeholder="Auto-generated if empty" />
      </Form.Item>
      <Form.Item name="user_ad_tag" label="Ad Tag" rules={[{ pattern: /^[0-9a-fA-F]{32}$/, message: "32 hex chars" }]}>
        <Input placeholder="32 hex chars" />
      </Form.Item>
      <Form.Item name="max_tcp_conns" label="Max TCP Connections">
        <InputNumber min={1} style={{ width: "100%" }} placeholder="Unlimited" />
      </Form.Item>
      <Form.Item name="max_unique_ips" label="Max Unique IPs">
        <InputNumber min={1} style={{ width: "100%" }} placeholder="Unlimited" />
      </Form.Item>
      <Form.Item name="data_quota_bytes" label="Data Quota (bytes)">
        <InputNumber min={0} style={{ width: "100%" }} placeholder="Unlimited" />
      </Form.Item>
      <Form.Item name="expiration" label="Expiration">
        <DatePicker showTime style={{ width: "100%" }} />
      </Form.Item>
    </>
  );

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between" }}>
        <Button icon={<PlusOutlined />} type="primary" onClick={() => setCreateOpen(true)}>
          Add User
        </Button>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
          Refresh
        </Button>
      </div>

      {isMobile ? (
        loading ? (
          <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
        ) : (
          users.map(renderUserMobile)
        )
      ) : (
        <Card>
          <Table
            rowKey="username"
            columns={columns}
            dataSource={users}
            loading={loading}
            pagination={false}
            size="small"
            scroll={{ x: 700 }}
          />
        </Card>
      )}

      {/* Create Modal */}
      <Modal
        title="Create Telemt User"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        onOk={() => createForm.submit()}
        okText="Create"
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          {userFormFields(true)}
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        title={`Edit ${editUser?.username}`}
        open={!!editUser}
        onCancel={() => { setEditUser(null); editForm.resetFields(); }}
        onOk={() => editForm.submit()}
        okText="Save"
      >
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          {userFormFields(false)}
        </Form>
      </Modal>

      {/* Links Modal */}
      <Modal
        title={`Links for ${linksUser?.username}`}
        open={!!linksUser}
        onCancel={() => setLinksUser(null)}
        footer={null}
        width={600}
      >
        {linksUser && (
          <div>
            {(["tls", "secure", "classic"] as const).map((type) => {
              const links = linksUser.links[type];
              if (!links.length) return null;
              return (
                <div key={type} style={{ marginBottom: 16 }}>
                  <Typography.Text strong style={{ textTransform: "uppercase", color: "rgba(255,255,255,0.6)", fontSize: 12 }}>
                    {type}
                  </Typography.Text>
                  {links.map((link, i) => (
                    <div
                      key={i}
                      style={{
                        marginTop: 8,
                        padding: "8px 12px",
                        background: "rgba(255,255,255,0.04)",
                        borderRadius: 6,
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Typography.Text
                        style={{ flex: 1, fontSize: 12, wordBreak: "break-all", color: "rgba(255,255,255,0.75)" }}
                      >
                        {link}
                      </Typography.Text>
                      <Button
                        type="text"
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => copyToClipboard(link)}
                      />
                    </div>
                  ))}
                </div>
              );
            })}
            {!linksUser.links.tls.length && !linksUser.links.secure.length && !linksUser.links.classic.length && (
              <Typography.Text type="secondary">No links available</Typography.Text>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}

// ======================== Main Page ========================

export default function TelmtPage() {
  const isMobile = useIsMobile();

  return (
    <div>
      <Typography.Title
        level={isMobile ? 5 : 4}
        style={{ margin: 0, marginBottom: isMobile ? 12 : 20, color: "rgba(255,255,255,0.88)" }}
      >
        Telemt
      </Typography.Title>
      <Tabs
        defaultActiveKey="server"
        items={[
          {
            key: "server",
            label: (
              <span>
                <CloudServerOutlined /> Server
              </span>
            ),
            children: <ServerTab />,
          },
          {
            key: "users",
            label: (
              <span>
                <UserOutlined /> Users
              </span>
            ),
            children: <UsersTab />,
          },
        ]}
      />
    </div>
  );
}
