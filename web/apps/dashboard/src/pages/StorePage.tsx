import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Badge } from "@xray/ui/components/badge";
import { Spinner } from "@xray/ui/components/spinner";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { api } from "../api/client";
import type { OrderParam } from "../api/types";
import Collapsible from "../components/Collapsible";
import ConfirmButton from "../components/ConfirmButton";

const TYPE_OPTIONS = [
  { value: "days", label: "days" },
  { value: "hwid", label: "hwid" },
  { value: "location", label: "location" },
  { value: "internal_sq", label: "internal_sq" },
  { value: "external_sq", label: "external_sq" },
];

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

const TYPE_VARIANT: Record<string, BadgeVariant> = {
  days: "default",
  hwid: "success",
  location: "warning",
  internal_sq: "secondary",
  external_sq: "secondary",
};

interface TreeItemGroup {
  itemId: number;
  paramGroups: {
    paramId: number;
    userDataGroups: {
      userDataId: number;
      params: OrderParam[];
    }[];
  }[];
}

function buildTree(params: OrderParam[]): TreeItemGroup[] {
  const itemMap = new Map<number, Map<number, Map<number, OrderParam[]>>>();

  for (const p of params) {
    if (!itemMap.has(p.item_id)) itemMap.set(p.item_id, new Map());
    const paramMap = itemMap.get(p.item_id)!;
    if (!paramMap.has(p.param_id)) paramMap.set(p.param_id, new Map());
    const udMap = paramMap.get(p.param_id)!;
    if (!udMap.has(p.user_data_id)) udMap.set(p.user_data_id, []);
    udMap.get(p.user_data_id)!.push(p);
  }

  const tree: TreeItemGroup[] = [];
  for (const [itemId, paramMap] of [...itemMap.entries()].sort((a, b) => a[0] - b[0])) {
    const paramGroups = [];
    for (const [paramId, udMap] of [...paramMap.entries()].sort((a, b) => a[0] - b[0])) {
      const userDataGroups = [];
      for (const [userDataId, ps] of [...udMap.entries()].sort((a, b) => a[0] - b[0])) {
        userDataGroups.push({ userDataId, params: ps });
      }
      paramGroups.push({ paramId, userDataGroups });
    }
    tree.push({ itemId, paramGroups });
  }
  return tree;
}

interface StoreForm {
  item_id: string;
  param_id: string;
  user_data_id: string;
  type: string;
  data: string;
}

const emptyForm: StoreForm = {
  item_id: "",
  param_id: "",
  user_data_id: "",
  type: "",
  data: "",
};

export default function StorePage() {
  const [params, setParams] = useState<OrderParam[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OrderParam | null>(null);
  const [filterItemId, setFilterItemId] = useState<string>("");
  const [form, setForm] = useState<StoreForm>(emptyForm);

  const patchForm = (patch: Partial<StoreForm>) => setForm((f) => ({ ...f, ...patch }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = filterItemId ? `?item_id=${filterItemId}` : "";
      const data = await api.get<OrderParam[]>(`/store/order-params${query}`);
      setParams(data);
    } catch {
      toast.error("Failed to load order params");
    }
    setLoading(false);
  }, [filterItemId]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = (prefill?: Partial<OrderParam>) => {
    setEditing(null);
    setForm({
      ...emptyForm,
      item_id: prefill?.item_id != null ? String(prefill.item_id) : "",
      param_id: prefill?.param_id != null ? String(prefill.param_id) : "",
      user_data_id: prefill?.user_data_id != null ? String(prefill.user_data_id) : "",
    });
    setModalOpen(true);
  };

  const openEdit = (record: OrderParam) => {
    setEditing(record);
    setForm({
      item_id: String(record.item_id),
      param_id: String(record.param_id),
      user_data_id: String(record.user_data_id),
      type: record.type,
      data: record.data,
    });
    setModalOpen(true);
  };

  const handleSave = async () => {
    if (!form.item_id || !form.param_id || !form.user_data_id || !form.type || !form.data) {
      toast.error("All fields are required");
      return;
    }
    const payload = {
      item_id: Number(form.item_id),
      param_id: Number(form.param_id),
      user_data_id: Number(form.user_data_id),
      type: form.type,
      data: form.data,
    };
    try {
      if (editing) {
        await api.put(`/store/order-params/${editing.id}`, payload);
        toast.success("Parameter updated");
      } else {
        await api.post("/store/order-params", payload);
        toast.success("Parameter created");
      }
      setModalOpen(false);
      await load();
    } catch {
      toast.error("Failed to save");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/store/order-params/${id}`);
      toast.success("Parameter deleted");
      await load();
    } catch {
      toast.error("Failed to delete");
    }
  };

  const tree = buildTree(params);

  const renderParamRow = (p: OrderParam) => (
    <div
      key={p.id}
      className="mb-1 flex items-center justify-between rounded-md border border-white/5 bg-white/5 px-3 py-2"
    >
      <div className="flex items-center gap-3">
        <Badge variant={TYPE_VARIANT[p.type] || "outline"}>{p.type}</Badge>
        <span className="font-mono text-foreground/85">{p.data}</span>
        <span className="text-[11px] text-muted-foreground/50">#{p.id}</span>
      </div>
      <div className="flex gap-1">
        <Button size="icon" variant="ghost" onClick={() => openEdit(p)}>
          <Pencil className="h-4 w-4" />
        </Button>
        <ConfirmButton title="Delete this parameter?" destructive onConfirm={() => handleDelete(p.id)}>
          <Button size="icon" variant="ghost" className="text-destructive">
            <Trash2 className="h-4 w-4" />
          </Button>
        </ConfirmButton>
      </div>
    </div>
  );

  const label = (text: string, value: number | string, extra?: string) => (
    <span className="flex items-center gap-1.5">
      <span className="text-xs text-muted-foreground">{text}</span>
      <span className="font-mono font-semibold text-foreground/85">{value}</span>
      {extra && <span className="text-[11px] text-muted-foreground/50">{extra}</span>}
    </span>
  );

  const addBtn = (onClick: () => void) => (
    <span
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.stopPropagation();
          onClick();
        }
      }}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground/60 hover:bg-white/5 hover:text-foreground"
    >
      <Plus className="h-4 w-4" />
    </span>
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-foreground md:text-xl">Order Parameters</h1>
        <div className="flex flex-wrap gap-2">
          <div className="relative w-[180px]">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Filter by Item ID"
              value={filterItemId}
              onChange={(e) => setFilterItemId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              className="pl-8"
            />
          </div>
          <Button variant="outline" onClick={() => openCreate()}>
            <Plus className="h-4 w-4" />
            Add Parameter
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : tree.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">No order parameters found</div>
      ) : (
        <div className="space-y-2">
          {tree.map((item) => {
            const totalParams = item.paramGroups.reduce(
              (s, pg) => s + pg.userDataGroups.reduce((s2, u) => s2 + u.params.length, 0),
              0,
            );
            return (
              <Collapsible
                key={item.itemId}
                title={
                  <span className="flex w-full items-center justify-between gap-2 pr-2">
                    {label(
                      "item_id",
                      item.itemId,
                      `${item.paramGroups.length} option${item.paramGroups.length !== 1 ? "s" : ""} / ${totalParams} param${totalParams !== 1 ? "s" : ""}`,
                    )}
                    {addBtn(() => openCreate({ item_id: item.itemId }))}
                  </span>
                }
              >
                <div className="space-y-2">
                  {item.paramGroups.map((pg) => {
                    const pgTotal = pg.userDataGroups.reduce((s, u) => s + u.params.length, 0);
                    return (
                      <Collapsible
                        key={pg.paramId}
                        title={
                          <span className="flex w-full items-center justify-between gap-2 pr-2">
                            {label(
                              "param_id",
                              pg.paramId,
                              `${pg.userDataGroups.length} variant${pg.userDataGroups.length !== 1 ? "s" : ""} / ${pgTotal} param${pgTotal !== 1 ? "s" : ""}`,
                            )}
                            {addBtn(() => openCreate({ item_id: item.itemId, param_id: pg.paramId }))}
                          </span>
                        }
                      >
                        {pg.userDataGroups.map((udg) => (
                          <div key={udg.userDataId} className="mb-2">
                            <div className="mb-1 flex items-center justify-between">
                              {label(
                                "user_data_id",
                                udg.userDataId,
                                `(${udg.params.length} param${udg.params.length !== 1 ? "s" : ""})`,
                              )}
                              {addBtn(() =>
                                openCreate({
                                  item_id: item.itemId,
                                  param_id: pg.paramId,
                                  user_data_id: udg.userDataId,
                                }),
                              )}
                            </div>
                            <div className="pl-2 md:pl-4">{udg.params.map(renderParamRow)}</div>
                          </div>
                        ))}
                      </Collapsible>
                    );
                  })}
                </div>
              </Collapsible>
            );
          })}
        </div>
      )}

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Order Parameter" : "New Order Parameter"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Item ID *</Label>
              <Input
                type="number"
                placeholder="Product ID (e.g. 12345)"
                value={form.item_id}
                onChange={(e) => patchForm({ item_id: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Param ID *</Label>
              <Input
                type="number"
                placeholder="Option ID (e.g. 35060)"
                value={form.param_id}
                onChange={(e) => patchForm({ param_id: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>User Data ID *</Label>
              <Input
                type="number"
                placeholder="Variant ID (e.g. 161578)"
                value={form.user_data_id}
                onChange={(e) => patchForm({ user_data_id: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Type *</Label>
              <Select value={form.type} onValueChange={(v: string) => patchForm({ type: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select parameter type" />
                </SelectTrigger>
                <SelectContent>
                  {TYPE_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Data *</Label>
              <Input
                placeholder="Value (e.g. 30, UUID, etc.)"
                value={form.data}
                onChange={(e) => patchForm({ data: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
