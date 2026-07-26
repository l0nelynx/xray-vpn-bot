import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  Copy,
  FolderTree,
  Plus,
  RefreshCw,
  Search,
  Save,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Checkbox } from "@xray/ui/components/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@xray/ui/components/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { Spinner } from "@xray/ui/components/spinner";
import { Switch } from "@xray/ui/components/switch";
import { Textarea } from "@xray/ui/components/textarea";
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
  invoice_internal_squad_ids: string[] | null;
  invoice_external_squad_id: string | null;
  invoice_traffic_limit_bytes: number | null;
  invoice_traffic_limit_strategy: string | null;
  invoice_remnawave_description: string | null;
  invoice_remnawave_tag: string | null;
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
  invoice_internal_squad_ids: string[] | null;
  invoice_external_squad_id: string | null;
  invoice_traffic_limit_bytes: number | null;
  invoice_traffic_limit_strategy: string | null;
  invoice_remnawave_description: string | null;
  invoice_remnawave_tag: string | null;
}

interface SquadInfo {
  uuid: string;
  name: string;
}

interface SquadCatalog {
  internal: SquadInfo[];
  external: SquadInfo[];
}

const GIB = 1024 ** 3;
const TRAFFIC_STRATEGIES = [
  ["NO_RESET", "No reset"],
  ["DAY", "Daily"],
  ["WEEK", "Weekly"],
  ["MONTH", "Monthly"],
  ["MONTH_ROLLING", "Rolling month"],
] as const;

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
  invoice_internal_squad_ids: [],
  invoice_external_squad_id: null,
  invoice_traffic_limit_bytes: 0,
  invoice_traffic_limit_strategy: "NO_RESET",
  invoice_remnawave_description: null,
  invoice_remnawave_tag: null,
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
  invoice_internal_squad_ids: node.invoice_internal_squad_ids ?? [],
  invoice_external_squad_id: node.invoice_external_squad_id,
  invoice_traffic_limit_bytes: node.invoice_traffic_limit_bytes ?? 0,
  invoice_traffic_limit_strategy: node.invoice_traffic_limit_strategy ?? "NO_RESET",
  invoice_remnawave_description: node.invoice_remnawave_description,
  invoice_remnawave_tag: node.invoice_remnawave_tag,
});

function InternalSquadSelect({
  squads,
  value,
  onChange,
}: {
  squads: SquadInfo[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const known = new Map(squads.map((squad) => [squad.uuid, squad]));
  const options = [
    ...squads,
    ...value
      .filter((uuid) => !known.has(uuid))
      .map((uuid) => ({ uuid, name: `Missing squad · ${uuid}` })),
  ].filter((squad) =>
    `${squad.name} ${squad.uuid}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-auto min-h-10 w-full justify-start text-left">
          {value.length
            ? value.map((uuid) => known.get(uuid)?.name ?? uuid).join(", ")
            : "Choose internal squads"}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-2" align="start">
        <div className="mb-2 flex items-center gap-2 rounded-md border px-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search squads"
            className="border-0 px-0 shadow-none focus-visible:ring-0"
          />
        </div>
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {options.map((squad) => {
            const checked = value.includes(squad.uuid);
            return (
              <label
                key={squad.uuid}
                className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-2 hover:bg-accent"
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={(next: boolean | "indeterminate") =>
                    onChange(
                      next === true
                        ? [...value, squad.uuid]
                        : value.filter((uuid) => uuid !== squad.uuid),
                    )
                  }
                />
                <span className="min-w-0">
                  <span className="block truncate text-sm">{squad.name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {squad.uuid}
                  </span>
                </span>
              </label>
            );
          })}
          {!options.length && (
            <div className="px-2 py-4 text-center text-sm text-muted-foreground">
              No squads found
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

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
  const [squads, setSquads] = useState<SquadCatalog>({ internal: [], external: [] });
  const [squadsLoading, setSquadsLoading] = useState(false);
  const [squadsError, setSquadsError] = useState<string | null>(null);

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
    void loadSquads();
  }, []);

  const loadSquads = async (refresh = false) => {
    setSquadsLoading(true);
    setSquadsError(null);
    try {
      const value = await api.get<SquadCatalog>(
        `/webapp-menu/remnawave-squads${refresh ? "?refresh=true" : ""}`,
      );
      setSquads(value);
    } catch (error) {
      setSquadsError((error as Error).message);
    } finally {
      setSquadsLoading(false);
    }
  };

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
        !(draft.invoice_internal_squad_ids?.length) ||
        !draft.invoice_external_squad_id?.trim()
      ) {
        toast.error("Complete Payment and Delivery fields before activating this invoice");
        return false;
      }
      if (draft.invoice_provider === "stars" && !Number.isInteger(draft.invoice_amount)) {
        toast.error("Telegram Stars amount must be a whole number");
        return false;
      }
      const trafficGb = (draft.invoice_traffic_limit_bytes ?? 0) / GIB;
      if (!Number.isInteger(trafficGb) || trafficGb < 0) {
        toast.error("Traffic limit must be a non-negative whole number of GB");
        return false;
      }
      if (
        draft.invoice_remnawave_tag &&
        !/^[A-Z0-9_]{1,16}$/.test(draft.invoice_remnawave_tag)
      ) {
        toast.error("Remnawave tag must contain up to 16 A-Z, 0-9 or underscore characters");
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
      invoice_internal_squad_ids:
        draft.action === "invoice" ? draft.invoice_internal_squad_ids : null,
      invoice_external_squad_id:
        draft.action === "invoice" ? draft.invoice_external_squad_id : null,
      invoice_traffic_limit_bytes:
        draft.action === "invoice" ? draft.invoice_traffic_limit_bytes : null,
      invoice_traffic_limit_strategy:
        draft.action === "invoice" ? draft.invoice_traffic_limit_strategy : null,
      invoice_remnawave_description:
        draft.action === "invoice" ? draft.invoice_remnawave_description : null,
      invoice_remnawave_tag:
        draft.action === "invoice" ? draft.invoice_remnawave_tag : null,
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

  const clonePaymentOption = () => {
    if (!draft || draft.action !== "invoice") return;
    setSelected(null);
    setDraft({
      ...draft,
      id: undefined,
      text_ru: `${draft.text_ru} (копия)`,
      text_en: `${draft.text_en} (Copy)`,
      is_active: false,
      invoice_internal_squad_ids: [...(draft.invoice_internal_squad_ids ?? [])],
    });
    toast.info("Clone created as a local draft. Save it to add it to the tree.");
  };

  const categories = flat.filter((node) => node.action === "buttons");

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
                  {draft.action === "invoice" && (
                    <div>
                      <Label>Category</Label>
                      <Select
                        value={draft.parent_id == null ? "root" : String(draft.parent_id)}
                        onValueChange={(value: string) =>
                          patch("parent_id", value === "root" ? null : Number(value))
                        }
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="root">Root</SelectItem>
                          {categories.map((category) => (
                            <SelectItem key={category.id} value={String(category.id)}>
                              {category.text_ru || category.text_en}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
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
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                          Delivery
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void loadSquads(true)}
                          disabled={squadsLoading}
                        >
                          <RefreshCw className={cn("h-4 w-4", squadsLoading && "animate-spin")} />
                          Refresh squads
                        </Button>
                      </div>
                      {squadsError && (
                        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                          Failed to load Remnawave squads: {squadsError}
                        </div>
                      )}
                      <div className="grid gap-3 md:grid-cols-2">
                        <div className="md:col-span-2">
                          <Label>Internal squads</Label>
                          <InternalSquadSelect
                            squads={squads.internal}
                            value={draft.invoice_internal_squad_ids ?? []}
                            onChange={(value) => patch("invoice_internal_squad_ids", value)}
                          />
                        </div>
                        <div className="md:col-span-2">
                          <Label>External squad</Label>
                          <Select
                            value={draft.invoice_external_squad_id ?? undefined}
                            onValueChange={(value: string) =>
                              patch("invoice_external_squad_id", value)
                            }
                          >
                            <SelectTrigger><SelectValue placeholder="Choose external squad" /></SelectTrigger>
                            <SelectContent>
                              {draft.invoice_external_squad_id &&
                                !squads.external.some(
                                  (item) => item.uuid === draft.invoice_external_squad_id,
                                ) && (
                                  <SelectItem value={draft.invoice_external_squad_id}>
                                    Missing squad · {draft.invoice_external_squad_id}
                                  </SelectItem>
                                )}
                              {squads.external.map((item) => (
                                <SelectItem key={item.uuid} value={item.uuid}>
                                  {item.name} · {item.uuid}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label>Traffic limit (GB)</Label>
                          <Input
                            type="number"
                            min={0}
                            step={1}
                            value={(draft.invoice_traffic_limit_bytes ?? 0) / GIB}
                            onChange={(event) => {
                              const gb = Math.max(0, Math.trunc(Number(event.target.value) || 0));
                              setDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      invoice_traffic_limit_bytes: gb * GIB,
                                      invoice_traffic_limit_strategy:
                                        gb === 0
                                          ? "NO_RESET"
                                          : current.invoice_traffic_limit_strategy ?? "MONTH",
                                    }
                                  : current,
                              );
                            }}
                          />
                          <p className="mt-1 text-xs text-muted-foreground">0 means unlimited.</p>
                        </div>
                        <div>
                          <Label>Traffic reset strategy</Label>
                          <Select
                            value={draft.invoice_traffic_limit_strategy ?? "NO_RESET"}
                            onValueChange={(value: string) =>
                              patch("invoice_traffic_limit_strategy", value)
                            }
                            disabled={(draft.invoice_traffic_limit_bytes ?? 0) === 0}
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {TRAFFIC_STRATEGIES.map(([value, label]) => (
                                <SelectItem key={value} value={value}>{label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="md:col-span-2">
                          <Label>Remnawave user description</Label>
                          <Textarea
                            value={draft.invoice_remnawave_description ?? ""}
                            onChange={(event) =>
                              patch("invoice_remnawave_description", event.target.value || null)
                            }
                            placeholder="Leave empty to keep the current description"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <Label>Remnawave user tag</Label>
                          <Input
                            value={draft.invoice_remnawave_tag ?? ""}
                            maxLength={16}
                            onChange={(event) =>
                              patch(
                                "invoice_remnawave_tag",
                                event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "") || null,
                              )
                            }
                            placeholder="PREMIUM_30"
                          />
                          <p className="mt-1 text-xs text-muted-foreground">
                            Up to 16 uppercase letters, digits and underscores.
                          </p>
                        </div>
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
                        {draft.action === "invoice" && (
                          <Button variant="outline" size="icon" onClick={clonePaymentOption} title="Clone payment option">
                            <Copy className="h-4 w-4" />
                          </Button>
                        )}
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
