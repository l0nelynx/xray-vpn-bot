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

export function actionSummary(actions: CrmAction[]): string {
  const parts: string[] = [];
  for (const a of actions.filter((x) => x.enabled)) {
    if (a.type === "send_message") parts.push("сообщение");
    if (a.type === "attach_button") parts.push("кнопка");
    if (a.type === "rw_bonus_days") parts.push(`+${a.days}д`);
    if (a.type === "rw_bonus_traffic") parts.push(`+${a.gb}ГБ`);
    if (a.type === "rw_reset_traffic") parts.push("сброс трафика");
  }
  return parts.length ? parts.join(", ") : "—";
}
