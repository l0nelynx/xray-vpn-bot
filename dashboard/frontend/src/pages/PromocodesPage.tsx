import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  GiftOutlined,
  PlusOutlined,
  ReloadOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";

interface PromoItem {
  promo_code: string;
  owner_username: string | null;
  owner_tg_id: number;
  usage_count: number;
  days_purchased: number;
  days_rewarded: number;
  discount_percent: number | null;
}

interface PromosListResponse {
  items: PromoItem[];
  total: number;
  page: number;
  per_page: number;
}

interface PromoSettings {
  default_discount_percent: number;
}

function PromosTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<PromoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<PromosListResponse>(`/promos?page=${page}&per_page=20`)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e: Error) => message.error(e.message || "Failed to load promos"))
      .finally(() => setLoading(false));
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (values: {
    promo_code: string;
    discount_percent?: number;
    owner_tg_id?: number;
  }) => {
    try {
      await api.post("/promos", {
        promo_code: values.promo_code.trim().toUpperCase(),
        discount_percent: values.discount_percent ?? null,
        owner_tg_id: values.owner_tg_id ?? null,
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

  const columns = [
    {
      title: "Code",
      dataIndex: "promo_code",
      key: "promo_code",
      render: (v: string) => <Typography.Text strong>{v}</Typography.Text>,
    },
    {
      title: "Owner",
      key: "owner",
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
      title: "Discount",
      dataIndex: "discount_percent",
      key: "discount_percent",
      width: 120,
      render: (v: number | null) =>
        v == null ? (
          <Tag>default</Tag>
        ) : (
          <Tag color="green">{v}%</Tag>
        ),
    },
    {
      title: "Usage",
      dataIndex: "usage_count",
      key: "usage_count",
      width: 80,
    },
    {
      title: "Days bought",
      dataIndex: "days_purchased",
      key: "days_purchased",
      width: 110,
    },
    {
      title: "Rewarded",
      dataIndex: "days_rewarded",
      key: "days_rewarded",
      width: 110,
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
      <Card>
        <Table
          rowKey="promo_code"
          columns={columns}
          dataSource={items}
          loading={loading}
          size={isMobile ? "small" : "middle"}
          scroll={{ x: 700 }}
          pagination={{
            current: page,
            pageSize: 20,
            total,
            onChange: setPage,
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
        <Form form={form} layout="vertical" onFinish={handleCreate}>
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
            name="discount_percent"
            label="Discount %"
            tooltip="Leave empty to use the default discount from Settings"
          >
            <InputNumber min={0} max={100} style={{ width: "100%" }} placeholder="default" />
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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get<PromoSettings>("/promos/settings");
      form.setFieldsValue({ default_discount_percent: r.default_discount_percent });
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
        default_discount_percent: values.default_discount_percent,
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
          Default discount % is applied to promo codes that don't have a specific
          discount value set.
        </Typography.Paragraph>
        <Form form={form} layout="vertical">
          <Form.Item
            name="default_discount_percent"
            label="Default promo discount (%)"
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={100} style={{ width: "100%" }} />
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
