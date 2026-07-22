import { useCallback, useEffect, useState } from "react";
import {
  App,
  Button,
  Card,
  Checkbox,
  DatePicker,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { TableProps } from "antd";
import {
  PlusOutlined,
  ReloadOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { api } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";

const { TextArea } = Input;

type GiveawayStatus = "draft" | "active" | "closed" | "drawn";

interface GiveawayConfig {
  distribution: string[];
  entry_condition: "click_only" | "channel_sub";
  ticket_sources: string[];
  chance_mode: "static" | "dynamic";
  winner_selection: "random" | "most_tickets";
}

interface GiveawayItem {
  id: number;
  title: string;
  channel_text: string;
  status: GiveawayStatus;
  config: GiveawayConfig;
  winner_count: number;
  starts_at: string | null;
  ends_at: string | null;
  drawn_at: string | null;
  created_at: string;
  participants: number;
  tickets: number;
}

interface ParticipantItem {
  tg_id: number;
  username: string | null;
  joined_at: string;
  ticket_count: number;
}

interface WinnerItem {
  rank: number;
  tg_id: number;
  username: string | null;
  tickets: number;
}

const STATUS_COLORS: Record<GiveawayStatus, string> = {
  draft: "default",
  active: "green",
  closed: "orange",
  drawn: "blue",
};

const PER_PAGE = 20;

function statusTag(status: GiveawayStatus) {
  return <Tag color={STATUS_COLORS[status]}>{status}</Tag>;
}

export default function GiveawaysPage() {
  const isMobile = useIsMobile();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<GiveawayItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<GiveawayItem | null>(null);
  const [detail, setDetail] = useState<GiveawayItem | null>(null);
  const [participants, setParticipants] = useState<ParticipantItem[]>([]);
  const [winners, setWinners] = useState<WinnerItem[]>([]);
  const [winnersOpen, setWinnersOpen] = useState(false);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(PER_PAGE),
      });
      if (statusFilter) params.set("status", statusFilter);
      const data = await api.get<{ items: GiveawayItem[]; total: number }>(
        `/giveaways?${params}`,
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      message.error((e as Error).message || "Failed to load giveaways");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, message]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    form.setFieldsValue({
      title: "",
      channel_text: "",
      winner_count: 1,
      entry_condition: "click_only",
      chance_mode: "static",
      winner_selection: "random",
      distribution_bot: true,
      distribution_channel: false,
      ticket_ref: false,
      ticket_purchase: false,
      starts_at: null,
      ends_at: null,
    });
    setDrawerOpen(true);
  };

  const openEdit = (item: GiveawayItem) => {
    setEditing(item);
    form.setFieldsValue({
      title: item.title,
      channel_text: item.channel_text,
      winner_count: item.winner_count,
      entry_condition: item.config.entry_condition,
      chance_mode: item.config.chance_mode,
      winner_selection: item.config.winner_selection,
      distribution_bot: item.config.distribution.includes("bot"),
      distribution_channel: item.config.distribution.includes("channel"),
      ticket_ref: item.config.ticket_sources.includes("invitee_ref_activation"),
      ticket_purchase: item.config.ticket_sources.includes("invitee_purchase"),
      starts_at: item.starts_at ? dayjs(item.starts_at) : null,
      ends_at: item.ends_at ? dayjs(item.ends_at) : null,
    });
    setDrawerOpen(true);
  };

  const buildConfig = (values: Record<string, unknown>): GiveawayConfig => {
    const distribution: string[] = [];
    if (values.distribution_bot) distribution.push("bot");
    if (values.distribution_channel) distribution.push("channel");
    const chanceMode = values.chance_mode as GiveawayConfig["chance_mode"];
    const ticketSources: string[] = [];
    if (chanceMode === "dynamic") {
      if (values.ticket_ref) ticketSources.push("invitee_ref_activation");
      if (values.ticket_purchase) ticketSources.push("invitee_purchase");
    }
    return {
      distribution: distribution.length ? distribution : ["bot"],
      entry_condition: values.entry_condition as GiveawayConfig["entry_condition"],
      ticket_sources: ticketSources,
      chance_mode: chanceMode,
      winner_selection: values.winner_selection as GiveawayConfig["winner_selection"],
    };
  };

  const onSave = async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        title: values.title,
        channel_text: values.channel_text || "",
        winner_count: values.winner_count,
        starts_at: values.starts_at ? values.starts_at.format("YYYY-MM-DDTHH:mm:ss") : null,
        ends_at: values.ends_at ? values.ends_at.format("YYYY-MM-DDTHH:mm:ss") : null,
        config: buildConfig(values),
      };
      if (editing) {
        await api.patch(`/giveaways/${editing.id}`, payload);
        message.success("Giveaway updated");
      } else {
        await api.post("/giveaways", payload);
        message.success("Giveaway created");
      }
      setDrawerOpen(false);
      load();
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return;
      message.error((e as Error).message || "Failed to save");
    }
  };

  const runAction = async (id: number, action: string, successMsg: string) => {
    try {
      await api.post(`/giveaways/${id}/${action}`);
      message.success(successMsg);
      load();
      if (detail?.id === id) {
        const updated = await api.get<GiveawayItem>(`/giveaways/${id}`);
        setDetail(updated);
      }
    } catch (e) {
      message.error((e as Error).message || "Action failed");
    }
  };

  const openDetail = async (item: GiveawayItem) => {
    setDetail(item);
    try {
      const [pData, wData] = await Promise.all([
        api.get<{ items: ParticipantItem[] }>(`/giveaways/${item.id}/participants?per_page=100`),
        api.get<{ winners: WinnerItem[] }>(`/giveaways/${item.id}/winners`),
      ]);
      setParticipants(pData.items);
      setWinners(wData.winners);
    } catch (e) {
      message.error((e as Error).message || "Failed to load details");
    }
  };

  const onDraw = async () => {
    if (!detail) return;
    try {
      const data = await api.post<{ winners: WinnerItem[] }>(`/giveaways/${detail.id}/draw`);
      setWinners(data.winners);
      setWinnersOpen(true);
      load();
      const updated = await api.get<GiveawayItem>(`/giveaways/${detail.id}`);
      setDetail(updated);
    } catch (e) {
      message.error((e as Error).message || "Draw failed");
    }
  };

  const copyWinners = () => {
    const text = winners
      .map(
        (w) =>
          `#${w.rank}: ${w.username ? `@${w.username}` : "—"} (${w.tg_id}) — ${w.tickets} tickets`,
      )
      .join("\n");
    navigator.clipboard.writeText(text);
    message.success("Copied to clipboard");
  };

  const columns: TableProps<GiveawayItem>["columns"] = [
    { title: "ID", dataIndex: "id", width: 64 },
    { title: "Title", dataIndex: "title", ellipsis: true },
    {
      title: "Status",
      dataIndex: "status",
      render: (s: GiveawayStatus) => statusTag(s),
    },
    { title: "Participants", dataIndex: "participants", width: 110 },
    { title: "Tickets", dataIndex: "tickets", width: 80 },
    { title: "Winners", dataIndex: "winner_count", width: 80 },
    {
      title: "Actions",
      key: "actions",
      render: (_v, record) => (
        <Space wrap>
          <Button size="small" onClick={() => openDetail(record)}>
            Open
          </Button>
          {record.status === "draft" && (
            <Button size="small" onClick={() => openEdit(record)}>
              Edit
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const chanceMode = Form.useWatch("chance_mode", form);
  const radioStyle = isMobile
    ? { display: "flex", flexDirection: "column" as const, gap: 8 }
    : undefined;

  const renderMobileCard = (item: GiveawayItem) => (
    <Card
      key={item.id}
      size="small"
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: "12px" } }}
      onClick={() => openDetail(item)}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "flex-start" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              color: "rgba(255,255,255,0.88)",
              marginBottom: 6,
              wordBreak: "break-word",
            }}
          >
            {item.title || `Giveaway #${item.id}`}
          </div>
          <div style={{ marginBottom: 6 }}>{statusTag(item.status)}</div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.55)" }}>
            #{item.id} · {item.participants} participants · {item.tickets} tickets
          </div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)", marginTop: 2 }}>
            Winners: {item.winner_count}
            {item.ends_at ? ` · Ends ${dayjs(item.ends_at).format("DD.MM HH:mm")}` : ""}
          </div>
        </div>
        {item.status === "draft" && (
          <Button
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              openEdit(item);
            }}
          >
            Edit
          </Button>
        )}
      </div>
    </Card>
  );

  return (
    <div>
      <Typography.Title
        level={isMobile ? 5 : 4}
        style={{ margin: 0, marginBottom: isMobile ? 12 : 20, color: "rgba(255,255,255,0.88)" }}
      >
        <TrophyOutlined /> Giveaways
      </Typography.Title>

      <div
        style={{
          marginBottom: 16,
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          justifyContent: isMobile ? "stretch" : "flex-start",
        }}
      >
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} block={isMobile}>
          New giveaway
        </Button>
        <Button icon={<ReloadOutlined />} onClick={load} loading={loading} block={isMobile}>
          Refresh
        </Button>
        <Select
          allowClear
          placeholder="Filter by status"
          style={{ width: isMobile ? "100%" : 160 }}
          value={statusFilter || undefined}
          onChange={(v) => {
            setStatusFilter(v || "");
            setPage(1);
          }}
          options={[
            { value: "draft", label: "draft" },
            { value: "active", label: "active" },
            { value: "closed", label: "closed" },
            { value: "drawn", label: "drawn" },
          ]}
        />
      </div>

      {isMobile ? (
        <>
          {loading ? (
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
              Loading...
            </div>
          ) : items.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
              No giveaways
            </div>
          ) : (
            items.map(renderMobileCard)
          )}
          <div
            style={{
              textAlign: "center",
              padding: "12px 0",
              color: "rgba(255,255,255,0.45)",
              fontSize: 12,
            }}
          >
            Page {page} · Total: {total}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
            <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Prev
            </Button>
            <Button
              size="small"
              disabled={page * PER_PAGE >= total}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        </>
      ) : (
        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={items}
          pagination={{
            current: page,
            pageSize: PER_PAGE,
            total,
            onChange: setPage,
            showSizeChanger: false,
          }}
          size="middle"
        />
      )}

      <Drawer
        title={editing ? `Edit #${editing.id}` : "New giveaway"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={isMobile ? "100%" : 520}
        styles={isMobile ? { body: { paddingBottom: 80 } } : undefined}
        extra={
          !isMobile ? (
            <Button type="primary" onClick={onSave}>
              Save
            </Button>
          ) : undefined
        }
        footer={
          isMobile ? (
            <Button type="primary" onClick={onSave} block>
              Save
            </Button>
          ) : undefined
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="channel_text" label="Post / broadcast text (HTML)">
            <TextArea rows={isMobile ? 4 : 5} />
          </Form.Item>
          <Form.Item name="winner_count" label="Number of winners" rules={[{ required: true }]}>
            <InputNumber min={1} max={100} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="starts_at" label="Starts at (optional)">
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="ends_at" label="Ends at (optional)">
            <DatePicker showTime style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="Distribution">
            <Space direction={isMobile ? "vertical" : "horizontal"} size={isMobile ? 8 : 16}>
              <Form.Item name="distribution_bot" valuePropName="checked" noStyle>
                <Checkbox>Bot broadcast</Checkbox>
              </Form.Item>
              <Form.Item name="distribution_channel" valuePropName="checked" noStyle>
                <Checkbox>Channel post</Checkbox>
              </Form.Item>
            </Space>
          </Form.Item>
          <Form.Item name="entry_condition" label="Entry requirement">
            <Radio.Group style={radioStyle}>
              <Radio value="click_only">Click participate</Radio>
              <Radio value="channel_sub">Channel subscription</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="chance_mode" label="Ticket mode">
            <Radio.Group style={radioStyle}>
              <Radio value="static">Static (1 ticket per participant)</Radio>
              <Radio value="dynamic">Dynamic (extra tickets for invitees)</Radio>
            </Radio.Group>
          </Form.Item>
          {chanceMode === "dynamic" && (
            <Form.Item label="Extra ticket sources">
              <Space direction="vertical" size={8}>
                <Form.Item name="ticket_ref" valuePropName="checked" noStyle>
                  <Checkbox>Invitee activated referral code</Checkbox>
                </Form.Item>
                <Form.Item name="ticket_purchase" valuePropName="checked" noStyle>
                  <Checkbox>Invitee purchased subscription</Checkbox>
                </Form.Item>
              </Space>
            </Form.Item>
          )}
          <Form.Item name="winner_selection" label="Winner selection">
            <Radio.Group style={radioStyle}>
              <Radio value="random">Random (weighted by tickets)</Radio>
              <Radio value="most_tickets">Most tickets</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Drawer>

      <Drawer
        title={detail ? `${detail.title} (#${detail.id})` : "Giveaway"}
        open={!!detail}
        onClose={() => setDetail(null)}
        width={isMobile ? "100%" : 640}
        styles={isMobile ? { body: { paddingBottom: 24 } } : undefined}
      >
        {detail && (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <div>
              {statusTag(detail.status)}{" "}
              <Typography.Text type="secondary">
                {detail.participants} participants · {detail.tickets} tickets
              </Typography.Text>
            </div>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
              }}
            >
              {detail.status === "draft" && (
                <Button
                  type="primary"
                  block={isMobile}
                  onClick={() => runAction(detail.id, "activate", "Activated")}
                >
                  Activate
                </Button>
              )}
              {detail.status === "active" && (
                <>
                  <Button
                    block={isMobile}
                    onClick={() => runAction(detail.id, "broadcast", "Broadcast queued")}
                  >
                    Bot broadcast
                  </Button>
                  <Button
                    block={isMobile}
                    onClick={() => runAction(detail.id, "channel-post", "Posted to channel")}
                  >
                    Channel post
                  </Button>
                  <Button block={isMobile} onClick={() => runAction(detail.id, "close", "Closed")}>
                    Close
                  </Button>
                </>
              )}
              {(detail.status === "active" || detail.status === "closed") && (
                <Button type="primary" danger block={isMobile} onClick={onDraw}>
                  Draw winners
                </Button>
              )}
              {detail.status === "drawn" && winners.length > 0 && (
                <Button block={isMobile} onClick={() => setWinnersOpen(true)}>
                  Show winners
                </Button>
              )}
            </div>
            <Card title="Participants" size="small">
              {isMobile ? (
                participants.length === 0 ? (
                  <Typography.Text type="secondary">No participants yet</Typography.Text>
                ) : (
                  participants.map((p) => (
                    <div
                      key={p.tg_id}
                      style={{
                        padding: "8px 0",
                        borderBottom: "1px solid rgba(255,255,255,0.06)",
                      }}
                    >
                      <div style={{ fontWeight: 500, color: "rgba(255,255,255,0.85)" }}>
                        {p.username ? `@${p.username}` : p.tg_id}
                      </div>
                      <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>
                        {p.tg_id} · {p.ticket_count} tickets
                      </div>
                    </div>
                  ))
                )
              ) : (
                <Table
                  rowKey="tg_id"
                  size="small"
                  pagination={false}
                  dataSource={participants}
                  columns={[
                    {
                      title: "User",
                      render: (_v, r) =>
                        r.username ? `@${r.username}` : String(r.tg_id),
                    },
                    { title: "tg_id", dataIndex: "tg_id" },
                    { title: "Tickets", dataIndex: "ticket_count" },
                  ]}
                />
              )}
            </Card>
          </Space>
        )}
      </Drawer>

      <Modal
        title="Winners"
        open={winnersOpen}
        onCancel={() => setWinnersOpen(false)}
        width={isMobile ? "calc(100vw - 16px)" : undefined}
        style={isMobile ? { top: 16, maxWidth: "calc(100vw - 16px)", margin: "0 auto" } : undefined}
        footer={[
          <Button key="copy" onClick={copyWinners} block={isMobile}>
            Copy list
          </Button>,
          <Button
            key="close"
            type="primary"
            onClick={() => setWinnersOpen(false)}
            block={isMobile}
          >
            Close
          </Button>,
        ]}
      >
        <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: isMobile ? 13 : undefined }}>
          {winners
            .map(
              (w) =>
                `#${w.rank}: ${w.username ? `@${w.username}` : "—"} (${w.tg_id}) — ${w.tickets} tickets`,
            )
            .join("\n") || "No winners yet"}
        </pre>
      </Modal>
    </div>
  );
}
