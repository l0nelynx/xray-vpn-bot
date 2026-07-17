import { api } from "../../api/client";

export type PushAudience = "all_tokens" | "user_ids";

export interface PushCampaignSummary {
  id: number;
  title: string;
  body: string;
  data: Record<string, string>;
  audience: string;
  audience_params: { user_ids?: number[] };
  status: string;
  total_targets: number;
  sent: number;
  failed: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_by: string;
}

export interface PushStats {
  token_count: number;
  fcm_configured: boolean;
}

export async function fetchPushStats(): Promise<PushStats> {
  return api.get<PushStats>("/push/stats");
}

export async function previewPushCount(payload: {
  audience: PushAudience;
  user_ids?: number[];
}): Promise<{ count: number; audience: string }> {
  return api.post("/push/preview-count", payload);
}

export async function launchPush(payload: {
  title: string;
  body: string;
  data?: Record<string, string>;
  audience: PushAudience;
  user_ids?: number[];
}): Promise<PushCampaignSummary> {
  return api.post("/push/campaigns/launch", payload);
}

export async function fetchPushCampaigns(): Promise<PushCampaignSummary[]> {
  const res = await api.get<{ campaigns: PushCampaignSummary[] }>("/push/campaigns");
  return res.campaigns;
}
