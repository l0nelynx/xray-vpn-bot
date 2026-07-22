import { useEffect, useState, useCallback, useMemo, type ReactNode } from "react";
import { toast } from "sonner";
import {
  RefreshCw,
  Plus,
  Pencil,
  Trash2,
  Link as LinkIcon,
  Copy,
  KeyRound,
  PauseCircle,
  PlayCircle,
  Server,
  User,
  Settings,
  MoreHorizontal,
  Timer,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { Label } from "@xray/ui/components/label";
import { Badge } from "@xray/ui/components/badge";
import { Checkbox } from "@xray/ui/components/checkbox";
import { Spinner } from "@xray/ui/components/spinner";
import { Alert, AlertDescription, AlertTitle } from "@xray/ui/components/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@xray/ui/components/tabs";
import { cn } from "@xray/ui/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@xray/ui/components/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@xray/ui/components/table";
import { api } from "../api/client";
import type {
  TelmtEnvelope,
  TelmtSystemInfo,
  TelmtSummary,
  TelmtHealth,
  TelmtRuntimeGates,
  TelmtUser,
  TelmtSecurityPosture,
  TelmtFreeParams,
  TelmtBulkResult,
  TelmtHealthReady,
  TelmtLimitsEffective,
  TelmtSecurityWhitelist,
  TelmtRuntimeConnectionsSummary,
  TelmtRuntimeRecentEvents,
  TelmtTlsFingerprints,
  TelmtConfigData,
  TelmtPatchConfigResponse,
} from "../api/types";
import { TELMT_EDITABLE_CONFIG_SECTIONS } from "../api/types";
import StatsCard from "../components/StatsCard";
import ConfirmButton from "../components/ConfirmButton";
import useIsMobile from "../hooks/useIsMobile";

function formatUptime(secs: number): string {
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(" ");
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function formatEpoch(secs: number): string {
  const d = new Date(secs * 1000);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatEpochShort(secs: number): string {
  const d = new Date(secs * 1000);
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatDateShort(iso: string): string {
  const d = new Date(iso);
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${String(d.getFullYear()).slice(2)}`;
}

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 16);
}

function fromLocalInput(local: string): string {
  return new Date(local).toISOString();
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 shrink-0 rounded-full",
        ok ? "bg-emerald-500" : "bg-muted-foreground/40",
      )}
    />
  );
}

function KV({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right text-foreground/85">{children}</span>
    </div>
  );
}

interface SimpleColumn<T> {
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
}

function SimpleTable<T>({
  columns,
  data,
  rowKey,
  empty = "No data",
  maxHeightClass,
}: {
  columns: SimpleColumn<T>[];
  data: T[];
  rowKey: (row: T, index: number) => string | number;
  empty?: ReactNode;
  maxHeightClass?: string;
}) {
  return (
    <div className={cn("overflow-auto rounded-lg border border-border", maxHeightClass)}>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {columns.map((c, i) => (
              <TableHead key={i} className={c.className}>
                {c.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={columns.length} className="h-20 text-center text-muted-foreground">
                {empty}
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, ri) => (
              <TableRow key={rowKey(row, ri)}>
                {columns.map((c, ci) => (
                  <TableCell key={ci} className={c.className}>
                    {c.cell(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}

// ======================== Server Tab ========================

function ServerTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [sysInfo, setSysInfo] = useState<TelmtSystemInfo | null>(null);
  const [summary, setSummary] = useState<TelmtSummary | null>(null);
  const [health, setHealth] = useState<TelmtHealth | null>(null);
  const [gates, setGates] = useState<TelmtRuntimeGates | null>(null);
  const [security, setSecurity] = useState<TelmtSecurityPosture | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get<TelmtEnvelope<TelmtSystemInfo>>("/telemt/system/info"),
      api.get<TelmtEnvelope<TelmtSummary>>("/telemt/stats/summary"),
      api.get<TelmtEnvelope<TelmtHealth>>("/telemt/health"),
      api.get<TelmtEnvelope<TelmtRuntimeGates>>("/telemt/runtime/gates"),
      api.get<TelmtEnvelope<TelmtSecurityPosture>>("/telemt/security/posture"),
    ])
      .then(([si, st, h, g, sec]) => {
        setSysInfo(si.data);
        setSummary(st.data);
        setHealth(h.data);
        setGates(g.data);
        setSecurity(sec.data);
      })
      .catch(() => toast.error("Failed to load telemt data"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !sysInfo) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button variant="outline" onClick={load} disabled={loading} className={cn(isMobile && "w-full")}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-2 md:gap-4 lg:grid-cols-4">
        <StatsCard title="Connections" value={summary?.connections_total ?? 0} loading={loading} />
        <StatsCard
          title="Bad Connections"
          value={summary?.connections_bad_total ?? 0}
          loading={loading}
          color={summary?.connections_bad_total ? "#ff4d4f" : "#36cfc9"}
        />
        <StatsCard title="Users" value={summary?.configured_users ?? 0} loading={loading} />
        <StatsCard
          title="Uptime"
          value={summary ? formatUptime(summary.uptime_seconds) : "..."}
          loading={loading}
        />
      </div>

      <div className="mt-2 grid grid-cols-1 gap-2 md:mt-4 md:gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">System Info</CardTitle>
          </CardHeader>
          <CardContent>
            {sysInfo && (
              <div className="divide-y divide-border/50">
                <KV label="Version">{sysInfo.version}</KV>
                <KV label="Architecture">{sysInfo.target_arch}</KV>
                <KV label="OS">{sysInfo.target_os}</KV>
                <KV label="Build Profile">{sysInfo.build_profile}</KV>
                {sysInfo.git_commit && <KV label="Git Commit">{sysInfo.git_commit}</KV>}
                <KV label="Config Path">{sysInfo.config_path}</KV>
                <KV label="Config Reloads">{sysInfo.config_reload_count}</KV>
                <KV label="Started">{formatEpoch(sysInfo.process_started_at_epoch_secs)}</KV>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Runtime &amp; Security</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {health && (
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Status:</span>
                <StatusDot ok={health.status === "ok"} />
                <span className="text-foreground/85">{health.status}</span>
                {health.read_only && <Badge variant="warning">Read-Only</Badge>}
              </div>
            )}
            {gates && (
              <div>
                <div className="mb-1.5 text-xs uppercase tracking-wide text-muted-foreground">
                  Runtime Gates
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant={gates.accepting_new_connections ? "success" : "destructive"}>
                    Accepting Connections
                  </Badge>
                  <Badge variant={gates.me_runtime_ready ? "success" : "warning"}>
                    ME {gates.me_runtime_ready ? "Ready" : "Not Ready"}
                  </Badge>
                  <Badge>Startup: {gates.startup_status}</Badge>
                  {gates.startup_progress_pct < 100 && (
                    <Badge variant="warning">{gates.startup_progress_pct.toFixed(0)}%</Badge>
                  )}
                  <Badge variant="outline">{gates.use_middle_proxy ? "Middle Proxy" : "Direct"}</Badge>
                </div>
              </div>
            )}
            {security && (
              <div>
                <div className="mb-1.5 text-xs uppercase tracking-wide text-muted-foreground">
                  Security
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge variant={security.api_auth_header_enabled ? "success" : "destructive"}>
                    Auth: {security.api_auth_header_enabled ? "ON" : "OFF"}
                  </Badge>
                  <Badge variant={security.api_whitelist_enabled ? "success" : "outline"}>
                    Whitelist:{" "}
                    {security.api_whitelist_enabled ? `${security.api_whitelist_entries} entries` : "OFF"}
                  </Badge>
                  <Badge variant="outline">Log: {security.log_level}</Badge>
                  <Badge variant={security.telemetry_core_enabled ? "success" : "outline"}>
                    Core Telemetry: {security.telemetry_core_enabled ? "ON" : "OFF"}
                  </Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ======================== Users Tab ========================

interface UserForm {
  username: string;
  secret: string;
  user_ad_tag: string;
  max_tcp_conns: string;
  max_unique_ips: string;
  data_quota_bytes: string;
  rate_limit_up_bps: string;
  rate_limit_down_bps: string;
  expiration: string;
}

const emptyUserForm: UserForm = {
  username: "",
  secret: "",
  user_ad_tag: "",
  max_tcp_conns: "",
  max_unique_ips: "",
  data_quota_bytes: "",
  rate_limit_up_bps: "",
  rate_limit_down_bps: "",
  expiration: "",
};

function UsersTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<TelmtUser[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<TelmtUser | null>(null);
  const [linksUser, setLinksUser] = useState<TelmtUser | null>(null);
  const [createForm, setCreateForm] = useState<UserForm>(emptyUserForm);
  const [editForm, setEditForm] = useState<UserForm>(emptyUserForm);
  const [selectedUsernames, setSelectedUsernames] = useState<string[]>([]);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkExtendOpen, setBulkExtendOpen] = useState(false);
  const [bulkLimitsOpen, setBulkLimitsOpen] = useState(false);
  const [bulkExtendDate, setBulkExtendDate] = useState("");
  const [bulkLimits, setBulkLimits] = useState<UserForm>(emptyUserForm);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<TelmtEnvelope<TelmtUser[]>>("/telemt/users")
      .then((r) => setUsers(r.data))
      .catch(() => toast.error("Failed to load telemt users"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const buildUserBody = (form: UserForm, includeUsername: boolean) => {
    const body: Record<string, unknown> = {};
    if (includeUsername) body.username = form.username;
    if (form.secret) body.secret = form.secret;
    if (form.user_ad_tag) body.user_ad_tag = form.user_ad_tag;
    if (form.max_tcp_conns !== "") body.max_tcp_conns = Number(form.max_tcp_conns);
    if (form.max_unique_ips !== "") body.max_unique_ips = Number(form.max_unique_ips);
    if (form.data_quota_bytes !== "") body.data_quota_bytes = Number(form.data_quota_bytes);
    if (form.rate_limit_up_bps !== "") body.rate_limit_up_bps = Number(form.rate_limit_up_bps);
    if (form.rate_limit_down_bps !== "") body.rate_limit_down_bps = Number(form.rate_limit_down_bps);
    if (form.expiration) body.expiration_rfc3339 = fromLocalInput(form.expiration);
    return body;
  };

  const handleCreate = async () => {
    if (!/^[A-Za-z0-9_.\-]{1,64}$/.test(createForm.username)) {
      toast.error("Username: letters, digits, _ . - (1-64)");
      return;
    }
    try {
      await api.post("/telemt/users", buildUserBody(createForm, true));
      toast.success("User created");
      setCreateOpen(false);
      setCreateForm(emptyUserForm);
      load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to create user");
    }
  };

  const handleEdit = async () => {
    if (!editUser) return;
    try {
      await api.patch(`/telemt/users/${editUser.username}`, buildUserBody(editForm, false));
      toast.success("User updated");
      setEditUser(null);
      load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to update user");
    }
  };

  const handleDelete = async (username: string) => {
    try {
      await api.delete(`/telemt/users/${username}`);
      toast.success(`User ${username} deleted`);
      load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to delete user");
    }
  };

  const simpleAction = async (username: string, path: string, okMsg: string, errMsg: string) => {
    try {
      await api.post(`/telemt/users/${username}/${path}`, {});
      toast.success(okMsg);
      load();
    } catch (e) {
      toast.error((e as Error).message || errMsg);
    }
  };

  const handleRotateSecret = (u: string) =>
    simpleAction(u, "rotate-secret", `Secret rotated for ${u}`, "Failed to rotate secret");
  const handleResetQuota = (u: string) =>
    simpleAction(u, "reset-quota", `Quota reset for ${u}`, "Failed to reset quota");
  const handleEnableUser = (u: string) =>
    simpleAction(u, "enable", `User ${u} enabled`, "Failed to enable user");
  const handleDisableUser = (u: string) =>
    simpleAction(u, "disable", `User ${u} disabled`, "Failed to disable user");

  const runBulk = async (path: string, payload: Record<string, unknown>, successText: string) => {
    setBulkLoading(true);
    try {
      const result = await api.post<TelmtBulkResult>(path, payload);
      if (result.failed > 0) {
        toast.warning(`${successText}: ${result.succeeded}/${result.processed} succeeded`);
      } else {
        toast.success(`${successText}: ${result.succeeded}/${result.processed} succeeded`);
      }
      if (result.errors.length) {
        const first = result.errors[0];
        toast.error(`First error: ${first.username} - ${first.detail}`);
      }
      setSelectedUsernames([]);
      load();
    } catch (e) {
      toast.error((e as Error).message || "Bulk operation failed");
    } finally {
      setBulkLoading(false);
    }
  };

  const openEdit = (user: TelmtUser) => {
    setEditUser(user);
    setEditForm({
      username: user.username,
      secret: "",
      user_ad_tag: user.user_ad_tag || "",
      max_tcp_conns: user.max_tcp_conns != null ? String(user.max_tcp_conns) : "",
      max_unique_ips: user.max_unique_ips != null ? String(user.max_unique_ips) : "",
      data_quota_bytes: user.data_quota_bytes != null ? String(user.data_quota_bytes) : "",
      rate_limit_up_bps: user.rate_limit_up_bps != null ? String(user.rate_limit_up_bps) : "",
      rate_limit_down_bps: user.rate_limit_down_bps != null ? String(user.rate_limit_down_bps) : "",
      expiration: toLocalInput(user.expiration_rfc3339),
    });
  };

  const renderUserLimits = (user: TelmtUser) => {
    const hasNone =
      !user.max_tcp_conns &&
      !user.max_unique_ips &&
      !user.data_quota_bytes &&
      !user.expiration_rfc3339;
    return (
      <div className="flex flex-wrap gap-1">
        {user.max_tcp_conns != null && <Badge variant="outline">TCP: {user.max_tcp_conns}</Badge>}
        {user.max_unique_ips != null && <Badge variant="outline">IPs: {user.max_unique_ips}</Badge>}
        {user.data_quota_bytes != null && (
          <Badge variant="outline">Quota: {formatBytes(user.data_quota_bytes)}</Badge>
        )}
        {user.rate_limit_up_bps != null && (
          <Badge variant="secondary">UP: {formatBytes(user.rate_limit_up_bps / 8)}/s</Badge>
        )}
        {user.rate_limit_down_bps != null && (
          <Badge variant="secondary">DOWN: {formatBytes(user.rate_limit_down_bps / 8)}/s</Badge>
        )}
        {user.expiration_rfc3339 && (
          <Badge variant={new Date(user.expiration_rfc3339) < new Date() ? "destructive" : "default"}>
            Exp: {formatDateShort(user.expiration_rfc3339)}
          </Badge>
        )}
        {hasNone && <span className="text-muted-foreground">No limits</span>}
      </div>
    );
  };

  const toggleUserSelection = (username: string, checked: boolean) => {
    setSelectedUsernames((prev) =>
      checked ? [...prev, username] : prev.filter((u) => u !== username),
    );
  };

  const toggleSelectAll = (checked: boolean) => {
    setSelectedUsernames(checked ? users.map((u) => u.username) : []);
  };

  const userActionsMenu = (user: TelmtUser) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setLinksUser(user)}>
          <LinkIcon className="h-4 w-4" /> Links
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => openEdit(user)}>
          <Pencil className="h-4 w-4" /> Edit
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleRotateSecret(user.username)}>
          <KeyRound className="h-4 w-4" /> Rotate Secret
        </DropdownMenuItem>
        {user.enabled === false ? (
          <DropdownMenuItem onClick={() => handleEnableUser(user.username)}>
            <PlayCircle className="h-4 w-4" /> Enable
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onClick={() => handleDisableUser(user.username)}>
            <PauseCircle className="h-4 w-4" /> Disable
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={() => handleResetQuota(user.username)}>
          <Timer className="h-4 w-4" /> Reset Quota
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive"
          onClick={() => {
            if (window.confirm(`Delete ${user.username}?`)) handleDelete(user.username);
          }}
        >
          <Trash2 className="h-4 w-4" /> Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const renderUserMobile = (user: TelmtUser) => {
    const selected = selectedUsernames.includes(user.username);
    return (
      <Card
        key={user.username}
        className={cn("mb-2", selected && "border-primary/55")}
      >
        <CardContent className="p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Checkbox
                checked={selected}
                onCheckedChange={(c: boolean | "indeterminate") =>
                  toggleUserSelection(user.username, c === true)
                }
              />
              <StatusDot ok={user.in_runtime} />
              <span className="break-all font-medium text-foreground/85">{user.username}</span>
              {user.enabled === false && <Badge variant="warning">disabled</Badge>}
            </div>
            {userActionsMenu(user)}
          </div>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <div className="text-[11px] text-muted-foreground">Conns</div>
              <div>{user.current_connections}</div>
            </div>
            <div>
              <div className="text-[11px] text-muted-foreground">IPs</div>
              <div>{user.active_unique_ips}</div>
            </div>
            <div>
              <div className="text-[11px] text-muted-foreground">Traffic</div>
              <div>{formatBytes(user.total_octets)}</div>
            </div>
          </div>
          <div className="mt-2">{renderUserLimits(user)}</div>
        </CardContent>
      </Card>
    );
  };

  const userFormFields = (form: UserForm, setForm: (f: UserForm) => void, isCreate: boolean) => {
    const patch = (p: Partial<UserForm>) => setForm({ ...form, ...p });
    return (
      <div className="space-y-3">
        {isCreate && (
          <div className="space-y-1.5">
            <Label>Username *</Label>
            <Input
              placeholder="username"
              value={form.username}
              onChange={(e) => patch({ username: e.target.value })}
            />
          </div>
        )}
        <div className="space-y-1.5">
          <Label>Secret</Label>
          <Input
            placeholder="Auto-generated if empty"
            value={form.secret}
            onChange={(e) => patch({ secret: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Ad Tag</Label>
          <Input
            placeholder="32 hex chars"
            value={form.user_ad_tag}
            onChange={(e) => patch({ user_ad_tag: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Max TCP Connections</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.max_tcp_conns}
            onChange={(e) => patch({ max_tcp_conns: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Max Unique IPs</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.max_unique_ips}
            onChange={(e) => patch({ max_unique_ips: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Data Quota (bytes)</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.data_quota_bytes}
            onChange={(e) => patch({ data_quota_bytes: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Rate Limit Up (bps)</Label>
          <Input
            type="number"
            placeholder="No limit"
            value={form.rate_limit_up_bps}
            onChange={(e) => patch({ rate_limit_up_bps: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Rate Limit Down (bps)</Label>
          <Input
            type="number"
            placeholder="No limit"
            value={form.rate_limit_down_bps}
            onChange={(e) => patch({ rate_limit_down_bps: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Expiration</Label>
          <Input
            type="datetime-local"
            value={form.expiration}
            onChange={(e) => patch({ expiration: e.target.value })}
          />
        </div>
      </div>
    );
  };

  const allSelected = users.length > 0 && selectedUsernames.length === users.length;

  const bulkToolbar = (
    <Card className="mb-3">
      <CardContent className="flex flex-wrap items-center gap-2 p-3">
        {isMobile && (
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={allSelected}
              onCheckedChange={(c: boolean | "indeterminate") => toggleSelectAll(c === true)}
            />
            Select all
          </label>
        )}
        <span className="text-sm text-muted-foreground">Selected: {selectedUsernames.length}</span>
        <Button
          variant="outline"
          size="sm"
          disabled={!selectedUsernames.length || bulkLoading}
          onClick={() => setBulkExtendOpen(true)}
        >
          Extend
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!selectedUsernames.length || bulkLoading}
          onClick={() => setBulkLimitsOpen(true)}
        >
          Update Limits
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" disabled={!selectedUsernames.length || bulkLoading}>
              <MoreHorizontal className="h-4 w-4" /> More
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem
              onClick={() => {
                if (
                  window.confirm(
                    `Reissue secret for ${selectedUsernames.length} users? Existing proxy links will stop working.`,
                  )
                ) {
                  runBulk(
                    "/telemt/users/bulk-rotate-secret",
                    { usernames: selectedUsernames },
                    "Bulk reissue secret",
                  );
                }
              }}
            >
              <KeyRound className="h-4 w-4" /> Reissue Secret
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() =>
                runBulk("/telemt/users/bulk-enable", { usernames: selectedUsernames }, "Bulk enable")
              }
            >
              <PlayCircle className="h-4 w-4" /> Enable
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() =>
                runBulk("/telemt/users/bulk-disable", { usernames: selectedUsernames }, "Bulk disable")
              }
            >
              <PauseCircle className="h-4 w-4" /> Disable
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <ConfirmButton
          title={`Delete ${selectedUsernames.length} users?`}
          destructive
          confirmText="Delete"
          onConfirm={() =>
            runBulk("/telemt/users/bulk-delete", { usernames: selectedUsernames }, "Bulk delete")
          }
        >
          <Button variant="destructive" size="sm" disabled={!selectedUsernames.length || bulkLoading}>
            Delete
          </Button>
        </ConfirmButton>
      </CardContent>
    </Card>
  );

  return (
    <div>
      <div className="mb-4 flex flex-col justify-between gap-2 md:flex-row">
        <Button onClick={() => setCreateOpen(true)} className={cn(isMobile && "w-full")}>
          <Plus className="h-4 w-4" />
          Add User
        </Button>
        <Button variant="outline" onClick={load} disabled={loading} className={cn(isMobile && "w-full")}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {bulkToolbar}

      {isMobile ? (
        loading ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-6 w-6" />
          </div>
        ) : users.length === 0 ? (
          <div className="py-10 text-center text-muted-foreground">No users</div>
        ) : (
          users.map(renderUserMobile)
        )
      ) : (
        <div className="overflow-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-10">
                  <Checkbox
                    checked={allSelected}
                    onCheckedChange={(c: boolean | "indeterminate") => toggleSelectAll(c === true)}
                  />
                </TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Connections</TableHead>
                <TableHead>Unique IPs</TableHead>
                <TableHead>Traffic</TableHead>
                <TableHead>Limits</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.length === 0 ? (
                <TableRow className="hover:bg-transparent">
                  <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                    {loading ? "Loading..." : "No users"}
                  </TableCell>
                </TableRow>
              ) : (
                users.map((r) => (
                  <TableRow key={r.username}>
                    <TableCell>
                      <Checkbox
                        checked={selectedUsernames.includes(r.username)}
                        onCheckedChange={(c: boolean | "indeterminate") =>
                          toggleUserSelection(r.username, c === true)
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span>{r.username}</span>
                        <StatusDot ok={r.in_runtime} />
                        {r.enabled === false && <Badge variant="warning">disabled</Badge>}
                      </div>
                    </TableCell>
                    <TableCell>{r.current_connections}</TableCell>
                    <TableCell>{r.active_unique_ips}</TableCell>
                    <TableCell>{formatBytes(r.total_octets)}</TableCell>
                    <TableCell>{renderUserLimits(r)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-0.5">
                        <Button variant="ghost" size="icon" title="Links" onClick={() => setLinksUser(r)}>
                          <LinkIcon className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="icon" title="Edit" onClick={() => openEdit(r)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Rotate Secret"
                          onClick={() => handleRotateSecret(r.username)}
                        >
                          <KeyRound className="h-4 w-4" />
                        </Button>
                        {r.enabled === false ? (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Enable user"
                            onClick={() => handleEnableUser(r.username)}
                          >
                            <PlayCircle className="h-4 w-4" />
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Disable user"
                            onClick={() => handleDisableUser(r.username)}
                          >
                            <PauseCircle className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Reset Quota"
                          onClick={() => handleResetQuota(r.username)}
                        >
                          <Timer className="h-4 w-4" />
                        </Button>
                        <ConfirmButton
                          title={`Delete ${r.username}?`}
                          destructive
                          confirmText="Delete"
                          onConfirm={() => handleDelete(r.username)}
                        >
                          <Button variant="ghost" size="icon" className="text-destructive" title="Delete">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </ConfirmButton>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog
        open={createOpen}
        onOpenChange={(o: boolean) => {
          setCreateOpen(o);
          if (!o) setCreateForm(emptyUserForm);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Telemt User</DialogTitle>
          </DialogHeader>
          {userFormFields(createForm, setCreateForm, true)}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editUser} onOpenChange={(o: boolean) => !o && setEditUser(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit {editUser?.username}</DialogTitle>
          </DialogHeader>
          {userFormFields(editForm, setEditForm, false)}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditUser(null)}>
              Cancel
            </Button>
            <Button onClick={handleEdit}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!linksUser} onOpenChange={(o: boolean) => !o && setLinksUser(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Links for {linksUser?.username}</DialogTitle>
          </DialogHeader>
          {linksUser && (
            <div>
              {(["tls", "secure", "classic"] as const).map((type) => {
                const links = linksUser.links[type];
                if (!links.length) return null;
                return (
                  <div key={type} className="mb-4">
                    <span className="text-xs font-semibold uppercase text-muted-foreground">
                      {type}
                    </span>
                    {links.map((link, i) => (
                      <div
                        key={i}
                        className="mt-2 flex items-center gap-2 rounded-md bg-white/5 px-3 py-2"
                      >
                        <span className="flex-1 break-all text-xs text-foreground/75">{link}</span>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => copyToClipboard(link)}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                );
              })}
              {!linksUser.links.tls.length &&
                !linksUser.links.secure.length &&
                !linksUser.links.classic.length && (
                  <span className="text-muted-foreground">No links available</span>
                )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog
        open={bulkExtendOpen}
        onOpenChange={(o: boolean) => {
          setBulkExtendOpen(o);
          if (!o) setBulkExtendDate("");
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bulk Extend ({selectedUsernames.length} users)</DialogTitle>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label>New Expiration *</Label>
            <Input
              type="datetime-local"
              value={bulkExtendDate}
              onChange={(e) => setBulkExtendDate(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkExtendOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={bulkLoading}
              onClick={() => {
                if (!bulkExtendDate) {
                  toast.error("Expiration is required");
                  return;
                }
                runBulk(
                  "/telemt/users/bulk-extend",
                  { usernames: selectedUsernames, expiration_rfc3339: fromLocalInput(bulkExtendDate) },
                  "Bulk extend",
                );
                setBulkExtendOpen(false);
                setBulkExtendDate("");
              }}
            >
              Apply
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={bulkLimitsOpen}
        onOpenChange={(o: boolean) => {
          setBulkLimitsOpen(o);
          if (!o) setBulkLimits(emptyUserForm);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Bulk Update Limits ({selectedUsernames.length} users)</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Max TCP Connections</Label>
              <Input
                type="number"
                value={bulkLimits.max_tcp_conns}
                onChange={(e) => setBulkLimits({ ...bulkLimits, max_tcp_conns: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Max Unique IPs</Label>
              <Input
                type="number"
                value={bulkLimits.max_unique_ips}
                onChange={(e) => setBulkLimits({ ...bulkLimits, max_unique_ips: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Data Quota (bytes)</Label>
              <Input
                type="number"
                value={bulkLimits.data_quota_bytes}
                onChange={(e) => setBulkLimits({ ...bulkLimits, data_quota_bytes: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Rate Limit Up (bps)</Label>
              <Input
                type="number"
                value={bulkLimits.rate_limit_up_bps}
                onChange={(e) => setBulkLimits({ ...bulkLimits, rate_limit_up_bps: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Rate Limit Down (bps)</Label>
              <Input
                type="number"
                value={bulkLimits.rate_limit_down_bps}
                onChange={(e) => setBulkLimits({ ...bulkLimits, rate_limit_down_bps: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkLimitsOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={bulkLoading}
              onClick={() => {
                const payload: Record<string, unknown> = { usernames: selectedUsernames };
                if (bulkLimits.max_tcp_conns !== "") payload.max_tcp_conns = Number(bulkLimits.max_tcp_conns);
                if (bulkLimits.max_unique_ips !== "") payload.max_unique_ips = Number(bulkLimits.max_unique_ips);
                if (bulkLimits.data_quota_bytes !== "")
                  payload.data_quota_bytes = Number(bulkLimits.data_quota_bytes);
                if (bulkLimits.rate_limit_up_bps !== "")
                  payload.rate_limit_up_bps = Number(bulkLimits.rate_limit_up_bps);
                if (bulkLimits.rate_limit_down_bps !== "")
                  payload.rate_limit_down_bps = Number(bulkLimits.rate_limit_down_bps);
                runBulk("/telemt/users/bulk-update-limits", payload, "Bulk update limits");
                setBulkLimitsOpen(false);
                setBulkLimits(emptyUserForm);
              }}
            >
              Apply
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ======================== Free Params Tab ========================

interface FreeForm {
  max_tcp_conns: string;
  max_unique_ips: string;
  data_quota_bytes: string;
  expire_days: string;
  rate_limit_up_bps: string;
  rate_limit_down_bps: string;
}

function FreeParamsTab() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<FreeForm>({
    max_tcp_conns: "",
    max_unique_ips: "",
    data_quota_bytes: "",
    expire_days: "30",
    rate_limit_up_bps: "",
    rate_limit_down_bps: "",
  });

  const patch = (p: Partial<FreeForm>) => setForm((f) => ({ ...f, ...p }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<TelmtFreeParams>("/telemt/free-params");
      setForm({
        max_tcp_conns: data.max_tcp_conns != null ? String(data.max_tcp_conns) : "",
        max_unique_ips: data.max_unique_ips != null ? String(data.max_unique_ips) : "",
        data_quota_bytes: data.data_quota_bytes != null ? String(data.data_quota_bytes) : "",
        expire_days: String(data.expire_days ?? 30),
        rate_limit_up_bps: data.rate_limit_up_bps != null ? String(data.rate_limit_up_bps) : "",
        rate_limit_down_bps: data.rate_limit_down_bps != null ? String(data.rate_limit_down_bps) : "",
      });
    } catch {
      toast.error("Failed to load free params");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    if (form.expire_days === "") {
      toast.error("Expire Days is required");
      return;
    }
    setSaving(true);
    try {
      const num = (v: string) => (v === "" ? null : Number(v));
      const payload: TelmtFreeParams = {
        max_tcp_conns: num(form.max_tcp_conns),
        max_unique_ips: num(form.max_unique_ips),
        data_quota_bytes: num(form.data_quota_bytes),
        expire_days: Number(form.expire_days) || 30,
        rate_limit_up_bps: num(form.rate_limit_up_bps),
        rate_limit_down_bps: num(form.rate_limit_down_bps),
      };
      await api.put("/telemt/free-params", payload);
      toast.success("Free params saved");
    } catch {
      toast.error("Failed to save free params");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  return (
    <Card className="max-w-full md:max-w-[600px]">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm">Telemt Free User Parameters</CardTitle>
        <Button onClick={onSave} disabled={saving}>
          Save
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          These parameters are used when creating a free Telemt user via the bot (channel subscription
          reward).
        </p>
        <div className="space-y-1.5">
          <Label>Expire Days *</Label>
          <Input
            type="number"
            placeholder="30"
            value={form.expire_days}
            onChange={(e) => patch({ expire_days: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Max TCP Connections</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.max_tcp_conns}
            onChange={(e) => patch({ max_tcp_conns: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Max Unique IPs</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.max_unique_ips}
            onChange={(e) => patch({ max_unique_ips: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Data Quota (bytes)</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.data_quota_bytes}
            onChange={(e) => patch({ data_quota_bytes: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Rate Limit Up (bps)</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.rate_limit_up_bps}
            onChange={(e) => patch({ rate_limit_up_bps: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Rate Limit Down (bps)</Label>
          <Input
            type="number"
            placeholder="Unlimited"
            value={form.rate_limit_down_bps}
            onChange={(e) => patch({ rate_limit_down_bps: e.target.value })}
          />
        </div>
      </CardContent>
    </Card>
  );
}

// ======================== Operations Tab ========================

function OperationsTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [healthReady, setHealthReady] = useState<TelmtHealthReady | null>(null);
  const [limits, setLimits] = useState<TelmtLimitsEffective | null>(null);
  const [whitelist, setWhitelist] = useState<TelmtSecurityWhitelist | null>(null);
  const [connSummary, setConnSummary] = useState<TelmtRuntimeConnectionsSummary | null>(null);
  const [recentEvents, setRecentEvents] = useState<TelmtRuntimeRecentEvents | null>(null);
  const [fingerprints, setFingerprints] = useState<TelmtTlsFingerprints | null>(null);
  const [usersWithQuota, setUsersWithQuota] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api.get<TelmtEnvelope<TelmtHealthReady>>("/telemt/health/ready"),
      api.get<TelmtEnvelope<TelmtLimitsEffective>>("/telemt/limits/effective"),
      api.get<TelmtEnvelope<TelmtSecurityWhitelist>>("/telemt/security/whitelist"),
      api.get<TelmtEnvelope<TelmtRuntimeConnectionsSummary>>("/telemt/runtime/connections/summary"),
      api.get<TelmtEnvelope<TelmtRuntimeRecentEvents>>("/telemt/runtime/events/recent"),
      api.get<TelmtEnvelope<TelmtTlsFingerprints>>("/telemt/runtime/tls-fingerprints"),
      api.get<TelmtEnvelope<TelmtUser[]>>("/telemt/users"),
    ]);

    const pick = <T,>(idx: number): T | null =>
      results[idx].status === "fulfilled" ? (results[idx] as PromiseFulfilledResult<T>).value : null;

    setHealthReady(pick<TelmtEnvelope<TelmtHealthReady>>(0)?.data ?? null);
    setLimits(pick<TelmtEnvelope<TelmtLimitsEffective>>(1)?.data ?? null);
    setWhitelist(pick<TelmtEnvelope<TelmtSecurityWhitelist>>(2)?.data ?? null);
    setConnSummary(pick<TelmtEnvelope<TelmtRuntimeConnectionsSummary>>(3)?.data ?? null);
    setRecentEvents(pick<TelmtEnvelope<TelmtRuntimeRecentEvents>>(4)?.data ?? null);
    setFingerprints(pick<TelmtEnvelope<TelmtTlsFingerprints>>(5)?.data ?? null);
    const users = pick<TelmtEnvelope<TelmtUser[]>>(6)?.data ?? [];
    setUsersWithQuota(users.filter((u) => u.data_quota_bytes != null && u.data_quota_bytes > 0).length);

    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed === results.length) {
      toast.error("Failed to load telemt operations data");
    } else if (failed > 0) {
      toast.warning(`Some telemt operations endpoints are unavailable (${failed}/${results.length})`);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const events = recentEvents?.data?.events ?? recentEvents?.events ?? [];
  const connTotals = connSummary?.data?.totals;
  const topByConns = connSummary?.data?.top?.by_connections ?? [];
  const topByTraffic = connSummary?.data?.top?.by_throughput ?? [];
  const fpByUser = fingerprints?.data?.by_user ?? [];
  const fpByIp = fingerprints?.data?.by_ip ?? [];
  const limitRows = limits
    ? [
        ...(limits.timeouts
          ? Object.entries(limits.timeouts).map(([k, v]) => ({ group: "timeouts", key: k, value: String(v) }))
          : []),
        ...(limits.upstream
          ? Object.entries(limits.upstream).map(([k, v]) => ({ group: "upstream", key: k, value: String(v) }))
          : []),
        ...(limits.user_ip_policy
          ? Object.entries(limits.user_ip_policy).map(([k, v]) => ({ group: "user_ip_policy", key: k, value: String(v) }))
          : []),
        ...(limits.user_tcp_policy
          ? Object.entries(limits.user_tcp_policy).map(([k, v]) => ({ group: "user_tcp_policy", key: k, value: String(v) }))
          : []),
        ...(limits.update_every_secs != null
          ? [{ group: "general", key: "update_every_secs", value: String(limits.update_every_secs) }]
          : []),
        ...(limits.me_reinit_every_secs != null
          ? [{ group: "general", key: "me_reinit_every_secs", value: String(limits.me_reinit_every_secs) }]
          : []),
        ...(limits.me_pool_force_close_secs != null
          ? [{ group: "general", key: "me_pool_force_close_secs", value: String(limits.me_pool_force_close_secs) }]
          : []),
      ]
    : [];

  type TopRow = { username: string; current_connections: number; total_octets: number };
  const topColumns: SimpleColumn<TopRow>[] = [
    { header: "User", cell: (r) => r.username },
    { header: "Conns", cell: (r) => r.current_connections },
    { header: "Traffic", cell: (r) => formatBytes(r.total_octets || 0) },
  ];

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button variant="outline" onClick={load} disabled={loading} className={cn(isMobile && "w-full")}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {loading && !healthReady ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-6 w-6" />
        </div>
      ) : (
        <div className="space-y-2 md:space-y-4">
          <div className="grid grid-cols-1 gap-2 md:gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Readiness</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                <Badge variant={healthReady?.ready ? "success" : "destructive"}>
                  {healthReady?.status || (healthReady?.ready ? "ready" : "not_ready")}
                </Badge>
                <p className="text-sm text-muted-foreground">
                  Upstreams: {healthReady?.healthy_upstreams ?? "—"}/{healthReady?.total_upstreams ?? "—"}
                </p>
                <p className="text-sm text-muted-foreground">
                  Admission: {healthReady?.admission_open ? "open" : "closed"}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Live Connections</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-semibold">{connTotals?.current_connections ?? 0}</div>
                <p className="text-sm text-muted-foreground">
                  ME {connTotals?.current_connections_me ?? 0} · Direct{" "}
                  {connTotals?.current_connections_direct ?? 0} · Active users{" "}
                  {connTotals?.active_users ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Quota Users</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-semibold">{usersWithQuota}</div>
                <p className="text-sm text-muted-foreground">users with data_quota_bytes &gt; 0</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Recent Events</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-semibold">{events.length}</div>
                <p className="text-sm text-muted-foreground">
                  capacity {recentEvents?.data?.capacity ?? "—"} · dropped{" "}
                  {recentEvents?.data?.dropped_total ?? 0}
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-2 md:gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Top by Connections</CardTitle>
              </CardHeader>
              <CardContent>
                <SimpleTable
                  columns={topColumns}
                  data={topByConns}
                  rowKey={(r) => r.username}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Top by Traffic</CardTitle>
              </CardHeader>
              <CardContent>
                <SimpleTable
                  columns={topColumns}
                  data={topByTraffic}
                  rowKey={(r) => r.username}
                />
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-2 md:gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Runtime Events</CardTitle>
              </CardHeader>
              <CardContent>
                <SimpleTable
                  maxHeightClass="max-h-96"
                  columns={[
                    { header: "#", cell: (r) => r.seq },
                    { header: "Time", cell: (r) => formatEpochShort(r.ts_epoch_secs) },
                    { header: "Event", cell: (r) => r.event_type },
                    { header: "Context", cell: (r) => r.context },
                  ]}
                  data={[...events].reverse()}
                  rowKey={(r) => String(r.seq)}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Security Whitelist</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="mb-2 flex flex-wrap gap-2">
                  <Badge variant={whitelist?.enabled ? "success" : "outline"}>
                    {whitelist?.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                  <Badge variant="outline">{whitelist?.entries_total ?? 0} entries</Badge>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(whitelist?.entries ?? []).map((e) => (
                    <Badge key={e} variant="outline">
                      {e}
                    </Badge>
                  ))}
                  {!whitelist?.entries?.length && (
                    <span className="text-muted-foreground">No whitelist entries</span>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 gap-2 md:gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">TLS Fingerprints by User</CardTitle>
              </CardHeader>
              <CardContent>
                <SimpleTable
                  maxHeightClass="max-h-96"
                  columns={[
                    { header: "User", cell: (r) => r.scope },
                    { header: "JA4", cell: (r) => r.ja4 },
                    { header: "OK", cell: (r) => r.auth_success },
                    { header: "Bad", cell: (r) => r.bad_or_probe },
                  ]}
                  data={fpByUser}
                  rowKey={(r, i) => `${r.scope}-${r.ja4}-${i}`}
                />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">TLS Fingerprints by IP</CardTitle>
              </CardHeader>
              <CardContent>
                <SimpleTable
                  maxHeightClass="max-h-96"
                  columns={[
                    { header: "IP", cell: (r) => r.scope },
                    { header: "JA4", cell: (r) => r.ja4 },
                    { header: "OK", cell: (r) => r.auth_success },
                    { header: "Bad", cell: (r) => r.bad_or_probe },
                  ]}
                  data={fpByIp}
                  rowKey={(r, i) => `${r.scope}-${r.ja3}-${i}`}
                />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Effective Limits</CardTitle>
            </CardHeader>
            <CardContent>
              <SimpleTable
                maxHeightClass="max-h-96"
                columns={[
                  { header: "Group", cell: (r) => r.group },
                  { header: "Key", cell: (r) => r.key },
                  { header: "Value", cell: (r) => r.value },
                ]}
                data={limitRows}
                rowKey={(r) => `${r.group}.${r.key}`}
              />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// ======================== Config Tab ========================

const EDITABLE_CONFIG_SET = new Set<string>(TELMT_EDITABLE_CONFIG_SECTIONS);

function filterEditableConfig(data: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    if (EDITABLE_CONFIG_SET.has(k)) out[k] = v;
  }
  return out;
}

function validateConfigPatch(parsed: Record<string, unknown>): string | null {
  const unknown = Object.keys(parsed).filter((k) => !EDITABLE_CONFIG_SET.has(k));
  if (unknown.length) {
    return `Not editable via Telemt API: ${unknown.join(", ")}. Allowed: ${TELMT_EDITABLE_CONFIG_SECTIONS.join(", ")}`;
  }
  return null;
}

function ConfigTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState<string>("");
  const [editorText, setEditorText] = useState("{}");
  const [lastPatch, setLastPatch] = useState<TelmtPatchConfigResponse | null>(null);

  const load = useCallback(async (clearPatch = true) => {
    setLoading(true);
    if (clearPatch) setLastPatch(null);
    try {
      const r = await api.get<TelmtEnvelope<TelmtConfigData>>("/telemt/config");
      const data = (r.data ?? {}) as Record<string, unknown>;
      const editable = filterEditableConfig(data);
      setEditorText(JSON.stringify(editable, null, 2));
      setRevision(r.revision || "");
    } catch (e) {
      toast.error((e as Error).message || "Failed to load telemt config");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  type ConfigValidation = { ok: true; sections: string[] } | { ok: false; error: string };

  const validation = useMemo<ConfigValidation>(() => {
    const trimmed = editorText.trim();
    if (!trimmed) return { ok: false, error: "Config is empty" };
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch (e) {
      const msg = (e as Error)?.message;
      return { ok: false, error: msg ? `Invalid JSON: ${msg}` : "Invalid JSON" };
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, error: "Config must be a JSON object" };
    }
    const obj = parsed as Record<string, unknown>;
    const forbidden = validateConfigPatch(obj);
    if (forbidden) return { ok: false, error: forbidden };
    return { ok: true, sections: Object.keys(obj) };
  }, [editorText]);

  const applyPatch = async (payload: Record<string, unknown>) => {
    setSaving(true);
    try {
      const r = await api.patch<TelmtEnvelope<TelmtPatchConfigResponse>>("/telemt/config", payload);
      const result = r.data;
      await load(false);
      if (result) {
        setLastPatch(result);
        if (result.revision) setRevision(result.revision);
      }
      toast.success(
        result?.restart_required
          ? `Config saved (restart required). Changed: ${(result.changed || []).join(", ") || "—"}`
          : `Config saved. Changed: ${(result?.changed || []).join(", ") || "—"}`,
      );
    } catch (e) {
      toast.error((e as Error).message || "Failed to patch telemt config");
    } finally {
      setSaving(false);
    }
  };

  const onSave = () => {
    if (!validation.ok) {
      toast.error(validation.error);
      return;
    }
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(editorText);
    } catch {
      toast.error("Invalid JSON");
      return;
    }
    const payload: Record<string, unknown> = { ...parsed };
    if (revision) payload.revision = revision;
    const sections = validation.sections;
    if (
      window.confirm(
        `Apply live config patch? Sections: ${sections.join(", ") || "—"}. Some changes may require a Telemt restart.`,
      )
    ) {
      applyPatch(payload);
    }
  };

  return (
    <div className="space-y-4">
      <Alert>
        <AlertTitle>Managed Telemt config sections</AlertTitle>
        <AlertDescription>
          Telemt <code>GET/PATCH /v1/config</code> exposes only:{" "}
          <code>{TELMT_EDITABLE_CONFIG_SECTIONS.join(", ")}</code>. Empty sections (e.g. no{" "}
          <code>[timeouts]</code> in toml) are omitted until present. Not available via API:{" "}
          <code>network</code>, <code>server</code> (incl. listeners/api), <code>access</code> (users —
          use the Users tab), <code>logging</code>, and other top-level keys. Edit those on the host in{" "}
          <code>config.toml</code>. Save uses <code>If-Match</code> revision.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader className="flex-col items-start gap-2 space-y-0 md:flex-row md:items-center md:justify-between">
          <CardTitle className="text-sm">Telemt Config</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            {revision && (
              <span className="text-xs text-muted-foreground">rev: {revision.slice(0, 12)}…</span>
            )}
            <Button variant="outline" size="sm" onClick={() => load()} disabled={loading}>
              <RefreshCw className="h-4 w-4" />
              Reload
            </Button>
            <Button size="sm" onClick={onSave} disabled={saving || !validation.ok}>
              Save Patch
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <div className="flex justify-center py-8">
              <Spinner className="h-6 w-6" />
            </div>
          ) : (
            <>
              {lastPatch?.restart_required && (
                <Alert variant="warning">
                  <AlertTitle>Telemt restart required</AlertTitle>
                  <AlertDescription>
                    Config was written live. Changed: {(lastPatch.changed || []).join(", ") || "—"}.
                    Restart the Telemt process so all fields take effect.
                  </AlertDescription>
                </Alert>
              )}
              <Textarea
                value={editorText}
                onChange={(e) => setEditorText(e.target.value)}
                rows={isMobile ? 14 : 22}
                spellCheck={false}
                className={cn("font-mono text-xs md:text-[13px]", !validation.ok && "border-destructive")}
              />
              <Alert variant={validation.ok ? "default" : "destructive"}>
                <AlertDescription>
                  {validation.ok
                    ? `Valid JSON (${validation.sections.length ? validation.sections.join(", ") : "empty object"})`
                    : validation.error}
                </AlertDescription>
              </Alert>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ======================== Main Page ========================

export default function TelmtPage() {
  return (
    <div>
      <h1 className="mb-3 text-lg font-semibold text-foreground md:mb-5 md:text-xl">Telemt</h1>
      <Tabs defaultValue="server">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="server">
            <Server className="h-4 w-4" /> Server
          </TabsTrigger>
          <TabsTrigger value="users">
            <User className="h-4 w-4" /> Users
          </TabsTrigger>
          <TabsTrigger value="free-params">
            <Settings className="h-4 w-4" /> Free Params
          </TabsTrigger>
          <TabsTrigger value="config">
            <Settings className="h-4 w-4" /> Config
          </TabsTrigger>
          <TabsTrigger value="operations">
            <Server className="h-4 w-4" /> Operations
          </TabsTrigger>
        </TabsList>
        <TabsContent value="server">
          <ServerTab />
        </TabsContent>
        <TabsContent value="users">
          <UsersTab />
        </TabsContent>
        <TabsContent value="free-params">
          <FreeParamsTab />
        </TabsContent>
        <TabsContent value="config">
          <ConfigTab />
        </TabsContent>
        <TabsContent value="operations">
          <OperationsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
