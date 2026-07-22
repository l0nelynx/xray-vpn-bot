import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  Save,
  ChevronRight,
  ChevronDown,
  ArrowUp,
  ArrowDown,
  Eye,
  EyeOff,
} from "lucide-react";
import { Card, CardContent } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Badge } from "@xray/ui/components/badge";
import { Spinner } from "@xray/ui/components/spinner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { api } from "../api/client";
import ConfirmButton from "../components/ConfirmButton";

type NodeAction = "buttons" | "invoice";

interface MenuNode {
  id: number;
  parent_id: number | null;
  text: string;
  action: NodeAction;
  sort_order: number;
  is_active: boolean;
  invoice_provider: string | null;
  invoice_amount: number | null;
  invoice_currency: string | null;
  invoice_method: string | null;
  invoice_days: number | null;
  invoice_tariff_slug: string | null;
  children: MenuNode[];
}

interface ProviderMethod {
  value: string;
  label: string;
}

interface ProviderInfo {
  name: string;
  payment_method: string;
  currencies: string[];
  methods: ProviderMethod[];
}

interface DraftNode {
  text: string;
  action: NodeAction;
  invoice_provider: string | null;
  invoice_amount: number | null;
  invoice_currency: string | null;
  invoice_method: string | null;
  invoice_days: number | null;
  invoice_squad_id: string;
  invoice_external_squad_id: string;
  is_active: boolean;
}

function packSlug(sid: string, esid: string): string | null {
  const s = sid.trim();
  const e = esid.trim();
  if (!s && !e) return null;
  return `sid:${s}:esid:${e}`;
}

function unpackSlug(slug: string | null): { sid: string; esid: string } {
  if (!slug || !slug.startsWith("sid:")) return { sid: "", esid: "" };
  const parts = slug.split(":");
  if (parts.length !== 4 || parts[2] !== "esid") return { sid: "", esid: "" };
  return { sid: parts[1], esid: parts[3] };
}

function nodeToDraft(n: MenuNode): DraftNode {
  const { sid, esid } = unpackSlug(n.invoice_tariff_slug);
  return {
    text: n.text,
    action: n.action,
    invoice_provider: n.invoice_provider,
    invoice_amount: n.invoice_amount,
    invoice_currency: n.invoice_currency,
    invoice_method: n.invoice_method,
    invoice_days: n.invoice_days,
    invoice_squad_id: sid,
    invoice_external_squad_id: esid,
    is_active: n.is_active,
  };
}

function draftEquals(a: DraftNode, b: DraftNode): boolean {
  return (
    a.text === b.text &&
    a.action === b.action &&
    a.invoice_provider === b.invoice_provider &&
    a.invoice_amount === b.invoice_amount &&
    a.invoice_currency === b.invoice_currency &&
    a.invoice_method === b.invoice_method &&
    a.invoice_days === b.invoice_days &&
    a.invoice_squad_id === b.invoice_squad_id &&
    a.invoice_external_squad_id === b.invoice_external_squad_id &&
    a.is_active === b.is_active
  );
}

function NodeRow({
  node,
  siblings,
  providers,
  depth,
  drafts,
  setDraft,
  expanded,
  toggleExpand,
  onSave,
  onDelete,
  onAddChild,
  onMove,
  onToggleActive,
}: {
  node: MenuNode;
  siblings: MenuNode[];
  providers: ProviderInfo[];
  depth: number;
  drafts: Record<number, DraftNode>;
  setDraft: (id: number, patch: Partial<DraftNode>) => void;
  expanded: Set<number>;
  toggleExpand: (id: number) => void;
  onSave: (id: number) => void;
  onDelete: (id: number) => void;
  onAddChild: (parentId: number) => void;
  onMove: (id: number, direction: "up" | "down") => void;
  onToggleActive: (id: number) => void;
}) {
  const draft = drafts[node.id] ?? nodeToDraft(node);
  const dirty = !draftEquals(draft, nodeToDraft(node));
  const isExpanded = expanded.has(node.id);
  const provider = providers.find((p) => p.name === draft.invoice_provider);
  const currencyOptions = provider?.currencies ?? [];
  const methodOptions = provider?.methods ?? [];
  const methodLocked = methodOptions.length <= 1;
  const orderedSiblings = useMemo(
    () => [...siblings].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id),
    [siblings],
  );
  const idx = orderedSiblings.findIndex((s) => s.id === node.id);
  const canMoveUp = idx > 0;
  const canMoveDown = idx >= 0 && idx < orderedSiblings.length - 1;

  const handleProviderChange = (val: string | undefined) => {
    const p = providers.find((pp) => pp.name === val);
    const methodValues = p?.methods.map((m) => m.value) ?? [];
    setDraft(node.id, {
      invoice_provider: val ?? null,
      invoice_currency:
        draft.invoice_currency && p?.currencies.includes(draft.invoice_currency)
          ? draft.invoice_currency
          : (p?.currencies[0] ?? null),
      invoice_method:
        draft.invoice_method && methodValues.includes(draft.invoice_method)
          ? draft.invoice_method
          : (p?.methods[0]?.value ?? null),
    });
  };

  return (
    <div style={{ marginLeft: depth * 24 }}>
      <Card
        className="mb-2"
        style={{
          background: depth === 0 ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.03)",
          borderColor: dirty
            ? "#FFD479"
            : node.is_active
              ? "rgba(255,255,255,0.10)"
              : "rgba(255,255,255,0.04)",
          opacity: node.is_active ? 1 : 0.5,
        }}
      >
        <CardContent className="flex flex-wrap items-start gap-2 p-3">
          {node.action === "buttons" ? (
            <Button variant="ghost" size="icon" onClick={() => toggleExpand(node.id)}>
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          ) : (
            <Badge variant="secondary" className="mt-1">
              invoice
            </Badge>
          )}
          {!node.is_active && (
            <Badge variant="outline" className="mt-1">
              hidden
            </Badge>
          )}

          <Input
            placeholder="Button text"
            value={draft.text}
            onChange={(e) => setDraft(node.id, { text: e.target.value })}
            className="w-[220px]"
          />

          <Select
            value={draft.action}
            onValueChange={(val: string) => setDraft(node.id, { action: val as NodeAction })}
          >
            <SelectTrigger className="w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="buttons">Buttons</SelectItem>
              <SelectItem value="invoice">Invoice</SelectItem>
            </SelectContent>
          </Select>

          {draft.action === "invoice" && (
            <>
              <Select
                value={draft.invoice_provider ?? undefined}
                onValueChange={(val: string) => handleProviderChange(val)}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((p) => (
                    <SelectItem key={p.name} value={p.name}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                type="number"
                placeholder="Amount"
                value={draft.invoice_amount ?? ""}
                onChange={(e) =>
                  setDraft(node.id, {
                    invoice_amount: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
                min={0}
                step={0.01}
                className="w-[120px]"
              />
              <Select
                value={draft.invoice_currency ?? undefined}
                onValueChange={(val: string) => setDraft(node.id, { invoice_currency: val })}
                disabled={!draft.invoice_provider}
              >
                <SelectTrigger className="w-[110px]">
                  <SelectValue placeholder="Currency" />
                </SelectTrigger>
                <SelectContent>
                  {currencyOptions.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={draft.invoice_method ?? undefined}
                onValueChange={(val: string) => setDraft(node.id, { invoice_method: val })}
                disabled={!draft.invoice_provider || methodLocked}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Method" />
                </SelectTrigger>
                <SelectContent>
                  {methodOptions.map((m) => (
                    <SelectItem key={m.value} value={m.value}>
                      {m.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                type="number"
                placeholder="Days"
                value={draft.invoice_days ?? ""}
                onChange={(e) =>
                  setDraft(node.id, {
                    invoice_days: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
                min={0}
                className="w-[90px]"
              />
              <Input
                placeholder="squad_id (sid)"
                value={draft.invoice_squad_id}
                onChange={(e) => setDraft(node.id, { invoice_squad_id: e.target.value })}
                className="w-[160px]"
              />
              <Input
                placeholder="external_squad_id (esid)"
                value={draft.invoice_external_squad_id}
                onChange={(e) => setDraft(node.id, { invoice_external_squad_id: e.target.value })}
                className="w-[200px]"
              />
            </>
          )}

          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              disabled={!canMoveUp}
              onClick={() => onMove(node.id, "up")}
              title="Move up"
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              disabled={!canMoveDown}
              onClick={() => onMove(node.id, "down")}
              title="Move down"
            >
              <ArrowDown className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              onClick={() => onToggleActive(node.id)}
              title={node.is_active ? "Hide (won't appear in app/portal)" : "Show"}
            >
              {node.is_active ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </Button>
            <Button size="sm" disabled={!dirty} onClick={() => onSave(node.id)}>
              <Save className="h-4 w-4" />
              Save
            </Button>
            {node.action === "buttons" && (
              <Button variant="outline" size="sm" onClick={() => onAddChild(node.id)}>
                <Plus className="h-4 w-4" />
                Sub
              </Button>
            )}
            <ConfirmButton
              title="Delete this node and all its children?"
              destructive
              confirmText="Delete"
              onConfirm={() => onDelete(node.id)}
            >
              <Button variant="destructive" size="icon">
                <Trash2 className="h-4 w-4" />
              </Button>
            </ConfirmButton>
          </div>
        </CardContent>
      </Card>

      {node.action === "buttons" && isExpanded && (
        <div>
          {[...node.children]
            .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
            .map((c) => (
              <NodeRow
                key={c.id}
                node={c}
                siblings={node.children}
                providers={providers}
                depth={depth + 1}
                drafts={drafts}
                setDraft={setDraft}
                expanded={expanded}
                toggleExpand={toggleExpand}
                onSave={onSave}
                onDelete={onDelete}
                onAddChild={onAddChild}
                onMove={onMove}
                onToggleActive={onToggleActive}
              />
            ))}
          {node.children.length === 0 && (
            <div className="mb-2 ml-6 text-xs text-muted-foreground">
              Empty — click "Sub" above to add child buttons.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function WebAppTariffsPage() {
  const [tree, setTree] = useState<MenuNode[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [drafts, setDrafts] = useState<Record<number, DraftNode>>({});
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  const flatten = useMemo(() => {
    const out: MenuNode[] = [];
    const walk = (ns: MenuNode[]) => {
      for (const n of ns) {
        out.push(n);
        if (n.children?.length) walk(n.children);
      }
    };
    walk(tree);
    return out;
  }, [tree]);

  const reload = async () => {
    setLoading(true);
    try {
      const t = await api.get<MenuNode[]>("/webapp-menu/tree");
      setTree(t);
    } catch (e: unknown) {
      toast.error(`Failed to load menu: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    api
      .get<{ providers: ProviderInfo[] }>("/webapp-menu/providers")
      .then((r) => setProviders(r.providers))
      .catch((e) => toast.error(`Failed to load providers: ${(e as Error).message}`));
  }, []);

  useEffect(() => {
    setDrafts((prev) => {
      const next: Record<number, DraftNode> = {};
      for (const n of flatten) {
        next[n.id] =
          prev[n.id] && !draftEquals(prev[n.id], nodeToDraft(n)) ? prev[n.id] : nodeToDraft(n);
      }
      return next;
    });
  }, [flatten]);

  const setDraft = (id: number, patch: Partial<DraftNode>) => {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...(prev[id] ?? ({} as DraftNode)), ...patch },
    }));
  };

  const toggleExpand = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAddRoot = async () => {
    try {
      const created = await api.post<MenuNode>("/webapp-menu/nodes", {
        parent_id: null,
        text: "New menu",
        action: "buttons",
        sort_order: tree.length,
        is_active: true,
      });
      toast.success("Node created");
      setExpanded((prev) => new Set(prev).add(created.id));
      await reload();
    } catch (e: unknown) {
      toast.error(`Create failed: ${(e as Error).message}`);
    }
  };

  const handleAddChild = async (parentId: number) => {
    const parent = flatten.find((n) => n.id === parentId);
    try {
      const created = await api.post<MenuNode>("/webapp-menu/nodes", {
        parent_id: parentId,
        text: "New button",
        action: "buttons",
        sort_order: parent?.children.length ?? 0,
        is_active: true,
      });
      toast.success("Child node created");
      setExpanded((prev) => {
        const next = new Set(prev);
        next.add(parentId);
        next.add(created.id);
        return next;
      });
      await reload();
    } catch (e: unknown) {
      toast.error(`Create failed: ${(e as Error).message}`);
    }
  };

  const handleSave = async (id: number) => {
    const draft = drafts[id];
    if (!draft) return;
    if (!draft.text.trim()) {
      toast.error("Button text cannot be empty");
      return;
    }
    if (draft.action === "invoice") {
      if (!draft.invoice_provider) {
        toast.error("Pick a payment provider for invoice nodes");
        return;
      }
      if (draft.invoice_amount == null || draft.invoice_amount <= 0) {
        toast.error("Invoice amount must be greater than 0");
        return;
      }
      if (!draft.invoice_currency) {
        toast.error("Pick a currency");
        return;
      }
      if (!draft.invoice_days || draft.invoice_days <= 0) {
        toast.error("Invoice 'days' must be greater than 0");
        return;
      }
    }
    try {
      const payload = {
        text: draft.text,
        action: draft.action,
        is_active: draft.is_active,
        invoice_provider: draft.invoice_provider,
        invoice_amount: draft.invoice_amount,
        invoice_currency: draft.invoice_currency,
        invoice_method: draft.invoice_method,
        invoice_days: draft.invoice_days,
        invoice_tariff_slug: packSlug(draft.invoice_squad_id, draft.invoice_external_squad_id),
      };
      await api.put<MenuNode>(`/webapp-menu/nodes/${id}`, payload);
      toast.success("Saved");
      await reload();
    } catch (e: unknown) {
      toast.error(`Save failed: ${(e as Error).message}`);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/webapp-menu/nodes/${id}`);
      toast.success("Deleted");
      await reload();
    } catch (e: unknown) {
      toast.error(`Delete failed: ${(e as Error).message}`);
    }
  };

  const handleToggleActive = async (id: number) => {
    const node = flatten.find((n) => n.id === id);
    if (!node) return;
    try {
      await api.put<MenuNode>(`/webapp-menu/nodes/${id}`, { is_active: !node.is_active });
      await reload();
    } catch (e: unknown) {
      toast.error(`Toggle failed: ${(e as Error).message}`);
    }
  };

  const handleMove = async (id: number, direction: "up" | "down") => {
    const node = flatten.find((n) => n.id === id);
    if (!node) return;
    const siblings =
      node.parent_id == null
        ? tree
        : (flatten.find((n) => n.id === node.parent_id)?.children ?? []);
    const ordered = [...siblings].sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);
    const idx = ordered.findIndex((s) => s.id === id);
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (idx < 0 || swapIdx < 0 || swapIdx >= ordered.length) return;

    const reordered = [...ordered];
    [reordered[idx], reordered[swapIdx]] = [reordered[swapIdx], reordered[idx]];

    const items = reordered.map((n, i) => ({
      id: n.id,
      parent_id: n.parent_id,
      sort_order: i,
    }));

    try {
      await api.put("/webapp-menu/reorder", { items });
      await reload();
    } catch (e: unknown) {
      toast.error(`Reorder failed: ${(e as Error).message}`);
    }
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-foreground md:text-2xl">Tariff Constructor</h1>
        <Button onClick={handleAddRoot}>
          <Plus className="h-4 w-4" />
          Add root menu
        </Button>
      </div>

      <p className="mb-4 text-sm text-muted-foreground">
        Build the WebApp menu tree. <b>Buttons</b> nodes can hold child buttons; <b>Invoice</b> nodes
        are leaves that trigger a payment when tapped in the WebApp.
      </p>

      {loading ? (
        <Card>
          <CardContent className="flex justify-center p-6">
            <Spinner className="h-6 w-6" />
          </CardContent>
        </Card>
      ) : tree.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center text-muted-foreground">
            No menu nodes yet — click 'Add root menu' to start.
          </CardContent>
        </Card>
      ) : (
        [...tree]
          .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)
          .map((n) => (
            <NodeRow
              key={n.id}
              node={n}
              siblings={tree}
              providers={providers}
              depth={0}
              drafts={drafts}
              setDraft={setDraft}
              expanded={expanded}
              toggleExpand={toggleExpand}
              onSave={handleSave}
              onDelete={handleDelete}
              onAddChild={handleAddChild}
              onMove={handleMove}
              onToggleActive={handleToggleActive}
            />
          ))
      )}
    </div>
  );
}
