import { useCallback, useEffect, useState } from "react";
import { Activity, ArrowUpRight, Clock3, ServerCrash } from "lucide-react";
import { useNavigate } from "react-router";
import { Alert, AlertDescription } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { api } from "../api/client";
import type { ApiHealthSummary } from "../api/types";

const labels: Record<string, string> = { miniapp: "MiniApp", bot: "Bot / webhooks", dashboard: "Dashboard" };

export default function ApiHealthWidget() {
  const navigate = useNavigate();
  const [data, setData] = useState<ApiHealthSummary | null>(null);
  const [error, setError] = useState(false);
  const load = useCallback(() => {
    api.get<ApiHealthSummary>("/api-health/summary?range=1h").then((value) => {
      setData(value); setError(false);
    }).catch(() => setError(true));
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60_000);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <Card className="overflow-hidden border-border/80">
      <CardHeader className="border-b border-border/70 pb-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base"><Activity className="h-4 w-4" />API health</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">Application traffic and service availability · last hour</p>
            <p className="mt-1 text-[11px] text-muted-foreground/80">Latest telemetry: {data?.last_telemetry_at ? new Date(data.last_telemetry_at).toLocaleString() : "waiting"}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate("/api-health")}>Open <ArrowUpRight className="h-4 w-4" /></Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {error ? (
          <Alert variant="destructive" className="m-4"><AlertDescription>API health data is unavailable.</AlertDescription></Alert>
        ) : (
          <>
            <div className="grid divide-y divide-border/70 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              {["miniapp", "bot", "dashboard"].map((name) => {
                const service = data?.services.find((item) => item.service === name);
                return <div key={name} className="flex items-center justify-between px-5 py-4">
                  <div className="flex items-center gap-2.5">
                    <span className={`h-2.5 w-2.5 rounded-full ${service?.is_healthy ? "bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.45)]" : "bg-red-400"}`} />
                    <span className="text-sm font-medium">{labels[name]}</span>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px]">{service ? `${Math.round(service.response_time_ms ?? 0)}ms` : "waiting"}</Badge>
                </div>;
              })}
            </div>
            <div className="grid grid-cols-3 border-t border-border/70 bg-muted/20">
              <div className="px-5 py-4"><p className="text-xs text-muted-foreground">Success</p><p className="mt-1 font-mono text-lg font-semibold">{data ? `${data.success_rate.toFixed(2)}%` : "—"}</p></div>
              <div className="border-x border-border/70 px-5 py-4"><p className="flex items-center gap-1 text-xs text-muted-foreground"><ServerCrash className="h-3 w-3" />5xx</p><p className="mt-1 font-mono text-lg font-semibold">{data?.server_errors ?? "—"}</p></div>
              <div className="px-5 py-4"><p className="flex items-center gap-1 text-xs text-muted-foreground"><Clock3 className="h-3 w-3" />p95</p><p className="mt-1 font-mono text-lg font-semibold">{data ? `${Math.round(data.p95_ms)} ms` : "—"}</p></div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
