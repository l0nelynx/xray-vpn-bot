import { App, Button, Descriptions, Divider, Drawer, Input, InputNumber, List, Space, Tag, Typography } from "antd";
import { EditOutlined, GiftOutlined, IdcardOutlined, SendOutlined, WalletOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { TransactionItem, UserDetail } from "../api/types";
import { formatPoints, POINTS_ICON } from "../points";
import useIsMobile from "../hooks/useIsMobile";

interface Props {
  /** Local DB users.id. When non-null the drawer fetches & shows this user. */
  userId: number | null;
  open: boolean;
  onClose: () => void;
  /** Called after edits so the opener can refresh its list. */
  onChanged?: () => void;
}

/**
 * Reusable user card. Fetches the user detail + transactions by local DB id
 * (works for Android/web accounts without tg_id). Used by the Users table
 * and the Support ticket view.
 */
export default function UserDrawer({ userId, open, onClose, onChanged }: Props) {
  const { message } = App.useApp();
  const isMobile = useIsMobile();

  const [user, setUser] = useState<UserDetail | null>(null);
  const [tx, setTx] = useState<TransactionItem[]>([]);
  const [loading, setLoading] = useState(false);

  // editable identifier fields
  const [editTgId, setEditTgId] = useState("");
  const [editUsername, setEditUsername] = useState("");
  const [editUuid, setEditUuid] = useState("");
  const [editRwId, setEditRwId] = useState("");
  const [idSaving, setIdSaving] = useState(false);

  const [emailInput, setEmailInput] = useState("");
  const [emailSaving, setEmailSaving] = useState(false);

  const [msgText, setMsgText] = useState("");
  const [msgSending, setMsgSending] = useState(false);

  const [creditsDelta, setCreditsDelta] = useState<number | null>(null);
  const [creditsSaving, setCreditsSaving] = useState(false);

  const load = async (id: number) => {
    setLoading(true);
    try {
      const u = await api.get<UserDetail>(`/users/${id}`);
      const t = await api.get<TransactionItem[]>(`/users/${id}/transactions`);
      setUser(u);
      setTx(t);
      setEditTgId(u.tg_id != null ? String(u.tg_id) : "");
      setEditUsername(u.username || "");
      setEditUuid(u.vless_uuid || "");
      setEditRwId(u.rw_id != null ? String(u.rw_id) : "");
      setEmailInput(u.email || "");
      setMsgText("");
      setCreditsDelta(null);
    } catch {
      message.error("Failed to load user");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && userId != null) load(userId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, userId]);

  const handleSaveIdentifiers = async () => {
    if (!user) return;
    const newTgId = editTgId.trim();
    if (newTgId && !/^-?\d+$/.test(newTgId)) {
      message.error("TG ID must be a number");
      return;
    }
    const rwIdTrimmed = editRwId.trim();
    if (rwIdTrimmed && !/^\d+$/.test(rwIdTrimmed)) {
      message.error("rw_id must be a number");
      return;
    }
    setIdSaving(true);
    try {
      await api.patch<{
        ok: boolean;
        id: number;
        tg_id: number | null;
        username: string | null;
        vless_uuid: string | null;
        rw_id: number | null;
      }>(
        `/users/${user.id}/identifiers`,
        {
          tg_id: newTgId ? Number(newTgId) : null,
          username: editUsername,
          vless_uuid: editUuid,
          rw_id: rwIdTrimmed ? Number(rwIdTrimmed) : null,
        }
      );
      message.success("Saved");
      await load(user.id);
      onChanged?.();
    } catch (e) {
      const status = (e as { status?: number })?.status;
      message.error(status === 409 ? "This TG ID is already in use" : "Failed to save");
    } finally {
      setIdSaving(false);
    }
  };

  const handleSaveEmail = async () => {
    if (!user || !emailInput.trim()) return;
    setEmailSaving(true);
    try {
      const res = await api.patch<{ ok: boolean; rw_uuid: string | null; rw_id: number | null }>(
        `/users/${user.id}/email`,
        { email: emailInput.trim() }
      );
      const parts = ["Email saved"];
      if (res.rw_uuid) parts.push(`UUID: ${res.rw_uuid}`);
      if (res.rw_id != null) parts.push(`rw_id: ${res.rw_id}`);
      message.success(parts.join(", "));
      await load(user.id);
      onChanged?.();
    } catch {
      message.error("Failed to save email");
    } finally {
      setEmailSaving(false);
    }
  };

  const handleAdjustCredits = async () => {
    if (!user || creditsDelta == null || creditsDelta === 0) return;
    setCreditsSaving(true);
    try {
      const res = await api.post<{ ok: boolean; balance: number }>(
        `/users/${user.id}/credits`,
        { amount: creditsDelta }
      );
      message.success(`Balance updated: ${formatPoints(res.balance)}`);
      setCreditsDelta(null);
      await load(user.id);
      onChanged?.();
    } catch (e) {
      const status = (e as { status?: number })?.status;
      message.error(status === 400 ? "Not enough points to deduct" : "Failed to update balance");
    } finally {
      setCreditsSaving(false);
    }
  };

  const handleSendMessage = async () => {
    if (!user || !msgText.trim()) return;
    if (user.tg_id == null) {
      message.error("User has no Telegram ID");
      return;
    }
    setMsgSending(true);
    try {
      await api.post(`/users/${user.id}/send-message`, { text: msgText });
      message.success("Message sent");
      setMsgText("");
    } catch {
      message.error("Failed to send");
    } finally {
      setMsgSending(false);
    }
  };

  const labelStyle = { color: "rgba(255,255,255,0.85)" } as const;
  const displayName = user
    ? (user.username || user.email || (user.tg_id != null ? String(user.tg_id) : `#${user.id}`))
    : "User";

  return (
    <Drawer
      title={user ? `User: ${displayName}` : "User"}
      open={open}
      onClose={onClose}
      width={isMobile ? "100%" : 520}
      loading={loading}
    >
      {user && (
        <>
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="ID">{user.id}</Descriptions.Item>
            <Descriptions.Item label="TG ID">{user.tg_id ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="Username">{user.username || "—"}</Descriptions.Item>
            <Descriptions.Item label="Email">{user.email || "—"}</Descriptions.Item>
            <Descriptions.Item label="vless_uuid">
              <Typography.Text copyable={!!user.vless_uuid} style={{ fontSize: 12, wordBreak: "break-all" }}>
                {user.vless_uuid || "—"}
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="rw_id">{user.rw_id ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="Provider">{user.api_provider}</Descriptions.Item>
            <Descriptions.Item label="Promo code">
              {user.promo_code ? <Tag color="purple" icon={<GiftOutlined />}>{user.promo_code}</Tag> : "—"}
            </Descriptions.Item>
            <Descriptions.Item label="Bonus points">
              <Tag color="blue" icon={<WalletOutlined />}>
                {formatPoints(user.bonus_credits ?? 0)}
              </Tag>
              <Typography.Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                1 point = 1 {POINTS_ICON} of tariff price
              </Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Open tickets">{user.tickets_count}</Descriptions.Item>
            <Descriptions.Item label="Banned">{user.is_banned ? "Yes" : "No"}</Descriptions.Item>
            <Descriptions.Item label="VIP">{user.vip ? "Yes" : "No"}</Descriptions.Item>
            <Descriptions.Item label="Language">{user.language || "—"}</Descriptions.Item>
            <Descriptions.Item label="Total Spent">{user.total_spent}</Descriptions.Item>
            <Descriptions.Item label="Transactions">{user.transactions_count}</Descriptions.Item>
          </Descriptions>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <Typography.Text strong style={labelStyle}>
            <IdcardOutlined style={{ marginRight: 6 }} />
            Identifiers
          </Typography.Text>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
            <Input
              addonBefore="TG ID"
              value={editTgId}
              onChange={(e) => setEditTgId(e.target.value)}
              placeholder="123456789 (optional)"
              allowClear
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
            <Input
              addonBefore="rw_id"
              value={editRwId}
              onChange={(e) => setEditRwId(e.target.value)}
              placeholder="Remnawave panel user id"
              allowClear
            />
            <Button type="primary" icon={<EditOutlined />} loading={idSaving} onClick={handleSaveIdentifiers}>
              Save identifiers
            </Button>
          </div>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <Typography.Text strong style={labelStyle}>
            <EditOutlined style={{ marginRight: 6 }} />
            User email
          </Typography.Text>
          <Space.Compact style={{ width: "100%", marginTop: 8 }}>
            <Input
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder="user@example.com"
              onPressEnter={handleSaveEmail}
            />
            <Button type="primary" onClick={handleSaveEmail} loading={emailSaving} icon={<EditOutlined />}>
              Save
            </Button>
          </Space.Compact>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <Typography.Text strong style={labelStyle}>
            <WalletOutlined style={{ marginRight: 6 }} />
            Bonus balance
          </Typography.Text>
          <Space.Compact style={{ width: "100%", marginTop: 8 }}>
            <InputNumber
              style={{ flex: 1 }}
              value={creditsDelta}
              onChange={(v) => setCreditsDelta(v)}
              placeholder={`± ${POINTS_ICON}`}
              min={-3650}
              max={3650}
            />
            <Button
              type="primary"
              onClick={handleAdjustCredits}
              loading={creditsSaving}
              disabled={creditsDelta == null || creditsDelta === 0}
            >
              Apply
            </Button>
          </Space.Compact>
          <Typography.Text type="secondary" style={{ display: "block", marginTop: 6, fontSize: 12 }}>
            Positive number credits, negative debits.
          </Typography.Text>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <Typography.Text strong style={labelStyle}>
            <SendOutlined style={{ marginRight: 6 }} />
            Message to user
          </Typography.Text>
          {user.tg_id == null && (
            <Typography.Text type="secondary" style={{ display: "block", marginTop: 6, fontSize: 12 }}>
              Unavailable: this account has no Telegram ID (Android / web).
            </Typography.Text>
          )}
          <Input.TextArea
            style={{ marginTop: 8 }}
            rows={3}
            value={msgText}
            onChange={(e) => setMsgText(e.target.value)}
            placeholder="Message text..."
            disabled={user.tg_id == null}
          />
          <Button
            type="primary"
            style={{ marginTop: 8 }}
            icon={<SendOutlined />}
            loading={msgSending}
            onClick={handleSendMessage}
            disabled={!msgText.trim() || user.tg_id == null}
          >
            Send
          </Button>

          <Divider style={{ borderColor: "rgba(255,255,255,0.1)" }} />

          <h4 style={{ color: "rgba(255,255,255,0.85)" }}>Transactions</h4>
          <List
            size="small"
            dataSource={tx}
            locale={{ emptyText: "No transactions" }}
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
