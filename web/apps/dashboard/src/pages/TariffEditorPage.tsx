import { useEffect, useState, useCallback, useRef } from "react";
import { Plus, Trash2, GripVertical, Save, ChevronDown } from "lucide-react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Switch } from "@xray/ui/components/switch";
import { Skeleton } from "@xray/ui/components/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { cn } from "@xray/ui/lib/utils";
import { api } from "../api/client";
import type { TariffPlan, TariffPrice, SquadProfile } from "../api/types";
import TariffPriceMatrix from "../components/TariffPriceMatrix";
import TelegramPreview from "../components/TelegramPreview";
import ConfirmButton from "../components/ConfirmButton";
import useUnsavedWarning from "../hooks/useUnsavedWarning";

const DEFAULT_PRICES: TariffPrice[] = [
  { payment_method: "stars", price: 0, currency: "⭐️", is_active: true },
  { payment_method: "crypto", price: 0, currency: "USDT", is_active: true },
  { payment_method: "SBP_APAY", price: 0, currency: "RUB", is_active: true },
  { payment_method: "CRYSTAL", price: 0, currency: "RUB", is_active: true },
];

const NO_SQUAD = "__none__";

function SortableTariffCard({
  plan,
  onUpdate,
  onDelete,
  squadProfiles,
}: {
  plan: TariffPlan;
  onUpdate: (plan: TariffPlan) => void;
  onDelete: (id: number) => void;
  squadProfiles: SquadProfile[];
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: plan.id });
  const [open, setOpen] = useState(false);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const updateField = (field: keyof TariffPlan, value: unknown) => {
    onUpdate({ ...plan, [field]: value } as TariffPlan);
  };

  return (
    <div ref={setNodeRef} style={style} className="mb-2">
      <Card>
        <div className="flex items-center gap-2 px-3 py-2">
          <span {...attributes} {...listeners} className="cursor-grab text-muted-foreground/50">
            <GripVertical className="h-4 w-4" />
          </span>
          <Switch
            checked={plan.is_active}
            onCheckedChange={(v: boolean) => updateField("is_active", v)}
          />
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="flex flex-1 items-center gap-2 text-left"
          >
            <span className="font-semibold text-foreground/85">{plan.name_ru}</span>
            <span className="text-xs text-muted-foreground">
              {plan.days} days — {plan.slug}
            </span>
            <ChevronDown
              className={cn("ml-auto h-4 w-4 transition-transform", open && "rotate-180")}
            />
          </button>
        </div>
        {open && (
          <CardContent className="flex flex-col gap-3 border-t border-border pt-3">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <div>
                <Label className="text-[11px] text-muted-foreground">Slug</Label>
                <Input
                  className="h-8"
                  value={plan.slug}
                  onChange={(e) => updateField("slug", e.target.value)}
                />
              </div>
              <div>
                <Label className="text-[11px] text-muted-foreground">Name RU</Label>
                <Input
                  className="h-8"
                  value={plan.name_ru}
                  onChange={(e) => updateField("name_ru", e.target.value)}
                />
              </div>
              <div>
                <Label className="text-[11px] text-muted-foreground">Name EN</Label>
                <Input
                  className="h-8"
                  value={plan.name_en}
                  onChange={(e) => updateField("name_en", e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-[11px] text-muted-foreground">Days</Label>
                  <Input
                    type="number"
                    className="h-8"
                    min={1}
                    value={plan.days}
                    onChange={(e) => updateField("days", Number(e.target.value) || 30)}
                  />
                </div>
                <div>
                  <Label className="text-[11px] text-muted-foreground">Disc %</Label>
                  <Input
                    type="number"
                    className="h-8"
                    min={0}
                    max={100}
                    value={plan.discount_percent}
                    onChange={(e) => updateField("discount_percent", Number(e.target.value) || 0)}
                  />
                </div>
              </div>
            </div>
            <div className="max-w-[240px]">
              <Label className="text-[11px] text-muted-foreground">Squad Profile</Label>
              <Select
                value={plan.squad_profile_id != null ? String(plan.squad_profile_id) : NO_SQUAD}
                onValueChange={(v: string) =>
                  updateField("squad_profile_id", v === NO_SQUAD ? null : Number(v))
                }
              >
                <SelectTrigger className="h-8">
                  <SelectValue placeholder="None (use config)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_SQUAD}>None (use config)</SelectItem>
                  {squadProfiles.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <div className="mb-2 text-xs text-muted-foreground">Prices by Payment Method</div>
              <TariffPriceMatrix
                prices={plan.prices}
                onChange={(prices) => onUpdate({ ...plan, prices })}
              />
            </div>

            <div className="text-right">
              <ConfirmButton
                title="Delete this tariff?"
                confirmText="Delete"
                destructive
                onConfirm={() => onDelete(plan.id)}
              >
                <Button size="sm" variant="destructive">
                  <Trash2 className="h-4 w-4" />
                  Delete
                </Button>
              </ConfirmButton>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}

export default function TariffEditorPage() {
  const [plans, setPlans] = useState<TariffPlan[]>([]);
  const [squadProfiles, setSquadProfiles] = useState<SquadProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewMethod, setPreviewMethod] = useState("stars");
  const [previewLang, setPreviewLang] = useState<"ru" | "en">("ru");
  const [isDirty, setIsDirty] = useState(false);
  const snapshotRef = useRef("");

  useUnsavedWarning(isDirty);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [data, squads] = await Promise.all([
        api.get<TariffPlan[]>("/tariffs/plans"),
        api.get<SquadProfile[]>("/squads"),
      ]);
      setPlans(data);
      setSquadProfiles(squads);
      snapshotRef.current = JSON.stringify(data);
      setIsDirty(false);
    } catch {
      toast.error("Failed to load tariffs");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
    setPlans((prev) => {
      const next = prev.map((p) => (p.id === updated.id ? updated : p));
      setIsDirty(JSON.stringify(next) !== snapshotRef.current);
      return next;
    });
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/tariffs/plans/${id}`);
      setPlans((prev) => prev.filter((p) => p.id !== id));
      toast.success("Tariff deleted");
    } catch {
      toast.error("Failed to delete");
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
        squad_profile_id: null,
        prices: DEFAULT_PRICES,
      });
      setPlans((prev) => [...prev, newPlan]);
      toast.success("Tariff created");
    } catch {
      toast.error("Failed to create");
    }
  };

  const handleSaveAll = async () => {
    setSaving(true);
    try {
      await api.put("/tariffs/plans/reorder", {
        items: plans.map((p, i) => ({ id: p.id, sort_order: i })),
      });
      await Promise.all(
        plans.map((plan) =>
          api.put(`/tariffs/plans/${plan.id}`, {
            slug: plan.slug,
            name_ru: plan.name_ru,
            name_en: plan.name_en,
            days: plan.days,
            sort_order: plan.sort_order,
            is_active: plan.is_active,
            discount_percent: plan.discount_percent,
            squad_profile_id: plan.squad_profile_id,
            prices: plan.prices,
          }),
        ),
      );
      toast.success("All tariffs saved!");
      await load();
    } catch {
      toast.error("Failed to save");
    }
    setSaving(false);
  };

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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-foreground md:text-xl">Tariff Editor</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleAdd}>
            <Plus className="h-4 w-4" />
            Add Tariff
          </Button>
          <Button onClick={handleSaveAll} disabled={saving}>
            <Save className="h-4 w-4" />
            Save All
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div>
          {loading ? (
            <Card>
              <CardContent className="space-y-3 p-6">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-3/4" />
              </CardContent>
            </Card>
          ) : plans.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                No tariffs yet
              </CardContent>
            </Card>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={plans.map((p) => p.id)}
                strategy={verticalListSortingStrategy}
              >
                {plans.map((plan) => (
                  <SortableTariffCard
                    key={plan.id}
                    plan={plan}
                    onUpdate={handleUpdate}
                    onDelete={handleDelete}
                    squadProfiles={squadProfiles}
                  />
                ))}
              </SortableContext>
            </DndContext>
          )}
        </div>

        <div>
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm text-foreground/85">Live Preview</CardTitle>
              <div className="flex gap-1">
                <Select value={previewMethod} onValueChange={(v: string) => setPreviewMethod(v)}>
                  <SelectTrigger className="h-8 w-[110px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stars">Stars</SelectItem>
                    <SelectItem value="crypto">Crypto</SelectItem>
                    <SelectItem value="SBP_APAY">SBP</SelectItem>
                    <SelectItem value="CRYSTAL">Crystal</SelectItem>
                  </SelectContent>
                </Select>
                <Select
                  value={previewLang}
                  onValueChange={(v: string) => setPreviewLang(v as "ru" | "en")}
                >
                  <SelectTrigger className="h-8 w-[64px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ru">RU</SelectItem>
                    <SelectItem value="en">EN</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              <TelegramPreview messageText="Выберите тарифный план:" buttons={previewButtons} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
