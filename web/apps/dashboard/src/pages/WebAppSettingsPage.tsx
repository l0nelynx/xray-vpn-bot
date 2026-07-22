import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { Label } from "@xray/ui/components/label";
import { Badge } from "@xray/ui/components/badge";
import { Switch } from "@xray/ui/components/switch";
import { Spinner } from "@xray/ui/components/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@xray/ui/components/tabs";
import { api } from "../api/client";

interface FeatureFlags {
  legacy_bot_constructor: boolean;
}

interface Maintenance {
  enabled: boolean;
  title: string;
  text: string;
}

interface RuntimeResponse {
  maintenance: Maintenance;
  values: Record<string, unknown>;
  sources: Record<string, string>;
}

interface ProviderFieldMeta {
  name: string;
  secret: boolean;
}

interface PaymentProviderState {
  provider: string;
  enabled: boolean;
  managed: boolean;
  source: string;
  fields: Record<string, unknown>;
  field_meta: ProviderFieldMeta[];
  updated_at?: string | null;
}

const RUNTIME_LABELS: Record<string, string> = {
  branding_name: "Brand name",
  news_id: "News channel ID",
  news_url: "News URL",
  support_bot_id: "Support contact",
  agreement_url: "Agreement URL",
  policy_url: "Privacy policy URL",
  logs_id: "Logs chat ID",
  web_id: "Web portal chat ID",
  admin_logs_length: "Admin logs length",
  free_days: "Free plan days",
  free_traffic: "Free plan traffic (GB)",
};

const NUMERIC_KEYS = new Set([
  "free_days",
  "free_traffic",
  "admin_logs_length",
  "news_id",
  "logs_id",
  "web_id",
]);

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

function sourceBadge(source: string) {
  const variant: BadgeVariant =
    source === "dashboard" ? "success" : source === "yaml" ? "warning" : "outline";
  return <Badge variant={variant}>{source}</Badge>;
}

interface ProviderForm {
  enabled: boolean;
  fields: Record<string, string>;
}

export default function WebAppSettingsPage() {
  const [flags, setFlags] = useState<FeatureFlags | null>(null);
  const [runtime, setRuntime] = useState<RuntimeResponse | null>(null);
  const [payments, setPayments] = useState<PaymentProviderState[] | null>(null);
  const [saving, setSaving] = useState(false);

  const [maintenance, setMaintenance] = useState<Maintenance>({ enabled: false, title: "", text: "" });
  const [runtimeValues, setRuntimeValues] = useState<Record<string, string>>({});
  const [providerForms, setProviderForms] = useState<Record<string, ProviderForm>>({});

  useEffect(() => {
    api
      .get<FeatureFlags>("/settings/features")
      .then(setFlags)
      .catch(() => toast.error("Failed to load feature flags"));
    api
      .get<RuntimeResponse>("/settings/runtime")
      .then((data) => {
        setRuntime(data);
        setMaintenance(data.maintenance);
        const values: Record<string, string> = {};
        for (const k of Object.keys(RUNTIME_LABELS)) {
          const v = data.values[k];
          values[k] = v == null ? "" : String(v);
        }
        setRuntimeValues(values);
      })
      .catch(() => toast.error("Failed to load runtime settings"));
    api
      .get<{ providers: PaymentProviderState[] }>("/settings/payments")
      .then((data) => {
        setPayments(data.providers);
        const forms: Record<string, ProviderForm> = {};
        for (const p of data.providers) {
          const fields: Record<string, string> = {};
          for (const f of p.field_meta) {
            const v = p.fields[f.name];
            fields[f.name] = f.secret ? "" : v == null ? "" : String(v);
          }
          forms[p.provider] = { enabled: p.enabled, fields };
        }
        setProviderForms(forms);
      })
      .catch(() => toast.error("Failed to load payment integrations"));
  }, []);

  async function handleToggle(value: boolean) {
    if (!flags) return;
    const updated = { ...flags, legacy_bot_constructor: value };
    setSaving(true);
    try {
      await api.put("/settings/features", updated);
      setFlags(updated);
      toast.success(
        value
          ? "Legacy bot constructor enabled. Restart the bot to apply."
          : "Legacy bot constructor disabled. Restart the bot to apply.",
      );
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  async function saveRuntime() {
    setSaving(true);
    try {
      const values = Object.fromEntries(
        Object.keys(RUNTIME_LABELS).map((k) => {
          const raw = runtimeValues[k] ?? "";
          if (NUMERIC_KEYS.has(k)) return [k, raw === "" ? null : Number(raw)];
          return [k, raw];
        }),
      );
      const payload = {
        maintenance: {
          enabled: !!maintenance.enabled,
          title: maintenance.title || "",
          text: maintenance.text || "",
        },
        values,
      };
      const data = await api.put<RuntimeResponse>("/settings/runtime", payload);
      setRuntime(data);
      setMaintenance(data.maintenance);
      const next: Record<string, string> = {};
      for (const k of Object.keys(RUNTIME_LABELS)) {
        const v = data.values[k];
        next[k] = v == null ? "" : String(v);
      }
      setRuntimeValues(next);
      toast.success("Runtime settings saved (no restart needed)");
    } catch {
      toast.error("Failed to save runtime settings");
    } finally {
      setSaving(false);
    }
  }

  async function saveProvider(provider: PaymentProviderState) {
    const pf = providerForms[provider.provider];
    if (!pf) return;
    setSaving(true);
    try {
      const updated = await api.put<PaymentProviderState>(`/settings/payments/${provider.provider}`, {
        enabled: !!pf.enabled,
        fields: Object.fromEntries(provider.field_meta.map((f) => [f.name, pf.fields[f.name]])),
      });
      setPayments((prev) => (prev || []).map((p) => (p.provider === updated.provider ? updated : p)));
      setProviderForms((prev) => {
        const fields: Record<string, string> = {};
        for (const f of updated.field_meta) {
          const v = updated.fields[f.name];
          fields[f.name] = f.secret ? "" : v == null ? "" : String(v);
        }
        return { ...prev, [updated.provider]: { enabled: updated.enabled, fields } };
      });
      toast.success(`${provider.provider}: saved (Dashboard is now source of truth)`);
    } catch {
      toast.error(`Failed to save ${provider.provider}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-foreground md:text-2xl">Settings</h1>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">
        Dual-source period: values saved here override <code>config.yml</code>. Until you save, YAML
        remains the fallback.
      </p>

      <Tabs defaultValue="runtime">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="runtime">Runtime</TabsTrigger>
          <TabsTrigger value="payments">Payments</TabsTrigger>
          <TabsTrigger value="flags">Feature flags</TabsTrigger>
        </TabsList>

        <TabsContent value="runtime">
          {!runtime ? (
            <Spinner className="h-6 w-6" />
          ) : (
            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-sm">Runtime &amp; maintenance</CardTitle>
                {sourceBadge(runtime.sources.maintenance || "db")}
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={maintenance.enabled}
                      onCheckedChange={(v: boolean) => setMaintenance((m) => ({ ...m, enabled: v }))}
                    />
                    <Label>Maintenance mode</Label>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Blocks MiniApp/web APIs and the user bot (admin bypass).
                  </p>
                </div>
                <div className="space-y-1.5">
                  <Label>Maintenance title</Label>
                  <Input
                    value={maintenance.title}
                    onChange={(e) => setMaintenance((m) => ({ ...m, title: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Maintenance text</Label>
                  <Textarea
                    rows={3}
                    value={maintenance.text}
                    onChange={(e) => setMaintenance((m) => ({ ...m, text: e.target.value }))}
                  />
                </div>
                {Object.entries(RUNTIME_LABELS).map(([key, label]) => (
                  <div key={key} className="space-y-1.5">
                    <Label className="flex items-center gap-2">
                      {label}
                      {sourceBadge(runtime.sources[key] || "default")}
                    </Label>
                    <Input
                      type={NUMERIC_KEYS.has(key) ? "number" : "text"}
                      value={runtimeValues[key] ?? ""}
                      onChange={(e) =>
                        setRuntimeValues((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                    />
                  </div>
                ))}
                <Button onClick={saveRuntime} disabled={saving}>
                  Save runtime
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="payments">
          {!payments ? (
            <Spinner className="h-6 w-6" />
          ) : (
            <div className="space-y-4">
              {payments.map((p) => {
                const pf = providerForms[p.provider] ?? { enabled: p.enabled, fields: {} };
                return (
                  <Card key={p.provider}>
                    <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="flex items-center gap-2 text-sm">
                        {p.provider}
                        {sourceBadge(p.source)}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={pf.enabled}
                          onCheckedChange={(v: boolean) =>
                            setProviderForms((prev) => ({
                              ...prev,
                              [p.provider]: { ...pf, enabled: v },
                            }))
                          }
                        />
                        <Label>Enabled</Label>
                      </div>
                      {p.field_meta.map((f) => (
                        <div key={f.name} className="space-y-1.5">
                          <Label>{f.name}</Label>
                          <Input
                            type={f.secret ? "password" : "text"}
                            placeholder={f.secret ? "leave blank to keep" : undefined}
                            value={pf.fields[f.name] ?? ""}
                            onChange={(e) =>
                              setProviderForms((prev) => ({
                                ...prev,
                                [p.provider]: {
                                  ...pf,
                                  fields: { ...pf.fields, [f.name]: e.target.value },
                                },
                              }))
                            }
                          />
                        </div>
                      ))}
                      <Button onClick={() => saveProvider(p)} disabled={saving}>
                        Save {p.provider}
                      </Button>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="flags">
          {flags === null ? (
            <Spinner className="h-6 w-6" />
          ) : (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Bot Feature Flags</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={flags.legacy_bot_constructor}
                      onCheckedChange={(v: boolean) => handleToggle(v)}
                      disabled={saving}
                    />
                    <Label>Legacy Bot Constructor</Label>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {flags.legacy_bot_constructor
                      ? "In-bot tariff menus and inline payments are active. Users can pay directly in Telegram."
                      : "Disabled — the bot directs users to the MiniApp for all purchases. Restart the bot after changing."}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
