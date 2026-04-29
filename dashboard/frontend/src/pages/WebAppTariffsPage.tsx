import { useEffect, useMemo, useState } from "react";
import {
  Typography, Card, Button, Input, InputNumber, Select, Space, Empty,
  message, Popconfirm, Spin, Tag,
} from "antd";
import {
  PlusOutlined, DeleteOutlined, SaveOutlined, CaretRightOutlined,
  CaretDownOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";

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
  invoice_days: number | null;
  invoice_tariff_slug: string | null;
  children: MenuNode[];
}

interface ProviderInfo {
  name: string;
  payment_method: string;
  currencies: string[];
}

interface DraftNode {
  text: string;
  action: NodeAction;
  invoice_provider: string | null;
  invoice_amount: number | null;
  invoice_currency: string | null;
  invoice_days: number | null;
  invoice_squad_id: string;
  invoice_external_squad_id: string;
  is_active: boolean;
}

// Constructor packs sid/esid into a single tariff_slug column on the server
// using the format consumed by app.handlers.subscription_service._parse_squad_slug.
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
    a.invoice_days === b.invoice_days &&
    a.invoice_squad_id === b.invoice_squad_id &&
    a.invoice_external_squad_id === b.invoice_external_squad_id &&
    a.is_active === b.is_active
  );
}

function NodeRow({
  node, providers, depth, drafts, setDraft, expanded, toggleExpand,
  onSave, onDelete, onAddChild,
}: {
  node: MenuNode;
  providers: ProviderInfo[];
  depth: number;
  drafts: Record<number, DraftNode>;
  setDraft: (id: number, patch: Partial<DraftNode>) => void;
  expanded: Set<number>;
  toggleExpand: (id: number) => void;
  onSave: (id: number) => void;
  onDelete: (id: number) => void;
  onAddChild: (parentId: number) => void;
}) {
  const draft = drafts[node.id] ?? nodeToDraft(node);
  const dirty = !draftEquals(draft, nodeToDraft(node));
  const isExpanded = expanded.has(node.id);
  const provider = providers.find((p) => p.name === draft.invoice_provider);
  const currencyOptions = provider?.currencies ?? [];

  const handleProviderChange = (val: string | undefined) => {
    const p = providers.find((pp) => pp.name === val);
    setDraft(node.id, {
      invoice_provider: val ?? null,
      invoice_currency:
        draft.invoice_currency && p?.currencies.includes(draft.invoice_currency)
          ? draft.invoice_currency
          : (p?.currencies[0] ?? null),
    });
  };

  return (
    <div style={{ marginLeft: depth * 24 }}>
      <Card
        size="small"
        style={{
          marginBottom: 8,
          background: depth === 0 ? "#161622" : "#1a1a28",
          borderColor: dirty ? "#faad14" : "rgba(255,255,255,0.08)",
        }}
        bodyStyle={{ padding: 12 }}
      >
        <Space wrap size="small" style={{ width: "100%" }} align="start">
          {node.action === "buttons" ? (
            <Button
              type="text"
              size="small"
              icon={isExpanded ? <CaretDownOutlined /> : <CaretRightOutlined />}
              onClick={() => toggleExpand(node.id)}
            />
          ) : (
            <Tag color="purple" style={{ marginTop: 4 }}>invoice</Tag>
          )}

          <Input
            placeholder="Button text"
            value={draft.text}
            onChange={(e) => setDraft(node.id, { text: e.target.value })}
            style={{ width: 220 }}
          />

          <Select
            value={draft.action}
            onChange={(val: NodeAction) => setDraft(node.id, { action: val })}
            options={[
              { value: "buttons", label: "Buttons" },
              { value: "invoice", label: "Invoice" },
            ]}
            style={{ width: 120 }}
          />

          {draft.action === "invoice" && (
            <>
              <Select
                placeholder="Provider"
                value={draft.invoice_provider ?? undefined}
                onChange={handleProviderChange}
                options={providers.map((p) => ({ value: p.name, label: p.name }))}
                style={{ width: 140 }}
                allowClear
              />
              <InputNumber
                placeholder="Amount"
                value={draft.invoice_amount ?? undefined}
                onChange={(val) =>
                  setDraft(node.id, { invoice_amount: val == null ? null : Number(val) })
                }
                min={0}
                step={0.01}
                style={{ width: 120 }}
              />
              <Select
                placeholder="Currency"
                value={draft.invoice_currency ?? undefined}
                onChange={(val) => setDraft(node.id, { invoice_currency: val ?? null })}
                options={currencyOptions.map((c) => ({ value: c, label: c }))}
                style={{ width: 110 }}
                disabled={!draft.invoice_provider}
                allowClear
              />
              <InputNumber
                placeholder="Days"
                value={draft.invoice_days ?? undefined}
                onChange={(val) =>
                  setDraft(node.id, { invoice_days: val == null ? null : Number(val) })
                }
                min={0}
                style={{ width: 90 }}
              />
              <Input
                placeholder="squad_id (sid)"
                value={draft.invoice_squad_id}
                onChange={(e) =>
                  setDraft(node.id, { invoice_squad_id: e.target.value })
                }
                style={{ width: 160 }}
              />
              <Input
                placeholder="external_squad_id (esid)"
                value={draft.invoice_external_squad_id}
                onChange={(e) =>
                  setDraft(node.id, { invoice_external_squad_id: e.target.value })
                }
                style={{ width: 200 }}
              />
            </>
          )}

          <Space size={4}>
            <Button
              size="small"
              type="primary"
              icon={<SaveOutlined />}
              disabled={!dirty}
              onClick={() => onSave(node.id)}
            >
              Save
            </Button>
            {node.action === "buttons" && (
              <Button
                size="small"
                icon={<PlusOutlined />}
                onClick={() => onAddChild(node.id)}
              >
                Sub
              </Button>
            )}
            <Popconfirm
              title="Delete this node and all its children?"
              onConfirm={() => onDelete(node.id)}
              okText="Delete"
              okButtonProps={{ danger: true }}
            >
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Space>
        </Space>
      </Card>

      {node.action === "buttons" && isExpanded && (
        <div>
          {node.children.map((c) => (
            <NodeRow
              key={c.id}
              node={c}
              providers={providers}
              depth={depth + 1}
              drafts={drafts}
              setDraft={setDraft}
              expanded={expanded}
              toggleExpand={toggleExpand}
              onSave={onSave}
              onDelete={onDelete}
              onAddChild={onAddChild}
            />
          ))}
          {node.children.length === 0 && (
            <div
              style={{
                marginLeft: 24,
                marginBottom: 8,
                color: "rgba(255,255,255,0.4)",
                fontSize: 12,
              }}
            >
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
      message.error(`Failed to load menu: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    api
      .get<{ providers: ProviderInfo[] }>("/webapp-menu/providers")
      .then((r) => setProviders(r.providers))
      .catch((e) => message.error(`Failed to load providers: ${e.message}`));
  }, []);

  // Reset drafts whenever tree changes (use server values).
  useEffect(() => {
    setDrafts((prev) => {
      const next: Record<number, DraftNode> = {};
      for (const n of flatten) {
        next[n.id] = prev[n.id] && !draftEquals(prev[n.id], nodeToDraft(n))
          ? prev[n.id]
          : nodeToDraft(n);
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
      message.success("Node created");
      setExpanded((prev) => new Set(prev).add(created.id));
      await reload();
    } catch (e: unknown) {
      message.error(`Create failed: ${(e as Error).message}`);
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
      message.success("Child node created");
      setExpanded((prev) => {
        const next = new Set(prev);
        next.add(parentId);
        next.add(created.id);
        return next;
      });
      await reload();
    } catch (e: unknown) {
      message.error(`Create failed: ${(e as Error).message}`);
    }
  };

  const handleSave = async (id: number) => {
    const draft = drafts[id];
    if (!draft) return;
    if (!draft.text.trim()) {
      message.error("Button text cannot be empty");
      return;
    }
    if (draft.action === "invoice") {
      if (!draft.invoice_provider) {
        message.error("Pick a payment provider for invoice nodes");
        return;
      }
      if (draft.invoice_amount == null || draft.invoice_amount <= 0) {
        message.error("Invoice amount must be greater than 0");
        return;
      }
      if (!draft.invoice_currency) {
        message.error("Pick a currency");
        return;
      }
      if (!draft.invoice_days || draft.invoice_days <= 0) {
        message.error("Invoice 'days' must be greater than 0");
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
        invoice_days: draft.invoice_days,
        invoice_tariff_slug: packSlug(
          draft.invoice_squad_id,
          draft.invoice_external_squad_id,
        ),
      };
      await api.put<MenuNode>(`/webapp-menu/nodes/${id}`, payload);
      message.success("Saved");
      await reload();
    } catch (e: unknown) {
      message.error(`Save failed: ${(e as Error).message}`);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/webapp-menu/nodes/${id}`);
      message.success("Deleted");
      await reload();
    } catch (e: unknown) {
      message.error(`Delete failed: ${(e as Error).message}`);
    }
  };

  return (
    <div>
      <Space
        align="center"
        style={{ marginBottom: 16, justifyContent: "space-between", width: "100%" }}
      >
        <Typography.Title level={3} style={{ margin: 0 }}>
          Tariff Constructor
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAddRoot}>
          Add root menu
        </Button>
      </Space>

      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        Build the WebApp menu tree. <b>Buttons</b> nodes can hold child buttons;{" "}
        <b>Invoice</b> nodes are leaves that trigger a payment when tapped in the WebApp.
      </Typography.Paragraph>

      {loading ? (
        <Card>
          <Spin />
        </Card>
      ) : tree.length === 0 ? (
        <Card>
          <Empty description="No menu nodes yet — click 'Add root menu' to start." />
        </Card>
      ) : (
        tree.map((n) => (
          <NodeRow
            key={n.id}
            node={n}
            providers={providers}
            depth={0}
            drafts={drafts}
            setDraft={setDraft}
            expanded={expanded}
            toggleExpand={toggleExpand}
            onSave={handleSave}
            onDelete={handleDelete}
            onAddChild={handleAddChild}
          />
        ))
      )}
    </div>
  );
}
