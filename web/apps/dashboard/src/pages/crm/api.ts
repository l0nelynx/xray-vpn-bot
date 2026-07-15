import { api } from "../../api/client";
import type {
  CampaignSummary,
  CrmAction,
  CrmCondition,
  CrmEventRow,
  ScanResult,
  SegmentDef,
} from "./types";

export async function fetchSegments(): Promise<SegmentDef[]> {
  const res = await api.get<{ segments: SegmentDef[] }>("/crm/segments");
  return res.segments;
}

export async function evaluateConditions(conditions: CrmCondition[]): Promise<ScanResult> {
  return api.post<ScanResult>("/crm/conditions/evaluate", { conditions });
}

export async function launchCampaign(payload: {
  name?: string;
  conditions: CrmCondition[];
  actions: CrmAction[];
  target_tg_ids?: number[];
}): Promise<CampaignSummary & { queue_status: string }> {
  return api.post("/crm/campaigns/launch", payload);
}

export async function fetchCampaigns(): Promise<CampaignSummary[]> {
  const res = await api.get<{ campaigns: CampaignSummary[] }>("/crm/campaigns");
  return res.campaigns;
}

export async function fetchEvents(): Promise<CrmEventRow[]> {
  const res = await api.get<{ events: CrmEventRow[] }>("/crm/events");
  return res.events;
}

export async function createEvent(payload: Record<string, unknown>): Promise<CrmEventRow> {
  return api.post("/crm/events", payload);
}

export async function updateEvent(
  id: number,
  payload: Record<string, unknown>
): Promise<CrmEventRow> {
  return api.patch(`/crm/events/${id}`, payload);
}

export async function deleteEvent(id: number): Promise<void> {
  await api.delete(`/crm/events/${id}`);
}

export async function fetchInternalSquads(): Promise<{ uuid: string; name: string }[]> {
  const res = await api.get<{ squads: { uuid: string; name: string }[] }>(
    "/crm/remnawave/internal-squads"
  );
  return res.squads;
}

export function normalizeRwTag(tag: string): string {
  return tag.trim().toUpperCase().replace(/\s+/g, "");
}

export async function runEventNow(
  id: number
): Promise<{ status: string; total?: number; campaign_id?: number }> {
  return api.post(`/crm/events/${id}/run-now`);
}
