import { App, Button, Descriptions, Divider, Drawer, Input, List, Space, Tag, Typography } from "antd";
import { EditOutlined, GiftOutlined, IdcardOutlined, SendOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { TransactionItem, UserDetail } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

interface Props {
  /** When non-null the drawer fetches & shows this user. */
  tgId: number | null;
  open: boolean;
  onClose: () => void;
  /** Called after edits so the opener can refresh its list. */
  onChanged?: () => void;
}

/**
 * Reusable user card. Fetches the user detail + transactions for `tgId` and
 * renders the account info, identifier editor (tg_id/username/vless_uuid),
 * email editor, promo/ticket stats, transaction history and a send-message box.
 * Used by the Users table and the Support ticket view.
 */
export default function UserDrawer({ tgId, open, onClose, onChanged }: Props) {
  const { message } = App.useApp();
  const isMobile = useIsMobile();

  const [user, setUser] = useState<UserDetail | null>(null);
  const [tx, setTx] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(false);

  // editable identifier fields
  const [editTgId, setEditTgId] = useState("");
  const [editUsername, setEditUsername] = useState("");
  const [editUuid, setEditUuid] = useState("");
  const [idSaving, setIdSaving] = useState(false);

  const [emailInput, setEmailInput] = useState("");
  const [emailSaving, setEmailSaving] = useState(false);

  const [msgText, setMsgText] = useState("");
  const [msgSending, setMsgSending] = useState(false);

  const load = async (id: number) => {
    setLoading(true);
    try {
      const u = await api.get<UserDetail>(`/users/${id}`);
      const t = await api.get<TransactionItem[]>(`/users/${id}/transactions`);
      setUser(u);
      setTx(t);
      setEditTgId(String(u.tg_id));
      setEditUsername(u.username || "");
      setEditUuid(u.vless_uuid || "");
      setEmailInput(u.email || "");
      setMsgText("");
    } catch {
      message.error("Не удалось загрузить пользователя");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && tgId != null) load(tgId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, tgId]);

  const handleSaveIdentifiers = async () => {
    if (!user) return;
    const newTgId = editTgId.trim();
    if (newTgId && !/^-?\d+$/.test(newTgId)) {
      message.error("TG ID должен быть числом");
      return;
    }
    setIdSaving(true);
    try {
      const res = await api.patch<{ ok: boolean; tg_id: number; username: string | null; vless_uuid: string | null }>(
        `/users/${user.tg_id}/identifiers`,
        {
          tg_id: newTgId ? Number(newTgId) : undefined,
          username: editUsername,
          vless_uuid: editUuid,
        }
      );
      message.success("Сохранено");
      // tg_id may have changed → reload by the new id and refresh the opener
      await load(res.tg_id);
      onChanged?.();
    } catch (e) {
      const status = (e as { status?: number })?.status;
      message.error(status === 409 ? "Этот TG ID уже занят" : "Ошибка сохранения");
    } finally {
      setIdSaving(false);
    }
  };

  const handleSaveEmail = async () => {
    if (!user || !emailInput.trim()) return;
    setEmailSaving(true);
    try {
      const res = await api.patch<{ ok: boolean; rw_uuid: string | null }>(
        `/users/${user.tg_id}/email`,
        { email: emailInput.trim() }
      );
      message.success(res.rw_uuid ? `Email сохранён, UUID: ${res.rw_uuid}` : "Email сохранён");
      await load(user.tg_id);
      onChanged?.();
    } catch {
      message.error("Ошибка сохранения email");
    } finally {
      setEmailSaving(false);
    }
  };

  const handleSendMessage = async () => {
    if (!user || !msgText.trim()) return;
    setMsgSending(true);
    try {
      await api.post(`/users/${user.tg_id}/send-message`, { text: msgText });
      message.success("Сообщение отправлено");
      setMsgText("");
    } catch {
      message.error("Ошибка отправки");
    } finally {
      setMsgSending(false);
    }
  };

  const labelStyle = { color: "rgba(255,255,255,0.85)" } as const;

  return (
    <Drawer
      title={user ? `User: ${user.username || user.tg_id}` : "User"}
      open={open}
      onClose={onClose}
      width={isMobile ? "100%" : 520}
      loading={loading}
    >
      {user && (
        <>
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="TG ID">{user.tg_id}</Descriptions.Item>
            <Descriptions.Item label="Username">{user.username || "—"}</Descriptions.Item>
            <Descriptions.Item label="Email">{user.email || "—"}</Descriptions.Item>
            <Descriptions.Item label="vless_uuid">
              <Typography.Text copyable={!!user.vless_uuid} style={{ fontSize: 12, wordBreak: "break-all" }}>
                {user.vless_uuid || "—"}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Provider">{user.api_provider}</Descriptions.Item>
            <Descriptions.Item label="Промокод">
              {user.promo_code ? <Tag color="purple" icon={<GiftOutlined />}>{user.promo_code}</Tag> : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="Тикетов открыто">{user.tickets_count}</Descriptions.Item>
            <Descriptions.Item label="Banned">{user.is_banned ? "Yes" : "No"}</Descriptions.Item>
            <Descriptions.Item label="VIP">{user.vip ? "Yes" : "No"}</Descriptions.Item>
            <Descriptions.Item label="Language">{user.language || "—"}</Descriptions.Item>
            <Descriptions.Item label="Total Spent">{user.total_spent}</Descriptions.Item>
            <Descriptions.Item label="Transactions">{user.transactions_count}</Descriptions.Item>
          </Descriptions>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <Typography.Text strong style={labelStyle}>
            <IdcardOutlined style={{ marginRight: 6 }} />
            Идентификаторы
          </Typography.Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
            <Input
              addonBefore="TG ID"
              value={editTgId}
              onChange={(e) => setEditTgId(e.target.value)}
              placeholder="123456789"
            />
            <Input
              addonBefore="Username"
              value={editUsername}
              onChange={(e) => setEditUsername(e.target.value)}
              placeholder="username"
              allowClear
            />
            <Input
              addonBefore="UUID"
              value={editUuid}
              onChange={(e) => setEditUuid(e.target.value)}
              placeholder="vless_uuid"
              allowClear
            />
            <Button type="primary" icon={<EditOutlined />} loading={idSaving} onClick={handleSaveIdentifiers}>
              Сохранить идентификаторы
            </Button>
          </div>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <Typography.Text strong style={labelStyle}>
            <EditOutlined style={{ marginRight: 6 }} />
            Email пользователя
          </Typography.Text>
          <Space.Compact style={{ width: "100%", marginTop: 8 }}>
            <Input
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder="user@example.com"
              onPressEnter={handleSaveEmail}
            />
            <Button type="primary" onClick={handleSaveEmail} loading={emailSaving} icon={<EditOutlined />}>
              Сохранить
            </Button>
          </Space.Compact>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <Typography.Text strong style={labelStyle}>
            <SendOutlined style={{ marginRight: 6 }} />
            Сообщение пользователю
          </Typography.Text>
          <Input.TextArea
            style={{ marginTop: 8 }}
            rows={3}
            value={msgText}
            onChange={(e) => setMsgText(e.target.value)}
            placeholder="Текст сообщения..."
          />
          <Button
            type="primary"
            style={{ marginTop: 8 }}
            icon={<SendOutlined />}
            loading={msgSending}
            onClick={handleSendMessage}
            disabled={!msgText.trim()}
          >
            Отправить
          </Button>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <h4 style={{ color: "rgba(255,255,255,0.85)" }}>Transactions</h4>
          <List
            size="small"
            dataSource={tx}
            locale={{ emptyText: "Нет транзакций" }}
            renderItem={(t) => (
              <List.Item>
                <List.Item.Meta
                  title={`${t.transaction_id} — ${t.order_status}`}
                  description={`${t.payment_method || "—"} | ${t.amount ?? 0} | ${t.days_ordered}d | ${t.created_at || "—"}`}
                />
              </List.Item>
            )}
          />
        </>
      )}
    </Drawer>
  );
}
