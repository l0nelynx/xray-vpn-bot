import type { CrmAction, CrmCondition, SegmentDef, SegmentParams } from "./types";

export function segmentParamDefaults(seg: SegmentDef): SegmentParams {
  const defaults: SegmentParams = {};
  seg.params.forEach((p) => {
    if (p.name !== "user_type") {
      defaults[p.name] = p.default;
    }
  });
  return defaults;
}

export function defaultConditions(segmentId: string, seg?: SegmentDef): CrmCondition[] {
  const conds: CrmCondition[] = [
    {
      type: "segment",
      segment_id: segmentId,
      params: seg ? segmentParamDefaults(seg) : {},
    },
    { type: "user_type", value: "all" },
  ];
  return conds;
}

export function defaultActions(): CrmAction[] {
  return [
    { type: "send_message", enabled: false, order: 100, text: "" },
    { type: "attach_button", enabled: false, order: 101, button_type: "open_bot" },
    { type: "rw_bonus_days", enabled: false, order: 10, days: 3 },
    { type: "rw_bonus_traffic", enabled: false, order: 11, gb: 5 },
    { type: "rw_reset_traffic", enabled: false, order: 12 },
  ];
}

/** Merge saved actions onto the full default set so the builder shows every type. */
export function mergeActions(stored?: CrmAction[] | null): CrmAction[] {
  const base = defaultActions();
  if (!stored?.length) return base;
  const byType = new Map(stored.map((a) => [a.type, a]));
  const merged = base.map((def) => {
    const found = byType.get(def.type);
    return found ? { ...def, ...found } : def;
  });
  for (const act of stored) {
    if (!base.some((d) => d.type === act.type)) {
      merged.push(act);
    }
  }
  return merged;
}

export function applyTemplateToActions(
  actions: CrmAction[],
  tpl: {
    message_text: string;
    suggested_bonus_days: number | null;
    suggested_bonus_traffic_gb: number | null;
    attach_button: boolean;
  }
): CrmAction[] {
  return actions.map((a) => {
    if (a.type === "send_message") {
      return { ...a, enabled: true, text: tpl.message_text };
    }
    if (a.type === "attach_button") {
      return { ...a, enabled: tpl.attach_button };
    }
    if (a.type === "rw_bonus_days" && tpl.suggested_bonus_days) {
      return { ...a, enabled: true, days: tpl.suggested_bonus_days };
    }
    if (a.type === "rw_bonus_traffic" && tpl.suggested_bonus_traffic_gb) {
      return { ...a, enabled: true, gb: tpl.suggested_bonus_traffic_gb };
    }
    return a;
  });
}

export function getSegmentCondition(conditions: CrmCondition[]): CrmCondition | undefined {
  return conditions.find((c) => c.type === "segment");
}

const RW_CONDITION_TYPES = new Set([
  "rw_internal_squad",
  "rw_traffic_limit",
  "rw_tag",
]);

export function stripRwConditions(conditions: CrmCondition[]): CrmCondition[] {
  return conditions.filter((c) => !RW_CONDITION_TYPES.has(c.type));
}

export function upsertRwCondition(
  conditions: CrmCondition[],
  type: string,
  payload: CrmCondition | null
): CrmCondition[] {
  const base = conditions.filter((c) => c.type !== type);
  if (!payload) return base;
  return [...base, payload];
}

export function actionSummary(actions: CrmAction[]): string {
  const parts: string[] = [];
  for (const a of actions.filter((x) => x.enabled)) {
    if (a.type === "send_message") parts.push("message");
    if (a.type === "attach_button") parts.push("button");
    if (a.type === "rw_bonus_days") parts.push(`+${a.days}d`);
    if (a.type === "rw_bonus_traffic") parts.push(`+${a.gb}GB`);
    if (a.type === "rw_reset_traffic") parts.push("traffic reset");
  }
  return parts.length ? parts.join(", ") : "—";
}
