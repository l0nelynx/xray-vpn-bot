import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Switch } from "@xray/ui/components/switch";
import { Alert, AlertDescription } from "@xray/ui/components/alert";
import { cn } from "@xray/ui/lib/utils";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@xray/ui/components/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@xray/ui/components/table";
import useIsMobile from "../../hooks/useIsMobile";
import ActionsBuilder from "./ActionsBuilder";
import ConfirmButton from "../../components/ConfirmButton";
import {
  createWebhookRule,
  deleteWebhookRule,
  fetchWebhookCatalog,
  fetchWebhookRules,
  updateWebhookRule,
} from "./api";
import { actionSummary, defaultActions, mergeActions } from "./helpers";
import type { CrmAction, CrmWebhookRuleRow, WebhookScopeGroup } from "./types";

interface RuleForm {
  name: string;
  enabled: boolean;
  scope: string | undefined;
  event: string | undefined;
  cooldown_hours: number | null;
}

const emptyForm: RuleForm = {
  name: "",
  enabled: true,
  scope: undefined,
  event: undefined,
  cooldown_hours: null,
};

export default function WebhooksTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(false);
  const [rules, setRules] = useState<CrmWebhookRuleRow[]>([]);
  const [catalog, setCatalog] = useState<WebhookScopeGroup[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<CrmWebhookRuleRow | null>(null);
  const [actions, setActions] = useState<CrmAction[]>(defaultActions());
  const [form, setForm] = useState<RuleForm>(emptyForm);

  const patchForm = (patch: Partial<RuleForm>) => setForm((f) => ({ ...f, ...patch }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRules(await fetchWebhookRules());
    } catch {
      toast.error("Failed to load webhook rules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    fetchWebhookCatalog()
      .then(setCatalog)
      .catch(() => {});
  }, [load]);

  const eventOptions = useMemo(() => {
    const group = catalog.find((g) => g.scope === form.scope);
    return group?.events || [];
  }, [catalog, form.scope]);

  const openCreate = () => {
    setEditing(null);
    const first = catalog[0];
    setActions(defaultActions());
    setForm({
      name: "",
      enabled: true,
      cooldown_hours: null,
      scope: first?.scope,
      event: first?.events[0]?.value,
    });
    setDrawerOpen(true);
  };

  const openEdit = (row: CrmWebhookRuleRow) => {
    setEditing(row);
    setActions(mergeActions(row.actions));
    setForm({
      name: row.name,
      enabled: row.enabled,
      scope: row.scope,
      event: row.event,
      cooldown_hours: row.cooldown_hours,
    });
    setDrawerOpen(true);
  };

  const saveRule = async () => {
    if (!form.name) {
      toast.warning("Name is required");
      return;
    }
    if (!form.scope || !form.event) {
      toast.warning("Scope and event are required");
      return;
    }
    if (!actions.some((a) => a.enabled)) {
      toast.warning("Enable at least one action");
      return;
    }
    const payload = {
      name: form.name,
      enabled: form.enabled,
      scope: form.scope,
      event: form.event,
      actions,
      cooldown_hours: form.cooldown_hours ?? null,
    };
    try {
      if (editing) {
        await updateWebhookRule(editing.id, payload);
        toast.success("Rule updated");
      } else {
        await createWebhookRule(payload);
        toast.success("Rule created");
      }
      setDrawerOpen(false);
      setEditing(null);
      load();
    } catch {
      toast.error("Failed to save");
    }
  };

  const toggleEnabled = async (row: CrmWebhookRuleRow, enabled: boolean) => {
    try {
      await updateWebhookRule(row.id, { enabled });
      load();
    } catch {
      toast.error("Failed to change status");
    }
  };

  const handleDelete = async (row: CrmWebhookRuleRow) => {
    try {
      await deleteWebhookRule(row.id);
      toast.success("Deleted");
      load();
    } catch {
      toast.error("Failed to delete");
    }
  };

  const onScopeChange = (v: string) => {
    const firstEvent = catalog.find((g) => g.scope === v)?.events[0]?.value;
    patchForm({ scope: v, event: firstEvent });
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Remnawave webhook → CRM actions (scope + event)
        </p>
        <Button onClick={openCreate}>New rule</Button>
      </div>

      {isMobile ? (
        <div className="space-y-2">
          {rules.map((row) => (
            <Card key={row.id}>
              <CardContent className="p-3">
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={row.enabled}
                      onCheckedChange={(v: boolean) => toggleEnabled(row, v)}
                    />
                    <button
                      type="button"
                      className="font-medium text-primary"
                      onClick={() => openEdit(row)}
                    >
                      {row.name || `#${row.id}`}
                    </button>
                  </div>
                  <div className="flex items-center">
                    <Button size="sm" variant="ghost" onClick={() => openEdit(row)}>
                      Edit
                    </Button>
                    <ConfirmButton title="Delete?" destructive onConfirm={() => handleDelete(row)}>
                      <Button size="sm" variant="ghost" className="text-destructive">
                        Del
                      </Button>
                    </ConfirmButton>
                  </div>
                </div>
                <code className="rounded bg-muted px-1 text-[11px]">
                  {row.scope}/{row.event}
                </code>
                <div className="mt-1.5 text-xs text-muted-foreground">
                  {actionSummary(row.actions)}
                  {row.cooldown_hours != null ? ` · cooldown ${row.cooldown_hours}h` : ""}
                </div>
                <div className="mt-1 text-xs">
                  recv {row.webhooks_received ?? 0} · sent {row.messages_sent ?? 0} ·{" "}
                  <span className={cn((row.messages_failed ?? 0) > 0 && "text-destructive")}>
                    fail {row.messages_failed ?? 0}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
          {!loading && rules.length === 0 && (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>No webhook rules yet</AlertDescription>
            </Alert>
          )}
        </div>
      ) : (
        <div className="overflow-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Name</TableHead>
                <TableHead>Scope / Event</TableHead>
                <TableHead>Actions</TableHead>
                <TableHead>Received</TableHead>
                <TableHead>Sent</TableHead>
                <TableHead>Failed</TableHead>
                <TableHead>Cooldown</TableHead>
                <TableHead>On</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
                    {loading ? "Loading..." : "No webhook rules"}
                  </TableCell>
                </TableRow>
              ) : (
                rules.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        onClick={() => openEdit(row)}
                      >
                        {row.name || `#${row.id}`}
                      </button>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs">
                        {row.scope} / {row.event}
                      </code>
                    </TableCell>
                    <TableCell>{actionSummary(row.actions)}</TableCell>
                    <TableCell>{row.webhooks_received ?? 0}</TableCell>
                    <TableCell>{row.messages_sent ?? 0}</TableCell>
                    <TableCell className={cn((row.messages_failed ?? 0) > 0 && "text-destructive")}>
                      {row.messages_failed ?? 0}
                    </TableCell>
                    <TableCell>{row.cooldown_hours != null ? `${row.cooldown_hours}h` : "—"}</TableCell>
                    <TableCell>
                      <Switch
                        checked={row.enabled}
                        onCheckedChange={(v: boolean) => toggleEnabled(row, v)}
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button size="sm" variant="outline" onClick={() => openEdit(row)}>
                          Edit
                        </Button>
                        <ConfirmButton
                          title="Delete this rule?"
                          destructive
                          onConfirm={() => handleDelete(row)}
                        >
                          <Button size="sm" variant="ghost" className="text-destructive">
                            Delete
                          </Button>
                        </ConfirmButton>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <Sheet
        open={drawerOpen}
        onOpenChange={(o: boolean) => {
          setDrawerOpen(o);
          if (!o) setEditing(null);
        }}
      >
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-[560px]">
          <SheetHeader className="flex-row items-center justify-between space-y-0">
            <SheetTitle>
              {editing ? `Edit: ${editing.name || `#${editing.id}`}` : "New webhook rule"}
            </SheetTitle>
            <Button size="sm" onClick={saveRule}>
              {editing ? "Save changes" : "Create"}
            </Button>
          </SheetHeader>

          <div className="space-y-4 py-4">
            {editing && (
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  Stats: received {editing.webhooks_received ?? 0}, sent {editing.messages_sent ?? 0},
                  failed {editing.messages_failed ?? 0}
                </AlertDescription>
              </Alert>
            )}

            <div className="space-y-1.5">
              <Label>Name *</Label>
              <Input
                placeholder="Torrent warning"
                value={form.name}
                onChange={(e) => patchForm({ name: e.target.value })}
              />
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={form.enabled}
                onCheckedChange={(v: boolean) => patchForm({ enabled: v })}
              />
              <Label>Enabled</Label>
            </div>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">1. Conditions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Scope *</Label>
                  <Select value={form.scope} onValueChange={(v: string) => onScopeChange(v)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select scope" />
                    </SelectTrigger>
                    <SelectContent>
                      {catalog.map((g) => (
                        <SelectItem key={g.scope} value={g.scope}>
                          {g.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Event *</Label>
                  <Select
                    value={form.event}
                    onValueChange={(v: string) => patchForm({ event: v })}
                    disabled={!form.scope}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select event" />
                    </SelectTrigger>
                    <SelectContent>
                      {eventOptions.map((e) => (
                        <SelectItem key={e.value} value={e.value}>
                          {e.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label>Cooldown (hours)</Label>
                  <Input
                    type="number"
                    min={1}
                    max={720}
                    placeholder="Optional"
                    value={form.cooldown_hours ?? ""}
                    onChange={(e) =>
                      patchForm({
                        cooldown_hours: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Skip re-running for the same user within this window. Empty = no limit.
                  </p>
                </div>
              </CardContent>
            </Card>

            <ActionsBuilder
              actions={actions}
              onChange={setActions}
              segmentId={null}
              templates={[]}
              variablesContext="webhook"
            />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
