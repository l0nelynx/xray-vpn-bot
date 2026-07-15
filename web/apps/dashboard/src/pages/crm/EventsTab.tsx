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
} from "antd";
import { useCallback, useEffect, useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import ActionsBuilder from "./ActionsBuilder";
import ConditionsBuilder from "./ConditionsBuilder";
import {
  createEvent,
  deleteEvent,
  fetchEvents,
  fetchSegments,
  runEventNow,
  updateEvent,
} from "./api";
import { actionSummary, defaultActions, defaultConditions, getSegmentCondition } from "./helpers";
import type { CrmAction, CrmCondition, CrmEventRow, SegmentDef } from "./types";
import { REPEAT_POLICIES, WEEKDAYS } from "./types";

export default function EventsTab() {
  const { message } = App.useApp();
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<CrmEventRow[]>([]);
  const [segments, setSegments] = useState<SegmentDef[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<CrmEventRow | null>(null);
  const [conditions, setConditions] = useState<CrmCondition[]>([]);
  const [actions, setActions] = useState<CrmAction[]>(defaultActions());
  const [selectedTgIds, setSelectedTgIds] = useState<number[]>([]);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEvents(await fetchEvents());
    } catch {
      message.error("Не удалось загрузить события");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    load();
    fetchSegments()
      .then(setSegments)
      .catch(() => {});
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    const firstSeg = segments[0];
    setConditions(firstSeg ? defaultConditions(firstSeg.id, firstSeg) : []);
    setActions(defaultActions());
    setSelectedTgIds([]);
    form.setFieldsValue({
      enabled: true,
      run_at_time: "01:00",
      frequency: "daily",
      repeat_policy: "cooldown",
      repeat_cooldown_days: 7,
    });
    setDrawerOpen(true);
  };

  const openEdit = (row: CrmEventRow) => {
    setEditing(row);
    setConditions(
      row.conditions?.length
        ? row.conditions
        : defaultConditions(row.segment_type || "limited", undefined)
    );
    setActions(row.actions?.length ? row.actions : defaultActions());
    setSelectedTgIds([]);
    form.setFieldsValue({
      name: row.name,
      enabled: row.enabled,
      run_at_time: row.run_at_time,
      frequency: row.frequency,
      weekday: row.weekday,
      repeat_policy: row.repeat_policy,
      repeat_cooldown_days: row.repeat_cooldown_days,
    });
    setDrawerOpen(true);
  };

  const saveEvent = async () => {
    const values = await form.validateFields();
    if (!actions.some((a) => a.enabled)) {
      message.warning("Включите хотя бы одно действие");
      return;
    }

    const segmentId = getSegmentCondition(conditions)?.segment_id;
    const payload: Record<string, unknown> = {
      name: values.name,
      enabled: values.enabled,
      conditions,
      actions,
      run_at_time: values.run_at_time,
      frequency: values.frequency,
      weekday: values.frequency === "weekly" ? values.weekday : null,
      repeat_policy: values.repeat_policy,
      repeat_cooldown_days: values.repeat_cooldown_days,
    };

    if (segmentId !== "all_users" && selectedTgIds.length > 0) {
      payload.conditions = [
        ...conditions.filter((c) => c.type !== "tg_allowlist"),
        { type: "tg_allowlist", tg_ids: selectedTgIds },
      ];
    }

    try {
      if (editing) {
        await updateEvent(editing.id, payload);
        message.success("Событие обновлено");
      } else {
        await createEvent(payload);
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
      await updateEvent(row.id, { enabled });
      load();
    } catch {
      message.error("Не удалось изменить статус");
    }
  };

  const handleRunNow = async (row: CrmEventRow) => {
    try {
      const res = await runEventNow(row.id);
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

  const handleDelete = async (row: CrmEventRow) => {
    try {
      await deleteEvent(row.id);
      message.success("Удалено");
      load();
    } catch {
      message.error("Ошибка удаления");
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

  const repeatLabel = (row: CrmEventRow) =>
    row.repeat_policy === "cooldown"
      ? `cooldown ${row.repeat_cooldown_days}д`
      : row.repeat_policy;

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
      title: "Действия",
      key: "actions",
      render: (_: unknown, r: CrmEventRow) =>
        r.actions?.length ? actionSummary(r.actions) : "—",
    },
    {
      title: "Расписание (UTC)",
      key: "schedule",
      render: (_: unknown, r: CrmEventRow) => scheduleLabel(r),
    },
    {
      title: "Повтор",
      key: "repeat",
      render: (_: unknown, r: CrmEventRow) => repeatLabel(r),
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
      key: "ops",
      width: 200,
      render: (_: unknown, r: CrmEventRow) => (
        <Space size="small">
          <Button size="small" onClick={() => openEdit(r)}>
            Изм.
          </Button>
          <Button size="small" type="primary" onClick={() => handleRunNow(r)}>
            Сейчас
          </Button>
          <Popconfirm title="Удалить событие?" onConfirm={() => handleDelete(r)}>
            <Button size="small" danger>
              Del
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const renderMobileEventCard = (row: CrmEventRow) => (
    <Card
      key={row.id}
      size="small"
      style={{ marginBottom: 8 }}
      styles={{ body: { padding: "12px" } }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, color: "rgba(255,255,255,0.88)", marginBottom: 4 }}>
            {row.name || `Событие #${row.id}`}
          </div>
          <div style={{ fontSize: 12, color: "rgba(255,255,255,0.45)", marginBottom: 6 }}>
            {row.segment_type ?? "—"} · {scheduleLabel(row)}
          </div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginBottom: 6 }}>
            {row.actions?.length ? actionSummary(row.actions) : "—"} · {repeatLabel(row)}
          </div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
            След.: {row.next_run_at ?? "—"}
          </div>
        </div>
        <Switch checked={row.enabled} onChange={(v) => toggleEnabled(row, v)} size="small" />
      </div>
      <Space wrap style={{ marginTop: 10 }}>
        <Button size="small" onClick={() => openEdit(row)}>
          Изм.
        </Button>
        <Button size="small" type="primary" onClick={() => handleRunNow(row)}>
          Сейчас
        </Button>
        <Popconfirm title="Удалить событие?" onConfirm={() => handleDelete(row)}>
          <Button size="small" danger>
            Del
          </Button>
        </Popconfirm>
      </Space>
    </Card>
  );

  const selectedFrequency = Form.useWatch("frequency", form);
  const selectedRepeat = Form.useWatch("repeat_policy", form);
  const segmentId = getSegmentCondition(conditions)?.segment_id ?? null;

  const headerActions = isMobile ? (
    <Space direction="vertical" style={{ width: "100%" }} size={8}>
      <Button onClick={load} loading={loading} block>
        Обновить
      </Button>
      <Button type="primary" onClick={openCreate} block>
        Новое событие
      </Button>
    </Space>
  ) : (
    <Space>
      <Button onClick={load} loading={loading}>
        Обновить
      </Button>
      <Button type="primary" onClick={openCreate}>
        Новое событие
      </Button>
    </Space>
  );

  return (
    <>
      <Card
        title="События по расписанию (UTC)"
        extra={isMobile ? undefined : headerActions}
        styles={isMobile ? { header: { flexWrap: "wrap" } } : undefined}
      >
        {isMobile && <div style={{ marginBottom: 12 }}>{headerActions}</div>}
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Время запуска указывается в UTC. Poller проверяет расписание каждые 15 минут."
        />
        {isMobile ? (
          loading ? (
            <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
              Загрузка...
            </div>
          ) : (
            events.map(renderMobileEventCard)
          )
        ) : (
          <Table
            rowKey="id"
            loading={loading}
            columns={columns}
            dataSource={events}
            size="small"
            pagination={{ pageSize: 20 }}
          />
        )}
      </Card>

      <Drawer
        title={editing ? `Событие #${editing.id}` : "Новое событие"}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={isMobile ? "100%" : 640}
        destroyOnHidden
        extra={
          <Button type="primary" onClick={saveEvent} size={isMobile ? "small" : "middle"}>
            Сохранить
          </Button>
        }
        styles={isMobile ? { body: { paddingBottom: 24 } } : undefined}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Название">
            <Input placeholder="Например: LIMITED — утреннее напоминание" />
          </Form.Item>
          <Form.Item name="enabled" label="Включено" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>

        <Card title="Триггер" size="small" style={{ marginBottom: 16 }}>
          <Form form={form} layout="vertical">
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
            <Form.Item name="repeat_policy" label="Политика повторов">
              <Select options={REPEAT_POLICIES} />
            </Form.Item>
            {selectedRepeat === "cooldown" && (
              <Form.Item name="repeat_cooldown_days" label="Cooldown (дней)">
                <InputNumber min={1} max={365} style={{ width: "100%" }} />
              </Form.Item>
            )}
          </Form>
        </Card>

        <ConditionsBuilder
          conditions={conditions}
          onChange={setConditions}
          segmentTypes={segments}
          selectedTgIds={selectedTgIds}
          onSelectedTgIdsChange={setSelectedTgIds}
        />

        <ActionsBuilder actions={actions} onChange={setActions} segmentId={segmentId} />
      </Drawer>
    </>
  );
}
