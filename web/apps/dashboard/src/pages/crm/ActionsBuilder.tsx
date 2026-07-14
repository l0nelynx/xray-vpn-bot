import {
  App,
  Button,
  Card,
  Collapse,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Typography,
} from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { ActionTypeMeta, CrmAction, CrmVariable, MessageTemplate } from "./types";

const { TextArea } = Input;

interface ActionsBuilderProps {
  actions: CrmAction[];
  onChange: (actions: CrmAction[]) => void;
  segmentId: string | null;
  templates?: MessageTemplate[];
}

export default function ActionsBuilder({
  actions,
  onChange,
  segmentId,
  templates: templatesProp,
}: ActionsBuilderProps) {
  const { message } = App.useApp();
  const [actionTypes, setActionTypes] = useState<ActionTypeMeta[]>([]);
  const [templates, setTemplates] = useState<MessageTemplate[]>(templatesProp || []);
  const [variablesOpen, setVariablesOpen] = useState(false);
  const [variables, setVariables] = useState<CrmVariable[]>([]);

  useEffect(() => {
    api.get<{ action_types: ActionTypeMeta[] }>("/crm/actions/types").then((r) => {
      setActionTypes(r.action_types);
    });
    api.get<{ variables: CrmVariable[] }>("/crm/variables").then((r) => {
      setVariables(r.variables);
    });
  }, []);

  useEffect(() => {
    if (templatesProp) {
      setTemplates(templatesProp);
      return;
    }
    if (!segmentId) {
      setTemplates([]);
      return;
    }
    api
      .get<{ templates: MessageTemplate[] }>(
        `/crm/templates?segment_id=${encodeURIComponent(segmentId)}`
      )
      .then((r) => setTemplates(r.templates))
      .catch(() => setTemplates([]));
  }, [segmentId, templatesProp]);

  const updateAction = (type: string, patch: Partial<CrmAction>) => {
    onChange(actions.map((a) => (a.type === type ? { ...a, ...patch } : a)));
  };

  const applyTemplate = (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl) return;
    onChange(
      actions.map((a) => {
        if (a.type === "send_message") {
          return { ...a, enabled: true, text: tpl.message_text };
        }
        if (a.type === "attach_button") {
          return { ...a, enabled: tpl.attach_button };
        }
        if (a.type === "rw_bonus_days" && tpl.suggested_bonus_days) {
          return { ...a, enabled: true, days: tpl.suggested_bonus_days };
        }
        if (a.type === "rw_bonus_traffic" && tpl.suggested_bonus_traffic_gb) {
          return { ...a, enabled: true, gb: tpl.suggested_bonus_traffic_gb };
        }
        return a;
      })
    );
  };

  const copyVariable = async (key: string) => {
    try {
      await navigator.clipboard.writeText(`{{${key}}}`);
      message.success(`Скопировано: {{${key}}}`);
    } catch {
      message.error("Не удалось скопировать");
    }
  };

  const telegramActions = actionTypes.filter((t) => t.category === "telegram");
  const rwActions = actionTypes.filter((t) => t.category === "remnawave");

  const renderAction = (meta: ActionTypeMeta) => {
    const act = actions.find((a) => a.type === meta.type);
    if (!act) return null;
    const disabled = meta.available === false;

    return (
      <Card
        key={meta.type}
        size="small"
        style={{ marginBottom: 8, opacity: disabled ? 0.5 : 1 }}
        title={
          <Space>
            <Switch
              size="small"
              checked={act.enabled && !disabled}
              disabled={disabled}
              onChange={(v) => updateAction(meta.type, { enabled: v })}
            />
            <span>{meta.label}</span>
          </Space>
        }
      >
        {meta.type === "send_message" && act.enabled && (
          <Space direction="vertical" style={{ width: "100%" }}>
            <Space style={{ justifyContent: "space-between", width: "100%" }}>
              <Typography.Text type="secondary">
                HTML, переменные {"{{username}}"}
              </Typography.Text>
              <Button size="small" icon={<InfoCircleOutlined />} onClick={() => setVariablesOpen(true)}>
                Переменные
              </Button>
            </Space>
            <TextArea
              rows={4}
              value={act.text || ""}
              onChange={(e) => updateAction(meta.type, { text: e.target.value })}
              placeholder="Привет, {{username}}!"
            />
          </Space>
        )}
        {meta.type === "attach_button" && act.enabled && (
          <Select
            value={act.button_type || "open_bot"}
            options={[{ value: "open_bot", label: "Открыть бота" }]}
            onChange={(v) => updateAction(meta.type, { button_type: v })}
            style={{ minWidth: 200 }}
          />
        )}
        {meta.type === "rw_bonus_days" && act.enabled && (
          <InputNumber
            min={1}
            max={365}
            value={act.days}
            onChange={(v) => updateAction(meta.type, { days: v ?? 1 })}
          />
        )}
        {meta.type === "rw_bonus_traffic" && act.enabled && (
          <InputNumber
            min={1}
            max={1000}
            value={act.gb}
            onChange={(v) => updateAction(meta.type, { gb: v ?? 1 })}
          />
        )}
        {meta.type === "rw_reset_traffic" && act.enabled && (
          <Typography.Text type="secondary">
            Сбросит счётчик использованного трафика в Remnawave
          </Typography.Text>
        )}
        {meta.type === "rw_set_status" && (
          <Typography.Text type="secondary">Скоро</Typography.Text>
        )}
      </Card>
    );
  };

  return (
    <Card title="2. Действия" size="small">
      {templates.length > 0 && (
        <Select
          allowClear
          placeholder="Применить шаблон"
          style={{ width: "100%", marginBottom: 12 }}
          options={templates.map((t) => ({ value: t.id, label: t.title }))}
          onChange={(v) => v && applyTemplate(v)}
        />
      )}

      <Collapse
        defaultActiveKey={["telegram", "remnawave"]}
        items={[
          {
            key: "telegram",
            label: "Telegram",
            children: telegramActions.map(renderAction),
          },
          {
            key: "remnawave",
            label: "Remnawave",
            children: rwActions.map(renderAction),
          },
        ]}
      />

      <Modal
        title="Переменные"
        open={variablesOpen}
        onCancel={() => setVariablesOpen(false)}
        footer={null}
      >
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          dataSource={variables}
          onRow={(row) => ({
            onClick: () => copyVariable(row.key),
            style: { cursor: "pointer" },
          })}
          columns={[
            {
              title: "Ключ",
              render: (_: unknown, r: CrmVariable) => (
                <Typography.Text code>{`{{${r.key}}}`}</Typography.Text>
              ),
            },
            { title: "Описание", dataIndex: "label" },
          ]}
        />
      </Modal>
    </Card>
  );
}
