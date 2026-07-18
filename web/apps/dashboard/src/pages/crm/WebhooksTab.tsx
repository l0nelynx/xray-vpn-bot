import {
  Alert,
  App,
  Button,
  Card,
  Drawer,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import ActionsBuilder from "./ActionsBuilder";
import {
  createWebhookRule,
  deleteWebhookRule,
  fetchWebhookCatalog,
  fetchWebhookRules,
  updateWebhookRule,
} from "./api";
import { actionSummary, defaultActions } from "./helpers";
import type { CrmAction, CrmWebhookRuleRow, WebhookScopeGroup } from "./types";

export default function WebhooksTab() {
  const { message } = App.useApp();
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(false);
  const [rules, setRules] = useState<CrmWebhookRuleRow[]>([]);
  const [catalog, setCatalog] = useState<WebhookScopeGroup[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<CrmWebhookRuleRow | null>(null);
  const [actions, setActions] = useState<CrmAction[]>(defaultActions());
  const [scope, setScope] = useState<string | undefined>();
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRules(await fetchWebhookRules());
    } catch {
      message.error("Failed to load webhook rules");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    load();
    fetchWebhookCatalog()
      .then(setCatalog)
      .catch(() => {});
  }, [load]);

  const eventOptions = useMemo(() => {
    const group = catalog.find((g) => g.scope === scope);
    return (group?.events || []).map((e) => ({ value: e.value, label: e.label }));
  }, [catalog, scope]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    const first = catalog[0];
    setScope(first?.scope);
    setActions(defaultActions());
    form.setFieldsValue({
      enabled: true,
      name: "",
      cooldown_hours: null,
      scope: first?.scope,
      event: first?.events[0]?.value,
    });
    setDrawerOpen(true);
  };

  const openEdit = (row: CrmWebhookRuleRow) => {
    setEditing(row);
    setScope(row.scope);
    setActions(row.actions?.length ? row.actions : defaultActions());
    form.setFieldsValue({
      name: row.name,
      enabled: row.enabled,
      scope: row.scope,
      event: row.event,
      cooldown_hours: row.cooldown_hours,
    });
    setDrawerOpen(true);
  };

  const saveRule = async () => {
    const values = await form.validateFields();
    if (!actions.some((a) => a.enabled)) {
      message.warning("Enable at least one action");
      return;
    }
    const payload = {
      name: values.name,
      enabled: values.enabled,
      scope: values.scope,
      event: values.event,
      actions,
      cooldown_hours: values.cooldown_hours ?? null,
    };
    try {
      if (editing) {
        await updateWebhookRule(editing.id, payload);
        message.success("Rule updated");
      } else {
        await createWebhookRule(payload);
        message.success("Rule created");
      }
      setDrawerOpen(false);
      load();
    } catch {
      message.error("Failed to save");
    }
  };

  const toggleEnabled = async (row: CrmWebhookRuleRow, enabled: boolean) => {
    try {
      await updateWebhookRule(row.id, { enabled });
      load();
    } catch {
      message.error("Failed to change status");
    }
  };

  const columns = [
    {
      title: "Name",
      dataIndex: "name",
      ellipsis: true,
      render: (name: string, row: CrmWebhookRuleRow) => (
        <Button type="link" onClick={() => openEdit(row)} style={{ padding: 0 }}>
          {name || `#${row.id}`}
        </Button>
      ),
    },
    {
      title: "Scope / Event",
      responsive: ["md" as const],
      render: (_: unknown, row: CrmWebhookRuleRow) => (
        <Typography.Text code style={{ fontSize: 12 }}>
          {row.scope} / {row.event}
        </Typography.Text>
      ),
    },
    {
      title: "Actions",
      responsive: ["lg" as const],
      render: (_: unknown, row: CrmWebhookRuleRow) => actionSummary(row.actions),
    },
    {
      title: "Received",
      width: 90,
      render: (_: unknown, row: CrmWebhookRuleRow) => row.webhooks_received ?? 0,
    },
    {
      title: "Sent",
      width: 70,
      render: (_: unknown, row: CrmWebhookRuleRow) => row.messages_sent ?? 0,
    },
    {
      title: "Failed",
      width: 80,
      render: (_: unknown, row: CrmWebhookRuleRow) => (
        <Typography.Text type={(row.messages_failed ?? 0) > 0 ? "danger" : undefined}>
          {row.messages_failed ?? 0}
        </Typography.Text>
      ),
    },
    {
      title: "Cooldown",
      width: 90,
      responsive: ["md" as const],
      render: (_: unknown, row: CrmWebhookRuleRow) =>
        row.cooldown_hours != null ? `${row.cooldown_hours}h` : "—",
    },
    {
      title: "On",
      width: 70,
      render: (_: unknown, row: CrmWebhookRuleRow) => (
        <Switch
          size="small"
          checked={row.enabled}
          onChange={(v) => toggleEnabled(row, v)}
        />
      ),
    },
    {
      title: "",
      width: 80,
      render: (_: unknown, row: CrmWebhookRuleRow) => (
        <Popconfirm
          title="Delete this rule?"
          onConfirm={async () => {
            try {
              await deleteWebhookRule(row.id);
              message.success("Deleted");
              load();
            } catch {
              message.error("Failed to delete");
            }
          }}
        >
          <Button danger size="small" type="link">
            Delete
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Space
        style={{
          width: "100%",
          justifyContent: "space-between",
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <Typography.Text type="secondary">
          Remnawave webhook → CRM actions (scope + event)
        </Typography.Text>
        <Button type="primary" onClick={openCreate}>
          New rule
        </Button>
      </Space>

      {isMobile ? (
        <Space direction="vertical" style={{ width: "100%" }} size={8}>
          {rules.map((row) => (
            <Card
              key={row.id}
              size="small"
              title={
                <Space>
                  <Switch
                    size="small"
                    checked={row.enabled}
                    onChange={(v) => toggleEnabled(row, v)}
                  />
                  <Button type="link" onClick={() => openEdit(row)} style={{ padding: 0 }}>
                    {row.name || `#${row.id}`}
                  </Button>
                </Space>
              }
              extra={
                <Popconfirm
                  title="Delete?"
                  onConfirm={async () => {
                    try {
                      await deleteWebhookRule(row.id);
                      load();
                    } catch {
                      message.error("Failed to delete");
                    }
                  }}
                >
                  <Button danger size="small" type="link">
                    Del
                  </Button>
                </Popconfirm>
              }
            >
              <Typography.Text code style={{ fontSize: 11 }}>
                {row.scope}/{row.event}
              </Typography.Text>
              <div style={{ marginTop: 6, fontSize: 12, opacity: 0.7 }}>
                {actionSummary(row.actions)}
                {row.cooldown_hours != null ? ` · cooldown ${row.cooldown_hours}h` : ""}
              </div>
              <div style={{ marginTop: 4, fontSize: 12 }}>
                recv {row.webhooks_received ?? 0} · sent {row.messages_sent ?? 0}
                {(row.messages_failed ?? 0) > 0 ? (
                  <Typography.Text type="danger">
                    {` · fail ${row.messages_failed}`}
                  </Typography.Text>
                ) : (
                  ` · fail ${row.messages_failed ?? 0}`
                )}
              </div>
            </Card>
          ))}
          {!loading && rules.length === 0 && (
            <Alert type="info" showIcon message="No webhook rules yet" />
          )}
        </Space>
      ) : (
        <Table
          rowKey="id"
          loading={loading}
          dataSource={rules}
          columns={columns}
          pagination={false}
          size="middle"
        />
      )}

      <Drawer
        title={editing ? "Edit webhook rule" : "New webhook rule"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={isMobile ? "100%" : 560}
        destroyOnHidden
        extra={
          <Button type="primary" onClick={saveRule}>
            Save
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="Torrent warning" />
          </Form.Item>
          <Form.Item name="enabled" label="Enabled" valuePropName="checked">
            <Switch />
          </Form.Item>

          <Card title="1. Conditions" size="small" style={{ marginBottom: 12 }}>
            <Form.Item name="scope" label="Scope" rules={[{ required: true }]}>
              <Select
                options={catalog.map((g) => ({ value: g.scope, label: g.label }))}
                onChange={(v) => {
                  setScope(v);
                  const firstEvent = catalog.find((g) => g.scope === v)?.events[0]?.value;
                  form.setFieldsValue({ event: firstEvent });
                }}
              />
            </Form.Item>
            <Form.Item name="event" label="Event" rules={[{ required: true }]}>
              <Select
                options={eventOptions}
                disabled={!scope}
              />
            </Form.Item>
            <Form.Item
              name="cooldown_hours"
              label="Cooldown (hours)"
              tooltip="Skip re-running for the same user within this window. Empty = no limit."
            >
              <InputNumber min={1} max={720} style={{ width: "100%" }} placeholder="Optional" />
            </Form.Item>
          </Card>

          <ActionsBuilder
            actions={actions}
            onChange={setActions}
            segmentId={null}
            templates={[]}
            variablesContext="webhook"
          />
        </Form>
      </Drawer>
    </div>
  );
}
