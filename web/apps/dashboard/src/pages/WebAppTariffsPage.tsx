import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  FolderTree,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { Spinner } from "@xray/ui/components/spinner";
import { Switch } from "@xray/ui/components/switch";
import { cn } from "@xray/ui/lib/utils";
import { api } from "../api/client";
import ConfirmButton from "../components/ConfirmButton";
import useUnsavedWarning from "../hooks/useUnsavedWarning";

type NodeAction = "buttons" | "invoice";

interface MenuNode {
  id: number;
  parent_id: number | null;
  text_ru: string;
  text_en: string;
  action: NodeAction;
  sort_order: number;
  is_active: boolean;
  invoice_provider: string | null;
  invoice_amount: number | null;
  invoice_currency: string | null;
  invoice_method: string | null;
  invoice_days: number | null;
  invoice_squad_id: string | null;
  invoice_external_squad_id: string | null;
  needs_attention: boolean;
  children: MenuNode[];
}

interface ProviderInfo {
  name: string;
  payment_method: string;
  currencies: string[];
  methods: { value: string; label: string }[];
  surfaces: string[];
}

interface DraftNode {
  id?: number;
  parent_id: number | null;
  text_ru: string;
  text_en: string;
  action: NodeAction;
  is_active: boolean;
  invoice_provider: string | null;
  invoice_amount: number | null;
  invoice_currency: string | null;
  invoice_method: string | null;
  invoice_days: number | null;
  invoice_squad_id: string | null;
  invoice_external_squad_id: string | null;
}

const emptyDraft = (parentId: number | null): DraftNode => ({
  parent_id: parentId,
  text_ru: "Новое меню",
  text_en: "New menu",
  action: "buttons",
  is_active: true,
  invoice_provider: null,
  invoice_amount: null,
  invoice_currency: null,
  invoice_method: null,
  invoice_days: null,
  invoice_squad_id: null,
  invoice_external_squad_id: null,
});

const toDraft = (node: MenuNode): DraftNode => ({
  id: node.id,
  parent_id: node.parent_id,
  text_ru: node.text_ru,
  text_en: node.text_en,
  action: node.action,
  is_active: node.is_active,
  invoice_provider: node.invoice_provider,
  invoice_amount: node.invoice_amount,
  invoice_currency: node.invoice_currency,
  invoice_method: node.invoice_method,
  invoice_days: node.invoice_days,
  invoice_squad_id: node.invoice_squad_id,
  invoice_external_squad_id: node.invoice_external_squad_id,
});

function TreeRow({
  node,
  depth,
  selectedId,
  expanded,
  onSelect,
  onExpand,
  onAdd,
}: {
  node: MenuNode;
  depth: number;
  selectedId?: number;
  expanded: Set<number>;
  onSelect: (node: MenuNode) => void;
  onExpand: (id: number) => void;
  onAdd: (parentId: number) => void;
}) {
  const open = expanded.has(node.id);
  return (
    <>
      <div
        className={cn(
          "group flex items-center gap-1 rounded-lg border px-2 py-2 transition-colors",
          selectedId === node.id
            ? "border-primary/35 bg-primary/10"
            : "border-transparent hover:border-white/10 hover:bg-white/[0.035]",
        )}
        style={{ marginLeft: depth * 18 }}
      >
        {node.action === "buttons" ? (
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onExpand(node.id)}>
            {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </Button>
        ) : (
          <CircleDollarSign className="mx-1.5 h-4 w-4 text-emerald-400" />
        )}
        <button className="min-w-0 flex-1 text-left" onClick={() => onSelect(node)}>
          <div className="truncate text-sm font-medium">{node.text_ru || node.text_en}</div>
          <div className="truncate text-[11px] text-muted-foreground">{node.text_en}</div>
        </button>
        {!node.is_active && <Badge variant="secondary">Hidden</Badge>}
        {node.needs_attention && <AlertTriangle className="h-4 w-4 text-amber-400" />}
        {node.action === "buttons" && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 opacity-0 group-hover:opacity-100 focus:opacity-100"
            onClick={() => onAdd(node.id)}
            title="Add child"
          >
            <Plus className="h-4 w-4" />
          </Button>
        )}
      </div>
      {node.action === "buttons" &&
        open &&
        node.children.map((child) => (
          <TreeRow
            key={child.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            expanded={expanded}
            onSelect={onSelect}
            onExpand={onExpand}
            onAdd={onAdd}
          />
        ))}
    </>
  );
}

export default function WebAppTariffsPage() {
  const [tree, setTree] = useState<MenuNode[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [selected, setSelected] = useState<MenuNode | null>(null);
  const [draft, setDraft] = useState<DraftNode | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const flat = useMemo(() => {
    const result: MenuNode[] = [];
    const walk = (nodes: MenuNode[]) =>
      nodes.forEach((node) => {
        result.push(node);
        walk(node.children);
      });
    walk(tree);
    return result;
  }, [tree]);

  const originalDraft = selected ? toDraft(selected) : null;
  const dirty = !!draft && JSON.stringify(draft) !== JSON.stringify(originalDraft);
  useUnsavedWarning(dirty);

  const reload = async (keepId?: number) => {
    setLoading(true);
    try {
      const data = await api.get<MenuNode[]>("/webapp-menu/tree");
      setTree(data);
      setExpanded((current) => {
        if (current.size) return current;
        return new Set(data.map((node) => node.id));
      });
      if (keepId) {
        const find = (nodes: MenuNode[]): MenuNode | null => {
          for (const node of nodes) {
            if (node.id === keepId) return node;
            const nested = find(node.children);
            if (nested) return nested;
          }
          return null;
        };
        const next = find(data);
        setSelected(next);
        setDraft(next ? toDraft(next) : null);
      }
    } catch (error) {
      toast.error(`Failed to load tariff tree: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    api
      .get<{ providers: ProviderInfo[] }>("/webapp-menu/providers")
      .then((value) => setProviders(value.providers))
      .catch((error) => toast.error(`Failed to load providers: ${error.message}`));
  }, []);

  const patch = <K extends keyof DraftNode>(key: K, value: DraftNode[K]) =>
    setDraft((current) => (current ? { ...current, [key]: value } : current));

  const selectNode = (node: MenuNode) => {
    setSelected(node);
    setDraft(toDraft(node));
  };

  const createAt = (parentId: number | null) => {
    setSelected(null);
    setDraft(emptyDraft(parentId));
    if (parentId != null) setExpanded((current) => new Set(current).add(parentId));
  };

  const provider = providers.find((item) => item.name === draft?.invoice_provider);

  const changeProvider = (name: string) => {
    const next = providers.find((item) => item.name === name);
    setDraft((current) =>
      current
        ? {
            ...current,
            invoice_provider: name,
            invoice_currency: next?.currencies[0] ?? null,
            invoice_method: next?.methods[0]?.value ?? null,
          }
        : current,
    );
  };

  const validate = () => {
    if (!draft?.text_ru.trim() || !draft.text_en.trim()) {
      toast.error("Add both RU and EN labels");
      return false;
    }
    if (draft.action === "invoice" && draft.is_active) {
      if (
        !draft.invoice_provider ||
        !draft.invoice_currency ||
        !draft.invoice_amount ||
        draft.invoice_amount <= 0 ||
        !draft.invoice_days ||
        draft.invoice_days <= 0 ||
        !draft.invoice_squad_id?.trim() ||
        !draft.invoice_external_squad_id?.trim()
      ) {
        toast.error("Complete Payment and Delivery fields before activating this invoice");
        return false;
      }
      if (draft.invoice_provider === "stars" && !Number.isInteger(draft.invoice_amount)) {
        toast.error("Telegram Stars amount must be a whole number");
        return false;
      }
    }
    return true;
  };

  const save = async () => {
    if (!draft || !validate()) return;
    setSaving(true);
    const payload = {
      ...draft,
      invoice_provider: draft.action === "invoice" ? draft.invoice_provider : null,
      invoice_amount: draft.action === "invoice" ? draft.invoice_amount : null,
      invoice_currency: draft.action === "invoice" ? draft.invoice_currency : null,
      invoice_method: draft.action === "invoice" ? draft.invoice_method : null,
      invoice_days: draft.action === "invoice" ? draft.invoice_days : null,
      invoice_squad_id: draft.action === "invoice" ? draft.invoice_squad_id : null,
      invoice_external_squad_id:
        draft.action === "invoice" ? draft.invoice_external_squad_id : null,
    };
    try {
      const saved = draft.id
        ? await api.put<MenuNode>(`/webapp-menu/nodes/${draft.id}`, payload)
        : await api.post<MenuNode>("/webapp-menu/nodes", {
            ...payload,
            sort_order:
              draft.parent_id == null
                ? tree.length
                : (flat.find((node) => node.id === draft.parent_id)?.children.length ?? 0),
          });
      toast.success(draft.id ? "Menu item saved" : "Menu item created");
      await reload(saved.id);
    } catch (error) {
      toast.error(`Save failed: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!draft?.id) return;
    try {
      await api.delete(`/webapp-menu/nodes/${draft.id}`);
      toast.success("Menu branch deleted");
      setSelected(null);
      setDraft(null);
      await reload();
    } catch (error) {
      toast.error(`Delete failed: ${(error as Error).message}`);
    }
  };

  const move = async (direction: -1 | 1) => {
    if (!selected) return;
    const siblings =
      selected.parent_id == null
        ? tree
        : (flat.find((node) => node.id === selected.parent_id)?.children ?? []);
    const ordered = [...siblings].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
    const index = ordered.findIndex((node) => node.id === selected.id);
    const target = index + direction;
    if (target < 0 || target >= ordered.length) return;
    [ordered[index], ordered[target]] = [ordered[target], ordered[index]];
    try {
      await api.put("/webapp-menu/reorder", {
        items: ordered.map((node, sort_order) => ({
          id: node.id,
          parent_id: node.parent_id,
          sort_order,
        })),
      });
      await reload(selected.id);
    } catch (error) {
      toast.error(`Move failed: ${(error as Error).message}`);
    }
  };

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <FolderTree className="h-5 w-5 text-primary" />
            <h1 className="text-xl font-semibold md:text-2xl">Tariff Constructor</h1>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground">
            One purchase tree for Telegram Bot, MiniApp, web and Android. Each active invoice
            stores its own payment and delivery settings.
          </p>
        </div>
        <Button onClick={() => createAt(null)}>
          <Plus className="h-4 w-4" />
          Add root item
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.4fr)]">
        <Card className="min-h-[420px]">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Purchase tree</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 p-2">
            {loading ? (
              <div className="flex justify-center py-12"><Spinner /></div>
            ) : tree.length ? (
              tree.map((node) => (
                <TreeRow
                  key={node.id}
                  node={node}
                  depth={0}
                  selectedId={draft?.id}
                  expanded={expanded}
                  onSelect={selectNode}
                  onExpand={(id) =>
                    setExpanded((current) => {
                      const next = new Set(current);
                      next.has(id) ? next.delete(id) : next.add(id);
                      return next;
                    })
                  }
                  onAdd={createAt}
                />
              ))
            ) : (
              <button
                className="w-full rounded-xl border border-dashed p-10 text-sm text-muted-foreground"
                onClick={() => createAt(null)}
              >
                The purchase tree is empty. Add the first category.
              </button>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-sm">
              {draft?.id ? "Item settings" : draft ? "New item" : "Select an item"}
            </CardTitle>
            {selected?.needs_attention && (
              <Badge variant="outline" className="border-amber-400/40 text-amber-300">
                <AlertTriangle className="h-3 w-3" /> Needs attention
              </Badge>
            )}
          </CardHeader>
          <CardContent>
            {!draft ? (
              <div className="py-16 text-center text-sm text-muted-foreground">
                Select a tree item to edit its labels, payment and delivery.
              </div>
            ) : (
              <div className="space-y-6">
                <section className="space-y-3">
                  <div className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    Labels
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div><Label>Russian</Label><Input value={draft.text_ru} onChange={(e) => patch("text_ru", e.target.value)} /></div>
                    <div><Label>English</Label><Input value={draft.text_en} onChange={(e) => patch("text_en", e.target.value)} /></div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <Label>Type</Label>
                      <Select
                        value={draft.action}
                        onValueChange={(value: string) => patch("action", value as NodeAction)}
                        disabled={!!selected?.children.length}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="buttons">Category</SelectItem>
                          <SelectItem value="invoice">Payment option</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-end gap-2 pb-2">
                      <Switch checked={draft.is_active} onCheckedChange={(value: boolean) => patch("is_active", value)} />
                      <Label>{draft.is_active ? "Visible to customers" : "Hidden draft"}</Label>
                    </div>
                  </div>
                </section>

                {draft.action === "invoice" && (
                  <>
                    <section className="space-y-3 border-t border-white/[0.07] pt-5">
                      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                        Payment
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div>
                          <Label>Provider</Label>
                          <Select value={draft.invoice_provider ?? undefined} onValueChange={changeProvider}>
                            <SelectTrigger><SelectValue placeholder="Choose provider" /></SelectTrigger>
                            <SelectContent>
                              {providers.map((item) => (
                                <SelectItem key={item.name} value={item.name}>
                                  {item.name}{item.name === "stars" ? " · Telegram only" : ""}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div><Label>Amount</Label><Input type="number" min={0} step={draft.invoice_provider === "stars" ? 1 : 0.01} value={draft.invoice_amount ?? ""} onChange={(e) => patch("invoice_amount", e.target.value ? Number(e.target.value) : null)} /></div>
                        <div>
                          <Label>Currency</Label>
                          <Select value={draft.invoice_currency ?? undefined} onValueChange={(value: string) => patch("invoice_currency", value)}>
                            <SelectTrigger><SelectValue placeholder="Currency" /></SelectTrigger>
                            <SelectContent>{provider?.currencies.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}</SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Method</Label>
                          <Select value={draft.invoice_method ?? undefined} onValueChange={(value: string) => patch("invoice_method", value)}>
                            <SelectTrigger><SelectValue placeholder="Method" /></SelectTrigger>
                            <SelectContent>{provider?.methods.map((method) => <SelectItem key={method.value} value={method.value}>{method.label}</SelectItem>)}</SelectContent>
                          </Select>
                        </div>
                        <div><Label>Subscription days</Label><Input type="number" min={1} value={draft.invoice_days ?? ""} onChange={(e) => patch("invoice_days", e.target.value ? Number(e.target.value) : null)} /></div>
                      </div>
                    </section>
                    <section className="space-y-3 border-t border-white/[0.07] pt-5">
                      <div className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                        Delivery
                      </div>
                      <div className="grid gap-3">
                        <div><Label>Internal squad ID</Label><Input value={draft.invoice_squad_id ?? ""} onChange={(e) => patch("invoice_squad_id", e.target.value || null)} /></div>
                        <div><Label>External squad ID</Label><Input value={draft.invoice_external_squad_id ?? ""} onChange={(e) => patch("invoice_external_squad_id", e.target.value || null)} /></div>
                      </div>
                    </section>
                  </>
                )}

                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.07] pt-4">
                  <div className="flex gap-1">
                    {draft.id && (
                      <>
                        <Button variant="outline" size="icon" onClick={() => void move(-1)} title="Move up"><ArrowUp className="h-4 w-4" /></Button>
                        <Button variant="outline" size="icon" onClick={() => void move(1)} title="Move down"><ArrowDown className="h-4 w-4" /></Button>
                        <ConfirmButton title="Delete this item and all children?" destructive confirmText="Delete" onConfirm={remove}>
                          <Button variant="ghost" size="icon" className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
                        </ConfirmButton>
                      </>
                    )}
                  </div>
                  <Button onClick={save} disabled={saving || (!!draft.id && !dirty)}>
                    {saving ? <Spinner /> : <Save className="h-4 w-4" />}
                    {draft.id ? "Save changes" : "Create item"}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
