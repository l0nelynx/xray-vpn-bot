import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Switch } from "@xray/ui/components/switch";
import { Alert, AlertDescription } from "@xray/ui/components/alert";
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
import ConditionsBuilder from "./ConditionsBuilder";
import ConfirmButton from "../../components/ConfirmButton";
import {
  createEvent,
  deleteEvent,
  fetchEvents,
  fetchSegments,
  runEventNow,
  updateEvent,
} from "./api";
import { actionSummary, defaultActions, defaultConditions, getSegmentCondition } from "./helpers";
import type { CrmAction, CrmCondition, CrmEventRow, SegmentDef } from "./types";
import { REPEAT_POLICIES, WEEKDAYS } from "./types";

interface EventForm {
  name: string;
  enabled: boolean;
  run_at_time: string;
  frequency: string;
  weekday: number | null;
  repeat_policy: string;
  repeat_cooldown_days: number;
}

const emptyForm: EventForm = {
  name: "",
  enabled: true,
  run_at_time: "01:00",
  frequency: "daily",
  weekday: null,
  repeat_policy: "cooldown",
  repeat_cooldown_days: 7,
};

export default function EventsTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<CrmEventRow[]>([]);
  const [segments, setSegments] = useState<SegmentDef[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<CrmEventRow | null>(null);
  const [conditions, setConditions] = useState<CrmCondition[]>([]);
  const [actions, setActions] = useState<CrmAction[]>(defaultActions());
  const [selectedTgIds, setSelectedTgIds] = useState<number[]>([]);
  const [form, setForm] = useState<EventForm>(emptyForm);

  const patchForm = (patch: Partial<EventForm>) => setForm((f) => ({ ...f, ...patch }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEvents(await fetchEvents());
    } catch {
      toast.error("Failed to load events");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    fetchSegments()
      .then(setSegments)
      .catch(() => {});
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    const firstSeg = segments[0];
    setConditions(firstSeg ? defaultConditions(firstSeg.id, firstSeg) : []);
    setActions(defaultActions());
    setSelectedTgIds([]);
    setForm(emptyForm);
    setDrawerOpen(true);
  };

  const openEdit = (row: CrmEventRow) => {
    setEditing(row);
    setConditions(
      row.conditions?.length
        ? row.conditions
        : defaultConditions(row.segment_type || "limited", undefined),
    );
    setActions(row.actions?.length ? row.actions : defaultActions());
    setSelectedTgIds([]);
    setForm({
      name: row.name,
      enabled: row.enabled,
      run_at_time: row.run_at_time,
      frequency: row.frequency,
      weekday: row.weekday,
      repeat_policy: row.repeat_policy,
      repeat_cooldown_days: row.repeat_cooldown_days,
    });
    setDrawerOpen(true);
  };

  const saveEvent = async () => {
    if (!form.run_at_time) {
      toast.warning("Run time is required");
      return;
    }
    if (form.frequency === "weekly" && form.weekday == null) {
      toast.warning("Select a day of week");
      return;
    }
    if (!actions.some((a) => a.enabled)) {
      toast.warning("Enable at least one action");
      return;
    }

    const segmentId = getSegmentCondition(conditions)?.segment_id;
    const payload: Record<string, unknown> = {
      name: form.name,
      enabled: form.enabled,
      conditions,
      actions,
      run_at_time: form.run_at_time,
      frequency: form.frequency,
      weekday: form.frequency === "weekly" ? form.weekday : null,
      repeat_policy: form.repeat_policy,
      repeat_cooldown_days: form.repeat_cooldown_days,
    };

    if (segmentId !== "all_users" && selectedTgIds.length > 0) {
      payload.conditions = [
        ...conditions.filter((c) => c.type !== "tg_allowlist"),
        { type: "tg_allowlist", tg_ids: selectedTgIds },
      ];
    }

    try {
      if (editing) {
        await updateEvent(editing.id, payload);
        toast.success("Event updated");
      } else {
        await createEvent(payload);
        toast.success("Event created");
      }
      setDrawerOpen(false);
      load();
    } catch {
      toast.error("Failed to save");
    }
  };

  const toggleEnabled = async (row: CrmEventRow, enabled: boolean) => {
    try {
      await updateEvent(row.id, { enabled });
      load();
    } catch {
      toast.error("Failed to change status");
    }
  };

  const handleRunNow = async (row: CrmEventRow) => {
    try {
      const res = await runEventNow(row.id);
      if (res.status === "empty") {
        toast.info("Audience is empty after the repeat filter");
      } else {
        toast.success(
          res.total
            ? `Launched: ${res.total} recipients (campaign #${res.campaign_id})`
            : "Event launched",
        );
      }
      load();
    } catch {
      toast.error("Failed to launch");
    }
  };

  const handleDelete = async (row: CrmEventRow) => {
    try {
      await deleteEvent(row.id);
      toast.success("Deleted");
      load();
    } catch {
      toast.error("Failed to delete");
    }
  };

  const scheduleLabel = (row: CrmEventRow) => {
    const wd =
      row.frequency === "weekly" && row.weekday != null
        ? WEEKDAYS.find((d) => d.value === row.weekday)?.label
        : null;
    const freq = row.frequency === "weekly" ? `weekly (${wd})` : "daily";
    return `${row.run_at_time} UTC, ${freq}`;
  };

  const repeatLabel = (row: CrmEventRow) =>
    row.repeat_policy === "cooldown" ? `cooldown ${row.repeat_cooldown_days}d` : row.repeat_policy;

  const rowOps = (r: CrmEventRow) => (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" onClick={() => openEdit(r)}>
        Edit
      </Button>
      <Button size="sm" onClick={() => handleRunNow(r)}>
        Run now
      </Button>
      <ConfirmButton title="Delete this event?" destructive onConfirm={() => handleDelete(r)}>
        <Button size="sm" variant="destructive">
          Del
        </Button>
      </ConfirmButton>
    </div>
  );

  const renderMobileEventCard = (row: CrmEventRow) => (
    <Card key={row.id} className="mb-2">
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="mb-1 font-semibold text-foreground/85">
              {row.name || `Event #${row.id}`}
            </div>
            <div className="mb-1.5 text-xs text-muted-foreground">
              {row.segment_type ?? "—"} · {scheduleLabel(row)}
            </div>
            <div className="mb-1.5 text-[11px] text-muted-foreground/70">
              {row.actions?.length ? actionSummary(row.actions) : "—"} · {repeatLabel(row)}
            </div>
            <div className="text-[11px] text-muted-foreground/70">
              Next: {row.next_run_at ?? "—"}
            </div>
          </div>
          <Switch checked={row.enabled} onCheckedChange={(v: boolean) => toggleEnabled(row, v)} />
        </div>
        <div className="mt-2.5">{rowOps(row)}</div>
      </CardContent>
    </Card>
  );

  const segmentId = getSegmentCondition(conditions)?.segment_id ?? null;

  const headerActions = (
    <div className="flex flex-col gap-2 md:flex-row">
      <Button variant="outline" onClick={load} disabled={loading} className="w-full md:w-auto">
        Refresh
      </Button>
      <Button onClick={openCreate} className="w-full md:w-auto">
        New event
      </Button>
    </div>
  );

  return (
    <>
      <Card>
        <CardHeader className="flex-col items-start gap-3 space-y-0 md:flex-row md:items-center md:justify-between">
          <CardTitle className="text-sm">Scheduled events (UTC)</CardTitle>
          {headerActions}
        </CardHeader>
        <CardContent>
          <Alert className="mb-4">
            <Info className="h-4 w-4" />
            <AlertDescription>
              Run time is specified in UTC. The poller checks the schedule every 15 minutes.
            </AlertDescription>
          </Alert>
          {isMobile ? (
            loading ? (
              <div className="py-10 text-center text-muted-foreground">Loading...</div>
            ) : (
              events.map(renderMobileEventCard)
            )
          ) : (
            <div className="overflow-auto rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead>ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Segment</TableHead>
                    <TableHead>Actions</TableHead>
                    <TableHead>Schedule (UTC)</TableHead>
                    <TableHead>Repeat</TableHead>
                    <TableHead>On</TableHead>
                    <TableHead>Next run</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.length === 0 ? (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
                        {loading ? "Loading..." : "No events"}
                      </TableCell>
                    </TableRow>
                  ) : (
                    events.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell>{r.id}</TableCell>
                        <TableCell>{r.name}</TableCell>
                        <TableCell>{r.segment_type ?? "—"}</TableCell>
                        <TableCell>{r.actions?.length ? actionSummary(r.actions) : "—"}</TableCell>
                        <TableCell className="whitespace-nowrap">{scheduleLabel(r)}</TableCell>
                        <TableCell className="whitespace-nowrap">{repeatLabel(r)}</TableCell>
                        <TableCell>
                          <Switch
                            checked={r.enabled}
                            onCheckedChange={(v: boolean) => toggleEnabled(r, v)}
                          />
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{r.next_run_at ?? "—"}</TableCell>
                        <TableCell>{rowOps(r)}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Sheet open={drawerOpen} onOpenChange={(o: boolean) => setDrawerOpen(o)}>
        <SheetContent
          side="right"
          className="w-full overflow-y-auto sm:max-w-[640px]"
        >
          <SheetHeader className="flex-row items-center justify-between space-y-0">
            <SheetTitle>{editing ? `Event #${editing.id}` : "New event"}</SheetTitle>
            <Button size="sm" onClick={saveEvent}>
              Save
            </Button>
          </SheetHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input
                placeholder="E.g.: LIMITED — morning reminder"
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
                <CardTitle className="text-sm">Trigger</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Run time (UTC) *</Label>
                  <Input
                    placeholder="01:00"
                    value={form.run_at_time}
                    onChange={(e) => patchForm({ run_at_time: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Frequency *</Label>
                  <Select
                    value={form.frequency}
                    onValueChange={(v: string) => patchForm({ frequency: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">Daily</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {form.frequency === "weekly" && (
                  <div className="space-y-1.5">
                    <Label>Day of week *</Label>
                    <Select
                      value={form.weekday != null ? String(form.weekday) : undefined}
                      onValueChange={(v: string) => patchForm({ weekday: Number(v) })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select day" />
                      </SelectTrigger>
                      <SelectContent>
                        {WEEKDAYS.map((d) => (
                          <SelectItem key={d.value} value={String(d.value)}>
                            {d.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div className="space-y-1.5">
                  <Label>Repeat policy</Label>
                  <Select
                    value={form.repeat_policy}
                    onValueChange={(v: string) => patchForm({ repeat_policy: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {REPEAT_POLICIES.map((p) => (
                        <SelectItem key={p.value} value={p.value}>
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {form.repeat_policy === "cooldown" && (
                  <div className="space-y-1.5">
                    <Label>Cooldown (days)</Label>
                    <Input
                      type="number"
                      min={1}
                      max={365}
                      value={form.repeat_cooldown_days}
                      onChange={(e) =>
                        patchForm({ repeat_cooldown_days: Number(e.target.value) || 1 })
                      }
                    />
                  </div>
                )}
              </CardContent>
            </Card>

            <ConditionsBuilder
              conditions={conditions}
              onChange={setConditions}
              segmentTypes={segments}
              selectedTgIds={selectedTgIds}
              onSelectedTgIdsChange={setSelectedTgIds}
            />

            <ActionsBuilder actions={actions} onChange={setActions} segmentId={segmentId} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
