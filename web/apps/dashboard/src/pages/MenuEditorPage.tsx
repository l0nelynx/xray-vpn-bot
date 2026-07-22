import { useEffect, useState, useCallback, useRef } from "react";
import { Plus, Trash2, Pencil, Save, GripVertical } from "lucide-react";
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
import { Textarea } from "@xray/ui/components/textarea";
import { Label } from "@xray/ui/components/label";
import { Switch } from "@xray/ui/components/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { cn } from "@xray/ui/lib/utils";
import { api } from "../api/client";
import type { MenuScreen, MenuButton as MenuButtonType } from "../api/types";
import TelegramPreview from "../components/TelegramPreview";
import ButtonEditor from "../components/ButtonEditor";
import ConfirmButton from "../components/ConfirmButton";
import useUnsavedWarning from "../hooks/useUnsavedWarning";

function SortableButtonItem({
  btn,
  onEdit,
  onDelete,
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
      style={style}
      className="mb-1 flex items-center gap-2 rounded-md border border-white/[0.06] bg-white/[0.02] px-3 py-2"
    >
      <span {...attributes} {...listeners} className="cursor-grab text-muted-foreground/50">
        <GripVertical className="h-4 w-4" />
      </span>
      <span
        className={cn(
          "h-2 w-2 flex-shrink-0 rounded-full",
          btn.is_active ? "bg-emerald-500" : "bg-muted-foreground/40",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] text-foreground/85">{btn.text_ru}</div>
        <div className="text-[11px] text-muted-foreground">
          {btn.button_type} · {btn.callback_data || btn.url || "—"}
          {btn.visibility_condition !== "always" && ` · ${btn.visibility_condition}`}
        </div>
      </div>
      <div className="flex gap-1">
        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onEdit}>
          <Pencil className="h-4 w-4" />
        </Button>
        <ConfirmButton title="Delete button?" confirmText="Delete" destructive onConfirm={onDelete}>
          <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive">
            <Trash2 className="h-4 w-4" />
          </Button>
        </ConfirmButton>
      </div>
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
  const [isDirty, setIsDirty] = useState(false);
  const snapshotRef = useRef("");

  useUnsavedWarning(isDirty);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const selected = screens.find((s) => s.id === selectedId) || null;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<MenuScreen[]>("/menus/screens");
      setScreens(data);
      snapshotRef.current = JSON.stringify(data);
      setIsDirty(false);
      if (data.length > 0 && !selectedId) {
        setSelectedId(data[0].id);
      }
    } catch {
      toast.error("Failed to load screens");
    }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updateScreen = (field: string, value: unknown) => {
    if (!selected) return;
    setScreens((prev) => {
      const next = prev.map((s) => (s.id === selected.id ? { ...s, [field]: value } : s));
      setIsDirty(JSON.stringify(next) !== snapshotRef.current);
      return next;
    });
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

      const sortedButtons = [...selected.buttons].sort((a, b) => a.sort_order - b.sort_order);
      await api.put(`/menus/screens/${selected.id}/buttons/reorder`, {
        items: sortedButtons.map((b, i) => ({ id: b.id, row: i, col: 0, sort_order: i })),
      });

      toast.success("Screen saved!");
      await load();
    } catch {
      toast.error("Failed to save");
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
      toast.success("Screen created");
    } catch {
      toast.error("Failed to create screen");
    }
  };

  const handleDeleteScreen = async (id: number) => {
    try {
      await api.delete(`/menus/screens/${id}`);
      setScreens((prev) => prev.filter((s) => s.id !== id));
      if (selectedId === id) {
        setSelectedId(screens.find((s) => s.id !== id)?.id || null);
      }
      toast.success("Screen deleted");
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Failed to delete");
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
              : s,
          ),
        );
      } else {
        const created = await api.post<MenuButtonType>(
          `/menus/screens/${selected.id}/buttons`,
          values,
        );
        setScreens((prev) =>
          prev.map((s) => (s.id === selected.id ? { ...s, buttons: [...s.buttons, created] } : s)),
        );
      }
      setBtnEditorOpen(false);
      setEditingBtn(null);
      toast.success("Button saved");
    } catch {
      toast.error("Failed to save button");
    }
  };

  const handleDeleteButton = async (btnId: number) => {
    if (!selected) return;
    try {
      await api.delete(`/menus/buttons/${btnId}`);
      setScreens((prev) =>
        prev.map((s) =>
          s.id === selected.id ? { ...s, buttons: s.buttons.filter((b) => b.id !== btnId) } : s,
        ),
      );
      toast.success("Button deleted");
    } catch {
      toast.error("Failed to delete button");
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
      prev.map((s) => (s.id === selected.id ? { ...s, buttons: reordered } : s)),
    );
  };

  const sortedButtons = selected
    ? [...selected.buttons].sort((a, b) => a.sort_order - b.sort_order)
    : [];

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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-foreground md:text-xl">Bot Menu Editor</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleAddScreen}>
            <Plus className="h-4 w-4" />
            Add Screen
          </Button>
          <Button onClick={handleSave} disabled={saving || !selected}>
            <Save className="h-4 w-4" />
            Save
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[5fr_10fr_9fr]">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Screens</CardTitle>
          </CardHeader>
          <CardContent className="px-2">
            {loading ? (
              <div className="py-4 text-center text-muted-foreground">Loading…</div>
            ) : screens.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">No screens</div>
            ) : (
              <div className="space-y-0.5">
                {screens.map((s) => (
                  <div
                    key={s.id}
                    onClick={() => setSelectedId(s.id)}
                    className={cn(
                      "flex cursor-pointer items-center justify-between gap-2 rounded-md border px-2 py-1.5",
                      s.id === selectedId
                        ? "border-primary/30 bg-primary/10"
                        : "border-transparent hover:bg-white/5",
                    )}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-[13px] text-foreground/85">{s.name}</div>
                      <div className="text-[10px] text-muted-foreground">
                        {s.slug} {s.is_system && "· system"}
                      </div>
                    </div>
                    {!s.is_system && (
                      <ConfirmButton
                        title="Delete screen?"
                        confirmText="Delete"
                        destructive
                        onConfirm={() => handleDeleteScreen(s.id)}
                      >
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-destructive"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </ConfirmButton>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div>
          {selected ? (
            <Card>
              <CardContent className="space-y-3 p-4">
                <div className="grid grid-cols-2 gap-2 md:grid-cols-[8fr_10fr_6fr]">
                  <div>
                    <Label className="text-[11px] text-muted-foreground">Slug</Label>
                    <Input
                      className="h-8"
                      value={selected.slug}
                      onChange={(e) => updateScreen("slug", e.target.value)}
                      disabled={selected.is_system}
                    />
                  </div>
                  <div>
                    <Label className="text-[11px] text-muted-foreground">Name</Label>
                    <Input
                      className="h-8"
                      value={selected.name}
                      onChange={(e) => updateScreen("name", e.target.value)}
                    />
                  </div>
                  <div>
                    <Label className="text-[11px] text-muted-foreground">Active</Label>
                    <div className="pt-1.5">
                      <Switch
                        checked={selected.is_active}
                        onCheckedChange={(v: boolean) => updateScreen("is_active", v)}
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <Label className="text-[11px] text-muted-foreground">Message Text (RU)</Label>
                  <Textarea
                    rows={2}
                    value={selected.message_text_ru || ""}
                    onChange={(e) => updateScreen("message_text_ru", e.target.value)}
                  />
                </div>
                <div>
                  <Label className="text-[11px] text-muted-foreground">Message Text (EN)</Label>
                  <Textarea
                    rows={2}
                    value={selected.message_text_en || ""}
                    onChange={(e) => updateScreen("message_text_en", e.target.value)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-foreground/70">
                    Buttons ({sortedButtons.length})
                  </span>
                  <Button size="sm" variant="outline" onClick={handleAddButton}>
                    <Plus className="h-4 w-4" />
                    Add Button
                  </Button>
                </div>

                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleButtonDragEnd}
                >
                  <SortableContext
                    items={sortedButtons.map((b) => b.id)}
                    strategy={verticalListSortingStrategy}
                  >
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
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                Select a screen from the list
              </CardContent>
            </Card>
          )}
        </div>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm text-foreground/85">Live Preview</CardTitle>
            <Select value={previewLang} onValueChange={(v: string) => setPreviewLang(v as "ru" | "en")}>
              <SelectTrigger className="h-8 w-[64px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ru">RU</SelectItem>
                <SelectItem value="en">EN</SelectItem>
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            <TelegramPreview messageText={previewMessage} buttons={previewButtons} />
          </CardContent>
        </Card>
      </div>

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
