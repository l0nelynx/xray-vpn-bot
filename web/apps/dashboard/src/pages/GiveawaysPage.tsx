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
  Spin,
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
        per_page: "20",
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

  return (
    <div>
      <Typography.Title
        level={isMobile ? 5 : 4}
        style={{ margin: 0, marginBottom: isMobile ? 12 : 20, color: "rgba(255,255,255,0.88)" }}
      >
        <TrophyOutlined /> Giveaways
      </Typography.Title>

      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Filter by status"
          style={{ width: 160 }}
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
        <Button icon={<ReloadOutlined />} onClick={load}>
          Refresh
        </Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          New giveaway
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={items}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: setPage,
        }}
        scroll={{ x: isMobile ? 640 : undefined }}
        size={isMobile ? "small" : "middle"}
      />

      <Drawer
        title={editing ? `Edit #${editing.id}` : "New giveaway"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={isMobile ? "100%" : 520}
        extra={
          <Button type="primary" onClick={onSave}>
            Save
          </Button>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="channel_text" label="Post / broadcast text (HTML)">
            <TextArea rows={5} />
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
            <Form.Item name="distribution_bot" valuePropName="checked" noStyle>
              <Checkbox>Bot broadcast</Checkbox>
            </Form.Item>
            <Form.Item name="distribution_channel" valuePropName="checked" noStyle>
              <Checkbox style={{ marginLeft: 16 }}>Channel post</Checkbox>
            </Form.Item>
          </Form.Item>
          <Form.Item name="entry_condition" label="Entry requirement">
            <Radio.Group>
              <Radio value="click_only">Click participate</Radio>
              <Radio value="channel_sub">Channel subscription</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="chance_mode" label="Ticket mode">
            <Radio.Group>
              <Radio value="static">Static (1 ticket per participant)</Radio>
              <Radio value="dynamic">Dynamic (extra tickets for invitees)</Radio>
            </Radio.Group>
          </Form.Item>
          {chanceMode === "dynamic" && (
            <Form.Item label="Extra ticket sources">
              <Form.Item name="ticket_ref" valuePropName="checked" noStyle>
                <Checkbox>Invitee activated referral code</Checkbox>
              </Form.Item>
              <br />
              <Form.Item name="ticket_purchase" valuePropName="checked" noStyle>
                <Checkbox>Invitee purchased subscription</Checkbox>
              </Form.Item>
            </Form.Item>
          )}
          <Form.Item name="winner_selection" label="Winner selection">
            <Radio.Group>
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
      >
        {detail && (
          <Spin spinning={false}>
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              <div>
                {statusTag(detail.status)}{" "}
                <Typography.Text type="secondary">
                  {detail.participants} participants · {detail.tickets} tickets
                </Typography.Text>
              </div>
              <Space wrap>
                {detail.status === "draft" && (
                  <Button type="primary" onClick={() => runAction(detail.id, "activate", "Activated")}>
                    Activate
                  </Button>
                )}
                {detail.status === "active" && (
                  <>
                    <Button onClick={() => runAction(detail.id, "broadcast", "Broadcast queued")}>
                      Bot broadcast
                    </Button>
                    <Button onClick={() => runAction(detail.id, "channel-post", "Posted to channel")}>
                      Channel post
                    </Button>
                    <Button onClick={() => runAction(detail.id, "close", "Closed")}>
                      Close
                    </Button>
                  </>
                )}
                {(detail.status === "active" || detail.status === "closed") && (
                  <Button type="primary" danger onClick={onDraw}>
                    Draw winners
                  </Button>
                )}
                {detail.status === "drawn" && winners.length > 0 && (
                  <Button onClick={() => setWinnersOpen(true)}>Show winners</Button>
                )}
              </Space>
              <Card title="Participants" size="small">
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
              </Card>
            </Space>
          </Spin>
        )}
      </Drawer>

      <Modal
        title="Winners"
        open={winnersOpen}
        onCancel={() => setWinnersOpen(false)}
        footer={[
          <Button key="copy" onClick={copyWinners}>
            Copy list
          </Button>,
          <Button key="close" type="primary" onClick={() => setWinnersOpen(false)}>
            Close
          </Button>,
        ]}
      >
        <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
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
