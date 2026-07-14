import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { TableRowSelection } from "antd/es/table/interface";
import {
  CalendarOutlined,
  CustomerServiceOutlined,
  HistoryOutlined,
  InfoCircleOutlined,
  ScanOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";

const { TextArea } = Input;

interface SegmentParam {
  name: string;
  label: string;
  type: "int" | "float";
  default: number;
  min?: number;
  max?: number;
}

interface SegmentDef {
  id: string;
  title: string;
  description: string;
  params: SegmentParam[];
}

interface ScanUser {
  tg_id: number;
  username: string | null;
  vless_uuid: string | null;
  meta: Record<string, unknown>;
}

interface ScanResult {
  segment_id: string;
  total: number;
  users: ScanUser[];
  warning: string | null;
}

interface CampaignSummary {
  id: number;
  name: string;
  segment_type: string | null;
  status: string;
  total_targets: number;
  messages_sent: number;
  messages_failed: number;
  perks_applied: number;
  perks_failed: number;
  bonus_days: number | null;
  bonus_traffic_gb: number | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_by: string;
}

interface ComposerState {
  segmentId: string | null;
  segmentParams: Record<string, number>;
  targetTgIds: number[];
  users: ScanUser[];
  totalCount?: number;
}

interface MessageTemplate {
  id: string;
  segment_id: string;
  title: string;
  message_text: string;
  suggested_bonus_days: number | null;
  suggested_bonus_traffic_gb: number | null;
  attach_button: boolean;
}

interface CrmVariable {
  key: string;
  label: string;
  description: string;
  example: string;
}

interface CrmEventRow {
  id: number;
  name: string;
  enabled: boolean;
  segment_type: string | null;
  segment_params: Record<string, number>;
  run_at_time: string;
  frequency: string;
  weekday: number | null;
  message_text: string;
  attach_button: boolean;
  bonus_days: number | null;
  bonus_traffic_gb: number | null;
  repeat_policy: string;
  repeat_cooldown_days: number;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
  created_by: string;
}

const WEEKDAYS = [
  { value: 0, label: "Пн" },
  { value: 1, label: "Вт" },
  { value: 2, label: "Ср" },
  { value: 3, label: "Чт" },
  { value: 4, label: "Пт" },
  { value: 5, label: "Сб" },
  { value: 6, label: "Вс" },
];

const REPEAT_POLICIES = [
  { value: "always", label: "Всегда" },
  { value: "once", label: "Один раз" },
  { value: "cooldown", label: "Cooldown" },
];

// ─────────────────────────────────────────────────────
// Segments tab
// ─────────────────────────────────────────────────────

interface SegmentsTabProps {
  onCompose: (state: ComposerState) => void;
}

function SegmentsTab({ onCompose }: SegmentsTabProps) {
  const { message } = App.useApp();
  const [segments, setSegments] = useState<SegmentDef[]>([]);
  const [scanModal, setScanModal] = useState<SegmentDef | null>(null);
  const [paramValues, setParamValues] = useState<Record<string, number>>({});
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<number[]>([]);

  useEffect(() => {
    api
      .get<{ segments: SegmentDef[] }>("/crm/segments")
      .then((r) => setSegments(r.segments))
      .catch(() => message.error("Не удалось загрузить сегменты"));
  }, [message]);

  const openScan = (seg: SegmentDef) => {
    const defaults: Record<string, number> = {};
    seg.params.forEach((p) => {
      defaults[p.name] = p.default;
    });
    setParamValues(defaults);
    setScanResult(null);
    setSelectedKeys([]);
    setScanModal(seg);
  };

  const runScan = async () => {
    if (!scanModal) return;
    setScanning(true);
    setScanResult(null);
    try {
      const res = await api.post<ScanResult>(
        `/crm/segments/${scanModal.id}/scan`,
        paramValues
      );
      setScanResult(res);
      setSelectedKeys(res.users.map((u) => u.tg_id));
      if (res.warning) {
        message.warning(res.warning);
      }
    } catch {
      message.error("Ошибка сканирования");
    } finally {
      setScanning(false);
    }
  };

  const rowSelection: TableRowSelection<ScanUser> = {
    selectedRowKeys: selectedKeys,
    onChange: (keys) => setSelectedKeys(keys as number[]),
  };

  const goCompose = () => {
    if (!scanResult || !scanModal || selectedKeys.length === 0) return;
    const users = scanResult.users.filter((u) => selectedKeys.includes(u.tg_id));
    const isAllUsers = scanModal.id === "all_users";
    onCompose({
      segmentId: scanModal.id,
      segmentParams: paramValues,
      targetTgIds: isAllUsers ? [] : users.map((u) => u.tg_id),
      users,
      totalCount: scanResult.total,
    });
    setScanModal(null);
    message.success("Аудитория передана в композер рассылки");
  };

  const columns = [
    { title: "TG ID", dataIndex: "tg_id", key: "tg_id", width: 120 },
    {
      title: "Username",
      dataIndex: "username",
      key: "username",
      render: (v: string | null) => v ?? "—",
    },
    {
      title: "Метрики",
      key: "meta",
      render: (_: unknown, row: ScanUser) => {
        const m = row.meta || {};
        const parts: string[] = [];
        if (m.status) parts.push(`status: ${m.status}`);
        if (m.days_left !== undefined) parts.push(`дней: ${m.days_left}`);
        if (m.traffic_percent !== undefined) parts.push(`трафик: ${m.traffic_percent}%`);
        if (m.devices !== undefined) parts.push(`устройств: ${m.devices}/${m.device_limit ?? "?"}`);
        return parts.length ? parts.join(", ") : "—";
      },
    },
  ];

  return (
    <>
      <Row gutter={[16, 16]}>
        {segments.map((seg) => (
          <Col xs={24} sm={12} lg={8} key={seg.id}>
            <Card
              size="small"
              title={seg.title}
              type={seg.id === "all_users" ? "inner" : undefined}
              style={
                seg.id === "all_users"
                  ? { borderColor: "#1677ff" }
                  : undefined
              }
              extra={
                <Button size="small" icon={<ScanOutlined />} onClick={() => openScan(seg)}>
                  Сканировать
                </Button>
              }
            >
              <Typography.Text type="secondary">{seg.description}</Typography.Text>
            </Card>
          </Col>
        ))}
      </Row>

      <Modal
        title={scanModal ? `Скан: ${scanModal.title}` : "Сканирование"}
        open={!!scanModal}
        onCancel={() => setScanModal(null)}
        width={720}
        footer={null}
        destroyOnHidden
      >
        {scanModal && scanModal.params.length > 0 && (
          <Form layout="inline" style={{ marginBottom: 16 }}>
            {scanModal.params.map((p) => (
              <Form.Item key={p.name} label={p.label}>
                <InputNumber
                  min={p.min}
                  max={p.max}
                  step={p.type === "float" ? 0.05 : 1}
                  value={paramValues[p.name]}
                  onChange={(v) =>
                    setParamValues((prev) => ({
                      ...prev,
                      [p.name]: v ?? p.default,
                    }))
                  }
                />
              </Form.Item>
            ))}
          </Form>
        )}

        <Button
          type="primary"
          icon={<ScanOutlined />}
          loading={scanning}
          onClick={runScan}
        >
          Запустить сканирование
        </Button>

        {scanResult?.warning && (
          <Alert type="warning" message={scanResult.warning} style={{ marginTop: 12 }} />
        )}

        {scanResult && (
          <div style={{ marginTop: 16 }}>
            <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
              <Descriptions.Item label="Всего в сегменте">
                <Tag color="blue">{scanResult.total}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="В превью">
                {scanResult.users.length}
                {scanResult.total > scanResult.users.length && " (первые 500)"}
              </Descriptions.Item>
            </Descriptions>

            {scanResult.users.length > 0 && (
              <>
                <Table
                  rowKey="tg_id"
                  rowSelection={rowSelection}
                  columns={columns}
                  dataSource={scanResult.users}
                  size="small"
                  pagination={{ pageSize: 20, showSizeChanger: false }}
                  scroll={{ y: 280 }}
                />
                <Button
                  type="primary"
                  style={{ marginTop: 12 }}
                  disabled={selectedKeys.length === 0}
                  onClick={goCompose}
                >
                  Создать рассылку ({selectedKeys.length})
                </Button>
              </>
            )}

            {scanResult.users.length === 0 && (
              <Typography.Text type="secondary">
                Пользователи не найдены.
              </Typography.Text>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}

// ─────────────────────────────────────────────────────
// Composer tab
// ─────────────────────────────────────────────────────

interface ComposerTabProps {
  initial: ComposerState | null;
  onClear: () => void;
  onLaunched: () => void;
}

function ComposerTab({ initial, onClear, onLaunched }: ComposerTabProps) {
  const { message } = App.useApp();
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [attachButton, setAttachButton] = useState(false);
  const [bonusDays, setBonusDays] = useState<number | null>(null);
  const [bonusTraffic, setBonusTraffic] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [audience, setAudience] = useState<ComposerState | null>(initial);
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [variablesOpen, setVariablesOpen] = useState(false);
  const [variables, setVariables] = useState<CrmVariable[]>([]);

  useEffect(() => {
    if (initial) {
      setAudience(initial);
      setSelectedTemplate(null);
    }
  }, [initial]);

  useEffect(() => {
    api
      .get<{ variables: CrmVariable[] }>("/crm/variables")
      .then((r) => setVariables(r.variables))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!audience?.segmentId) {
      setTemplates([]);
      return;
    }
    api
      .get<{ templates: MessageTemplate[] }>(
        `/crm/templates?segment_id=${encodeURIComponent(audience.segmentId)}`
      )
      .then((r) => setTemplates(r.templates))
      .catch(() => setTemplates([]));
  }, [audience?.segmentId]);

  const applyTemplate = (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl) return;
    setSelectedTemplate(templateId);
    setText(tpl.message_text);
    setAttachButton(tpl.attach_button);
    setBonusDays(tpl.suggested_bonus_days);
    setBonusTraffic(tpl.suggested_bonus_traffic_gb);
  };

  const copyVariable = async (key: string) => {
    const token = `{{${key}}}`;
    try {
      await navigator.clipboard.writeText(token);
      message.success(`Скопировано: ${token}`);
    } catch {
      message.error("Не удалось скопировать");
    }
  };

  const isAllUsers = audience?.segmentId === "all_users";

  const launch = async () => {
    if (!audience || (!isAllUsers && audience.targetTgIds.length === 0)) {
      message.warning("Выберите аудиторию на вкладке «Сегменты»");
      return;
    }
    if (!text.trim()) {
      message.warning("Введите текст сообщения");
      return;
    }
    setLoading(true);
    try {
      await api.post("/crm/campaigns/launch", {
        name: name || undefined,
        segment_type: audience.segmentId,
        segment_params: audience.segmentParams,
        message_text: text,
        attach_button: attachButton,
        bonus_days: bonusDays && bonusDays > 0 ? bonusDays : null,
        bonus_traffic_gb: bonusTraffic && bonusTraffic > 0 ? bonusTraffic : null,
        target_tg_ids: audience.targetTgIds,
      });
      message.success(
        isAllUsers
          ? `Кампания поставлена в очередь (${audience.totalCount ?? "все"} пользователей)`
          : `Кампания поставлена в очередь для ${audience.targetTgIds.length} пользователей`
      );
      setText("");
      setName("");
      setBonusDays(null);
      setBonusTraffic(null);
      setAudience(null);
      onClear();
      onLaunched();
    } catch {
      message.error("Ошибка запуска кампании");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Новая кампания" style={{ maxWidth: 800 }}>
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
        {audience ? (
          <Alert
            type="info"
            showIcon
            message={`Аудитория: ${
              audience.segmentId === "all_users"
                ? audience.totalCount ?? "все"
                : audience.targetTgIds.length
            } пользователей`}
            description={
              audience.segmentId === "all_users"
                ? "Массовая рассылка всем незабаненным пользователям с tg_id"
                : audience.segmentId
                  ? `Сегмент: ${audience.segmentId}`
                  : undefined
            }
            action={
              <Button size="small" onClick={() => { setAudience(null); onClear(); }}>
                Сбросить
              </Button>
            }
          />
        ) : (
          <Alert
            type="warning"
            message="Сначала отсканируйте сегмент и выберите получателей"
          />
        )}

        <Input
          placeholder="Название кампании (необязательно)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        {audience?.segmentId && templates.length > 0 && (
          <Select
            allowClear
            placeholder="Шаблон сообщения"
            style={{ width: "100%" }}
            value={selectedTemplate}
            onChange={(v) => {
              if (v) applyTemplate(v);
              else setSelectedTemplate(null);
            }}
            options={templates.map((t) => ({ value: t.id, label: t.title }))}
          />
        )}

        <Space style={{ width: "100%", justifyContent: "space-between" }}>
          <Typography.Text type="secondary">Текст сообщения (HTML)</Typography.Text>
          <Button
            size="small"
            icon={<InfoCircleOutlined />}
            onClick={() => setVariablesOpen(true)}
          >
            Переменные
          </Button>
        </Space>

        <TextArea
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Привет, {{username}}! Осталось {{days_left}} дн."
        />

        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          Подстановки: {"{{username}}"}, {"{{days_left}}"}, {"{{traffic_left}}"}, {"{{hwid_devices}}"}
        </Typography.Text>

        <Checkbox
          checked={attachButton}
          onChange={(e) => setAttachButton(e.target.checked)}
        >
          Прикрепить кнопку «Открыть бота»
        </Checkbox>

        <Space wrap>
          <span>Бонус дней:</span>
          <InputNumber
            min={0}
            max={365}
            placeholder="0"
            value={bonusDays}
            onChange={(v) => setBonusDays(v)}
          />
          <span>Бонус трафика (ГБ):</span>
          <InputNumber
            min={0}
            max={1000}
            placeholder="0"
            value={bonusTraffic}
            onChange={(v) => setBonusTraffic(v)}
          />
        </Space>

        {(bonusDays || bonusTraffic) && audience && (
          <Typography.Text type="secondary">
            Бонусы будут начислены автоматически в Remnawave перед отправкой
            сообщения.
          </Typography.Text>
        )}

        <Popconfirm
          title="Запустить кампанию?"
          description={`Получателей: ${
            audience?.segmentId === "all_users"
              ? audience?.totalCount ?? "все"
              : audience?.targetTgIds.length ?? 0
          }`}
          onConfirm={launch}
          okText="Запустить"
          cancelText="Отмена"
          disabled={!audience || (!isAllUsers && !audience.targetTgIds.length)}
        >
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={loading}
            disabled={!audience || (!isAllUsers && !audience.targetTgIds.length)}
          >
            Запустить кампанию
          </Button>
        </Popconfirm>
      </Space>

      <Modal
        title="Переменные сообщения"
        open={variablesOpen}
        onCancel={() => setVariablesOpen(false)}
        footer={null}
        width={560}
      >
        <Typography.Paragraph type="secondary">
          Нажмите на переменную, чтобы скопировать в буфер обмена.
        </Typography.Paragraph>
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
              title: "Переменная",
              key: "key",
              render: (_: unknown, r: CrmVariable) => (
                <Typography.Text code>{`{{${r.key}}}`}</Typography.Text>
              ),
            },
            { title: "Описание", dataIndex: "label", key: "label" },
            {
              title: "Пример",
              dataIndex: "example",
              key: "example",
              render: (v: string) => <Typography.Text type="secondary">{v}</Typography.Text>,
            },
          ]}
        />
      </Modal>
    </Card>
  );
}

// ─────────────────────────────────────────────────────
// History tab
// ─────────────────────────────────────────────────────

function HistoryTab() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ campaigns: CampaignSummary[] }>("/crm/campaigns");
      setCampaigns(res.campaigns);
    } catch {
      message.error("Не удалось загрузить историю");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    load();
  }, [load]);

  const statusColor = (s: string) => {
    if (s === "completed") return "green";
    if (s === "running") return "processing";
    if (s === "queued") return "blue";
    if (s === "failed") return "red";
    return "default";
  };

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 70 },
    { title: "Название", dataIndex: "name", key: "name", ellipsis: true },
    {
      title: "Сегмент",
      dataIndex: "segment_type",
      key: "segment_type",
      render: (v: string | null) => v ?? "—",
    },
    {
      title: "Статус",
      dataIndex: "status",
      key: "status",
      render: (v: string) => <Tag color={statusColor(v)}>{v}</Tag>,
    },
    { title: "Целей", dataIndex: "total_targets", key: "total_targets", width: 80 },
    {
      title: "Отправлено",
      key: "sent",
      render: (_: unknown, r: CampaignSummary) =>
        `${r.messages_sent} / ${r.messages_failed} ош.`,
    },
    {
      title: "Бонусы",
      key: "perks",
      render: (_: unknown, r: CampaignSummary) => {
        const parts: string[] = [];
        if (r.bonus_days) parts.push(`+${r.bonus_days}д`);
        if (r.bonus_traffic_gb) parts.push(`+${r.bonus_traffic_gb}ГБ`);
        if (!parts.length) return "—";
        return `${parts.join(", ")} (${r.perks_applied}/${r.perks_failed} ош.)`;
      },
    },
    { title: "Создана", dataIndex: "created_at", key: "created_at", width: 170 },
  ];

  return (
    <Card
      title="История кампаний"
      extra={
        <Button onClick={load} loading={loading}>
          Обновить
        </Button>
      }
    >
      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={campaigns}
        size="small"
        pagination={{ pageSize: 20 }}
      />
    </Card>
  );
}

// ─────────────────────────────────────────────────────
// Events tab (UTC schedule)
// ─────────────────────────────────────────────────────

function EventsTab() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<CrmEventRow[]>([]);
  const [segments, setSegments] = useState<SegmentDef[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<CrmEventRow | null>(null);
  const [form] = Form.useForm();
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [variablesOpen, setVariablesOpen] = useState(false);
  const [variables, setVariables] = useState<CrmVariable[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ events: CrmEventRow[] }>("/crm/events");
      setEvents(res.events);
    } catch {
      message.error("Не удалось загрузить события");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    load();
    api
      .get<{ segments: SegmentDef[] }>("/crm/segments")
      .then((r) => setSegments(r.segments))
      .catch(() => {});
    api
      .get<{ variables: CrmVariable[] }>("/crm/variables")
      .then((r) => setVariables(r.variables))
      .catch(() => {});
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      enabled: true,
      run_at_time: "01:00",
      frequency: "daily",
      repeat_policy: "cooldown",
      repeat_cooldown_days: 7,
      attach_button: true,
      segment_params: {},
    });
    setTemplates([]);
    setDrawerOpen(true);
  };

  const openEdit = (row: CrmEventRow) => {
    setEditing(row);
    form.setFieldsValue({
      ...row,
      segment_params: row.segment_params || {},
    });
    if (row.segment_type) {
      api
        .get<{ templates: MessageTemplate[] }>(
          `/crm/templates?segment_id=${encodeURIComponent(row.segment_type)}`
        )
        .then((r) => setTemplates(r.templates))
        .catch(() => setTemplates([]));
    }
    setDrawerOpen(true);
  };

  const onSegmentChange = (segmentId: string) => {
    const seg = segments.find((s) => s.id === segmentId);
    const defaults: Record<string, number> = {};
    seg?.params.forEach((p) => {
      defaults[p.name] = p.default;
    });
    form.setFieldValue("segment_params", defaults);
    api
      .get<{ templates: MessageTemplate[] }>(
        `/crm/templates?segment_id=${encodeURIComponent(segmentId)}`
      )
      .then((r) => setTemplates(r.templates))
      .catch(() => setTemplates([]));
  };

  const applyTemplate = (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl) return;
    form.setFieldsValue({
      message_text: tpl.message_text,
      attach_button: tpl.attach_button,
      bonus_days: tpl.suggested_bonus_days,
      bonus_traffic_gb: tpl.suggested_bonus_traffic_gb,
    });
  };

  const saveEvent = async () => {
    const values = await form.validateFields();
    const payload = {
      ...values,
      bonus_days: values.bonus_days && values.bonus_days > 0 ? values.bonus_days : null,
      bonus_traffic_gb:
        values.bonus_traffic_gb && values.bonus_traffic_gb > 0
          ? values.bonus_traffic_gb
          : null,
      weekday: values.frequency === "weekly" ? values.weekday : null,
    };
    try {
      if (editing) {
        await api.patch(`/crm/events/${editing.id}`, payload);
        message.success("Событие обновлено");
      } else {
        await api.post("/crm/events", payload);
        message.success("Событие создано");
      }
      setDrawerOpen(false);
      load();
    } catch {
      message.error("Ошибка сохранения");
    }
  };

  const toggleEnabled = async (row: CrmEventRow, enabled: boolean) => {
    try {
      await api.patch(`/crm/events/${row.id}`, { enabled });
      load();
    } catch {
      message.error("Не удалось изменить статус");
    }
  };

  const runNow = async (row: CrmEventRow) => {
    try {
      const res = await api.post<{ status: string; total?: number; campaign_id?: number }>(
        `/crm/events/${row.id}/run-now`
      );
      if (res.status === "empty") {
        message.info("Аудитория пуста после фильтра повторов");
      } else {
        message.success(
          res.total
            ? `Запущено: ${res.total} получателей (кампания #${res.campaign_id})`
            : "Событие запущено"
        );
      }
      load();
    } catch {
      message.error("Ошибка запуска");
    }
  };

  const deleteEvent = async (row: CrmEventRow) => {
    try {
      await api.delete(`/crm/events/${row.id}`);
      message.success("Удалено");
      load();
    } catch {
      message.error("Ошибка удаления");
    }
  };

  const copyVariable = async (key: string) => {
    try {
      await navigator.clipboard.writeText(`{{${key}}}`);
      message.success(`Скопировано: {{${key}}}`);
    } catch {
      message.error("Не удалось скопировать");
    }
  };

  const scheduleLabel = (row: CrmEventRow) => {
    const wd =
      row.frequency === "weekly" && row.weekday != null
        ? WEEKDAYS.find((d) => d.value === row.weekday)?.label
        : null;
    const freq = row.frequency === "weekly" ? `еженед. (${wd})` : "ежедн.";
    return `${row.run_at_time} UTC, ${freq}`;
  };

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    { title: "Название", dataIndex: "name", key: "name", ellipsis: true },
    {
      title: "Сегмент",
      dataIndex: "segment_type",
      key: "segment_type",
      render: (v: string | null) => v ?? "—",
    },
    {
      title: "Расписание (UTC)",
      key: "schedule",
      render: (_: unknown, r: CrmEventRow) => scheduleLabel(r),
    },
    {
      title: "Повтор",
      key: "repeat",
      render: (_: unknown, r: CrmEventRow) =>
        r.repeat_policy === "cooldown"
          ? `cooldown ${r.repeat_cooldown_days}д`
          : r.repeat_policy,
    },
    {
      title: "Вкл",
      key: "enabled",
      width: 70,
      render: (_: unknown, r: CrmEventRow) => (
        <Switch checked={r.enabled} onChange={(v) => toggleEnabled(r, v)} size="small" />
      ),
    },
    {
      title: "След. запуск",
      dataIndex: "next_run_at",
      key: "next_run_at",
      width: 160,
      render: (v: string | null) => v ?? "—",
    },
    {
      title: "",
      key: "actions",
      width: 200,
      render: (_: unknown, r: CrmEventRow) => (
        <Space size="small">
          <Button size="small" onClick={() => openEdit(r)}>
            Изм.
          </Button>
          <Button size="small" type="primary" onClick={() => runNow(r)}>
            Сейчас
          </Button>
          <Popconfirm title="Удалить событие?" onConfirm={() => deleteEvent(r)}>
            <Button size="small" danger>
              Del
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const selectedSegment = Form.useWatch("segment_type", form);
  const selectedFrequency = Form.useWatch("frequency", form);
  const selectedRepeat = Form.useWatch("repeat_policy", form);
  const segmentDef = segments.find((s) => s.id === selectedSegment);

  return (
    <>
      <Card
        title="События по расписанию (UTC)"
        extra={
          <Space>
            <Button onClick={load} loading={loading}>
              Обновить
            </Button>
            <Button type="primary" onClick={openCreate}>
              Новое событие
            </Button>
          </Space>
        }
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Время запуска указывается в UTC. Poller проверяет расписание каждые 15 минут."
        />
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={events}
          size="small"
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Drawer
        title={editing ? `Событие #${editing.id}` : "Новое событие"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={520}
        destroyOnHidden
        extra={
          <Button type="primary" onClick={saveEvent}>
            Сохранить
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Название">
            <Input placeholder="Например: LIMITED — утреннее напоминание" />
          </Form.Item>
          <Form.Item name="enabled" label="Включено" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item
            name="segment_type"
            label="Сегмент"
            rules={[{ required: true, message: "Выберите сегмент" }]}
          >
            <Select
              options={segments.map((s) => ({ value: s.id, label: s.title }))}
              onChange={onSegmentChange}
            />
          </Form.Item>
          {segmentDef && segmentDef.params.length > 0 && (
            <Form.Item label="Параметры сегмента">
              <Space wrap>
                {segmentDef.params.map((p) => (
                  <Form.Item
                    key={p.name}
                    name={["segment_params", p.name]}
                    label={p.label}
                    style={{ marginBottom: 0 }}
                  >
                    <InputNumber
                      min={p.min}
                      max={p.max}
                      step={p.type === "float" ? 0.05 : 1}
                    />
                  </Form.Item>
                ))}
              </Space>
            </Form.Item>
          )}
          <Form.Item name="run_at_time" label="Время запуска (UTC)" rules={[{ required: true }]}>
            <Input placeholder="01:00" />
          </Form.Item>
          <Form.Item name="frequency" label="Частота" rules={[{ required: true }]}>
            <Select
              options={[
                { value: "daily", label: "Ежедневно" },
                { value: "weekly", label: "Еженедельно" },
              ]}
            />
          </Form.Item>
          {selectedFrequency === "weekly" && (
            <Form.Item name="weekday" label="День недели" rules={[{ required: true }]}>
              <Select options={WEEKDAYS} />
            </Form.Item>
          )}
          {templates.length > 0 && (
            <Form.Item label="Шаблон">
              <Select
                allowClear
                placeholder="Выберите шаблон"
                options={templates.map((t) => ({ value: t.id, label: t.title }))}
                onChange={(v) => v && applyTemplate(v)}
              />
            </Form.Item>
          )}
          <Space style={{ width: "100%", justifyContent: "space-between" }}>
            <Typography.Text>Сообщение (HTML)</Typography.Text>
            <Button size="small" onClick={() => setVariablesOpen(true)}>
              Переменные
            </Button>
          </Space>
          <Form.Item
            name="message_text"
            rules={[{ required: true, message: "Введите текст" }]}
          >
            <Input.TextArea rows={5} placeholder="Привет, {{username}}!" />
          </Form.Item>
          <Form.Item name="attach_button" valuePropName="checked">
            <Checkbox>Кнопка «Открыть бота»</Checkbox>
          </Form.Item>
          <Space wrap>
            <Form.Item name="bonus_days" label="Бонус дней">
              <InputNumber min={0} max={365} />
            </Form.Item>
            <Form.Item name="bonus_traffic_gb" label="Бонус ГБ">
              <InputNumber min={0} max={1000} />
            </Form.Item>
          </Space>
          <Form.Item name="repeat_policy" label="Политика повторов">
            <Select options={REPEAT_POLICIES} />
          </Form.Item>
          {selectedRepeat === "cooldown" && (
            <Form.Item name="repeat_cooldown_days" label="Cooldown (дней)">
              <InputNumber min={1} max={365} />
            </Form.Item>
          )}
        </Form>
      </Drawer>

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
    </>
  );
}

// ─────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────

export default function CrmPage() {
  const [activeTab, setActiveTab] = useState("segments");
  const [composerState, setComposerState] = useState<ComposerState | null>(null);

  const items = [
    {
      key: "segments",
      label: (
        <span>
          <ScanOutlined /> Сегменты
        </span>
      ),
      children: (
        <SegmentsTab
          onCompose={(state) => {
            setComposerState(state);
            setActiveTab("composer");
          }}
        />
      ),
    },
    {
      key: "composer",
      label: (
        <span>
          <SendOutlined /> Рассылка
        </span>
      ),
      children: (
        <ComposerTab
          initial={composerState}
          onClear={() => setComposerState(null)}
          onLaunched={() => setActiveTab("history")}
        />
      ),
    },
    {
      key: "events",
      label: (
        <span>
          <CalendarOutlined /> События
        </span>
      ),
      children: <EventsTab />,
    },
    {
      key: "history",
      label: (
        <span>
          <HistoryOutlined /> История
        </span>
      ),
      children: <HistoryTab />,
    },
  ];

  return (
    <div>
      <Typography.Title
        level={4}
        style={{ marginBottom: 20, color: "rgba(255,255,255,0.88)" }}
      >
        <CustomerServiceOutlined style={{ marginRight: 8 }} />
        CRM
      </Typography.Title>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
    </div>
  );
}
