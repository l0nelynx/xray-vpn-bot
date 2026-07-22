import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent } from "@xray/ui/components/card";
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
import { fetchPushCampaigns, type PushCampaignSummary } from "./api";

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
  const [campaigns, setCampaigns] = useState<PushCampaignSummary[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCampaigns(await fetchPushCampaigns());
    } catch {
      toast.error("Failed to load push history");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const audienceLabel = (r: PushCampaignSummary) => {
    if (r.audience === "user_ids") {
      const n = r.audience_params?.user_ids?.length ?? 0;
      return `user_ids (${n})`;
    }
    return "all_tokens";
  };

  const renderMobileCard = (r: PushCampaignSummary) => (
    <Card key={r.id} className="mb-2">
      <CardContent className="p-3">
        <div className="mb-1.5 flex items-center justify-between">
          <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
          <span className="text-xs text-muted-foreground">#{r.id}</span>
        </div>
        <div className="mb-1 font-semibold text-foreground/85">{r.title || "—"}</div>
        <div className="mb-1 text-xs text-muted-foreground">
          {audienceLabel(r)} · {r.total_targets} targets
        </div>
        <div className="text-[11px] text-muted-foreground/70">
          Sent: {r.sent} / failed: {r.failed}
        </div>
        <div className="text-[11px] text-muted-foreground/70">{r.created_at || "—"}</div>
      </CardContent>
    </Card>
  );

  return (
    <div>
      <div className="mb-3">
        <Button variant="outline" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </div>
      {isMobile ? (
        <div>
          {campaigns.length === 0 && !loading ? (
            <Card>
              <CardContent className="p-4 text-muted-foreground">No push campaigns yet</CardContent>
            </Card>
          ) : (
            campaigns.map(renderMobileCard)
          )}
        </div>
      ) : (
        <div className="overflow-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Audience</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Targets</TableHead>
                <TableHead>Sent</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>By</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                    {loading ? "Loading..." : "No push campaigns"}
                  </TableCell>
                </TableRow>
              ) : (
                campaigns.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{r.id}</TableCell>
                    <TableCell>{r.title}</TableCell>
                    <TableCell>{audienceLabel(r)}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                    </TableCell>
                    <TableCell>{r.total_targets}</TableCell>
                    <TableCell>
                      {r.sent} / {r.failed} failed
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{r.created_at}</TableCell>
                    <TableCell>{r.created_by}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
