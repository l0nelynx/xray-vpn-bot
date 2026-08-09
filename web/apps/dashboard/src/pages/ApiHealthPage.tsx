import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, BellRing, ChevronLeft, ChevronRight, Clock3, DatabaseZap,
  ExternalLink, RefreshCw, Search, ShieldCheck, SlidersHorizontal,
} from "lucide-react";
import { useNavigate } from "react-router";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { Alert, AlertDescription } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Input } from "@xray/ui/components/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@xray/ui/components/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@xray/ui/components/sheet";
import { Switch } from "@xray/ui/components/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@xray/ui/components/table";
import { api } from "../api/client";
import type {
  ApiAlertSettings, ApiEndpointHealth, ApiErrorEvent, ApiErrorGroup, ApiHealthSeriesPoint, ApiHealthSummary,
} from "../api/types";
import { toast } from "sonner";

const RANGE_OPTIONS = [
  ["1h", "1 hour"], ["6h", "6 hours"], ["24h", "24 hours"],
  ["7d", "7 days"], ["30d", "30 days"], ["90d", "90 days"],
] as const;
const SERVICE_LABELS: Record<string, string> = { miniapp: "MiniApp", bot: "Bot / webhooks", dashboard: "Dashboard" };
const GRID = "oklch(1 0 0 / 8%)";
const AXIS = { fill: "oklch(0.68 0 0)", fontSize: 11 };
const TOOLTIP = { background: "oklch(0.18 0 0)", border: "1px solid oklch(1 0 0 / 14%)", borderRadius: 8, fontSize: 12 };

function formatTime(value: string | null, compact = false) {
  if (!value) return "—";
  const date = new Date(value);
  return compact
    ? date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : date.toLocaleString();
}

function Metric({ label, value, hint, tone = "default" }: { label: string; value: string; hint: string; tone?: "default" | "danger" }) {
  return <div className="border-l border-border/70 pl-4 first:border-l-0 first:pl-0">
    <p className="text-[11px] font-medium uppercase tracking-[.13em] text-muted-foreground">{label}</p>
    <p className={`mt-2 font-mono text-2xl font-semibold tracking-tight ${tone === "danger" ? "text-red-400" : "text-foreground"}`}>{value}</p>
    <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
  </div>;
}

export default function ApiHealthPage() {
  const navigate = useNavigate();
  const [range, setRange] = useState("24h");
  const [service, setService] = useState("all");
  const [statusClass, setStatusClass] = useState("all");
  const [search, setSearch] = useState("");
  const [summary, setSummary] = useState<ApiHealthSummary | null>(null);
  const [series, setSeries] = useState<ApiHealthSeriesPoint[]>([]);
  const [endpoints, setEndpoints] = useState<ApiEndpointHealth[]>([]);
  const [errors, setErrors] = useState<ApiErrorEvent[]>([]);
  const [groups, setGroups] = useState<ApiErrorGroup[]>([]);
  const [errorTotal, setErrorTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [settings, setSettings] = useState<ApiAlertSettings | null>(null);
  const [selected, setSelected] = useState<ApiErrorEvent | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [saving, setSaving] = useState(false);

  const query = useMemo(() => {
    const params = new URLSearchParams({ range });
    if (service !== "all") params.set("service", service);
    return params.toString();
  }, [range, service]);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const errorParams = new URLSearchParams({ range, per_page: "25", page: String(page) });
      if (service !== "all") errorParams.set("service", service);
      if (statusClass !== "all") errorParams.set("status_class", statusClass);
      if (search.trim()) errorParams.set("q", search.trim());
      const [summaryData, seriesData, endpointData, errorData] = await Promise.all([
        api.get<ApiHealthSummary>(`/api-health/summary?${query}`),
        api.get<ApiHealthSeriesPoint[]>(`/api-health/series?${query}`),
        api.get<ApiEndpointHealth[]>(`/api-health/endpoints?${query}`),
        api.get<{ items: ApiErrorEvent[]; groups: ApiErrorGroup[]; total: number }>(`/api-health/errors?${errorParams}`),
      ]);
      setSummary(summaryData); setSeries(seriesData); setEndpoints(endpointData);
      setErrors(errorData.items); setGroups(errorData.groups ?? []); setErrorTotal(errorData.total); setLoadError(false);
    } catch (error) {
      console.error("Failed to load API health dashboard", error);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [query, range, service, statusClass, search, page]);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => load(true), 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    api.get<ApiAlertSettings>("/api-health/settings").then(setSettings).catch(() => {});
  }, []);

  const saveSettings = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      setSettings(await api.put<ApiAlertSettings>("/api-health/settings", settings));
      toast.success("Alert settings saved");
    } catch { toast.error("Failed to save alert settings"); }
    finally { setSaving(false); }
  };

  const openError = async (item: ApiErrorEvent) => {
    setSelected(item);
    try { setSelected(await api.get<ApiErrorEvent>(`/api-health/errors/${item.id}`)); } catch { /* summary remains visible */ }
  };

  const filteredErrors = errors;

  return <div className="space-y-6">
    <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div className="max-w-2xl space-y-1.5">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[.16em] text-emerald-400"><Activity className="h-3.5 w-3.5" />Application telemetry</div>
        <h2 className="text-2xl font-semibold tracking-tight">API Health</h2>
        <p className="text-sm text-muted-foreground">Availability, request outcomes and latency across the APIs your users depend on.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Select value={service} onValueChange={(value: string) => { setService(value); setPage(1); }}><SelectTrigger className="w-[165px]"><SelectValue /></SelectTrigger><SelectContent>
          <SelectItem value="all">All services</SelectItem><SelectItem value="miniapp">MiniApp</SelectItem><SelectItem value="bot">Bot / webhooks</SelectItem><SelectItem value="dashboard">Dashboard</SelectItem>
        </SelectContent></Select>
        <Select value={range} onValueChange={(value: string) => { setRange(value); setPage(1); }}><SelectTrigger className="w-[135px]"><SelectValue /></SelectTrigger><SelectContent>
          {RANGE_OPTIONS.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
        </SelectContent></Select>
        <Button variant="outline" size="icon" onClick={() => load()} aria-label="Refresh"><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></Button>
      </div>
    </div>

    {loadError && <Alert variant="destructive"><AlertDescription className="flex items-center justify-between">API health data could not be loaded.<Button size="sm" variant="outline" onClick={() => load()}>Retry</Button></AlertDescription></Alert>}
    {(summary?.dropped_events ?? 0) > 0 && <Alert variant="destructive"><AlertDescription>{summary?.dropped_events.toLocaleString()} telemetry events were dropped in this period. User requests were not affected.</AlertDescription></Alert>}

    <Card className="overflow-hidden border-border/80">
      <div className="grid divide-y divide-border/70 md:grid-cols-3 md:divide-x md:divide-y-0">
        {["miniapp", "bot", "dashboard"].map((name) => {
          const item = summary?.services.find((entry) => entry.service === name);
          return <div key={name} className={`relative px-5 py-5 ${item?.is_healthy ? "bg-emerald-500/[.025]" : "bg-red-500/[.035]"}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3"><span className={`h-3 w-3 rounded-full ${item?.is_healthy ? "bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,.55)]" : "bg-red-400 shadow-[0_0_16px_rgba(248,113,113,.35)]"}`} /><div><p className="font-medium">{SERVICE_LABELS[name]}</p><p className="mt-1 text-xs text-muted-foreground">Checked {formatTime(item?.checked_at ?? null, true)}</p></div></div>
              <Badge variant={item?.is_healthy ? "outline" : "destructive"}>{item?.is_healthy ? "Operational" : item ? "Unavailable" : "Waiting"}</Badge>
            </div>
            <div className="mt-5 flex items-center justify-between border-t border-border/60 pt-3 text-xs"><span className="text-muted-foreground">Probe latency</span><span className="font-mono">{item ? `${Math.round(item.response_time_ms ?? 0)} ms` : "—"}</span></div>
          </div>;
        })}
      </div>
    </Card>

    <Card><CardContent className="grid grid-cols-2 gap-x-4 gap-y-6 pt-6 md:grid-cols-4 xl:grid-cols-8">
      <Metric label="Requests" value={(summary?.requests ?? 0).toLocaleString()} hint={`${summary?.avg_rps ?? 0} avg RPS`} />
      <Metric label="Success" value={`${(summary?.success_rate ?? 100).toFixed(2)}%`} hint="2xx and 3xx responses" />
      <Metric label="4xx rate" value={`${(summary?.client_error_rate ?? 0).toFixed(2)}%`} hint={`${summary?.client_errors ?? 0} client errors`} />
      <Metric label="5xx rate" value={`${(summary?.server_error_rate ?? 0).toFixed(2)}%`} hint={`${summary?.server_errors ?? 0} server errors`} tone={(summary?.server_errors ?? 0) > 0 ? "danger" : "default"} />
      <Metric label="Average" value={`${Math.round(summary?.avg_ms ?? 0)} ms`} hint="Mean response time" />
      <Metric label="p50" value={`${Math.round(summary?.p50_ms ?? 0)} ms`} hint="Typical request" />
      <Metric label="p95" value={`${Math.round(summary?.p95_ms ?? 0)} ms`} hint="Slow edge" />
      <Metric label="Slow requests" value={(summary?.slow_requests ?? 0).toLocaleString()} hint={`> 2000 ms · p99 ${Math.round(summary?.p99_ms ?? 0)} ms`} />
    </CardContent></Card>

    <div className="grid gap-6 xl:grid-cols-5">
      <Card className="xl:col-span-3"><CardHeader><CardTitle className="text-base">Request outcomes</CardTitle><p className="text-xs text-muted-foreground">Status classes over the selected window</p></CardHeader><CardContent className="h-[290px]">
        <ResponsiveContainer width="100%" height="100%"><BarChart data={series}><CartesianGrid stroke={GRID} vertical={false} /><XAxis dataKey="bucket" tickFormatter={(v) => formatTime(v, true)} tick={AXIS} stroke={GRID} minTickGap={32} /><YAxis yAxisId="requests" tick={AXIS} stroke={GRID} width={42} /><YAxis yAxisId="rate" orientation="right" tick={AXIS} stroke={GRID} width={42} unit="%" /><Tooltip contentStyle={TOOLTIP} labelFormatter={(v) => formatTime(String(v))} /><Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar yAxisId="requests" dataKey="status_2xx" name="2xx" stackId="status" fill="oklch(0.72 0.16 155)" /><Bar yAxisId="requests" dataKey="status_3xx" name="3xx" stackId="status" fill="oklch(0.72 0.12 235)" /><Bar yAxisId="requests" dataKey="status_4xx" name="4xx" stackId="status" fill="oklch(0.78 0.15 85)" /><Bar yAxisId="requests" dataKey="status_5xx" name="5xx" stackId="status" fill="oklch(0.65 0.22 25)" radius={[3, 3, 0, 0]} /><Line yAxisId="rate" type="monotone" dataKey="error_rate" name="Error rate" stroke="oklch(0.78 0.17 45)" strokeWidth={2} dot={false} />
        </BarChart></ResponsiveContainer>
      </CardContent></Card>
      <Card className="xl:col-span-2"><CardHeader><CardTitle className="text-base">Latency envelope</CardTitle><p className="text-xs text-muted-foreground">p50, p95 and p99 response time</p></CardHeader><CardContent className="h-[290px]">
        <ResponsiveContainer width="100%" height="100%"><AreaChart data={series}><defs><linearGradient id="p95fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="oklch(0.72 0.12 235)" stopOpacity={.28} /><stop offset="1" stopColor="oklch(0.72 0.12 235)" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke={GRID} vertical={false} /><XAxis dataKey="bucket" tickFormatter={(v) => formatTime(v, true)} tick={AXIS} stroke={GRID} minTickGap={32} /><YAxis tick={AXIS} stroke={GRID} width={48} unit="ms" /><Tooltip contentStyle={TOOLTIP} labelFormatter={(v) => formatTime(String(v))} /><Area type="monotone" dataKey="p95_ms" name="p95" stroke="oklch(0.72 0.12 235)" fill="url(#p95fill)" strokeWidth={2} /><Line type="monotone" dataKey="p50_ms" name="p50" stroke="oklch(0.72 0.16 155)" dot={false} /><Line type="monotone" dataKey="p99_ms" name="p99" stroke="oklch(0.72 0.18 45)" dot={false} /></AreaChart></ResponsiveContainer>
      </CardContent></Card>
    </div>

    <Card><CardHeader><div className="flex items-center justify-between"><div><CardTitle className="text-base">Endpoint performance</CardTitle><p className="mt-1 text-xs text-muted-foreground">Ranked by server errors, then traffic</p></div><DatabaseZap className="h-4 w-4 text-muted-foreground" /></div></CardHeader><CardContent className="p-0">
      <Table><TableHeader><TableRow><TableHead>Endpoint</TableHead><TableHead>Service</TableHead><TableHead className="text-right">Requests</TableHead><TableHead className="text-right">4xx</TableHead><TableHead className="text-right">5xx</TableHead><TableHead className="text-right">Error %</TableHead><TableHead className="text-right">Avg</TableHead><TableHead className="text-right">p95 / p99</TableHead><TableHead className="text-right">Max</TableHead></TableRow></TableHeader><TableBody>
        {endpoints.length === 0 ? <TableRow><TableCell colSpan={9} className="h-24 text-center text-muted-foreground">No request data in this period.</TableCell></TableRow> : endpoints.map((item) => <TableRow key={`${item.service}:${item.method}:${item.route}`}><TableCell><div className="flex items-center gap-2"><Badge variant="outline" className="font-mono text-[10px]">{item.method}</Badge><code className="max-w-[360px] truncate text-xs">{item.route}</code></div></TableCell><TableCell>{SERVICE_LABELS[item.service] ?? item.service}</TableCell><TableCell className="text-right font-mono">{item.requests.toLocaleString()}</TableCell><TableCell className="text-right font-mono text-amber-300">{item.client_errors}</TableCell><TableCell className="text-right font-mono text-red-400">{item.server_errors}</TableCell><TableCell className="text-right font-mono">{item.error_rate.toFixed(2)}%</TableCell><TableCell className="text-right font-mono">{Math.round(item.avg_ms)} ms</TableCell><TableCell className="text-right font-mono">{Math.round(item.p95_ms)} / {Math.round(item.p99_ms)} ms</TableCell><TableCell className="text-right font-mono">{Math.round(item.max_ms)} ms</TableCell></TableRow>)}
      </TableBody></Table>
    </CardContent></Card>

    <div className="grid gap-6 xl:grid-cols-3">
      <Card className="xl:col-span-2"><CardHeader><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><CardTitle className="text-base">Error journal</CardTitle><p className="mt-1 text-xs text-muted-foreground">{errorTotal.toLocaleString()} retained events · 4xx details are sampled</p></div><div className="flex gap-2"><Select value={statusClass} onValueChange={(value: string) => { setStatusClass(value); setPage(1); }}><SelectTrigger className="w-[110px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All</SelectItem><SelectItem value="5xx">5xx</SelectItem><SelectItem value="4xx">4xx</SelectItem></SelectContent></Select><div className="relative"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="User, IP, request ID" className="w-[220px] pl-8" /></div></div></div></CardHeader><CardContent className="space-y-2">
        {filteredErrors.length === 0 ? <div className="flex h-32 flex-col items-center justify-center text-sm text-muted-foreground"><ShieldCheck className="mb-2 h-6 w-6" />No matching errors.</div> : filteredErrors.map((item) => <button key={item.id} onClick={() => openError(item)} className="flex w-full items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><Badge variant={item.status_code >= 500 ? "destructive" : "outline"} className="font-mono">{item.status_code}</Badge><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="text-xs font-semibold">{item.method}</span><code className="truncate text-xs text-foreground/80">{item.route}</code></div><p className="mt-1 truncate text-xs text-muted-foreground">{item.exception_type || "HTTP error"} · {item.error_message}</p></div><div className="hidden text-right text-[11px] text-muted-foreground sm:block"><div>{formatTime(item.occurred_at, true)}</div><div className="mt-1 font-mono">{item.client_ip || "unknown IP"}</div></div></button>)}
        <div className="flex items-center justify-between border-t border-border/70 pt-3"><span className="text-xs text-muted-foreground">Page {page} of {Math.max(1, Math.ceil(errorTotal / 25))}</span><div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft className="h-4 w-4" />Previous</Button><Button variant="outline" size="sm" disabled={page * 25 >= errorTotal} onClick={() => setPage((value) => value + 1)}>Next<ChevronRight className="h-4 w-4" /></Button></div></div>
      </CardContent></Card>

      <Card><CardHeader><div className="flex items-center justify-between"><div><CardTitle className="text-base">Alert policy</CardTitle><p className="mt-1 text-xs text-muted-foreground">Telegram notifications via the admin bot</p></div><BellRing className="h-4 w-4 text-muted-foreground" /></div></CardHeader><CardContent className="space-y-5">
        {!settings ? <p className="text-sm text-muted-foreground">Loading settings…</p> : <>
          <div className="flex items-center justify-between rounded-lg border border-border/70 p-3"><div><p className="text-sm font-medium">Telegram alerts</p><p className="text-xs text-muted-foreground">Disable without stopping collection</p></div><Switch checked={settings.enabled} onCheckedChange={(enabled: boolean) => setSettings({ ...settings, enabled })} /></div>
          {[
            ["5xx in 5 minutes", "server_error_threshold", "Alert when the count is greater than this value"],
            ["p95 latency, ms", "latency_p95_ms", "Requires the minimum request sample"],
            ["Minimum requests", "latency_min_requests", "Avoid latency alerts on tiny samples"],
            ["Failed health checks", "health_failures", "Consecutive one-minute checks"],
            ["Cooldown, minutes", "cooldown_minutes", "Minimum time between repeated alerts"],
          ].map(([label, key, hint]) => <label key={key} className="block"><span className="flex items-center justify-between text-sm"><span>{label}</span><SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" /></span><Input type="number" value={settings[key as keyof ApiAlertSettings] as number} onChange={(e) => setSettings({ ...settings, [key]: Number(e.target.value) })} className="mt-2 font-mono" /><span className="mt-1 block text-[11px] text-muted-foreground">{hint}</span></label>)}
          <Button className="w-full" onClick={saveSettings} disabled={saving}>{saving ? "Saving…" : "Save alert policy"}</Button>
        </>}
      </CardContent></Card>
    </div>

    <Card><CardHeader><CardTitle className="text-base">Error groups</CardTitle><p className="text-xs text-muted-foreground">Top fingerprints and the number of affected users in the filtered period</p></CardHeader><CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
      {groups.length === 0 ? <p className="text-sm text-muted-foreground">No grouped errors.</p> : groups.map((group) => <button key={group.fingerprint} onClick={() => { setSearch(group.fingerprint); setPage(1); }} className="rounded-lg border border-border/70 p-4 text-left transition-colors hover:bg-muted/40"><div className="flex items-center justify-between"><Badge variant={group.status_code >= 500 ? "destructive" : "outline"}>{group.status_code}</Badge><span className="font-mono text-xs">{group.count.toLocaleString()} events</span></div><p className="mt-3 truncate text-sm font-medium">{group.exception_type || "HTTP error"}</p><code className="mt-1 block truncate text-[11px] text-muted-foreground">{group.route}</code><div className="mt-3 flex justify-between text-xs text-muted-foreground"><span>{group.affected_users} affected users</span><span>{formatTime(group.last_seen_at, true)}</span></div></button>)}
    </CardContent></Card>

    <Sheet open={!!selected} onOpenChange={(open: boolean) => !open && setSelected(null)}><SheetContent side="right" className="w-full overflow-y-auto sm:max-w-2xl"><SheetHeader><SheetTitle className="flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-red-400" />Request failure</SheetTitle><SheetDescription>{selected?.request_id}</SheetDescription></SheetHeader>{selected && <div className="mt-6 space-y-6">
      <div className="grid grid-cols-2 gap-3">{[
        ["Status", selected.status_code], ["Service", SERVICE_LABELS[selected.service] ?? selected.service], ["Endpoint", `${selected.method} ${selected.route}`], ["Duration", `${Math.round(selected.duration_ms)} ms`],
        ["User ID", selected.user_id ?? "—"], ["Telegram ID", selected.tg_id ?? "—"], ["Client IP", selected.client_ip ?? "—"], ["Occurred", formatTime(selected.occurred_at)],
      ].map(([label, value]) => <div key={label} className="rounded-lg border border-border/70 p-3"><p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p><p className="mt-1 break-all font-mono text-xs">{value}</p></div>)}</div>
      <div><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Error</p><div className="mt-2 rounded-lg border border-red-500/20 bg-red-500/[.04] p-4"><p className="text-sm font-medium">{selected.exception_type || "HTTP error"}</p><p className="mt-2 whitespace-pre-wrap break-words font-mono text-xs text-muted-foreground">{selected.error_message}</p></div></div>
      <div><p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Traceback</p><pre className="mt-2 max-h-[420px] overflow-auto rounded-lg border border-border bg-black/30 p-4 text-[11px] leading-relaxed text-foreground/80">{selected.traceback || "No traceback was captured for this response."}</pre></div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 className="h-3.5 w-3.5" />Fingerprint <code>{selected.error_fingerprint}</code></div>
      {selected.user_id && <Button variant="outline" onClick={() => navigate(`/users?search=${selected.user_id}`)}>Open user <ExternalLink className="h-4 w-4" /></Button>}
    </div>}</SheetContent></Sheet>
  </div>;
}
