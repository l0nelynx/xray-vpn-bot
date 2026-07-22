import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type { ColumnDef } from "@tanstack/react-table";
import { Gift, Plus, RefreshCw, Search, Settings, Trash2, Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Label } from "@xray/ui/components/label";
import { Badge } from "@xray/ui/components/badge";
import { Spinner } from "@xray/ui/components/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@xray/ui/components/tabs";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@xray/ui/components/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
import { api } from "../api/client";
import useIsMobile from "../hooks/useIsMobile";
import useDebounce from "../hooks/useDebounce";
import MobileSortControl, { type SortOrder } from "../components/MobileSortControl";
import DataTable from "../components/DataTable";
import TablePagination from "../components/TablePagination";
import ConfirmButton from "../components/ConfirmButton";
import { makeSortToggle } from "../utils/tableChange";
import { formatPoints, POINTS_ICON } from "../points";

type PromoType = "referral" | "promotional";

const PROMO_SORT_OPTIONS = [
  { value: "promo_code", label: "Code" },
  { value: "promo_type", label: "Type" },
  { value: "owner_username", label: "Owner" },
  { value: "credit_grant", label: "Points (🪙)" },
  { value: "usage_count", label: "Usage" },
  { value: "days_purchased", label: "Invitee days bought" },
  { value: "points_rewarded", label: "Owner reward (🪙)" },
];

interface PromoItem {
  promo_code: string;
  promo_type: PromoType;
  owner_username: string | null;
  owner_tg_id: number;
  usage_count: number;
  days_purchased: number;
  points_rewarded: number;
  credit_grant: number | null;
}

interface PromosListResponse {
  items: PromoItem[];
  total: number;
  page: number;
  per_page: number;
}

interface PromoSettings {
  default_credit_grant: number;
  points_reward_per_30: number;
  reward_cap_points: number;
}

function PromosTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<PromoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sort, setSort] = useState("id");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [createOpen, setCreateOpen] = useState(false);
  const [code, setCode] = useState("");
  const [promoType, setPromoType] = useState<PromoType>("promotional");
  const [creditGrant, setCreditGrant] = useState("");
  const [ownerTgId, setOwnerTgId] = useState("");
  const debouncedSearch = useDebounce(search, 400);
  const perPage = 20;

  const load = useCallback(() => {
    setLoading(true);
    const url =
      `/promos?page=${page}&per_page=20&sort=${sort}&order=${order}` +
      `&type=${typeFilter}&search=${encodeURIComponent(debouncedSearch)}`;
    api
      .get<PromosListResponse>(url)
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e: Error) => toast.error(e.message || "Failed to load promos"))
      .finally(() => setLoading(false));
  }, [page, sort, order, typeFilter, debouncedSearch]);

  useEffect(() => {
    load();
  }, [load]);

  const resetForm = () => {
    setCode("");
    setPromoType("promotional");
    setCreditGrant("");
    setOwnerTgId("");
  };

  const handleCreate = async () => {
    const trimmed = code.trim();
    if (!trimmed) {
      toast.error("Code is required");
      return;
    }
    if (trimmed.length > 20) {
      toast.error("Max 20 chars");
      return;
    }
    if (!/^[A-Za-z0-9_-]+$/.test(trimmed)) {
      toast.error("Letters, digits, _ and - only");
      return;
    }
    try {
      await api.post("/promos", {
        promo_code: trimmed.toUpperCase(),
        credit_grant: creditGrant === "" ? null : Number(creditGrant),
        owner_tg_id: ownerTgId === "" ? null : Number(ownerTgId),
        promo_type: promoType,
      });
      toast.success("Promo created");
      setCreateOpen(false);
      resetForm();
      load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to create promo");
    }
  };

  const handleDelete = async (code: string) => {
    try {
      await api.delete(`/promos/${encodeURIComponent(code)}`);
      toast.success(`Promo ${code} deleted`);
      load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to delete");
    }
  };

  const onSortChange = makeSortToggle({ sort, order, setSort, setOrder, setPage });

  const columns: ColumnDef<PromoItem, unknown>[] = [
    {
      id: "promo_code",
      header: "Code",
      meta: { sortKey: "promo_code" },
      cell: ({ row }) => <span className="font-semibold">{row.original.promo_code}</span>,
    },
    {
      id: "promo_type",
      header: "Type",
      meta: { sortKey: "promo_type" },
      cell: ({ row }) =>
        row.original.promo_type === "referral" ? (
          <Badge variant="secondary">Referral</Badge>
        ) : (
          <Badge>Promotional</Badge>
        ),
    },
    {
      id: "owner_username",
      header: "Owner",
      meta: { sortKey: "owner_username" },
      cell: ({ row }) =>
        row.original.owner_username ? (
          <span>
            @{row.original.owner_username}{" "}
            <span className="text-xs text-muted-foreground">({row.original.owner_tg_id})</span>
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      id: "credit_grant",
      header: "Points (🪙)",
      meta: { sortKey: "credit_grant" },
      cell: ({ row }) =>
        row.original.credit_grant == null ? (
          <Badge variant="outline">default</Badge>
        ) : (
          <Badge variant="success">{formatPoints(row.original.credit_grant)}</Badge>
        ),
    },
    { id: "usage_count", header: "Usage", meta: { sortKey: "usage_count" }, cell: ({ row }) => row.original.usage_count },
    {
      id: "days_purchased",
      header: "Invitee days bought",
      meta: { sortKey: "days_purchased" },
      cell: ({ row }) => row.original.days_purchased,
    },
    {
      id: "points_rewarded",
      header: "Owner reward (🪙)",
      meta: { sortKey: "points_rewarded" },
      cell: ({ row }) => <Badge variant="success">{formatPoints(row.original.points_rewarded)}</Badge>,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <ConfirmButton
          title={`Delete promo ${row.original.promo_code}?`}
          destructive
          confirmText="Delete"
          onConfirm={() => handleDelete(row.original.promo_code)}
        >
          <Button variant="ghost" size="icon" className="text-destructive">
            <Trash2 className="h-4 w-4" />
          </Button>
        </ConfirmButton>
      ),
    },
  ];

  const renderMobileCard = (promo: PromoItem) => (
    <Card key={promo.promo_code} className="mb-2">
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="mb-1 break-all font-semibold text-foreground/85">{promo.promo_code}</div>
            <div className="mb-1.5">
              {promo.promo_type === "referral" ? (
                <Badge variant="secondary">Referral</Badge>
              ) : (
                <Badge>Promotional</Badge>
              )}
            </div>
            <div className="mb-1 text-xs text-muted-foreground">
              {promo.owner_username ? `@${promo.owner_username} (${promo.owner_tg_id})` : "No owner"}
            </div>
            <div className="text-xs text-muted-foreground">
              {promo.credit_grant == null
                ? "Points: default"
                : `Points: ${formatPoints(promo.credit_grant)}`}
              {" · "}Usage: {promo.usage_count}
            </div>
            <div className="mt-0.5 text-[11px] text-muted-foreground/70">
              Invitee days: {promo.days_purchased} · Owner reward:{" "}
              {formatPoints(promo.points_rewarded)}
            </div>
          </div>
          <ConfirmButton
            title={`Delete promo ${promo.promo_code}?`}
            destructive
            confirmText="Delete"
            onConfirm={() => handleDelete(promo.promo_code)}
          >
            <Button variant="destructive" size="icon">
              <Trash2 className="h-4 w-4" />
            </Button>
          </ConfirmButton>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div>
      <div className="mb-4 flex flex-wrap justify-between gap-2">
        <Button onClick={() => setCreateOpen(true)} className="w-full md:w-auto">
          <Plus className="h-4 w-4" />
          Create Promo
        </Button>
        <Button variant="outline" onClick={load} disabled={loading} className="w-full md:w-auto">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative flex-1 md:max-w-[280px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by code or owner"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-8"
          />
        </div>
        <Select
          value={typeFilter}
          onValueChange={(v: string) => {
            setTypeFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="promotional">Promotional</SelectItem>
            <SelectItem value="referral">Referral</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isMobile ? (
        <>
          <MobileSortControl
            options={PROMO_SORT_OPTIONS}
            sort={sort}
            order={order}
            onChange={(s, o) => {
              setSort(s);
              setOrder(o);
              setPage(1);
            }}
          />
          {loading ? (
            <div className="py-10 text-center text-muted-foreground">Loading...</div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">No promocodes</div>
          ) : (
            items.map(renderMobileCard)
          )}
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      ) : (
        <>
          <DataTable
            columns={columns}
            data={items}
            loading={loading}
            rowKey={(r) => r.promo_code}
            sort={sort}
            order={order}
            onSortChange={onSortChange}
            empty="No promocodes"
            minWidth={700}
          />
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      )}

      <Dialog
        open={createOpen}
        onOpenChange={(o: boolean) => {
          setCreateOpen(o);
          if (!o) resetForm();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Promo Code</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Code *</Label>
              <Input placeholder="SUMMER25" value={code} onChange={(e) => setCode(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label>Type</Label>
              <Select value={promoType} onValueChange={(v: string) => setPromoType(v as PromoType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="promotional">Promotional</SelectItem>
                  <SelectItem value="referral">Referral</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>{`Credit grant (${POINTS_ICON} points)`}</Label>
              <Input
                type="number"
                min={0}
                max={3650}
                placeholder="default"
                value={creditGrant}
                onChange={(e) => setCreditGrant(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Owner tg_id</Label>
              <Input
                type="number"
                placeholder="empty for stand-alone"
                value={ownerTgId}
                onChange={(e) => setOwnerTgId(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate}>Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SettingsTab() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [defaultCreditGrant, setDefaultCreditGrant] = useState("");
  const [pointsRewardPer30, setPointsRewardPer30] = useState("");
  const [rewardCapPoints, setRewardCapPoints] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get<PromoSettings>("/promos/settings");
      setDefaultCreditGrant(String(r.default_credit_grant));
      setPointsRewardPer30(String(r.points_reward_per_30));
      setRewardCapPoints(String(r.reward_cap_points));
    } catch (e) {
      toast.error((e as Error).message || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onSave = async () => {
    if (defaultCreditGrant === "" || pointsRewardPer30 === "" || rewardCapPoints === "") {
      toast.error("All fields are required");
      return;
    }
    try {
      setSaving(true);
      await api.put("/promos/settings", {
        default_credit_grant: Number(defaultCreditGrant),
        points_reward_per_30: Number(pointsRewardPer30),
        reward_cap_points: Number(rewardCapPoints),
      });
      toast.success("Settings saved");
    } catch (e) {
      toast.error((e as Error).message || "Failed to save");
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
        <CardTitle className="text-sm">Promo Settings</CardTitle>
        <Button onClick={onSave} disabled={saving}>
          Save
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Все бонусы — в баллах {POINTS_ICON}. <strong>Default credit grant</strong> — сколько
          получает пользователь при активации кода. <strong>Owner reward per 30 days</strong> —
          сколько баллов начисляется владельцу рефкода за каждые 30 дней покупок приглашённых.{" "}
          <strong>Reward cap</strong> — максимум баллов владельцу с одного кода за всё время.
        </p>
        <div className="space-y-1.5">
          <Label>{`Default credit grant (${POINTS_ICON}) *`}</Label>
          <Input
            type="number"
            min={0}
            max={3650}
            value={defaultCreditGrant}
            onChange={(e) => setDefaultCreditGrant(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>{`Owner reward per 30 invitee-days (${POINTS_ICON}) *`}</Label>
          <Input
            type="number"
            min={0}
            max={3650}
            value={pointsRewardPer30}
            onChange={(e) => setPointsRewardPer30(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>{`Owner reward cap (${POINTS_ICON}) *`}</Label>
          <Input
            type="number"
            min={0}
            max={365000}
            value={rewardCapPoints}
            onChange={(e) => setRewardCapPoints(e.target.value)}
          />
        </div>
      </CardContent>
    </Card>
  );
}

type ReferralMetric = "total" | "paying";

interface ReferralStatItem {
  owner_tg_id: number;
  owner_username: string | null;
  promo_code: string;
  referral_count: number;
  paying_referral_count: number;
  days_purchased: number;
  points_rewarded: number;
}

const REFERRAL_SORT_OPTIONS = [
  { value: "referral_count", label: "Total referrals" },
  { value: "paying_referral_count", label: "Paying referrals" },
  { value: "owner_username", label: "Owner" },
  { value: "days_purchased", label: "Invitee days bought" },
  { value: "points_rewarded", label: "Owner reward" },
];

function ReferralStatsTab() {
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<ReferralStatItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [metric, setMetric] = useState<ReferralMetric>("total");
  const [sort, setSort] = useState("referral_count");
  const [order, setOrder] = useState<SortOrder>("desc");
  const debouncedSearch = useDebounce(search, 300);
  const perPage = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        per_page: "20",
        sort,
        order,
        metric,
        search: debouncedSearch,
      });
      const data = await api.get<{ items: ReferralStatItem[]; total: number }>(
        `/promos/referral-stats?${params}`,
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      toast.error((e as Error).message || "Failed to load referral stats");
    } finally {
      setLoading(false);
    }
  }, [page, sort, order, metric, debouncedSearch]);

  useEffect(() => {
    load();
  }, [load]);

  const onMetricChange = (m: ReferralMetric) => {
    setMetric(m);
    setSort(m === "paying" ? "paying_referral_count" : "referral_count");
    setPage(1);
  };

  const onSortChange = makeSortToggle({ sort, order, setSort, setOrder, setPage });

  const columns: ColumnDef<ReferralStatItem, unknown>[] = [
    {
      id: "rank",
      header: "#",
      cell: ({ row }) => (page - 1) * perPage + row.index + 1,
    },
    {
      id: "owner",
      header: "Owner",
      cell: ({ row }) => (
        <span>
          {row.original.owner_username ? `@${row.original.owner_username}` : "—"}{" "}
          <span className="text-muted-foreground">({row.original.owner_tg_id})</span>
        </span>
      ),
    },
    { id: "promo_code", header: "Code", cell: ({ row }) => row.original.promo_code },
    {
      id: "primary_metric",
      header: metric === "paying" ? "Paying referrals" : "Total referrals",
      meta: { sortKey: metric === "paying" ? "paying_referral_count" : "referral_count" },
      cell: ({ row }) =>
        metric === "paying" ? row.original.paying_referral_count : row.original.referral_count,
    },
    {
      id: "secondary_metric",
      header: metric === "paying" ? "Total" : "Paying",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {metric === "paying" ? row.original.referral_count : row.original.paying_referral_count}
        </span>
      ),
    },
    {
      id: "days_purchased",
      header: "Invitee days",
      meta: { sortKey: "days_purchased" },
      cell: ({ row }) => row.original.days_purchased,
    },
    {
      id: "points_rewarded",
      header: `Owner reward (${POINTS_ICON})`,
      meta: { sortKey: "points_rewarded" },
      cell: ({ row }) => formatPoints(row.original.points_rewarded),
    },
  ];

  const renderMobileCard = (item: ReferralStatItem, index: number) => {
    const rank = (page - 1) * perPage + index + 1;
    const primary = metric === "paying" ? item.paying_referral_count : item.referral_count;
    const secondary = metric === "paying" ? item.referral_count : item.paying_referral_count;
    return (
      <Card key={item.owner_tg_id} className="mb-2">
        <CardContent className="flex items-start gap-2.5 p-3">
          <div className="flex h-7 min-w-7 items-center justify-center rounded-lg bg-white/5 text-xs font-semibold text-muted-foreground">
            {rank}
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-0.5 break-words font-semibold text-foreground/85">
              {item.owner_username ? `@${item.owner_username}` : "—"}
            </div>
            <div className="mb-1.5 text-xs text-muted-foreground">
              {item.owner_tg_id} · <code>{item.promo_code}</code>
            </div>
            <div className="text-sm text-foreground/75">
              {metric === "paying" ? "Paying" : "Total"}: <strong>{primary}</strong>
              <span className="ml-2 text-muted-foreground">
                {metric === "paying" ? "Total" : "Paying"}: {secondary}
              </span>
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground/70">
              Invitee days: {item.days_purchased} · Owner reward:{" "}
              {formatPoints(item.points_rewarded)}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        <Select value={metric} onValueChange={(v: string) => onMetricChange(v as ReferralMetric)}>
          <SelectTrigger className="w-full md:w-[220px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="total">Top by total referrals</SelectItem>
            <SelectItem value="paying">Top by paying referrals</SelectItem>
          </SelectContent>
        </Select>
        <div className="relative flex-1 md:max-w-[280px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search code, username, tg_id"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-8"
          />
        </div>
        <Button variant="outline" onClick={load} disabled={loading} className="w-full md:w-auto">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {isMobile ? (
        <>
          <MobileSortControl
            options={REFERRAL_SORT_OPTIONS}
            sort={sort}
            order={order}
            onChange={(s, o) => {
              setSort(s);
              setOrder(o);
              setPage(1);
            }}
          />
          {loading ? (
            <div className="py-10 text-center text-muted-foreground">Loading...</div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">No referral stats</div>
          ) : (
            items.map(renderMobileCard)
          )}
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      ) : (
        <>
          <DataTable
            columns={columns}
            data={items}
            loading={loading}
            rowKey={(r) => r.owner_tg_id}
            sort={sort}
            order={order}
            onSortChange={onSortChange}
            empty="No referral stats"
          />
          <TablePagination page={page} perPage={perPage} total={total} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}

export default function PromocodesPage() {
  return (
    <div>
      <h1 className="mb-3 text-lg font-semibold text-foreground md:mb-5 md:text-xl">Promocodes</h1>
      <Tabs defaultValue="list">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="list">
            <Gift className="h-4 w-4" /> Codes
          </TabsTrigger>
          <TabsTrigger value="settings">
            <Settings className="h-4 w-4" /> Settings
          </TabsTrigger>
          <TabsTrigger value="referral-stats">
            <Trophy className="h-4 w-4" /> Referral stats
          </TabsTrigger>
        </TabsList>
        <TabsContent value="list">
          <PromosTab />
        </TabsContent>
        <TabsContent value="settings">
          <SettingsTab />
        </TabsContent>
        <TabsContent value="referral-stats">
          <ReferralStatsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
