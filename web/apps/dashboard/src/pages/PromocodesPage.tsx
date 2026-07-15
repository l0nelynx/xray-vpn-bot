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
} from "@ant-design/icons";
import { api } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";
import useDebounce from "../hooks/useDebounce";
import MobileSortControl, { SortOrder } from "../components/MobileSortControl";
import { makePaginatedTableChange } from "../utils/tableChange";

type PromoType = "referral" | "promotional";

const PROMO_SORT_OPTIONS = [
  { value: "promo_code", label: "Code" },
  { value: "promo_type", label: "Type" },
  { value: "owner_username", label: "Owner" },
  { value: "credit_grant", label: "Credits" },
  { value: "usage_count", label: "Usage" },
  { value: "days_purchased", label: "Days bought" },
  { value: "days_rewarded", label: "Rewarded" },
];

interface PromoItem {
  promo_code: string;
  promo_type: PromoType;
  owner_username: string | null;
  owner_tg_id: number;
  usage_count: number;
  days_purchased: number;
  days_rewarded: number;
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
  days_reward_per_30: number;
  reward_cap_days: number;
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
      title: "Credits",
      dataIndex: "credit_grant",
      key: "credit_grant",
      width: 120,
      sorter: true,
      sortOrder: sortOrderFor("credit_grant"),
      render: (v: number | null) =>
        v == null ? <Tag>default</Tag> : <Tag color="green">{v} d</Tag>,
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
      title: "Days bought",
      dataIndex: "days_purchased",
      key: "days_purchased",
      width: 110,
      sorter: true,
      sortOrder: sortOrderFor("days_purchased"),
    },
    {
      title: "Rewarded",
      dataIndex: "days_rewarded",
      key: "days_rewarded",
      width: 110,
      sorter: true,
      sortOrder: sortOrderFor("days_rewarded"),
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

  return (
    <div>
      <div
        style={{
          marginBottom: 16,
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <Button
          icon={<PlusOutlined />}
          type="primary"
          onClick={() => setCreateOpen(true)}
        >
          Create Promo
        </Button>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
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

      {isMobile && (
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
      )}

      <Card>
        <Table
          rowKey="promo_code"
          columns={columns}
          dataSource={items}
          loading={loading}
          onChange={handleTableChange}
          size={isMobile ? "small" : "middle"}
          scroll={{ x: 700 }}
          pagination={{
            current: page,
            pageSize: 20,
            total,
            showSizeChanger: false,
          }}
        />
      </Card>

      <Modal
        title="Create Promo Code"
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="Create"
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
            label="Credit grant (days)"
            tooltip="Leave empty to use default from Settings"
          >
            <InputNumber min={0} max={3650} style={{ width: "100%" }} placeholder="default" />
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
        days_reward_per_30: r.days_reward_per_30,
        reward_cap_days: r.reward_cap_days,
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
        days_reward_per_30: values.days_reward_per_30,
        reward_cap_days: values.reward_cap_days,
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
          <Button type="primary" loading={saving} onClick={onSave}>
            Save
          </Button>
        }
        style={{ maxWidth: 600 }}
      >
        <Typography.Paragraph type="secondary">
          Default credits (days) granted by promo codes without a per-code override.
          Reward settings control referral owner bonus days.
        </Typography.Paragraph>
        <Form form={form} layout="vertical">
          <Form.Item
            name="default_credit_grant"
            label="Default credit grant (days)"
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={3650} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="days_reward_per_30"
            label="Reward days per 30 days purchased"
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={365} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item
            name="reward_cap_days"
            label="Reward cap (days)"
            tooltip="Maximum cumulative bonus days a single referral owner can ever earn."
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={3650} style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Card>
    </Spin>
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
        ]}
      />
    </div>
  );
}
