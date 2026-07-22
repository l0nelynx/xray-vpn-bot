import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Badge } from "@xray/ui/components/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@xray/ui/components/table";
import useIsMobile from "../../hooks/useIsMobile";
import { fetchCampaigns } from "./api";
import type { CampaignSummary } from "./types";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

function statusVariant(s: string): BadgeVariant {
  if (s === "completed") return "success";
  if (s === "running") return "default";
  if (s === "queued") return "secondary";
  if (s === "failed") return "destructive";
  return "outline";
}

export default function HistoryTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCampaigns(await fetchCampaigns());
    } catch {
      toast.error("Failed to load history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const perksLabel = (r: CampaignSummary) => {
    const parts: string[] = [];
    if (r.bonus_days) parts.push(`+${r.bonus_days}d`);
    if (r.bonus_traffic_gb) parts.push(`+${r.bonus_traffic_gb}GB`);
    if (!parts.length) return "—";
    return `${parts.join(", ")} (${r.perks_applied}/${r.perks_failed} failed)`;
  };

  const renderMobileCampaignCard = (r: CampaignSummary) => (
    <Card key={r.id} className="mb-2">
      <CardContent className="p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
          <span className="text-xs text-muted-foreground">#{r.id}</span>
        </div>
        <div className="mb-1 font-semibold text-foreground/85">{r.name || "—"}</div>
        <div className="mb-1 text-xs text-muted-foreground">
          {r.segment_type ?? "—"} · {r.total_targets} targets
        </div>
        <div className="text-[11px] text-muted-foreground/70">
          Sent: {r.messages_sent} / failed: {r.messages_failed}
        </div>
        <div className="text-[11px] text-muted-foreground/70">Bonuses: {perksLabel(r)}</div>
        <div className="text-[11px] text-muted-foreground/70">{r.created_at || "—"}</div>
      </CardContent>
    </Card>
  );

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm">Campaign history</CardTitle>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {isMobile ? (
          loading ? (
            <div className="py-10 text-center text-muted-foreground">Loading...</div>
          ) : (
            campaigns.map(renderMobileCampaignCard)
          )
        ) : (
          <div className="overflow-auto rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Segment</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Targets</TableHead>
                  <TableHead>Sent</TableHead>
                  <TableHead>Bonuses</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaigns.length === 0 ? (
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                      {loading ? "Loading..." : "No campaigns"}
                    </TableCell>
                  </TableRow>
                ) : (
                  campaigns.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{r.id}</TableCell>
                      <TableCell>{r.name}</TableCell>
                      <TableCell>{r.segment_type ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                      </TableCell>
                      <TableCell>{r.total_targets}</TableCell>
                      <TableCell>
                        {r.messages_sent} / {r.messages_failed} failed
                      </TableCell>
                      <TableCell>{perksLabel(r)}</TableCell>
                      <TableCell>{r.created_at}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
