import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
  App,
} from "antd";
import type { TableProps } from "antd";
import {
  DeleteOutlined,
  GiftOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SettingOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";
import useDebounce from "../hooks/useDebounce";
import MobileSortControl, { SortOrder } from "../components/MobileSortControl";
import { makePaginatedTableChange } from "../utils/tableChange";
import { formatPoints, POINTS_ICON } from "../points";

type PromoType = "referral" | "promotional";

const PROMO_SORT_OPTIONS = [
  { value: "promo_code", label: "Code" },
  { value: "promo_type", label: "Type" },
  { value: "owner_username", label: "Owner" },
  { value: "credit_grant", label: "Points (🪙)" },
  { value: "usage_count", label: "Usage" },
  { value: "days_purchased", label: "Invitee days bought" },
  { value: "points_rewarded", label: "Owner reward (🪙)" },
];

interface PromoItem {
  promo_code: string;
  promo_type: PromoType;
  owner_username: string | null;
  owner_tg_id: number;
  usage_count: number;
  days_purchased: number;
  points_rewarded: number;
  credit_grant: number | null;
}

interface PromosListResponse {
  items: PromoItem[];
  total: number;
  page: number;
  per_page: number;
}

interface PromoSettings {
  default_credit_grant: number;
  points_reward_per_30: number;
  reward_cap_points: number;
}

function PromosTab() {
  const isMobile = useIsMobile();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<PromoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sort, setSort] = useState("id");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();
  const debouncedSearch = useDebounce(search, 400);

  const load = useCallback(() => {
    setLoading(true);
    const url =
      `/promos?page=${page}&per_page=20&sort=${sort}&order=${order}` +
      `&type=${typeFilter}&search=${encodeURIComponent(debouncedSearch)}`;
    api
      .get<PromosListResponse>(url)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e: Error) => message.error(e.message || "Failed to load promos"))
      .finally(() => setLoading(false));
  }, [page, sort, order, typeFilter, debouncedSearch]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (values: {
    promo_code: string;
    credit_grant?: number;
    owner_tg_id?: number;
    promo_type?: PromoType;
  }) => {
    try {
      await api.post("/promos", {
        promo_code: values.promo_code.trim().toUpperCase(),
        credit_grant: values.credit_grant ?? null,
        owner_tg_id: values.owner_tg_id ?? null,
        promo_type: values.promo_type ?? "promotional",
      });
      message.success("Promo created");
      setCreateOpen(false);
      form.resetFields();
      load();
    } catch (e) {
      message.error((e as Error).message || "Failed to create promo");
    }
  };

  const handleDelete = async (code: string) => {
    try {
      await api.delete(`/promos/${encodeURIComponent(code)}`);
      message.success(`Promo ${code} deleted`);
      load();
    } catch (e) {
      message.error((e as Error).message || "Failed to delete");
    }
  };

  const sortOrderFor = (key: string) =>
    sort === key ? (order === "asc" ? "ascend" : "descend") : null;

  const columns: TableProps<PromoItem>["columns"] = [
    {
      title: "Code",
      dataIndex: "promo_code",
      key: "promo_code",
      sorter: true,
      sortOrder: sortOrderFor("promo_code"),
      render: (v: string) => <Typography.Text strong>{v}</Typography.Text>,
    },
    {
      title: "Type",
      dataIndex: "promo_type",
      key: "promo_type",
      width: 120,
      sorter: true,
      sortOrder: sortOrderFor("promo_type"),
      render: (v: PromoType) =>
        v === "referral" ? (
          <Tag color="purple">Referral</Tag>
        ) : (
          <Tag color="blue">Promotional</Tag>
        ),
    },
    {
      title: "Owner",
      key: "owner_username",
      sorter: true,
      sortOrder: sortOrderFor("owner_username"),
      render: (_: unknown, r: PromoItem) =>
        r.owner_username ? (
          <span>
            @{r.owner_username}{" "}
            <span style={{ color: "rgba(255,255,255,0.4)", fontSize: 12 }}>
              ({r.owner_tg_id})
            </span>
          </span>
        ) : (
          <span style={{ color: "rgba(255,255,255,0.3)" }}>—</span>
        ),
    },
    {
      title: "Points (🪙)",
      dataIndex: "credit_grant",
      key: "credit_grant",
      width: 120,
      sorter: true,
      sortOrder: sortOrderFor("credit_grant"),
      render: (v: number | null) =>
        v == null ? <Tag>default</Tag> : <Tag color="green">{formatPoints(v)}</Tag>,
    },
    {
      title: "Usage",
      dataIndex: "usage_count",
      key: "usage_count",
      width: 80,
      sorter: true,
      sortOrder: sortOrderFor("usage_count"),
    },
    {
      title: "Invitee days bought",
      dataIndex: "days_purchased",
      key: "days_purchased",
      width: 130,
      sorter: true,
      sortOrder: sortOrderFor("days_purchased"),
    },
    {
      title: "Owner reward (🪙)",
      dataIndex: "points_rewarded",
      key: "points_rewarded",
      width: 140,
      sorter: true,
      sortOrder: sortOrderFor("points_rewarded"),
      render: (v: number) => <Tag color="green">{formatPoints(v)}</Tag>,
    },
    {
      title: "",
      key: "actions",
      width: 60,
      render: (_: unknown, r: PromoItem) => (
        <Popconfirm
          title={`Delete promo ${r.promo_code}?`}
          onConfirm={() => handleDelete(r.promo_code)}
          okText="Delete"
          okButtonProps={{ danger: true }}
        >
          <Button type="text" size="small" icon={<DeleteOutlined />} danger />
        </Popconfirm>
      ),
    },
  ];

  const handleTableChange = makePaginatedTableChange<PromoItem>({
    page,
    sort,
    order,
    setPage,
    setSort,
    setOrder,
  });

  const perPage = 20;

  const renderMobileCard = (promo: PromoItem) => (
    <Card
      key={promo.promo_code}
      size="small"
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: "12px" } }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              color: "rgba(255,255,255,0.88)",
              marginBottom: 4,
              wordBreak: "break-all",
            }}
          >
            {promo.promo_code}
          </div>
          <div style={{ marginBottom: 6 }}>
            {promo.promo_type === "referral" ? (
              <Tag color="purple" style={{ margin: 0 }}>Referral</Tag>
            ) : (
              <Tag color="blue" style={{ margin: 0 }}>Promotional</Tag>
            )}
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 4 }}>
            {promo.owner_username
              ? `@${promo.owner_username} (${promo.owner_tg_id})`
              : "No owner"}
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.55)" }}>
            {promo.credit_grant == null ? "Points: default" : `Points: ${formatPoints(promo.credit_grant)}`}
            {" · "}
            Usage: {promo.usage_count}
          </div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginTop: 2 }}>
            Invitee days: {promo.days_purchased} · Owner reward: {formatPoints(promo.points_rewarded)}
          </div>
        </div>
        <Popconfirm
          title={`Delete promo ${promo.promo_code}?`}
          onConfirm={() => handleDelete(promo.promo_code)}
          okText="Delete"
          okButtonProps={{ danger: true }}
        >
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </div>
    </Card>
  );

  return (
    <div>
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          justifyContent: isMobile ? "stretch" : "space-between",
        }}
      >
        <Button
          icon={<PlusOutlined />}
          type="primary"
          onClick={() => setCreateOpen(true)}
          block={isMobile}
        >
          Create Promo
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={load}
          loading={loading}
          block={isMobile}
        >
          Refresh
        </Button>
      </div>

      <div style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", gap: 8 }}>
        <Input
          placeholder="Search by code or owner"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          style={{ flex: 1, minWidth: isMobile ? "100%" : 220, maxWidth: isMobile ? "100%" : 280 }}
          allowClear
        />
        <Select
          value={typeFilter}
          onChange={(v) => {
            setTypeFilter(v);
            setPage(1);
          }}
          style={{ width: isMobile ? "100%" : 160 }}
          options={[
            { value: "all", label: "All types" },
            { value: "promotional", label: "Promotional" },
            { value: "referral", label: "Referral" },
          ]}
        />
      </div>

      {isMobile ? (
        <>
          <MobileSortControl
            options={PROMO_SORT_OPTIONS}
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
              Loading...
            </div>
          ) : items.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
              No promocodes
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
        <Card>
          <Table
            rowKey="promo_code"
            columns={columns}
            dataSource={items}
            loading={loading}
            onChange={handleTableChange}
            size="middle"
            scroll={{ x: 700 }}
            pagination={{
              current: page,
              pageSize: perPage,
              total,
              showSizeChanger: false,
            }}
          />
        </Card>
      )}

      <Modal
        title="Create Promo Code"
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="Create"
        width={isMobile ? "100%" : undefined}
        style={isMobile ? { top: 16, maxWidth: "calc(100vw - 16px)", margin: "0 auto" } : undefined}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ promo_type: "promotional" }}
        >
          <Form.Item
            name="promo_code"
            label="Code"
            rules={[
              { required: true, message: "Required" },
              { max: 20, message: "Max 20 chars" },
              {
                pattern: /^[A-Za-z0-9_-]+$/,
                message: "Letters, digits, _ and - only",
              },
            ]}
          >
            <Input placeholder="SUMMER25" autoFocus />
          </Form.Item>
          <Form.Item
            name="promo_type"
            label="Type"
            tooltip="Promotional: anyone, each code once per user. Referral: new users only, one referral code ever per user."
          >
            <Select
              options={[
                { value: "promotional", label: "Promotional" },
                { value: "referral", label: "Referral" },
              ]}
            />
          </Form.Item>
          <Form.Item
            name="credit_grant"
            label={`Credit grant (${POINTS_ICON} points)`}
            tooltip={`Bonus points credited to the user when they activate this code. Empty = use default from Settings.`}
          >
            <InputNumber min={0} max={3650} style={{ width: "100%" }} placeholder="default" addonAfter={POINTS_ICON} />
          </Form.Item>
          <Form.Item
            name="owner_tg_id"
            label="Owner tg_id"
            tooltip="Optional. Links the promo to a specific user for referral rewards. Leave empty for stand-alone promos."
          >
            <InputNumber style={{ width: "100%" }} placeholder="empty for stand-alone" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

function SettingsTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const { message } = App.useApp();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get<PromoSettings>("/promos/settings");
      form.setFieldsValue({
        default_credit_grant: r.default_credit_grant,
        points_reward_per_30: r.points_reward_per_30,
        reward_cap_points: r.reward_cap_points,
      });
    } catch (e) {
      message.error((e as Error).message || "Failed to load settings");
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
      await api.put("/promos/settings", {
        default_credit_grant: values.default_credit_grant,
        points_reward_per_30: values.points_reward_per_30,
        reward_cap_points: values.reward_cap_points,
      });
      message.success("Settings saved");
    } catch (e) {
      message.error((e as Error).message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Spin spinning={loading}>
      <Card
        title="Promo Settings"
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
          Все бонусы — в баллах {POINTS_ICON}. <strong>Default credit grant</strong> — сколько
          получает пользователь при активации кода. <strong>Owner reward per 30 days</strong> —
          сколько баллов начисляется владельцу рефкода за каждые 30 дней покупок приглашённых.
          <strong> Reward cap</strong> — максимум баллов владельцу с одного кода за всё время.
        </Typography.Paragraph>
        <Form form={form} layout="vertical">
          <Form.Item
            name="default_credit_grant"
            label={`Default credit grant (${POINTS_ICON})`}
            tooltip="Points credited to user balance on promo activation."
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={3650} style={{ width: "100%" }} addonAfter={POINTS_ICON} />
          </Form.Item>
          <Form.Item
            name="points_reward_per_30"
            label={`Owner reward per 30 invitee-days (${POINTS_ICON})`}
            tooltip="Bonus points credited to referral owner wallet per each 30 subscription-days purchased by invitees."
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={3650} style={{ width: "100%" }} addonAfter={POINTS_ICON} />
          </Form.Item>
          <Form.Item
            name="reward_cap_points"
            label={`Owner reward cap (${POINTS_ICON})`}
            tooltip="Maximum total bonus points one referral owner can earn from invitee purchases."
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={365_000} style={{ width: "100%" }} addonAfter={POINTS_ICON} />
          </Form.Item>
          {isMobile && (
            <Button type="primary" loading={saving} onClick={onSave} block>
              Save
            </Button>
          )}
        </Form>
      </Card>
    </Spin>
  );
}

type ReferralMetric = "total" | "paying";

interface ReferralStatItem {
  owner_tg_id: number;
  owner_username: string | null;
  promo_code: string;
  referral_count: number;
  paying_referral_count: number;
  days_purchased: number;
  points_rewarded: number;
}

const REFERRAL_SORT_OPTIONS = [
  { value: "referral_count", label: "Total referrals" },
  { value: "paying_referral_count", label: "Paying referrals" },
  { value: "owner_username", label: "Owner" },
  { value: "days_purchased", label: "Invitee days bought" },
  { value: "points_rewarded", label: "Owner reward" },
];

function ReferralStatsTab() {
  const isMobile = useIsMobile();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<ReferralStatItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [metric, setMetric] = useState<ReferralMetric>("total");
  const [sort, setSort] = useState("referral_count");
  const [order, setOrder] = useState<SortOrder>("desc");
  const debouncedSearch = useDebounce(search, 300);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: "20",
        sort,
        order,
        metric,
        search: debouncedSearch,
      });
      const data = await api.get<{
        items: ReferralStatItem[];
        total: number;
      }>(`/promos/referral-stats?${params}`);
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      message.error((e as Error).message || "Failed to load referral stats");
    } finally {
      setLoading(false);
    }
  }, [page, sort, order, metric, debouncedSearch, message]);

  useEffect(() => {
    load();
  }, [load]);

  const onMetricChange = (m: ReferralMetric) => {
    setMetric(m);
    setSort(m === "paying" ? "paying_referral_count" : "referral_count");
    setPage(1);
  };

  const columns: TableProps<ReferralStatItem>["columns"] = [
    {
      title: "#",
      key: "rank",
      width: 56,
      render: (_v, _r, index) => (page - 1) * 20 + index + 1,
    },
    {
      title: "Owner",
      key: "owner",
      render: (_v, r) => (
        <span>
          {r.owner_username ? `@${r.owner_username}` : "—"}{" "}
          <Typography.Text type="secondary">({r.owner_tg_id})</Typography.Text>
        </span>
      ),
    },
    { title: "Code", dataIndex: "promo_code", key: "promo_code" },
    {
      title: metric === "paying" ? "Paying referrals" : "Total referrals",
      key: "primary_metric",
      render: (_v, r) =>
        metric === "paying" ? r.paying_referral_count : r.referral_count,
      sorter: true,
    },
    {
      title: metric === "paying" ? "Total" : "Paying",
      key: "secondary_metric",
      render: (_v, r) => (
        <Typography.Text type="secondary">
          {metric === "paying" ? r.referral_count : r.paying_referral_count}
        </Typography.Text>
      ),
    },
    { title: "Invitee days", dataIndex: "days_purchased", key: "days_purchased", sorter: true },
    {
      title: `Owner reward (${POINTS_ICON})`,
      dataIndex: "points_rewarded",
      key: "points_rewarded",
      render: (v: number) => formatPoints(v),
      sorter: true,
    },
  ];

  const handleReferralTableChange = makePaginatedTableChange<ReferralStatItem>({
    page,
    sort,
    order,
    setPage,
    setSort,
    setOrder,
  });

  const perPage = 20;

  const renderMobileCard = (item: ReferralStatItem, index: number) => {
    const rank = (page - 1) * perPage + index + 1;
    const primary =
      metric === "paying" ? item.paying_referral_count : item.referral_count;
    const secondary =
      metric === "paying" ? item.referral_count : item.paying_referral_count;
    return (
      <Card
        key={item.owner_tg_id}
        size="small"
        style={{ marginBottom: 8 }}
        styles={{ body: { padding: "12px" } }}
      >
        <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
          <div
            style={{
              minWidth: 28,
              height: 28,
              borderRadius: 8,
              background: "rgba(255,255,255,0.06)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              color: "rgba(255,255,255,0.65)",
              fontWeight: 600,
            }}
          >
            {rank}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontWeight: 600,
                color: "rgba(255,255,255,0.88)",
                marginBottom: 2,
                wordBreak: "break-word",
              }}
            >
              {item.owner_username ? `@${item.owner_username}` : "—"}
            </div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 6 }}>
              {item.owner_tg_id} · <code>{item.promo_code}</code>
            </div>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.75)" }}>
              {metric === "paying" ? "Paying" : "Total"}: <strong>{primary}</strong>
              <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                {metric === "paying" ? "Total" : "Paying"}: {secondary}
              </Typography.Text>
            </div>
            <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginTop: 4 }}>
              Invitee days: {item.days_purchased} · Owner reward:{" "}
              {formatPoints(item.points_rewarded)}
            </div>
          </div>
        </div>
      </Card>
    );
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", flexWrap: "wrap", gap: 8 }}>
        <Select
          value={metric}
          onChange={onMetricChange}
          style={{ width: isMobile ? "100%" : 220 }}
          options={[
            { value: "total", label: "Top by total referrals" },
            { value: "paying", label: "Top by paying referrals" },
          ]}
        />
        <Input
          placeholder="Search code, username, tg_id"
          prefix={<SearchOutlined />}
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          style={{ flex: 1, minWidth: isMobile ? "100%" : 220, maxWidth: isMobile ? "100%" : 280 }}
          allowClear
        />
        <Button icon={<ReloadOutlined />} onClick={load} block={isMobile} loading={loading}>
          Refresh
        </Button>
      </div>

      {isMobile ? (
        <>
          <MobileSortControl
            options={REFERRAL_SORT_OPTIONS}
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
              Loading...
            </div>
          ) : items.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
              No referral stats
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
          rowKey="owner_tg_id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize: perPage,
            total,
            showSizeChanger: false,
          }}
          onChange={handleReferralTableChange}
          size="middle"
        />
      )}
    </div>
  );
}

export default function PromocodesPage() {
  const isMobile = useIsMobile();
  return (
    <div>
      <Typography.Title
        level={isMobile ? 5 : 4}
        style={{
          margin: 0,
          marginBottom: isMobile ? 12 : 20,
          color: "rgba(255,255,255,0.88)",
        }}
      >
        Promocodes
      </Typography.Title>
      <Tabs
        defaultActiveKey="list"
        size={isMobile ? "small" : "middle"}
        tabBarGutter={isMobile ? 12 : undefined}
        items={[
          {
            key: "list",
            label: (
              <span>
                <GiftOutlined /> Codes
              </span>
            ),
            children: <PromosTab />,
          },
          {
            key: "settings",
            label: (
              <span>
                <SettingOutlined /> Settings
              </span>
            ),
            children: <SettingsTab />,
          },
          {
            key: "referral-stats",
            label: (
              <span>
                <TrophyOutlined /> Referral stats
              </span>
            ),
            children: <ReferralStatsTab />,
          },
        ]}
      />
    </div>
  );
}
