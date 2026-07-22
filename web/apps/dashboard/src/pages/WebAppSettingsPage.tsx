import { useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { api } from "../api/client";

interface FeatureFlags {
  legacy_bot_constructor: boolean;
}

interface Maintenance {
  enabled: boolean;
  title: string;
  text: string;
}

interface RuntimeResponse {
  maintenance: Maintenance;
  values: Record<string, unknown>;
  sources: Record<string, string>;
}

interface ProviderFieldMeta {
  name: string;
  secret: boolean;
}

interface PaymentProviderState {
  provider: string;
  enabled: boolean;
  managed: boolean;
  source: string;
  fields: Record<string, unknown>;
  field_meta: ProviderFieldMeta[];
  updated_at?: string | null;
}

const RUNTIME_LABELS: Record<string, string> = {
  branding_name: "Brand name",
  news_id: "News channel ID",
  news_url: "News URL",
  support_bot_id: "Support contact",
  agreement_url: "Agreement URL",
  policy_url: "Privacy policy URL",
  logs_id: "Logs chat ID",
  web_id: "Web portal chat ID",
  admin_logs_length: "Admin logs length",
  free_days: "Free plan days",
  free_traffic: "Free plan traffic (GB)",
};

function sourceTag(source: string) {
  const color =
    source === "dashboard" ? "green" : source === "yaml" ? "gold" : "default";
  return <Tag color={color}>{source}</Tag>;
}

export default function WebAppSettingsPage() {
  const { message } = App.useApp();
  const [flags, setFlags] = useState<FeatureFlags | null>(null);
  const [runtime, setRuntime] = useState<RuntimeResponse | null>(null);
  const [payments, setPayments] = useState<PaymentProviderState[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [runtimeForm] = Form.useForm();

  useEffect(() => {
    api
      .get<FeatureFlags>("/settings/features")
      .then(setFlags)
      .catch(() => message.error("Failed to load feature flags"));
    api
      .get<RuntimeResponse>("/settings/runtime")
      .then((data) => {
        setRuntime(data);
        runtimeForm.setFieldsValue({
          ...data.maintenance,
          ...data.values,
        });
      })
      .catch(() => message.error("Failed to load runtime settings"));
    api
      .get<{ providers: PaymentProviderState[] }>("/settings/payments")
      .then((data) => setPayments(data.providers))
      .catch(() => message.error("Failed to load payment integrations"));
  }, [message, runtimeForm]);

  async function handleToggle(value: boolean) {
    if (!flags) return;
    const updated = { ...flags, legacy_bot_constructor: value };
    setSaving(true);
    try {
      await api.put("/settings/features", updated);
      setFlags(updated);
      message.success(
        value
          ? "Legacy bot constructor enabled. Restart the bot to apply."
          : "Legacy bot constructor disabled. Restart the bot to apply."
      );
    } catch {
      message.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  async function saveRuntime() {
    const all = runtimeForm.getFieldsValue();
    setSaving(true);
    try {
      const payload = {
        maintenance: {
          enabled: !!all.enabled,
          title: all.title || "",
          text: all.text || "",
        },
        values: Object.fromEntries(
          Object.keys(RUNTIME_LABELS).map((k) => [k, all[k]])
        ),
      };
      const data = await api.put<RuntimeResponse>("/settings/runtime", payload);
      setRuntime(data);
      runtimeForm.setFieldsValue({ ...data.maintenance, ...data.values });
      message.success("Runtime settings saved (no restart needed)");
    } catch {
      message.error("Failed to save runtime settings");
    } finally {
      setSaving(false);
    }
  }

  async function saveProvider(provider: PaymentProviderState, values: Record<string, unknown>) {
    setSaving(true);
    try {
      const updated = await api.put<PaymentProviderState>(
        `/settings/payments/${provider.provider}`,
        {
          enabled: !!values.enabled,
          fields: Object.fromEntries(
            provider.field_meta.map((f) => [f.name, values[f.name]])
          ),
        }
      );
      setPayments((prev) =>
        (prev || []).map((p) => (p.provider === updated.provider ? updated : p))
      );
      message.success(`${provider.provider}: saved (Dashboard is now source of truth)`);
    } catch {
      message.error(`Failed to save ${provider.provider}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <Typography.Title level={3}>Settings</Typography.Title>
      <Typography.Paragraph type="secondary">
        Dual-source period: values saved here override{" "}
        <code>config.yml</code>. Until you save, YAML remains the fallback.
      </Typography.Paragraph>

      <Tabs
        items={[
          {
            key: "runtime",
            label: "Runtime",
            children: !runtime ? (
              <Spin />
            ) : (
              <Card
                title="Runtime & maintenance"
                extra={sourceTag(runtime.sources.maintenance || "db")}
              >
                <Form form={runtimeForm} layout="vertical" onFinish={saveRuntime}>
                  <Form.Item
                    name="enabled"
                    label="Maintenance mode"
                    valuePropName="checked"
                    help="Blocks MiniApp/web APIs and the user bot (admin bypass)."
                  >
                    <Switch checkedChildren="ON" unCheckedChildren="OFF" />
                  </Form.Item>
                  <Form.Item name="title" label="Maintenance title">
                    <Input />
                  </Form.Item>
                  <Form.Item name="text" label="Maintenance text">
                    <Input.TextArea rows={3} />
                  </Form.Item>
                  {Object.entries(RUNTIME_LABELS).map(([key, label]) => (
                    <Form.Item
                      key={key}
                      name={key}
                      label={
                        <Space>
                          {label}
                          {sourceTag(runtime.sources[key] || "default")}
                        </Space>
                      }
                    >
                      {key === "free_days" ||
                      key === "free_traffic" ||
                      key === "admin_logs_length" ||
                      key === "news_id" ||
                      key === "logs_id" ||
                      key === "web_id" ? (
                        <InputNumber style={{ width: "100%" }} />
                      ) : (
                        <Input />
                      )}
                    </Form.Item>
                  ))}
                  <Button type="primary" htmlType="submit" loading={saving}>
                    Save runtime
                  </Button>
                </Form>
              </Card>
            ),
          },
          {
            key: "payments",
            label: "Payments",
            children: !payments ? (
              <Spin />
            ) : (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                {payments.map((p) => (
                  <Card
                    key={p.provider}
                    title={
                      <Space>
                        {p.provider}
                        {sourceTag(p.source)}
                      </Space>
                    }
                    size="small"
                  >
                    <Form
                      layout="vertical"
                      initialValues={{ enabled: p.enabled, ...p.fields }}
                      key={`${p.provider}-${p.updated_at || p.source}`}
                      onFinish={(vals) => saveProvider(p, vals)}
                    >
                      <Form.Item
                        name="enabled"
                        label="Enabled"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                      {p.field_meta.map((f) => (
                        <Form.Item key={f.name} name={f.name} label={f.name}>
                          {f.secret ? (
                            <Input.Password placeholder="leave blank to keep" />
                          ) : (
                            <Input />
                          )}
                        </Form.Item>
                      ))}
                      <Button type="primary" htmlType="submit" loading={saving}>
                        Save {p.provider}
                      </Button>
                    </Form>
                  </Card>
                ))}
              </Space>
            ),
          },
          {
            key: "flags",
            label: "Feature flags",
            children:
              flags === null ? (
                <Spin />
              ) : (
                <Card title="Bot Feature Flags">
                  <Form layout="vertical">
                    <Form.Item
                      label="Legacy Bot Constructor"
                      help={
                        flags.legacy_bot_constructor
                          ? "In-bot tariff menus and inline payments are active. Users can pay directly in Telegram."
                          : "Disabled — the bot directs users to the MiniApp for all purchases. Restart the bot after changing."
                      }
                    >
                      <Switch
                        checked={flags.legacy_bot_constructor}
                        onChange={handleToggle}
                        loading={saving}
                        checkedChildren="ON"
                        unCheckedChildren="OFF"
                      />
                    </Form.Item>
                  </Form>
                </Card>
              ),
          },
        ]}
      />
    </div>
  );
}
