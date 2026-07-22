import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ScanLine } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Switch } from "@xray/ui/components/switch";
import { Checkbox } from "@xray/ui/components/checkbox";
import { Label } from "@xray/ui/components/label";
import { Badge } from "@xray/ui/components/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { api } from "../../api/client";
import Collapsible from "../../components/Collapsible";
import { fetchInternalSquads, normalizeRwTag } from "./api";
import { getSegmentCondition, segmentParamDefaults, upsertRwCondition } from "./helpers";
import type {
  CrmCondition,
  InternalSquadOption,
  ScanResult,
  ScanUser,
  SegmentDef,
  SegmentParams,
} from "./types";
import { USER_TYPE_OPTIONS } from "./types";

interface ConditionsBuilderProps {
  conditions: CrmCondition[];
  onChange: (conditions: CrmCondition[]) => void;
  segmentTypes: SegmentDef[];
  selectedTgIds: number[];
  onSelectedTgIdsChange: (ids: number[]) => void;
  onScanComplete?: (total: number) => void;
}

function SegmentParamField({
  param,
  value,
  onChange,
}: {
  param: SegmentDef["params"][0];
  value?: number | string;
  onChange: (v: number | string) => void;
}) {
  if (param.type === "select") {
    return (
      <Select
        value={(value as string) ?? (param.default as string)}
        onValueChange={(v: string) => onChange(v)}
      >
        <SelectTrigger className="w-full md:w-[180px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {param.options?.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  return (
    <Input
      type="number"
      className="w-full md:w-[180px]"
      min={param.min}
      max={param.max}
      step={param.type === "float" ? 0.05 : 1}
      value={value as number | undefined}
      onChange={(e) => {
        const raw = e.target.value;
        onChange(raw === "" ? (param.default as number) : Number(raw));
      }}
    />
  );
}

function formatScanMeta(row: ScanUser): string {
  const m = row.meta || {};
  const parts: string[] = [];
  if (m.status) parts.push(`status: ${m.status}`);
  if (m.days_left !== undefined) parts.push(`days: ${m.days_left}`);
  if (m.traffic_percent !== undefined) parts.push(`traffic: ${m.traffic_percent}%`);
  return parts.length ? parts.join(", ") : "—";
}

export default function ConditionsBuilder({
  conditions,
  onChange,
  segmentTypes,
  selectedTgIds,
  onSelectedTgIdsChange,
  onScanComplete,
}: ConditionsBuilderProps) {
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [internalSquads, setInternalSquads] = useState<InternalSquadOption[]>([]);

  useEffect(() => {
    fetchInternalSquads()
      .then(setInternalSquads)
      .catch(() => {});
  }, []);

  const segmentCond = getSegmentCondition(conditions);
  const userTypeCond = conditions.find((c) => c.type === "user_type");
  const rwSquadCond = conditions.find((c) => c.type === "rw_internal_squad");
  const rwTrafficCond = conditions.find((c) => c.type === "rw_traffic_limit");
  const rwTagCond = conditions.find((c) => c.type === "rw_tag");
  const segmentDef = segmentTypes.find((s) => s.id === segmentCond?.segment_id);

  const updateSegment = (patch: Partial<CrmCondition>) => {
    onChange(conditions.map((c) => (c.type === "segment" ? { ...c, ...patch } : c)));
  };

  const updateSegmentParams = (params: SegmentParams) => {
    updateSegment({ params });
  };

  const updateUserType = (value: string) => {
    const has = conditions.some((c) => c.type === "user_type");
    if (has) {
      onChange(conditions.map((c) => (c.type === "user_type" ? { ...c, value } : c)));
    } else {
      onChange([...conditions, { type: "user_type", value }]);
    }
  };

  const toggleRwSquad = (enabled: boolean) => {
    if (!enabled) {
      onChange(upsertRwCondition(conditions, "rw_internal_squad", null));
      return;
    }
    const first = internalSquads[0]?.uuid;
    if (!first) {
      toast.warning("Internal squads not loaded");
      return;
    }
    onChange(
      upsertRwCondition(conditions, "rw_internal_squad", {
        type: "rw_internal_squad",
        squad_id: rwSquadCond?.squad_id || first,
      }),
    );
  };

  const toggleRwTraffic = (enabled: boolean) => {
    if (!enabled) {
      onChange(upsertRwCondition(conditions, "rw_traffic_limit", null));
      return;
    }
    onChange(
      upsertRwCondition(conditions, "rw_traffic_limit", {
        type: "rw_traffic_limit",
        limit_gb: rwTrafficCond?.limit_gb ?? 5,
      }),
    );
  };

  const toggleRwTag = (enabled: boolean) => {
    if (!enabled) {
      onChange(upsertRwCondition(conditions, "rw_tag", null));
      return;
    }
    onChange(
      upsertRwCondition(conditions, "rw_tag", {
        type: "rw_tag",
        tag: rwTagCond?.tag || "",
      }),
    );
  };

  const onSegmentIdChange = (segmentId: string) => {
    const seg = segmentTypes.find((s) => s.id === segmentId);
    updateSegment({
      segment_id: segmentId,
      params: seg ? segmentParamDefaults(seg) : {},
    });
    setScanResult(null);
    onSelectedTgIdsChange([]);
  };

  const runScan = async () => {
    if (!segmentCond?.segment_id) {
      toast.warning("Select a segment");
      return;
    }
    setScanning(true);
    setScanResult(null);
    try {
      const res = await api.post<ScanResult>("/crm/conditions/evaluate", { conditions });
      setScanResult(res);
      onSelectedTgIdsChange(res.users.map((u) => u.tg_id));
      onScanComplete?.(res.total);
      if (res.warning) toast.warning(res.warning);
    } catch {
      toast.error("Scan failed");
    } finally {
      setScanning(false);
    }
  };

  const toggleUser = (tgId: number, checked: boolean) => {
    if (checked) {
      onSelectedTgIdsChange([...selectedTgIds, tgId]);
    } else {
      onSelectedTgIdsChange(selectedTgIds.filter((id) => id !== tgId));
    }
  };

  const segmentParams = segmentDef?.params.filter((p) => p.name !== "user_type") ?? [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">1. Conditions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1.5">
          <Label>1.1 Segment *</Label>
          <Select value={segmentCond?.segment_id} onValueChange={(v: string) => onSegmentIdChange(v)}>
            <SelectTrigger className="w-full md:max-w-[400px]">
              <SelectValue placeholder="Select a segment" />
            </SelectTrigger>
            <SelectContent>
              {segmentTypes.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {segmentParams.length > 0 && (
          <div className="space-y-1.5">
            <Label>Segment parameters</Label>
            <div className="flex flex-col gap-3 md:flex-row md:flex-wrap">
              {segmentParams.map((p) => (
                <div key={p.name} className="space-y-1">
                  <Label className="text-xs text-muted-foreground">{p.label}</Label>
                  <SegmentParamField
                    param={p}
                    value={segmentCond?.params?.[p.name]}
                    onChange={(v) =>
                      updateSegmentParams({ ...(segmentCond?.params || {}), [p.name]: v })
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-1.5">
          <Label>1.2 User type</Label>
          <Select value={userTypeCond?.value ?? "all"} onValueChange={(v: string) => updateUserType(v)}>
            <SelectTrigger className="w-full md:max-w-[240px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {USER_TYPE_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Collapsible title="1.3 Remnawave (optional)">
          <div className="space-y-4">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Switch checked={!!rwSquadCond} onCheckedChange={(v: boolean) => toggleRwSquad(v)} />
                <span className="text-sm">Internal Squad</span>
              </div>
              {rwSquadCond && (
                <Select
                  value={rwSquadCond.squad_id}
                  onValueChange={(squad_id: string) =>
                    onChange(
                      upsertRwCondition(conditions, "rw_internal_squad", {
                        type: "rw_internal_squad",
                        squad_id,
                      }),
                    )
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select a squad" />
                  </SelectTrigger>
                  <SelectContent>
                    {internalSquads.map((s) => (
                      <SelectItem key={s.uuid} value={s.uuid}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div>
              <div className="mb-2 flex items-center gap-2">
                <Switch
                  checked={!!rwTrafficCond}
                  onCheckedChange={(v: boolean) => toggleRwTraffic(v)}
                />
                <span className="text-sm">Traffic Limit (GB)</span>
              </div>
              {rwTrafficCond && (
                <>
                  <Input
                    type="number"
                    min={0}
                    max={10000}
                    className="w-full"
                    value={rwTrafficCond.limit_gb}
                    onChange={(e) =>
                      onChange(
                        upsertRwCondition(conditions, "rw_traffic_limit", {
                          type: "rw_traffic_limit",
                          limit_gb: e.target.value === "" ? 0 : Number(e.target.value),
                        }),
                      )
                    }
                  />
                  <p className="mt-1 text-xs text-muted-foreground">0 = unlimited</p>
                </>
              )}
            </div>

            <div>
              <div className="mb-2 flex items-center gap-2">
                <Switch checked={!!rwTagCond} onCheckedChange={(v: boolean) => toggleRwTag(v)} />
                <span className="text-sm">Tag</span>
              </div>
              {rwTagCond && (
                <>
                  <Input
                    placeholder="PROMO_1"
                    className="w-full"
                    value={rwTagCond.tag || ""}
                    onChange={(e) =>
                      onChange(
                        upsertRwCondition(conditions, "rw_tag", {
                          type: "rw_tag",
                          tag: normalizeRwTag(e.target.value),
                        }),
                      )
                    }
                  />
                  <p className="mt-1 text-xs text-muted-foreground">UPPERCASE, no spaces</p>
                </>
              )}
            </div>
          </div>
        </Collapsible>

        <Button className="w-full md:w-auto" onClick={runScan} disabled={scanning}>
          <ScanLine className="h-4 w-4" />
          Preview / scan
        </Button>

        {scanResult && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-4 text-sm">
              <span>
                Total in segment: <Badge>{scanResult.total}</Badge>
              </span>
              <span className="text-muted-foreground">
                In preview: {scanResult.users.length}
                {scanResult.total > scanResult.users.length && " (first 500)"}
              </span>
            </div>
            {scanResult.users.length > 0 && (
              <>
                <p className="text-sm text-muted-foreground">
                  1.3 Manual selection (optional) — {selectedTgIds.length} selected
                </p>
                <div className="max-h-64 space-y-1.5 overflow-auto rounded-lg border border-border p-2">
                  {scanResult.users.map((user) => (
                    <div
                      key={user.tg_id}
                      className="flex items-start gap-2.5 rounded-md border border-border/60 p-2"
                    >
                      <Checkbox
                        checked={selectedTgIds.includes(user.tg_id)}
                        onCheckedChange={(c: boolean | "indeterminate") =>
                          toggleUser(user.tg_id, c === true)
                        }
                      />
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold text-foreground/85">
                          {user.username || "—"}
                        </div>
                        <div className="text-xs text-muted-foreground">TG: {user.tg_id}</div>
                        <div className="mt-1 text-[11px] text-muted-foreground/70">
                          {formatScanMeta(user)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
