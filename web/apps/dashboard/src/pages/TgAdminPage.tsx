import { useState } from "react";
import {
  App,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Input,
  Popconfirm,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import {
  SendOutlined,
  ScanOutlined,
  DeleteOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";

const { TextArea } = Input;

interface ScanUser {
  tg_id: number;
  username: string | null;
  vless_uuid?: string;
}

interface ScanResult {
  total_checked: number;
  to_disable?: ScanUser[];
  to_delete?: ScanUser[];
  errors: number;
}

interface ExecuteResult {
  disabled?: number;
  deleted?: number;
  notified: number;
  errors: number;
}

// ─────────────────────────────────────────────────────
// Channel post tab
// ─────────────────────────────────────────────────────
function ChannelPostTab() {
  const { message } = App.useApp();
  const [text, setText] = useState("");
  const [attachButton, setAttachButton] = useState(true);
  const [loading, setLoading] = useState(false);

  const send = async () => {
    if (!text.trim()) {
      message.warning("Введите текст поста");
      return;
    }
    setLoading(true);
    try {
      await api.post("/tg-admin/channel-post", { text, attach_button: attachButton });
      message.success("Пост опубликован в канале");
      setText("");
    } catch {
      message.error("Ошибка публикации в канале");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Пост в канал" style={{ maxWidth: 700 }}>
      <Space direction="vertical" style={{ width: "100%" }} size={12}>
        <TextArea
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Текст поста (HTML-разметка поддерживается)"
        />
        <Checkbox checked={attachButton} onChange={(e) => setAttachButton(e.target.checked)}>
          Прикрепить кнопку «Открыть бота»
        </Checkbox>
        <Popconfirm
          title="Опубликовать пост?"
          onConfirm={send}
          okText="Опубликовать"
          cancelText="Отмена"
        >
          <Button type="primary" icon={<SendOutlined />} loading={loading}>
            Опубликовать
          </Button>
        </Popconfirm>
      </Space>
    </Card>
  );
}

// ─────────────────────────────────────────────────────
// Generic clean tab (sub-clean + telemt-clean)
// ─────────────────────────────────────────────────────
interface CleanTabProps {
  title: string;
  scanEndpoint: string;
  executeEndpoint: string;
  listKey: "to_disable" | "to_delete";
  executeKey: "tg_ids" | "usernames";
  executeLabel: string;
  executeIcon: React.ReactNode;
  executeConfirm: string;
}

function CleanTab({
  title,
  scanEndpoint,
  executeEndpoint,
  listKey,
  executeKey,
  executeLabel,
  executeIcon,
  executeConfirm,
}: CleanTabProps) {
  const { message } = App.useApp();
  const [scanning, setScanning] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [execResult, setExecResult] = useState<ExecuteResult | null>(null);

  const scan = async () => {
    setScanning(true);
    setScanResult(null);
    setExecResult(null);
    try {
      const res = await api.post<ScanResult>(scanEndpoint, {});
      setScanResult(res);
    } catch {
      message.error("Ошибка сканирования");
    } finally {
      setScanning(false);
    }
  };

  const execute = async () => {
    if (!scanResult) return;
    const users = scanResult[listKey] ?? [];
    if (!users.length) return;

    const payload =
      executeKey === "tg_ids"
        ? { tg_ids: users.map((u) => u.tg_id) }
        : { usernames: users.map((u) => u.username).filter(Boolean) };

    setExecuting(true);
    try {
      const res = await api.post<ExecuteResult>(executeEndpoint, payload);
      setExecResult(res);
      setScanResult(null);
      message.success("Операция завершена");
    } catch {
      message.error("Ошибка выполнения");
    } finally {
      setExecuting(false);
    }
  };

  const users = scanResult?.[listKey] ?? [];

  const columns = [
    { title: "TG ID", dataIndex: "tg_id", key: "tg_id", width: 130 },
    { title: "Username", dataIndex: "username", key: "username", render: (v: string | null) => v ?? "—" },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card title={title}>
        <Space wrap>
          <Button icon={<ScanOutlined />} loading={scanning} onClick={scan}>
            Сканировать
          </Button>
          {scanResult && users.length > 0 && (
            <Popconfirm
              title={executeConfirm}
              description={`Пользователей: ${users.length}`}
              onConfirm={execute}
              okText="Выполнить"
              cancelText="Отмена"
            >
              <Button
                danger
                icon={executeIcon}
                loading={executing}
              >
                {executeLabel} ({users.length})
              </Button>
            </Popconfirm>
          )}
        </Space>

        {scanResult && (
          <div style={{ marginTop: 16 }}>
            <Descriptions size="small" column={3} style={{ marginBottom: 12 }}>
              <Descriptions.Item label="Проверено">{scanResult.total_checked}</Descriptions.Item>
              <Descriptions.Item label="К обработке">
                <Tag color={users.length > 0 ? "orange" : "green"}>{users.length}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Ошибок">
                <Tag color={scanResult.errors > 0 ? "red" : "default"}>{scanResult.errors}</Tag>
              </Descriptions.Item>
            </Descriptions>
            {users.length > 0 && (
              <Table
                rowKey="tg_id"
                columns={columns}
                dataSource={users}
                size="small"
                pagination={{ pageSize: 50, showSizeChanger: false }}
                scroll={{ y: 300 }}
              />
            )}
            {users.length === 0 && (
              <Typography.Text type="secondary">Неподписанных пользователей не найдено.</Typography.Text>
            )}
          </div>
        )}
      </Card>

      {execResult && (
        <Card title="Результат">
          <Descriptions size="small" column={3}>
            {execResult.disabled !== undefined && (
              <Descriptions.Item label="Отключено">{execResult.disabled}</Descriptions.Item>
            )}
            {execResult.deleted !== undefined && (
              <Descriptions.Item label="Удалено">{execResult.deleted}</Descriptions.Item>
            )}
            <Descriptions.Item label="Уведомлено">{execResult.notified}</Descriptions.Item>
            <Descriptions.Item label="Ошибок">
              <Tag color={execResult.errors > 0 ? "red" : "default"}>{execResult.errors}</Tag>
            </Descriptions.Item>
          </Descriptions>
        </Card>
      )}
    </Space>
  );
}

// ─────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────
export default function TgAdminPage() {
  const items = [
    {
      key: "channel",
      label: "Пост в канал",
      children: <ChannelPostTab />,
    },
    {
      key: "subclean",
      label: "FREE Sub Check",
      children: (
        <CleanTab
          title="FREE users sub check — пользователи без подписки на канал"
          scanEndpoint="/tg-admin/sub-clean/scan"
          executeEndpoint="/tg-admin/sub-clean/execute"
          listKey="to_disable"
          executeKey="tg_ids"
          executeLabel="Отключить"
          executeIcon={<StopOutlined />}
          executeConfirm="Отключить выбранных пользователей в RemnaWave и отправить уведомления?"
        />
      ),
    },
    {
      key: "telemt",
      label: "Telemt Clean",
      children: (
        <CleanTab
          title="Telemt Clean — удаление пользователей без подписки на канал"
          scanEndpoint="/tg-admin/telemt-clean/scan"
          executeEndpoint="/tg-admin/telemt-clean/execute"
          listKey="to_delete"
          executeKey="usernames"
          executeLabel="Удалить из Telemt"
          executeIcon={<DeleteOutlined />}
          executeConfirm="Удалить выбранных пользователей из Telemt и отправить уведомления?"
        />
      ),
    },
  ];

  return (
    <div>
      <Typography.Title
        level={4}
        style={{ marginBottom: 20, color: "rgba(255,255,255,0.88)" }}
      >
        TG Admin
      </Typography.Title>
      <Tabs items={items} />
    </div>
  );
}
