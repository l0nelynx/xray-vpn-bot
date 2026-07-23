import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
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

interface ProviderState {
  provider: string;
  enabled: boolean;
  managed: boolean;
  source: string;
  fields: Record<string, unknown>;
  field_meta: ProviderFieldMeta[];
  updated_at?: string | null;
}

const RUNTIME_CORE: Record<string, string> = {
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

const RUNTIME_REMNAWAVE: Record<string, string> = {
  rw_free_id: "FREE squad UUID",
  rw_pro_id: "PRO squad UUID",
  rw_ext_free_id: "External FREE squad UUID",
  rw_ext_pro_id: "External PRO squad UUID",
  subscription_url: "Subscription base URL",
};

const RUNTIME_EMAIL: Record<string, string> = {
  smtp_host: "SMTP host",
  smtp_port: "SMTP port",
  smtp_user: "SMTP user",
  smtp_from: "SMTP from",
  smtp_use_tls: "SMTP use TLS (465)",
  email_code_ttl: "Email code TTL (sec)",
  email_code_max_attempts: "Email code max attempts",
};

const RUNTIME_ANDROID: Record<string, string> = {
  android_access_ttl: "Access token TTL (sec)",
  android_refresh_ttl: "Refresh token TTL (sec)",
  android_jwt_issuer: "JWT issuer",
};

const RUNTIME_STORE: Record<string, string> = {
  store_url: "Store API URL",
};

const RUNTIME_WEB: Record<string, string> = {
  web_allowed_origins: "Allowed origins (comma or JSON list)",
};

const RUNTIME_PUSH: Record<string, string> = {
  fcm_project_id: "FCM project ID",
  google_play_package_name: "Google Play package name",
};

const ALL_RUNTIME_LABELS: Record<string, string> = {
  ...RUNTIME_CORE,
  ...RUNTIME_REMNAWAVE,
  ...RUNTIME_EMAIL,
  ...RUNTIME_ANDROID,
  ...RUNTIME_STORE,
  ...RUNTIME_WEB,
  ...RUNTIME_PUSH,
};

const NUMERIC_KEYS = new Set([
  "free_days",
  "free_traffic",
  "admin_logs_length",
  "news_id",
  "logs_id",
  "web_id",
  "smtp_port",
  "email_code_ttl",
  "email_code_max_attempts",
  "android_access_ttl",
  "android_refresh_ttl",
]);

const BOOL_KEYS = new Set(["smtp_use_tls"]);

const INTEGRATION_TABS: { id: string; label: string; providers: string[]; runtime: Record<string, string> }[] = [
  { id: "email", label: "Email", providers: ["smtp"], runtime: RUNTIME_EMAIL },
  { id: "android", label: "Android", providers: ["android"], runtime: RUNTIME_ANDROID },
  { id: "store", label: "Store", providers: ["store"], runtime: RUNTIME_STORE },
  { id: "web", label: "Web", providers: ["web"], runtime: RUNTIME_WEB },
  { id: "push", label: "Push / Play", providers: ["fcm", "google_play"], runtime: RUNTIME_PUSH },
];

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

function formatRuntimeValue(key: string, v: unknown): string {
  if (v == null) return "";
  if (BOOL_KEYS.has(key)) return v ? "true" : "false";
  if (key === "web_allowed_origins") {
    if (Array.isArray(v)) return v.join(", ");
    return String(v);
  }
  return String(v);
}

function parseRuntimeValue(key: string, raw: string): unknown {
  if (NUMERIC_KEYS.has(key)) return raw === "" ? null : Number(raw);
  if (BOOL_KEYS.has(key)) {
    const s = raw.trim().toLowerCase();
    return s === "1" || s === "true" || s === "yes" || s === "on";
  }
  if (key === "web_allowed_origins") {
    const trimmed = raw.trim();
    if (!trimmed) return [];
    if (trimmed.startsWith("[")) {
      try {
        const parsed = JSON.parse(trimmed);
        if (Array.isArray(parsed)) return parsed.map(String);
      } catch {
        /* fall through */
      }
    }
    return trimmed.split(",").map((s) => s.trim()).filter(Boolean);
  }
  return raw;
}

function RuntimeFields({
  labels,
  runtime,
  runtimeValues,
  setRuntimeValues,
}: {
  labels: Record<string, string>;
  runtime: RuntimeResponse;
  runtimeValues: Record<string, string>;
  setRuntimeValues: Dispatch<SetStateAction<Record<string, string>>>;
}) {
  return (
    <>
      {Object.entries(labels).map(([key, label]) => (
        <div key={key} className="space-y-1.5">
          <Label className="flex items-center gap-2">
            {label}
            {sourceBadge(runtime.sources[key] || "default")}
          </Label>
          <Input
            type={NUMERIC_KEYS.has(key) ? "number" : "text"}
            value={runtimeValues[key] ?? ""}
            onChange={(e) => setRuntimeValues((prev) => ({ ...prev, [key]: e.target.value }))}
          />
        </div>
      ))}
    </>
  );
}

function IntegrationCards({
  providers,
  forms,
  setForms,
  saving,
  onSave,
}: {
  providers: ProviderState[];
  forms: Record<string, ProviderForm>;
  setForms: Dispatch<SetStateAction<Record<string, ProviderForm>>>;
  saving: boolean;
  onSave: (p: ProviderState) => void;
}) {
  if (!providers.length) return null;
  return (
    <div className="space-y-4">
      {providers.map((p) => {
        const pf = forms[p.provider] ?? { enabled: p.enabled, fields: {} };
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
                    setForms((prev) => ({
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
                  {f.name.endsWith("_sa_json") || f.name.includes("sa_json") ? (
                    <Textarea
                      rows={4}
                      placeholder={f.secret ? "paste JSON or leave blank to keep" : undefined}
                      value={pf.fields[f.name] ?? ""}
                      onChange={(e) =>
                        setForms((prev) => ({
                          ...prev,
                          [p.provider]: {
                            ...pf,
                            fields: { ...pf.fields, [f.name]: e.target.value },
                          },
                        }))
                      }
                    />
                  ) : (
                    <Input
                      type={f.secret ? "password" : "text"}
                      placeholder={f.secret ? "leave blank to keep" : undefined}
                      value={pf.fields[f.name] ?? ""}
                      onChange={(e) =>
                        setForms((prev) => ({
                          ...prev,
                          [p.provider]: {
                            ...pf,
                            fields: { ...pf.fields, [f.name]: e.target.value },
                          },
                        }))
                      }
                    />
                  )}
                </div>
              ))}
              <Button onClick={() => onSave(p)} disabled={saving}>
                Save {p.provider}
              </Button>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

export default function WebAppSettingsPage() {
  const [flags, setFlags] = useState<FeatureFlags | null>(null);
  const [runtime, setRuntime] = useState<RuntimeResponse | null>(null);
  const [payments, setPayments] = useState<ProviderState[] | null>(null);
  const [integrations, setIntegrations] = useState<ProviderState[] | null>(null);
  const [saving, setSaving] = useState(false);

  const [maintenance, setMaintenance] = useState<Maintenance>({ enabled: false, title: "", text: "" });
  const [runtimeValues, setRuntimeValues] = useState<Record<string, string>>({});
  const [providerForms, setProviderForms] = useState<Record<string, ProviderForm>>({});
  const [integrationForms, setIntegrationForms] = useState<Record<string, ProviderForm>>({});

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
        for (const k of Object.keys(ALL_RUNTIME_LABELS)) {
          values[k] = formatRuntimeValue(k, data.values[k]);
        }
        setRuntimeValues(values);
      })
      .catch(() => toast.error("Failed to load runtime settings"));
    api
      .get<{ providers: ProviderState[] }>("/settings/payments")
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
    api
      .get<{ providers: ProviderState[] }>("/settings/integrations")
      .then((data) => {
        setIntegrations(data.providers);
        const forms: Record<string, ProviderForm> = {};
        for (const p of data.providers) {
          const fields: Record<string, string> = {};
          for (const f of p.field_meta) {
            const v = p.fields[f.name];
            fields[f.name] = f.secret ? "" : v == null ? "" : String(v);
          }
          forms[p.provider] = { enabled: p.enabled, fields };
        }
        setIntegrationForms(forms);
      })
      .catch(() => toast.error("Failed to load service integrations"));
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

  async function saveRuntime(keys: string[]) {
    setSaving(true);
    try {
      const values = Object.fromEntries(
        keys.map((k) => [k, parseRuntimeValue(k, runtimeValues[k] ?? "")]),
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
      for (const k of Object.keys(ALL_RUNTIME_LABELS)) {
        next[k] = formatRuntimeValue(k, data.values[k]);
      }
      setRuntimeValues(next);
      toast.success("Settings saved (no restart needed)");
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  async function saveProvider(provider: ProviderState) {
    const pf = providerForms[provider.provider];
    if (!pf) return;
    setSaving(true);
    try {
      const updated = await api.put<ProviderState>(`/settings/payments/${provider.provider}`, {
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

  async function saveIntegration(provider: ProviderState) {
    const pf = integrationForms[provider.provider];
    if (!pf) return;
    setSaving(true);
    try {
      const updated = await api.put<ProviderState>(
        `/settings/integrations/${provider.provider}`,
        {
          enabled: !!pf.enabled,
          fields: Object.fromEntries(provider.field_meta.map((f) => [f.name, pf.fields[f.name]])),
        },
      );
      setIntegrations((prev) =>
        (prev || []).map((p) => (p.provider === updated.provider ? updated : p)),
      );
      setIntegrationForms((prev) => {
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
        <TabsList className="mb-4 flex h-auto flex-wrap gap-1">
          <TabsTrigger value="runtime">Runtime</TabsTrigger>
          <TabsTrigger value="remnawave">Remnawave</TabsTrigger>
          {INTEGRATION_TABS.map((t) => (
            <TabsTrigger key={t.id} value={t.id}>
              {t.label}
            </TabsTrigger>
          ))}
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
                <RuntimeFields
                  labels={RUNTIME_CORE}
                  runtime={runtime}
                  runtimeValues={runtimeValues}
                  setRuntimeValues={setRuntimeValues}
                />
                <Button onClick={() => saveRuntime(Object.keys(RUNTIME_CORE))} disabled={saving}>
                  Save runtime
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="remnawave">
          {!runtime ? (
            <Spinner className="h-6 w-6" />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Remnawave squads</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-xs text-muted-foreground">
                  Panel URL / API token / webhook secret stay in <code>config.yml</code>.
                </p>
                <RuntimeFields
                  labels={RUNTIME_REMNAWAVE}
                  runtime={runtime}
                  runtimeValues={runtimeValues}
                  setRuntimeValues={setRuntimeValues}
                />
                <Button
                  onClick={() => saveRuntime(Object.keys(RUNTIME_REMNAWAVE))}
                  disabled={saving}
                >
                  Save Remnawave
                </Button>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {INTEGRATION_TABS.map((tab) => (
          <TabsContent key={tab.id} value={tab.id}>
            {!runtime || !integrations ? (
              <Spinner className="h-6 w-6" />
            ) : (
              <div className="space-y-4">
                {Object.keys(tab.runtime).length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">{tab.label} settings</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <RuntimeFields
                        labels={tab.runtime}
                        runtime={runtime}
                        runtimeValues={runtimeValues}
                        setRuntimeValues={setRuntimeValues}
                      />
                      <Button
                        onClick={() => saveRuntime(Object.keys(tab.runtime))}
                        disabled={saving}
                      >
                        Save {tab.label} settings
                      </Button>
                    </CardContent>
                  </Card>
                )}
                <IntegrationCards
                  providers={integrations.filter((p) => tab.providers.includes(p.provider))}
                  forms={integrationForms}
                  setForms={setIntegrationForms}
                  saving={saving}
                  onSave={saveIntegration}
                />
              </div>
            )}
          </TabsContent>
        ))}

        <TabsContent value="payments">
          {!payments ? (
            <Spinner className="h-6 w-6" />
          ) : (
            <IntegrationCards
              providers={payments}
              forms={providerForms}
              setForms={setProviderForms}
              saving={saving}
              onSave={saveProvider}
            />
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
                      ? "In-bot tariff menus and inline payments are active. Prices come from Dashboard tariffs."
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
