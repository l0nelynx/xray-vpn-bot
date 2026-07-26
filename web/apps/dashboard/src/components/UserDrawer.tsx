import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, ExternalLink, Gift, IdCard, Link2, Pencil, Send, Star, Unlink, Wallet } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@xray/ui/components/sheet";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { Badge } from "@xray/ui/components/badge";
import { Separator } from "@xray/ui/components/separator";
import { Spinner } from "@xray/ui/components/spinner";
import ConfirmButton from "./ConfirmButton";
import { api } from "../api/client";
import type { ManagedSubscription, TransactionItem, UserDetail } from "../api/types";
import { formatPoints, POINTS_ICON } from "../points";
import useIsMobile from "../hooks/useIsMobile";

interface Props {
  /** Local DB users.id. When non-null the drawer fetches & shows this user. */
  userId: number | null;
  open: boolean;
  onClose: () => void;
  /** Called after edits so the opener can refresh its list. */
  onChanged?: () => void;
}

function copyText(text: string) {
  navigator.clipboard?.writeText(text).then(
    () => toast.success("Copied"),
    () => toast.error("Copy failed"),
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 border-b border-border/60 py-1.5 text-sm last:border-0">
      <div className="w-32 flex-shrink-0 text-muted-foreground">{label}</div>
      <div className="min-w-0 flex-1 break-words text-foreground">{children}</div>
    </div>
  );
}

function LabeledInput({
  label,
  ...props
}: { label: string } & React.ComponentProps<typeof Input>) {
  return (
    <div className="flex items-center overflow-hidden rounded-md border border-input">
      <span className="flex-shrink-0 border-r border-input bg-muted px-3 py-2 text-xs text-muted-foreground">
        {label}
      </span>
      <Input className="h-9 rounded-none border-0 focus-visible:ring-0" {...props} />
    </div>
  );
}

export default function UserDrawer({ userId, open, onClose, onChanged }: Props) {
  const isMobile = useIsMobile();

  const [user, setUser] = useState<UserDetail | null>(null);
  const [tx, setTx] = useState<TransactionItem[]>([]);
  const [subscriptions, setSubscriptions] = useState<ManagedSubscription[]>([]);
  const [loading, setLoading] = useState(false);

  const [editTgId, setEditTgId] = useState("");
  const [editUsername, setEditUsername] = useState("");
  const [editUuid, setEditUuid] = useState("");
  const [idSaving, setIdSaving] = useState(false);

  const [emailInput, setEmailInput] = useState("");
  const [emailSaving, setEmailSaving] = useState(false);

  const [msgText, setMsgText] = useState("");
  const [msgSending, setMsgSending] = useState(false);

  const [creditsDelta, setCreditsDelta] = useState<string>("");
  const [creditsSaving, setCreditsSaving] = useState(false);
  const [addRwId, setAddRwId] = useState("");
  const [addLabel, setAddLabel] = useState("");
  const [addPrimary, setAddPrimary] = useState(false);
  const [subscriptionSaving, setSubscriptionSaving] = useState(false);

  const load = async (id: number) => {
    setLoading(true);
    try {
      const [u, t, s] = await Promise.all([
        api.get<UserDetail>(`/users/${id}`),
        api.get<TransactionItem[]>(`/users/${id}/transactions`),
        api.get<{ subscriptions: ManagedSubscription[] }>(`/users/${id}/subscriptions`),
      ]);
      setUser(u);
      setTx(t);
      setSubscriptions(s.subscriptions);
      setEditTgId(u.tg_id != null ? String(u.tg_id) : "");
      setEditUsername(u.username || "");
      setEditUuid(u.vless_uuid || "");
      setEmailInput(u.email || "");
      setMsgText("");
      setCreditsDelta("");
      setAddRwId("");
      setAddLabel("");
      setAddPrimary(false);
    } catch {
      toast.error("Failed to load user");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && userId != null) load(userId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, userId]);

  const handleSaveIdentifiers = async () => {
    if (!user) return;
    const newTgId = editTgId.trim();
    if (newTgId && !/^-?\d+$/.test(newTgId)) {
      toast.error("TG ID must be a number");
      return;
    }
    setIdSaving(true);
    try {
      await api.patch(`/users/${user.id}/identifiers`, {
        tg_id: newTgId ? Number(newTgId) : null,
        username: editUsername,
        vless_uuid: editUuid,
      });
      toast.success("Saved");
      await load(user.id);
      onChanged?.();
    } catch (e) {
      const status = (e as { status?: number })?.status;
      toast.error(status === 409 ? "This TG ID is already in use" : "Failed to save");
    } finally {
      setIdSaving(false);
    }
  };

  const subscriptionError = (error: unknown, fallback: string) => {
    const detail = (error as { detail?: string | { code?: string } })?.detail;
    const code = typeof detail === "object" ? detail?.code : detail;
    const messages: Record<string, string> = {
      subscription_already_linked: "This subscription belongs to another account",
      subscription_not_found: "Subscription was not found",
      primary_change_required: "Choose another primary subscription first",
      remnawave_unavailable: "Remnawave is temporarily unavailable",
    };
    return (code && messages[code]) || fallback;
  };

  const handleAttachSubscription = async () => {
    if (!user || !/^\d+$/.test(addRwId.trim())) {
      toast.error("rw_id must be a positive number");
      return;
    }
    setSubscriptionSaving(true);
    try {
      await api.post(`/users/${user.id}/subscriptions`, {
        rw_id: Number(addRwId),
        label: addLabel.trim() || null,
        make_primary: addPrimary,
      });
      toast.success("Subscription linked");
      await load(user.id);
      onChanged?.();
    } catch (error) {
      toast.error(subscriptionError(error, "Failed to link subscription"));
    } finally {
      setSubscriptionSaving(false);
    }
  };

  const handleRenameSubscription = async (subscription: ManagedSubscription) => {
    if (!user) return;
    const label = window.prompt("Subscription label", subscription.label || "");
    if (label === null) return;
    try {
      await api.patch(`/users/${user.id}/subscriptions/${subscription.id}`, {
        label: label.trim() || null,
      });
      await load(user.id);
      toast.success("Label saved");
    } catch (error) {
      toast.error(subscriptionError(error, "Failed to rename subscription"));
    }
  };

  const handlePrimarySubscription = async (subscriptionId: number) => {
    if (!user) return;
    try {
      await api.post(`/users/${user.id}/subscriptions/${subscriptionId}/primary`);
      await load(user.id);
      onChanged?.();
      toast.success("Primary subscription changed");
    } catch (error) {
      toast.error(subscriptionError(error, "Failed to change primary subscription"));
    }
  };

  const handleDetachSubscription = async (subscriptionId: number) => {
    if (!user) return;
    try {
      await api.delete(`/users/${user.id}/subscriptions/${subscriptionId}`);
      await load(user.id);
      onChanged?.();
      toast.success("Subscription unlinked; Remnawave user was not deleted");
    } catch (error) {
      toast.error(subscriptionError(error, "Failed to unlink subscription"));
    }
  };

  const handleSaveEmail = async () => {
    if (!user || !emailInput.trim()) return;
    setEmailSaving(true);
    try {
      const res = await api.patch<{ ok: boolean; rw_uuid: string | null; rw_id: number | null }>(
        `/users/${user.id}/email`,
        { email: emailInput.trim() },
      );
      const parts = ["Email saved"];
      if (res.rw_uuid) parts.push(`UUID: ${res.rw_uuid}`);
      if (res.rw_id != null) parts.push(`rw_id: ${res.rw_id}`);
      toast.success(parts.join(", "));
      await load(user.id);
      onChanged?.();
    } catch {
      toast.error("Failed to save email");
    } finally {
      setEmailSaving(false);
    }
  };

  const handleAdjustCredits = async () => {
    const delta = Number(creditsDelta);
    if (!user || !creditsDelta || Number.isNaN(delta) || delta === 0) return;
    setCreditsSaving(true);
    try {
      const res = await api.post<{ ok: boolean; balance: number }>(`/users/${user.id}/credits`, {
        amount: delta,
      });
      toast.success(`Balance updated: ${formatPoints(res.balance)}`);
      setCreditsDelta("");
      await load(user.id);
      onChanged?.();
    } catch (e) {
      const status = (e as { status?: number })?.status;
      toast.error(status === 400 ? "Not enough points to deduct" : "Failed to update balance");
    } finally {
      setCreditsSaving(false);
    }
  };

  const handleSendMessage = async () => {
    if (!user || !msgText.trim()) return;
    if (user.tg_id == null) {
      toast.error("User has no Telegram ID");
      return;
    }
    setMsgSending(true);
    try {
      await api.post(`/users/${user.id}/send-message`, { text: msgText });
      toast.success("Message sent");
      setMsgText("");
    } catch {
      toast.error("Failed to send");
    } finally {
      setMsgSending(false);
    }
  };

  const displayName = user
    ? user.username || user.email || (user.tg_id != null ? String(user.tg_id) : `#${user.id}`)
    : "User";

  return (
    <Sheet open={open} onOpenChange={(o: boolean) => !o && onClose()}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 overflow-y-auto sm:max-w-[520px]"
        style={isMobile ? { maxWidth: "100%" } : undefined}
      >
        <SheetHeader>
          <SheetTitle>{user ? `User: ${displayName}` : "User"}</SheetTitle>
        </SheetHeader>

        {loading ? (
          <div className="flex flex-1 items-center justify-center py-20">
            <Spinner className="h-6 w-6" />
          </div>
        ) : (
          user && (
            <div className="mt-4 space-y-4">
              <div className="rounded-lg border border-border p-3">
                <Row label="ID">{user.id}</Row>
                <Row label="TG ID">{user.tg_id ?? "—"}</Row>
                <Row label="Username">{user.username || "—"}</Row>
                <Row label="Email">{user.email || "—"}</Row>
                <Row label="vless_uuid">
                  {user.vless_uuid ? (
                    <span className="flex items-center gap-2">
                      <span className="break-all font-mono text-xs">{user.vless_uuid}</span>
                      <button
                        type="button"
                        onClick={() => copyText(user.vless_uuid!)}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ) : (
                    "—"
                  )}
                </Row>
                <Row label="rw_id">{user.rw_id ?? "—"}</Row>
                <Row label="Provider">{user.api_provider}</Row>
                <Row label="Promo code">
                  {user.promo_code ? (
                    <Badge variant="secondary" className="gap-1">
                      <Gift className="h-3 w-3" />
                      {user.promo_code}
                    </Badge>
                  ) : (
                    "—"
                  )}
                </Row>
                <Row label="Bonus points">
                  <span className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary" className="gap-1">
                      <Wallet className="h-3 w-3" />
                      {formatPoints(user.bonus_credits ?? 0)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      1 point = 1 {POINTS_ICON} of tariff price
                    </span>
                  </span>
                </Row>
                <Row label="Open tickets">{user.tickets_count}</Row>
                <Row label="Banned">{user.is_banned ? "Yes" : "No"}</Row>
                <Row label="VIP">{user.vip ? "Yes" : "No"}</Row>
                <Row label="Language">{user.language || "—"}</Row>
                <Row label="Total Spent">{user.total_spent}</Row>
                <Row label="Transactions">{user.transactions_count}</Row>
                <Row label="Subscriptions">{user.subscriptions_count}</Row>
              </div>

              <Separator />

              <div>
                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <Link2 className="h-4 w-4" />
                  Subscriptions
                </div>
                <div className="space-y-2">
                  {subscriptions.length === 0 ? (
                    <div className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
                      No linked subscriptions
                    </div>
                  ) : (
                    subscriptions.map((subscription) => (
                      <div key={subscription.id} className="rounded-lg border border-border p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-1.5">
                              <span className="font-medium">{subscription.label || `Subscription ${subscription.rw_id}`}</span>
                              {subscription.is_primary && <Badge variant="secondary">Primary</Badge>}
                              <Badge variant={subscription.status === "unavailable" ? "destructive" : "outline"}>
                                {subscription.status || "unknown"}
                              </Badge>
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              rw_id {subscription.rw_id} · {subscription.tariff} · {subscription.days_left}d · {subscription.devices_count} devices
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              Traffic {subscription.traffic_used_gb} / {subscription.data_limit_gb ?? "∞"} GB · source {subscription.source}
                            </div>
                          </div>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {!subscription.is_primary && (
                            <Button size="sm" variant="outline" onClick={() => handlePrimarySubscription(subscription.id)}>
                              <Star className="h-3.5 w-3.5" /> Primary
                            </Button>
                          )}
                          <Button size="sm" variant="outline" onClick={() => handleRenameSubscription(subscription)}>
                            <Pencil className="h-3.5 w-3.5" /> Rename
                          </Button>
                          {subscription.subscription_url && (
                            <>
                              <Button size="sm" variant="outline" onClick={() => copyText(subscription.subscription_url!)}>
                                <Copy className="h-3.5 w-3.5" /> Copy URL
                              </Button>
                              <Button size="sm" variant="outline" asChild>
                                <a href={subscription.subscription_url} target="_blank" rel="noreferrer">
                                  <ExternalLink className="h-3.5 w-3.5" /> Open
                                </a>
                              </Button>
                            </>
                          )}
                          <ConfirmButton
                            title="Unlink this subscription? The Remnawave user will not be deleted."
                            confirmText="Unlink"
                            destructive
                            onConfirm={() => handleDetachSubscription(subscription.id)}
                          >
                            <Button size="sm" variant="destructive">
                              <Unlink className="h-3.5 w-3.5" /> Unlink
                            </Button>
                          </ConfirmButton>
                        </div>
                      </div>
                    ))
                  )}
                </div>
                <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                  <Input value={addRwId} onChange={(e) => setAddRwId(e.target.value)} inputMode="numeric" placeholder="Remnawave rw_id" />
                  <Input value={addLabel} onChange={(e) => setAddLabel(e.target.value)} placeholder="Label (optional)" />
                  <Button onClick={handleAttachSubscription} disabled={subscriptionSaving}>Link</Button>
                </div>
                <label className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <input type="checkbox" checked={addPrimary} onChange={(e) => setAddPrimary(e.target.checked)} />
                  Make primary after linking
                </label>
              </div>

              <Separator />

              <div>
                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <IdCard className="h-4 w-4" />
                  Identifiers
                </div>
                <div className="flex flex-col gap-2">
                  <LabeledInput
                    label="TG ID"
                    value={editTgId}
                    onChange={(e) => setEditTgId(e.target.value)}
                    placeholder="123456789 (optional)"
                  />
                  <LabeledInput
                    label="Username"
                    value={editUsername}
                    onChange={(e) => setEditUsername(e.target.value)}
                    placeholder="username"
                  />
                  <LabeledInput
                    label="UUID"
                    value={editUuid}
                    onChange={(e) => setEditUuid(e.target.value)}
                    placeholder="vless_uuid"
                  />
                  <Button onClick={handleSaveIdentifiers} disabled={idSaving}>
                    <Pencil className="h-4 w-4" />
                    Save identifiers
                  </Button>
                </div>
              </div>

              <Separator />

              <div>
                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <Pencil className="h-4 w-4" />
                  User email
                </div>
                <div className="flex gap-2">
                  <Input
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    placeholder="user@example.com"
                    onKeyDown={(e) => e.key === "Enter" && handleSaveEmail()}
                  />
                  <Button onClick={handleSaveEmail} disabled={emailSaving}>
                    Save
                  </Button>
                </div>
              </div>

              <Separator />

              <div>
                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <Wallet className="h-4 w-4" />
                  Bonus balance
                </div>
                <div className="flex gap-2">
                  <Input
                    type="number"
                    className="flex-1"
                    value={creditsDelta}
                    onChange={(e) => setCreditsDelta(e.target.value)}
                    placeholder={`± ${POINTS_ICON}`}
                    min={-3650}
                    max={3650}
                  />
                  <Button
                    onClick={handleAdjustCredits}
                    disabled={creditsSaving || !creditsDelta || Number(creditsDelta) === 0}
                  >
                    Apply
                  </Button>
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  Positive number credits, negative debits.
                </p>
              </div>

              <Separator />

              <div>
                <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <Send className="h-4 w-4" />
                  Message to user
                </div>
                {user.tg_id == null && (
                  <p className="mb-2 text-xs text-muted-foreground">
                    Unavailable: this account has no Telegram ID (Android / web).
                  </p>
                )}
                <Textarea
                  rows={3}
                  value={msgText}
                  onChange={(e) => setMsgText(e.target.value)}
                  placeholder="Message text..."
                  disabled={user.tg_id == null}
                />
                <Button
                  className="mt-2"
                  disabled={msgSending || !msgText.trim() || user.tg_id == null}
                  onClick={handleSendMessage}
                >
                  <Send className="h-4 w-4" />
                  Send
                </Button>
              </div>

              <Separator />

              <div>
                <h4 className="mb-2 text-sm font-semibold">Transactions</h4>
                {tx.length === 0 ? (
                  <div className="py-4 text-center text-sm text-muted-foreground">
                    No transactions
                  </div>
                ) : (
                  <div className="divide-y divide-border rounded-lg border border-border">
                    {tx.map((t) => (
                      <div key={t.transaction_id} className="p-2.5">
                        <div className="text-sm font-medium">
                          {t.transaction_id} — {t.order_status}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {t.payment_method || "—"} | {t.amount ?? 0} | {t.days_ordered}d |{" "}
                          {t.created_at || "—"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )
        )}
      </SheetContent>
    </Sheet>
  );
}
