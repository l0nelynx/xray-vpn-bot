import { useEffect, useState, useCallback, type Key } from "react";
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
  App,
  Descriptions,
  Space,
  Tabs,
  Tooltip,
  Popconfirm,
  Spin,
  Badge,
  Checkbox,
  Dropdown,
  Alert,
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
  KeyOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  CloudServerOutlined,
  UserOutlined,
  SettingOutlined,
  MoreOutlined,
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
  TelmtFreeParams,
  TelmtBulkResult,
  TelmtHealthReady,
  TelmtUsersQuotaResponse,
  TelmtLimitsEffective,
  TelmtSecurityWhitelist,
  TelmtRuntimeConnectionsSummary,
  TelmtRuntimeRecentEvents,
  TelmtTlsFingerprints,
  TelmtConfigData,
  TelmtPatchConfigResponse,
  TelmtConfigSectionName,
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

function mobileModalProps(isMobile: boolean) {
  return isMobile
    ? {
        width: "100%" as const,
        style: { top: 16, maxWidth: "calc(100vw - 16px)", margin: "0 auto" },
        styles: { body: { maxHeight: "70vh", overflowY: "auto" as const } },
      }
    : {};
}

// ======================== Server Tab ========================

function ServerTab() {
  const isMobile = useIsMobile();
  const { message } = App.useApp();
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
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading} block={isMobile}>
          Refresh
        </Button>
      </div>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={12} sm={12} lg={6}>
          <StatsCard
            title="Connections"
            value={summary?.connections_total ?? 0}
            loading={loading}
            color="#7C9CFF"
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
  const { message, modal } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<TelmtUser[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<TelmtUser | null>(null);
  const [linksUser, setLinksUser] = useState<TelmtUser | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [bulkExtendForm] = Form.useForm();
  const [bulkLimitsForm] = Form.useForm();
  const [selectedUsernames, setSelectedUsernames] = useState<Key[]>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkExtendOpen, setBulkExtendOpen] = useState(false);
  const [bulkLimitsOpen, setBulkLimitsOpen] = useState(false);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success("Copied to clipboard");
  };

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
      if (values.rate_limit_up_bps != null) body.rate_limit_up_bps = values.rate_limit_up_bps;
      if (values.rate_limit_down_bps != null) body.rate_limit_down_bps = values.rate_limit_down_bps;
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
      if (values.rate_limit_up_bps != null) body.rate_limit_up_bps = values.rate_limit_up_bps;
      if (values.rate_limit_down_bps != null) body.rate_limit_down_bps = values.rate_limit_down_bps;
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

  const handleRotateSecret = async (username: string) => {
    try {
      await api.post(`/telemt/users/${username}/rotate-secret`, {});
      message.success(`Secret rotated for ${username}`);
      load();
    } catch (e: any) {
      message.error(e.message || "Failed to rotate secret");
    }
  };

  const handleResetQuota = async (username: string) => {
    try {
      await api.post(`/telemt/users/${username}/reset-quota`, {});
      message.success(`Quota reset for ${username}`);
      load();
    } catch (e: any) {
      message.error(e.message || "Failed to reset quota");
    }
  };

  const handleEnableUser = async (username: string) => {
    try {
      await api.post(`/telemt/users/${username}/enable`, {});
      message.success(`User ${username} enabled`);
      load();
    } catch (e: any) {
      message.error(e.message || "Failed to enable user");
    }
  };

  const handleDisableUser = async (username: string) => {
    try {
      await api.post(`/telemt/users/${username}/disable`, {});
      message.success(`User ${username} disabled`);
      load();
    } catch (e: any) {
      message.error(e.message || "Failed to disable user");
    }
  };

  const runBulk = async (path: string, payload: any, successText: string) => {
    setBulkLoading(true);
    try {
      const result = await api.post<TelmtBulkResult>(path, payload);
      if (result.failed > 0) {
        message.warning(`${successText}: ${result.succeeded}/${result.processed} succeeded`);
      } else {
        message.success(`${successText}: ${result.succeeded}/${result.processed} succeeded`);
      }
      if (result.errors.length) {
        const first = result.errors[0];
        message.error(`First error: ${first.username} - ${first.detail}`);
      }
      setSelectedUsernames([]);
      load();
    } catch (e: any) {
      message.error(e.message || "Bulk operation failed");
    } finally {
      setBulkLoading(false);
    }
  };

  const selectedAsStrings = selectedUsernames.map(String);

  const openEdit = (user: TelmtUser) => {
    setEditUser(user);
    editForm.setFieldsValue({
      user_ad_tag: user.user_ad_tag || undefined,
      max_tcp_conns: user.max_tcp_conns,
      max_unique_ips: user.max_unique_ips,
      data_quota_bytes: user.data_quota_bytes,
      rate_limit_up_bps: user.rate_limit_up_bps,
      rate_limit_down_bps: user.rate_limit_down_bps,
      expiration: user.expiration_rfc3339 ? dayjs(user.expiration_rfc3339) : undefined,
    });
  };

  const renderUserLimits = (user: TelmtUser) => (
    <Space wrap size={4}>
      {user.max_tcp_conns != null && <Tag>TCP: {user.max_tcp_conns}</Tag>}
      {user.max_unique_ips != null && <Tag>IPs: {user.max_unique_ips}</Tag>}
      {user.data_quota_bytes != null && <Tag>Quota: {formatBytes(user.data_quota_bytes)}</Tag>}
      {user.rate_limit_up_bps != null && <Tag color="purple">UP: {formatBytes(user.rate_limit_up_bps / 8)}/s</Tag>}
      {user.rate_limit_down_bps != null && <Tag color="purple">DOWN: {formatBytes(user.rate_limit_down_bps / 8)}/s</Tag>}
      {user.expiration_rfc3339 && (
        <Tag color={dayjs(user.expiration_rfc3339).isBefore(dayjs()) ? "red" : "blue"}>
          Exp: {dayjs(user.expiration_rfc3339).format("DD.MM.YY")}
        </Tag>
      )}
      {!user.max_tcp_conns && !user.max_unique_ips && !user.data_quota_bytes && !user.expiration_rfc3339 && (
        <span style={{ color: "rgba(255,255,255,0.3)" }}>No limits</span>
      )}
    </Space>
  );

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
      render: (_: any, r: TelmtUser) => renderUserLimits(r),
    },
    {
      title: "",
      key: "actions",
      width: 220,
      render: (_: any, r: TelmtUser) => (
        <Space size={4}>
          <Tooltip title="Links">
            <Button type="text" size="small" icon={<LinkOutlined />} onClick={() => setLinksUser(r)} />
          </Tooltip>
          <Tooltip title="Edit">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          </Tooltip>
          <Tooltip title="Rotate Secret">
            <Button type="text" size="small" icon={<KeyOutlined />} onClick={() => handleRotateSecret(r.username)} />
          </Tooltip>
          <Tooltip title="Enable user">
            <Button type="text" size="small" icon={<PlayCircleOutlined />} onClick={() => handleEnableUser(r.username)} />
          </Tooltip>
          <Tooltip title="Disable user">
            <Button type="text" size="small" icon={<PauseCircleOutlined />} onClick={() => handleDisableUser(r.username)} />
          </Tooltip>
          <Tooltip title="Reset Quota">
            <Button type="text" size="small" onClick={() => handleResetQuota(r.username)}>
              RQ
            </Button>
          </Tooltip>
          <Popconfirm title={`Delete ${r.username}?`} onConfirm={() => handleDelete(r.username)} okText="Delete" okButtonProps={{ danger: true }}>
            <Button type="text" size="small" icon={<DeleteOutlined />} danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const toggleUserSelection = (username: string, checked: boolean) => {
    setSelectedUsernames((prev) =>
      checked ? [...prev, username] : prev.filter((k) => String(k) !== username),
    );
  };

  const toggleSelectAll = (checked: boolean) => {
    setSelectedUsernames(checked ? users.map((u) => u.username) : []);
  };

  const renderUserMobile = (user: TelmtUser) => {
    const selected = selectedUsernames.some((k) => String(k) === user.username);
    return (
      <Card
        key={user.username}
        size="small"
        style={{
          marginBottom: 8,
          borderColor: selected ? "rgba(124,156,255,0.55)" : undefined,
        }}
        title={
          <Space>
            <Checkbox
              checked={selected}
              onChange={(e) => toggleUserSelection(user.username, e.target.checked)}
            />
            <Badge status={user.in_runtime ? "success" : "default"} />
            <span style={{ wordBreak: "break-all" }}>{user.username}</span>
          </Space>
        }
        extra={
          <Dropdown
            menu={{
              items: [
                { key: "links", icon: <LinkOutlined />, label: "Links", onClick: () => setLinksUser(user) },
                { key: "edit", icon: <EditOutlined />, label: "Edit", onClick: () => openEdit(user) },
                { key: "rotate", icon: <KeyOutlined />, label: "Rotate Secret", onClick: () => handleRotateSecret(user.username) },
                { key: "enable", icon: <PlayCircleOutlined />, label: "Enable", onClick: () => handleEnableUser(user.username) },
                { key: "disable", icon: <PauseCircleOutlined />, label: "Disable", onClick: () => handleDisableUser(user.username) },
                { key: "reset-quota", label: "Reset Quota", onClick: () => handleResetQuota(user.username) },
                { type: "divider" },
                {
                  key: "delete",
                  icon: <DeleteOutlined />,
                  label: "Delete",
                  danger: true,
                  onClick: () => {
                    modal.confirm({
                      title: `Delete ${user.username}?`,
                      okText: "Delete",
                      okButtonProps: { danger: true },
                      onOk: () => handleDelete(user.username),
                    });
                  },
                },
              ],
            }}
            trigger={["click"]}
          >
            <Button type="text" size="small" icon={<MoreOutlined />} />
          </Dropdown>
        }
      >
        <Row gutter={[8, 8]}>
          <Col span={8}>
            <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>Conns</span>
            <div>{user.current_connections}</div>
          </Col>
          <Col span={8}>
            <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>IPs</span>
            <div>{user.active_unique_ips}</div>
          </Col>
          <Col span={8}>
            <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 11 }}>Traffic</span>
            <div>{formatBytes(user.total_octets)}</div>
          </Col>
          <Col span={24}>{renderUserLimits(user)}</Col>
        </Row>
      </Card>
    );
  };

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
      <Form.Item name="rate_limit_up_bps" label="Rate Limit Up (bps)">
        <InputNumber min={1} style={{ width: "100%" }} placeholder="No limit" />
      </Form.Item>
      <Form.Item name="rate_limit_down_bps" label="Rate Limit Down (bps)">
        <InputNumber min={1} style={{ width: "100%" }} placeholder="No limit" />
      </Form.Item>
      <Form.Item name="expiration" label="Expiration">
        <DatePicker showTime style={{ width: "100%" }} />
      </Form.Item>
    </>
  );

  const bulkToolbar = (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Space wrap style={{ width: "100%" }}>
        {isMobile && (
          <Checkbox
            checked={users.length > 0 && selectedUsernames.length === users.length}
            indeterminate={selectedUsernames.length > 0 && selectedUsernames.length < users.length}
            onChange={(e) => toggleSelectAll(e.target.checked)}
          >
            Select all
          </Checkbox>
        )}
        <Typography.Text type="secondary">
          Selected: {selectedUsernames.length}
        </Typography.Text>
        <Popconfirm
          title={`Delete ${selectedUsernames.length} users?`}
          onConfirm={() => runBulk("/telemt/users/bulk-delete", { usernames: selectedAsStrings }, "Bulk delete")}
          disabled={!selectedUsernames.length}
        >
          <Button danger disabled={!selectedUsernames.length} loading={bulkLoading} block={isMobile}>
            Bulk Delete
          </Button>
        </Popconfirm>
        <Button disabled={!selectedUsernames.length} loading={bulkLoading} onClick={() => setBulkExtendOpen(true)} block={isMobile}>
          Bulk Extend
        </Button>
        <Button disabled={!selectedUsernames.length} loading={bulkLoading} onClick={() => runBulk("/telemt/users/bulk-rotate-secret", { usernames: selectedAsStrings }, "Bulk reissue secret")} block={isMobile}>
          Bulk Reissue Secret
        </Button>
        <Button disabled={!selectedUsernames.length} loading={bulkLoading} onClick={() => runBulk("/telemt/users/bulk-enable", { usernames: selectedAsStrings }, "Bulk enable")} block={isMobile}>
          Bulk Enable
        </Button>
        <Button disabled={!selectedUsernames.length} loading={bulkLoading} onClick={() => runBulk("/telemt/users/bulk-disable", { usernames: selectedAsStrings }, "Bulk disable")} block={isMobile}>
          Bulk Disable
        </Button>
        <Button disabled={!selectedUsernames.length} loading={bulkLoading} onClick={() => setBulkLimitsOpen(true)} block={isMobile}>
          Bulk Update Limits
        </Button>
      </Space>
    </Card>
  );

  return (
    <div>
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          flexDirection: isMobile ? "column" : "row",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <Button icon={<PlusOutlined />} type="primary" onClick={() => setCreateOpen(true)} block={isMobile}>
          Add User
        </Button>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading} block={isMobile}>
          Refresh
        </Button>
      </div>

      {bulkToolbar}

      {isMobile ? (
        loading ? (
          <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
        ) : users.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
            No users
          </div>
        ) : (
          users.map(renderUserMobile)
        )
      ) : (
        <Card>
          <Table
            rowKey="username"
            rowSelection={{
              selectedRowKeys: selectedUsernames,
              onChange: (keys) => setSelectedUsernames(keys),
            }}
            columns={columns}
            dataSource={users}
            loading={loading}
            pagination={false}
            size="small"
            scroll={{ x: 700 }}
          />
        </Card>
      )}

      <Modal
        title="Create Telemt User"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        onOk={() => createForm.submit()}
        okText="Create"
        {...mobileModalProps(isMobile)}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          {userFormFields(true)}
        </Form>
      </Modal>

      <Modal
        title={`Edit ${editUser?.username}`}
        open={!!editUser}
        onCancel={() => { setEditUser(null); editForm.resetFields(); }}
        onOk={() => editForm.submit()}
        okText="Save"
        {...mobileModalProps(isMobile)}
      >
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          {userFormFields(false)}
        </Form>
      </Modal>

      <Modal
        title={`Links for ${linksUser?.username}`}
        open={!!linksUser}
        onCancel={() => setLinksUser(null)}
        footer={null}
        {...mobileModalProps(isMobile)}
        width={isMobile ? "100%" : 600}
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

      <Modal
        title={`Bulk Extend (${selectedUsernames.length} users)`}
        open={bulkExtendOpen}
        onCancel={() => {
          setBulkExtendOpen(false);
          bulkExtendForm.resetFields();
        }}
        onOk={() => bulkExtendForm.submit()}
        okText="Apply"
        confirmLoading={bulkLoading}
        {...mobileModalProps(isMobile)}
      >
        <Form
          form={bulkExtendForm}
          layout="vertical"
          onFinish={(values) => {
            runBulk(
              "/telemt/users/bulk-extend",
              {
                usernames: selectedAsStrings,
                expiration_rfc3339: values.expiration.toISOString(),
              },
              "Bulk extend",
            );
            setBulkExtendOpen(false);
            bulkExtendForm.resetFields();
          }}
        >
          <Form.Item
            name="expiration"
            label="New Expiration"
            rules={[{ required: true, message: "Expiration is required" }]}
          >
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`Bulk Update Limits (${selectedUsernames.length} users)`}
        open={bulkLimitsOpen}
        onCancel={() => {
          setBulkLimitsOpen(false);
          bulkLimitsForm.resetFields();
        }}
        onOk={() => bulkLimitsForm.submit()}
        okText="Apply"
        confirmLoading={bulkLoading}
        {...mobileModalProps(isMobile)}
      >
        <Form
          form={bulkLimitsForm}
          layout="vertical"
          onFinish={(values) => {
            const payload: any = { usernames: selectedAsStrings };
            if (values.max_tcp_conns != null) payload.max_tcp_conns = values.max_tcp_conns;
            if (values.max_unique_ips != null) payload.max_unique_ips = values.max_unique_ips;
            if (values.data_quota_bytes != null) payload.data_quota_bytes = values.data_quota_bytes;
            if (values.rate_limit_up_bps != null) payload.rate_limit_up_bps = values.rate_limit_up_bps;
            if (values.rate_limit_down_bps != null) payload.rate_limit_down_bps = values.rate_limit_down_bps;
            runBulk("/telemt/users/bulk-update-limits", payload, "Bulk update limits");
            setBulkLimitsOpen(false);
            bulkLimitsForm.resetFields();
          }}
        >
          <Form.Item name="max_tcp_conns" label="Max TCP Connections">
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="max_unique_ips" label="Max Unique IPs">
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="data_quota_bytes" label="Data Quota (bytes)">
            <InputNumber min={0} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="rate_limit_up_bps" label="Rate Limit Up (bps)">
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="rate_limit_down_bps" label="Rate Limit Down (bps)">
            <InputNumber min={1} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ======================== Main Page ========================

// ======================== Free Params Tab ========================

function FreeParamsTab() {
  const isMobile = useIsMobile();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<TelmtFreeParams>("/telemt/free-params");
      form.setFieldsValue({
        max_tcp_conns: data.max_tcp_conns,
        max_unique_ips: data.max_unique_ips,
        data_quota_bytes: data.data_quota_bytes,
        expire_days: data.expire_days,
      });
    } catch {
      message.error("Failed to load free params");
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload: TelmtFreeParams = {
        max_tcp_conns: values.max_tcp_conns ?? null,
        max_unique_ips: values.max_unique_ips ?? null,
        data_quota_bytes: values.data_quota_bytes ?? null,
        expire_days: values.expire_days ?? 30,
      };
      await api.put("/telemt/free-params", payload);
      message.success("Free params saved");
    } catch {
      message.error("Failed to save free params");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Spin spinning={loading}>
      <Card
        title="Telemt Free User Parameters"
        extra={
          !isMobile ? (
            <Button type="primary" loading={saving} onClick={onSave}>
              Save
            </Button>
          ) : undefined
        }
        style={{ maxWidth: isMobile ? "100%" : 600 }}
      >
        <Typography.Paragraph type="secondary">
          These parameters are used when creating a free Telemt user via the bot
          (channel subscription reward).
        </Typography.Paragraph>
        <Form form={form} layout="vertical">
          <Form.Item
            name="expire_days"
            label="Expire Days"
            tooltip="Number of days added to current date for account expiration"
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={1} max={3650} style={{ width: "100%" }} placeholder="30" />
          </Form.Item>
          <Form.Item
            name="max_tcp_conns"
            label="Max TCP Connections"
            tooltip="Maximum concurrent TCP connections (leave empty for unlimited)"
          >
            <InputNumber min={1} style={{ width: "100%" }} placeholder="Unlimited" />
          </Form.Item>
          <Form.Item
            name="max_unique_ips"
            label="Max Unique IPs"
            tooltip="Maximum unique source IPs allowed (leave empty for unlimited)"
          >
            <InputNumber min={1} style={{ width: "100%" }} placeholder="Unlimited" />
          </Form.Item>
          <Form.Item
            name="data_quota_bytes"
            label="Data Quota (bytes)"
            tooltip="Maximum data usage in bytes (leave empty for unlimited)"
          >
            <InputNumber min={0} style={{ width: "100%" }} placeholder="Unlimited" />
          </Form.Item>
        </Form>
        {isMobile && (
          <Button type="primary" loading={saving} onClick={onSave} block>
            Save
          </Button>
        )}
      </Card>
    </Spin>
  );
}

function OperationsTab() {
  const isMobile = useIsMobile();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [healthReady, setHealthReady] = useState<TelmtHealthReady | null>(null);
  const [limits, setLimits] = useState<TelmtLimitsEffective | null>(null);
  const [whitelist, setWhitelist] = useState<TelmtSecurityWhitelist | null>(null);
  const [connSummary, setConnSummary] = useState<TelmtRuntimeConnectionsSummary | null>(null);
  const [recentEvents, setRecentEvents] = useState<TelmtRuntimeRecentEvents | null>(null);
  const [fingerprints, setFingerprints] = useState<TelmtTlsFingerprints | null>(null);
  const [quota, setQuota] = useState<TelmtUsersQuotaResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api.get<TelmtEnvelope<TelmtHealthReady>>("/telemt/health/ready"),
      api.get<TelmtEnvelope<TelmtLimitsEffective>>("/telemt/limits/effective"),
      api.get<TelmtEnvelope<TelmtSecurityWhitelist>>("/telemt/security/whitelist"),
      api.get<TelmtEnvelope<TelmtRuntimeConnectionsSummary>>("/telemt/runtime/connections/summary"),
      api.get<TelmtEnvelope<TelmtRuntimeRecentEvents>>("/telemt/runtime/events/recent"),
      api.get<TelmtEnvelope<TelmtTlsFingerprints>>("/telemt/runtime/tls-fingerprints"),
      api.get<TelmtEnvelope<TelmtUsersQuotaResponse>>("/telemt/users/quota"),
    ]);

    const pick = <T,>(idx: number): T | null =>
      results[idx].status === "fulfilled" ? (results[idx] as PromiseFulfilledResult<T>).value : null;

    setHealthReady(pick<TelmtEnvelope<TelmtHealthReady>>(0)?.data ?? null);
    setLimits(pick<TelmtEnvelope<TelmtLimitsEffective>>(1)?.data ?? null);
    setWhitelist(pick<TelmtEnvelope<TelmtSecurityWhitelist>>(2)?.data ?? null);
    setConnSummary(pick<TelmtEnvelope<TelmtRuntimeConnectionsSummary>>(3)?.data ?? null);
    setRecentEvents(pick<TelmtEnvelope<TelmtRuntimeRecentEvents>>(4)?.data ?? null);
    setFingerprints(pick<TelmtEnvelope<TelmtTlsFingerprints>>(5)?.data ?? null);
    setQuota(pick<TelmtEnvelope<TelmtUsersQuotaResponse>>(6)?.data ?? null);

    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed === results.length) {
      message.error("Failed to load telemt operations data");
    } else if (failed > 0) {
      message.warning(`Some telemt operations endpoints are unavailable (${failed}/${results.length})`);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const jsonBlock = (value: unknown) => (
    <pre
      style={{
        margin: 0,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        fontSize: isMobile ? 11 : 12,
        maxHeight: isMobile ? 220 : 360,
        overflow: "auto",
      }}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  );

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "flex-end" }}>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading} block={isMobile}>
          Refresh
        </Button>
      </div>
      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]}>
        <Col xs={24} sm={12} lg={8}>
          <Card title="Readiness" size={isMobile ? "small" : "default"}>
            <Space direction="vertical">
              <Tag color={healthReady?.ready ? "green" : "red"}>
                {healthReady?.ready ? "Ready" : "Not ready"}
              </Tag>
              {healthReady?.reason && <Typography.Text type="secondary">{healthReady.reason}</Typography.Text>}
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card title="Quota Users" size={isMobile ? "small" : "default"}>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {quota?.users?.length ?? 0}
            </Typography.Title>
            <Typography.Text type="secondary">users with configured quota</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card title="Recent Events" size={isMobile ? "small" : "default"}>
            <Typography.Title level={4} style={{ margin: 0 }}>
              {recentEvents?.events?.length ?? 0}
            </Typography.Title>
            <Typography.Text type="secondary">recent runtime events</Typography.Text>
          </Card>
        </Col>
      </Row>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginTop: isMobile ? 8 : 8 }}>
        <Col xs={24} lg={12}>
          <Card title="Effective Limits" size={isMobile ? "small" : "default"}>
            {jsonBlock(limits)}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Security Whitelist" size={isMobile ? "small" : "default"}>
            {jsonBlock(whitelist)}
          </Card>
        </Col>
      </Row>

      <Row gutter={[isMobile ? 8 : 16, isMobile ? 8 : 16]} style={{ marginTop: 8 }}>
        <Col xs={24} lg={12}>
          <Card title="Connections Summary" size={isMobile ? "small" : "default"}>
            {jsonBlock(connSummary)}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="TLS Fingerprints" size={isMobile ? "small" : "default"}>
            {jsonBlock(fingerprints)}
          </Card>
        </Col>
      </Row>
    </div>
  );
}

const EDITABLE_CONFIG_SECTIONS: TelmtConfigSectionName[] = [
  "general",
  "timeouts",
  "censorship",
  "upstreams",
  "show_link",
  "dc_overrides",
];

function ConfigTab() {
  const isMobile = useIsMobile();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState<string>("");
  const [editorText, setEditorText] = useState("{}");
  const [lastPatch, setLastPatch] = useState<TelmtPatchConfigResponse | null>(null);

  const load = useCallback(async (clearPatch = true) => {
    setLoading(true);
    if (clearPatch) setLastPatch(null);
    try {
      const r = await api.get<TelmtEnvelope<TelmtConfigData>>("/telemt/config");
      const data = r.data ?? {};
      const editable: TelmtConfigData = {};
      for (const key of EDITABLE_CONFIG_SECTIONS) {
        if (data[key] != null) editable[key] = data[key];
      }
      setEditorText(JSON.stringify(editable, null, 2));
      setRevision(r.revision || "");
    } catch (e: any) {
      message.error(e.message || "Failed to load telemt config");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(editorText);
    } catch {
      message.error("Invalid JSON");
      return;
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      message.error("Config must be a JSON object");
      return;
    }

    const unknown = Object.keys(parsed).filter(
      (k) => !EDITABLE_CONFIG_SECTIONS.includes(k as TelmtConfigSectionName),
    );
    if (unknown.length) {
      message.error(`Non-editable keys: ${unknown.join(", ")}`);
      return;
    }

    const payload: Record<string, unknown> = { ...parsed };
    if (revision) payload.revision = revision;

    setSaving(true);
    try {
      const r = await api.patch<TelmtEnvelope<TelmtPatchConfigResponse>>("/telemt/config", payload);
      const result = r.data;
      await load(false);
      if (result) {
        setLastPatch(result);
        if (result.revision) setRevision(result.revision);
      }
      message.success(
        result?.restart_required
          ? `Config saved (restart required). Changed: ${(result.changed || []).join(", ") || "—"}`
          : `Config saved. Changed: ${(result?.changed || []).join(", ") || "—"}`,
      );
    } catch (e: any) {
      message.error(e.message || "Failed to patch telemt config");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Spin spinning={loading}>
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <Alert
          type="info"
          showIcon
          message="Editable sections only"
          description={
            <>
              Allowed keys: <code>{EDITABLE_CONFIG_SECTIONS.join(", ")}</code>.
              Users/secrets (<code>access</code>), <code>server</code> and <code>network</code> are not editable here.
              Save uses optimistic concurrency via <code>If-Match</code> revision.
            </>
          }
        />

        <Card
          size={isMobile ? "small" : "default"}
          title="Telemt Config"
          extra={
            <Space wrap>
              {revision && (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  rev: {revision.slice(0, 12)}…
                </Typography.Text>
              )}
              <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
                Reload
              </Button>
              {!isMobile && (
                <Button type="primary" onClick={onSave} loading={saving}>
                  Save Patch
                </Button>
              )}
            </Space>
          }
        >
          {lastPatch?.restart_required && (
            <Alert
              style={{ marginBottom: 12 }}
              type="warning"
              showIcon
              message="Restart required"
              description={`Changed sections: ${(lastPatch.changed || []).join(", ") || "—"}. Telemt wrote the config, but some fields need a process restart.`}
            />
          )}
          <Input.TextArea
            value={editorText}
            onChange={(e) => setEditorText(e.target.value)}
            autoSize={{ minRows: isMobile ? 14 : 22, maxRows: isMobile ? 28 : 40 }}
            style={{
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              fontSize: isMobile ? 12 : 13,
            }}
            spellCheck={false}
          />
          {isMobile && (
            <Button type="primary" onClick={onSave} loading={saving} block style={{ marginTop: 12 }}>
              Save Patch
            </Button>
          )}
        </Card>
      </Space>
    </Spin>
  );
}

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
        size={isMobile ? "small" : "middle"}
        tabBarGutter={isMobile ? 8 : undefined}
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
          {
            key: "free-params",
            label: (
              <span>
                <SettingOutlined /> {isMobile ? "Free" : "Free Params"}
              </span>
            ),
            children: <FreeParamsTab />,
          },
          {
            key: "config",
            label: (
              <span>
                <SettingOutlined /> Config
              </span>
            ),
            children: <ConfigTab />,
          },
          {
            key: "operations",
            label: (
              <span>
                <CloudServerOutlined /> {isMobile ? "Ops" : "Operations"}
              </span>
            ),
            children: <OperationsTab />,
          },
        ]}
      />
    </div>
  );
}
