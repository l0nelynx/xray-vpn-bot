import { useEffect, useState, useCallback } from "react";
import {
  Typography, Card, Button, Input, InputNumber, Switch, Space, Row, Col,
  message, Popconfirm, Select, Collapse, Empty,
} from "antd";
import {
  PlusOutlined, DeleteOutlined, HolderOutlined, SaveOutlined,
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
import type { TariffPlan, TariffPrice } from "../api/types";
import TariffPriceMatrix from "../components/TariffPriceMatrix";
import TelegramPreview from "../components/TelegramPreview";
import useIsMobile from "../hooks/useIsMobile";

const DEFAULT_PRICES: TariffPrice[] = [
  { payment_method: "stars", price: 0, currency: "⭐️", is_active: true },
  { payment_method: "crypto", price: 0, currency: "USDT", is_active: true },
  { payment_method: "SBP_APAY", price: 0, currency: "RUB", is_active: true },
  { payment_method: "CRYSTAL", price: 0, currency: "RUB", is_active: true },
];

function SortableTariffCard({
  plan, onUpdate, onDelete,
}: {
  plan: TariffPlan;
  onUpdate: (plan: TariffPlan) => void;
  onDelete: (id: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: plan.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const updateField = (field: keyof TariffPlan, value: unknown) => {
    onUpdate({ ...plan, [field]: value } as TariffPlan);
  };

  return (
    <div ref={setNodeRef} style={style}>
      <Collapse
        size="small"
        items={[{
          key: plan.id,
          label: (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span {...attributes} {...listeners} style={{ cursor: "grab" }}>
                <HolderOutlined style={{ color: "rgba(255,255,255,0.3)" }} />
              </span>
              <Switch
                size="small"
                checked={plan.is_active}
                onChange={(v) => updateField("is_active", v)}
                onClick={(_, e) => e.stopPropagation()}
              />
              <span style={{ fontWeight: 600, color: "rgba(255,255,255,0.85)" }}>
                {plan.name_ru}
              </span>
              <span style={{ color: "rgba(255,255,255,0.35)", fontSize: 12 }}>
                {plan.days} days — {plan.slug}
              </span>
            </div>
          ),
          children: (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <Row gutter={12}>
                <Col span={6}>
                  <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Slug</label>
                  <Input size="small" value={plan.slug} onChange={(e) => updateField("slug", e.target.value)} />
                </Col>
                <Col span={6}>
                  <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Name RU</label>
                  <Input size="small" value={plan.name_ru} onChange={(e) => updateField("name_ru", e.target.value)} />
                </Col>
                <Col span={6}>
                  <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Name EN</label>
                  <Input size="small" value={plan.name_en} onChange={(e) => updateField("name_en", e.target.value)} />
                </Col>
                <Col span={3}>
                  <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Days</label>
                  <InputNumber size="small" min={1} value={plan.days} onChange={(v) => updateField("days", v ?? 30)} style={{ width: "100%" }} />
                </Col>
                <Col span={3}>
                  <label style={{ fontSize: 11, color: "rgba(255,255,255,0.45)" }}>Discount %</label>
                  <InputNumber size="small" min={0} max={100} value={plan.discount_percent} onChange={(v) => updateField("discount_percent", v ?? 0)} style={{ width: "100%" }} />
                </Col>
              </Row>

              <div>
                <Typography.Text style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", display: "block", marginBottom: 8 }}>
                  Prices by Payment Method
                </Typography.Text>
                <TariffPriceMatrix
                  prices={plan.prices}
                  onChange={(prices) => onUpdate({ ...plan, prices })}
                />
              </div>

              <div style={{ textAlign: "right" }}>
                <Popconfirm title="Delete this tariff?" onConfirm={() => onDelete(plan.id)}>
                  <Button size="small" danger icon={<DeleteOutlined />}>Delete</Button>
                </Popconfirm>
              </div>
            </div>
          ),
        }]}
        style={{ marginBottom: 8 }}
      />
    </div>
  );
}

export default function TariffEditorPage() {
  const [plans, setPlans] = useState<TariffPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewMethod, setPreviewMethod] = useState("stars");
  const [previewLang, setPreviewLang] = useState<"ru" | "en">("ru");
  const isMobile = useIsMobile();

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<TariffPlan[]>("/tariffs/plans");
      setPlans(data);
    } catch {
      message.error("Failed to load tariffs");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setPlans((prev) => {
      const oldIdx = prev.findIndex((p) => p.id === active.id);
      const newIdx = prev.findIndex((p) => p.id === over.id);
      const reordered = arrayMove(prev, oldIdx, newIdx);
      return reordered.map((p, i) => ({ ...p, sort_order: i }));
    });
  };

  const handleUpdate = (updated: TariffPlan) => {
    setPlans((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/tariffs/plans/${id}`);
      setPlans((prev) => prev.filter((p) => p.id !== id));
      message.success("Tariff deleted");
    } catch {
      message.error("Failed to delete");
    }
  };

  const handleAdd = async () => {
    try {
      const newPlan = await api.post<TariffPlan>("/tariffs/plans", {
        slug: `new_tariff_${Date.now()}`,
        name_ru: "Новый тариф",
        name_en: "New Tariff",
        days: 30,
        sort_order: plans.length,
        is_active: true,
        discount_percent: 0,
        prices: DEFAULT_PRICES,
      });
      setPlans((prev) => [...prev, newPlan]);
      message.success("Tariff created");
    } catch {
      message.error("Failed to create");
    }
  };

  const handleSaveAll = async () => {
    setSaving(true);
    try {
      // Save reorder
      await api.put("/tariffs/plans/reorder", {
        items: plans.map((p, i) => ({ id: p.id, sort_order: i })),
      });
      // Save each plan
      for (const plan of plans) {
        await api.put(`/tariffs/plans/${plan.id}`, {
          slug: plan.slug,
          name_ru: plan.name_ru,
          name_en: plan.name_en,
          days: plan.days,
          sort_order: plan.sort_order,
          is_active: plan.is_active,
          discount_percent: plan.discount_percent,
          prices: plan.prices,
        });
      }
      message.success("All tariffs saved!");
      await load();
    } catch {
      message.error("Failed to save");
    }
    setSaving(false);
  };

  // Build preview buttons
  const previewButtons = plans
    .filter((p) => p.is_active)
    .map((p, i) => {
      const priceInfo = p.prices.find((pr) => pr.payment_method === previewMethod && pr.is_active);
      const priceText = priceInfo ? `${priceInfo.price} ${priceInfo.currency}` : "—";
      const name = previewLang === "en" ? p.name_en : p.name_ru;
      return {
        text: `${name} | ${priceText}`,
        row: i,
      };
    });
  previewButtons.push({ text: "Назад", row: previewButtons.length });
  previewButtons.push({ text: "На главную", row: previewButtons.length });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0, color: "rgba(255,255,255,0.88)" }}>
          Tariff Editor
        </Typography.Title>
        <Space>
          <Button icon={<PlusOutlined />} onClick={handleAdd}>Add Tariff</Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSaveAll}>
            Save All
          </Button>
        </Space>
      </div>

      <Row gutter={24}>
        <Col xs={24} lg={14}>
          {loading ? (
            <Card loading />
          ) : plans.length === 0 ? (
            <Card><Empty description="No tariffs yet" /></Card>
          ) : (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={plans.map((p) => p.id)} strategy={verticalListSortingStrategy}>
                {plans.map((plan) => (
                  <SortableTariffCard
                    key={plan.id}
                    plan={plan}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                  />
                ))}
              </SortableContext>
            </DndContext>
          )}
        </Col>

        <Col xs={24} lg={10}>
          <Card
            title={<span style={{ color: "rgba(255,255,255,0.85)" }}>Live Preview</span>}
            extra={
              <Space size={4}>
                <Select
                  size="small"
                  value={previewMethod}
                  onChange={setPreviewMethod}
                  style={{ width: 110 }}
                  options={[
                    { value: "stars", label: "Stars" },
                    { value: "crypto", label: "Crypto" },
                    { value: "SBP_APAY", label: "SBP" },
                    { value: "CRYSTAL", label: "Crystal" },
                  ]}
                />
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
              </Space>
            }
          >
            <TelegramPreview
              messageText="Выберите тарифный план:"
              buttons={previewButtons}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
