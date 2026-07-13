import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { TableRowSelection } from "antd/es/table/interface";
import {
  CustomerServiceOutlined,
  HistoryOutlined,
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

  useEffect(() => {
    if (initial) {
      setAudience(initial);
    }
  }, [initial]);

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

        <TextArea
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Текст сообщения (HTML)"
        />

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
