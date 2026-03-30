import { useEffect, useState, useCallback } from "react";
import {
  Typography, Card, Button, Input, Switch, Space, Row, Col, List,
  message, Popconfirm, Select, Empty, Badge,
} from "antd";
import {
  PlusOutlined, DeleteOutlined, EditOutlined, SaveOutlined,
  HolderOutlined,
} from "@ant-design/icons";
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
  DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, verticalListSortingStrategy, useSortable, arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api } from "../api/client";
import type { MenuScreen, MenuButton as MenuButtonType } from "../api/types";
import TelegramPreview from "../components/TelegramPreview";
import ButtonEditor from "../components/ButtonEditor";
import useIsMobile from "../hooks/useIsMobile";

function SortableButtonItem({
  btn, onEdit, onDelete,
}: {
  btn: MenuButtonType;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: btn.id });
  const style = { transform: CSS.Transform.toString(transform), transition };

  return (
    <div
      ref={setNodeRef}
      style={{
        ...style,
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 12px",
        background: "rgba(255,255,255,0.02)",
        borderRadius: 6,
        marginBottom: 4,
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <span {...attributes} {...listeners} style={{ cursor: "grab" }}>
        <HolderOutlined style={{ color: "rgba(255,255,255,0.3)" }} />
      </span>
      <Badge
        status={btn.is_active ? "success" : "default"}
        style={{ marginRight: 4 }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.85)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {btn.text_ru}
        </div>
        <div style={{ fontSize: 11, color: "rgba(255,255,255,0.35)" }}>
          {btn.button_type} · {btn.callback_data || btn.url || "—"}
          {btn.visibility_condition !== "always" && ` · ${btn.visibility_condition}`}
        </div>
      </div>
      <Space size={4}>
        <Button size="small" type="text" icon={<EditOutlined />} onClick={onEdit} />
        <Popconfirm title="Delete button?" onConfirm={onDelete} placement="left">
          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    </div>
  );
}

export default function MenuEditorPage() {
  const [screens, setScreens] = useState<MenuScreen[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingBtn, setEditingBtn] = useState<Partial<MenuButtonType> | null>(null);
  const [btnEditorOpen, setBtnEditorOpen] = useState(false);
  const [previewLang, setPreviewLang] = useState<"ru" | "en">("ru");
  const isMobile = useIsMobile();

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const selected = screens.find((s) => s.id === selectedId) || null;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<MenuScreen[]>("/menus/screens");
      setScreens(data);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
      }
    } catch {
      message.error("Failed to load screens");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateScreen = (field: string, value: unknown) => {
    if (!selected) return;
    setScreens((prev) =>
      prev.map((s) => (s.id === selected.id ? { ...s, [field]: value } : s))
    );
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await api.put(`/menus/screens/${selected.id}`, {
        slug: selected.slug,
        name: selected.name,
        message_text_ru: selected.message_text_ru,
        message_text_en: selected.message_text_en,
        is_active: selected.is_active,
      });

      // Save button reorder
      const sortedButtons = [...selected.buttons].sort((a, b) => a.sort_order - b.sort_order);
      await api.put(`/menus/screens/${selected.id}/buttons/reorder`, {
        items: sortedButtons.map((b, i) => ({
          id: b.id, row: i, col: 0, sort_order: i,
        })),
      });

      message.success("Screen saved!");
      await load();
    } catch {
      message.error("Failed to save");
    }
    setSaving(false);
  };

  const handleAddScreen = async () => {
    try {
      const newScreen = await api.post<MenuScreen>("/menus/screens", {
        slug: `screen_${Date.now()}`,
        name: "New Screen",
        message_text_ru: "",
        message_text_en: "",
        is_system: false,
        is_active: true,
      });
      setScreens((prev) => [...prev, newScreen]);
      setSelectedId(newScreen.id);
      message.success("Screen created");
    } catch {
      message.error("Failed to create screen");
    }
  };

  const handleDeleteScreen = async (id: number) => {
    try {
      await api.delete(`/menus/screens/${id}`);
      setScreens((prev) => prev.filter((s) => s.id !== id));
      if (selectedId === id) {
        setSelectedId(screens.find((s) => s.id !== id)?.id || null);
      }
      message.success("Screen deleted");
    } catch (e: unknown) {
      message.error(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const handleAddButton = () => {
    setEditingBtn({
      text_ru: "",
      text_en: "",
      callback_data: "",
      button_type: "callback",
      is_active: true,
      visibility_condition: "always",
      row: selected?.buttons.length || 0,
      col: 0,
      sort_order: selected?.buttons.length || 0,
    });
    setBtnEditorOpen(true);
  };

  const handleEditButton = (btn: MenuButtonType) => {
    setEditingBtn(btn);
    setBtnEditorOpen(true);
  };

  const handleSaveButton = async (values: Partial<MenuButtonType>) => {
    if (!selected) return;
    try {
      if (values.id) {
        const updated = await api.put<MenuButtonType>(`/menus/buttons/${values.id}`, values);
        setScreens((prev) =>
          prev.map((s) =>
            s.id === selected.id
              ? { ...s, buttons: s.buttons.map((b) => (b.id === updated.id ? updated : b)) }
              : s
          )
        );
      } else {
        const created = await api.post<MenuButtonType>(`/menus/screens/${selected.id}/buttons`, values);
        setScreens((prev) =>
          prev.map((s) =>
            s.id === selected.id ? { ...s, buttons: [...s.buttons, created] } : s
          )
        );
      }
      setBtnEditorOpen(false);
      setEditingBtn(null);
      message.success("Button saved");
    } catch {
      message.error("Failed to save button");
    }
  };

  const handleDeleteButton = async (btnId: number) => {
    if (!selected) return;
    try {
      await api.delete(`/menus/buttons/${btnId}`);
      setScreens((prev) =>
        prev.map((s) =>
          s.id === selected.id
            ? { ...s, buttons: s.buttons.filter((b) => b.id !== btnId) }
            : s
        )
      );
      message.success("Button deleted");
    } catch {
      message.error("Failed to delete button");
    }
  };

  const handleButtonDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id || !selected) return;

    const buttons = [...selected.buttons];
    const oldIdx = buttons.findIndex((b) => b.id === active.id);
    const newIdx = buttons.findIndex((b) => b.id === over.id);
    const reordered = arrayMove(buttons, oldIdx, newIdx).map((b, i) => ({
      ...b,
      row: i,
      sort_order: i,
    }));

    setScreens((prev) =>
      prev.map((s) => (s.id === selected.id ? { ...s, buttons: reordered } : s))
    );
  };

  const sortedButtons = selected
    ? [...selected.buttons].sort((a, b) => a.sort_order - b.sort_order)
    : [];

  // Preview
  const previewButtons = sortedButtons
    .filter((b) => b.is_active)
    .map((b, i) => ({
      text: previewLang === "en" ? b.text_en : b.text_ru,
      row: i,
    }));

  const previewMessage = selected
    ? (previewLang === "en" ? selected.message_text_en : selected.message_text_ru) || ""
    : "";

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0, color: "rgba(255,255,255,0.88)" }}>
          Bot Menu Editor
        </Typography.Title>
        <Space>
          <Button icon={<PlusOutlined />} onClick={handleAddScreen}>Add Screen</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave} disabled={!selected}>
            Save
          </Button>
        </Space>
      </div>

      <Row gutter={16}>
        {/* Screen list */}
        <Col xs={24} lg={5}>
          <Card title="Screens" size="small" loading={loading}>
            {screens.length === 0 ? (
              <Empty description="No screens" />
            ) : (
              <List
                size="small"
                dataSource={screens}
                renderItem={(s) => (
                  <List.Item
                    onClick={() => setSelectedId(s.id)}
                    style={{
                      cursor: "pointer",
                      background: s.id === selectedId ? "rgba(100,149,237,0.1)" : "transparent",
                      borderRadius: 6,
                      padding: "6px 8px",
                      marginBottom: 2,
                      border: s.id === selectedId ? "1px solid rgba(100,149,237,0.3)" : "1px solid transparent",
                    }}
                    actions={
                      !s.is_system
                        ? [
                            <Popconfirm
                              key="del"
                              title="Delete screen?"
                              onConfirm={(e) => {
                                e?.stopPropagation();
                                handleDeleteScreen(s.id);
                              }}
                            >
                              <Button
                                size="small"
                                type="text"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={(e) => e.stopPropagation()}
                              />
                            </Popconfirm>,
                          ]
                        : undefined
                    }
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 13, color: "rgba(255,255,255,0.85)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {s.name}
                      </div>
                      <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)" }}>
                        {s.slug} {s.is_system && "· system"}
                      </div>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* Editor */}
        <Col xs={24} lg={10}>
          {selected ? (
            <Card size="small">
              <Space direction="vertical" style={{ width: "100%" }} size={12}>
                <Row gutter={8}>
                  <Col span={8}>
                    <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Slug</label>
                    <Input
                      size="small"
                      value={selected.slug}
                      onChange={(e) => updateScreen("slug", e.target.value)}
                      disabled={selected.is_system}
                    />
                  </Col>
                  <Col span={10}>
                    <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Name</label>
                    <Input size="small" value={selected.name} onChange={(e) => updateScreen("name", e.target.value)} />
                  </Col>
                  <Col span={6}>
                    <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Active</label>
                    <div><Switch size="small" checked={selected.is_active} onChange={(v) => updateScreen("is_active", v)} /></div>
                  </Col>
                </Row>

                <div>
                  <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Message Text (RU)</label>
                  <Input.TextArea
                    size="small"
                    rows={2}
                    value={selected.message_text_ru || ""}
                    onChange={(e) => updateScreen("message_text_ru", e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Message Text (EN)</label>
                  <Input.TextArea
                    size="small"
                    rows={2}
                    value={selected.message_text_en || ""}
                    onChange={(e) => updateScreen("message_text_en", e.target.value)}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <Typography.Text strong style={{ color: "rgba(255,255,255,0.7)" }}>
                    Buttons ({sortedButtons.length})
                  </Typography.Text>
                  <Button size="small" icon={<PlusOutlined />} onClick={handleAddButton}>
                    Add Button
                  </Button>
                </div>

                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleButtonDragEnd}>
                  <SortableContext items={sortedButtons.map((b) => b.id)} strategy={verticalListSortingStrategy}>
                    {sortedButtons.map((btn) => (
                      <SortableButtonItem
                        key={btn.id}
                        btn={btn}
                        onEdit={() => handleEditButton(btn)}
                        onDelete={() => handleDeleteButton(btn.id)}
                      />
                    ))}
                  </SortableContext>
                </DndContext>
              </Space>
            </Card>
          ) : (
            <Card>
              <Empty description="Select a screen from the list" />
            </Card>
          )}
        </Col>

        {/* Preview */}
        <Col xs={24} lg={9}>
          <Card
            title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Live Preview</span>}
            extra={
              <Select
                size="small"
                value={previewLang}
                onChange={(v) => setPreviewLang(v as "ru" | "en")}
                style={{ width: 60 }}
                options={[
                  { value: "ru", label: "RU" },
                  { value: "en", label: "EN" },
                ]}
              />
            }
          >
            <TelegramPreview
              messageText={previewMessage}
              buttons={previewButtons}
            />
          </Card>
        </Col>
      </Row>

      <ButtonEditor
        open={btnEditorOpen}
        button={editingBtn}
        onSave={handleSaveButton}
        onCancel={() => {
          setBtnEditorOpen(false);
          setEditingBtn(null);
        }}
      />
    </div>
  );
}
