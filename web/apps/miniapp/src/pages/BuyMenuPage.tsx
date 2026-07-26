import { Check, ChevronLeft } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { Alert, AlertTitle } from "@xray/ui/components/alert";
import { Badge } from "@xray/ui/components/badge";
import { Button } from "@xray/ui/components/button";
import { Spinner } from "@xray/ui/components/spinner";
import { formatPoints, POINTS_ICON } from "../points";
import {
  ApiError,
  MenuNode,
  PromoState,
  menu,
  payments,
  promo as promoApi,
} from "../api/client";
import { useT } from "../i18n/LocaleContext";
import { hapticImpact, openLink, showAlert } from "../tg/webapp";

interface ViewResult {
  chipLevels: MenuNode[][];
  invoices: MenuNode[];
}

function buildView(
  nodes: MenuNode[],
  selections: (number | null)[],
  depth = 0
): ViewResult {
  const btns = nodes.filter((n) => n.action === "buttons");
  const invs = nodes.filter((n) => n.action === "invoice");

  if (btns.length === 0) return { chipLevels: [], invoices: invs };

  const selectedId = selections[depth] ?? null;
  const selNode = selectedId !== null ? btns.find((n) => n.id === selectedId) : undefined;

  if (!selNode) {
    return { chipLevels: [btns], invoices: invs };
  }

  const nested = buildView(selNode.children, selections, depth + 1);
  return {
    chipLevels: [btns, ...nested.chipLevels],
    invoices: nested.invoices,
  };
}

export default function BuyMenuPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const subscriptionId = Number(searchParams.get("subscription_id") || 0) || undefined;
  const { t } = useT();
  const [tree, setTree] = useState<MenuNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selections, setSelections] = useState<(number | null)[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [promoState, setPromoState] = useState<PromoState | null>(null);

  useEffect(() => {
    menu
      .getTree()
      .then((r) => setTree(r.tree))
      .catch((e: ApiError | Error) => setError(e.message));
    promoApi.getState().then(setPromoState).catch(() => {});
  }, []);

  const { chipLevels, invoices } = useMemo(() => {
    if (!tree) return { chipLevels: [], invoices: [] };
    return buildView(tree, selections);
  }, [tree, selections]);

  const selectedInvoice = useMemo(
    () => invoices.find((n) => n.id === selectedInvoiceId) ?? null,
    [invoices, selectedInvoiceId]
  );

  const balance = promoState?.balance ?? 0;
  const pointsCost = selectedInvoice?.invoice?.points_cost ?? 0;
  const canPayCredits = pointsCost > 0 && balance >= pointsCost;

  const selectChip = (depth: number, id: number) => {
    hapticImpact("light");
    setSelections((prev) => {
      const toggling = prev[depth] === id;
      const next = prev.slice(0, depth);
      next[depth] = toggling ? null : id;
      return next;
    });
    setSelectedInvoiceId(null);
  };

  const selectInvoice = (id: number) => {
    hapticImpact("light");
    setSelectedInvoiceId((prev) => (prev === id ? null : id));
  };

  const handlePayFiat = async () => {
    if (!selectedInvoice?.invoice) return;
    const inv = selectedInvoice.invoice;

    if (!inv.days || inv.days <= 0) {
      showAlert(t("buy.alert.missingDays"));
      return;
    }

    setBusyId(selectedInvoice.id);
    try {
      const res = await payments.createInvoice({
        node_id: selectedInvoice.id,
        description: selectedInvoice.text,
        subscription_id: subscriptionId,
      });
      openLink(res.url);
      navigate("/buy/success", { state: { paymentUrl: res.url } });
    } catch (e) {
      showAlert(t("buy.alert.invoiceError", { message: (e as Error).message }));
    } finally {
      setBusyId(null);
    }
  };

  const handlePayCredits = async () => {
    if (!selectedInvoice?.invoice || !canPayCredits) return;
    setBusyId(selectedInvoice.id);
    try {
      const res = await payments.payWithCredits({
        node_id: selectedInvoice.id,
        subscription_id: subscriptionId,
      });
      if (res.ok) {
        setPromoState((prev) =>
          prev ? { ...prev, balance: res.balance_after ?? prev.balance } : prev
        );
        navigate("/buy/success", { state: { paidWithCredits: true } });
      }
    } catch (e) {
      showAlert(t("buy.alert.creditsError", { message: (e as Error).message }));
    } finally {
      setBusyId(null);
    }
  };

  if (error) {
    return (
      <div className="page">
        <Alert variant="destructive">
          <AlertTitle>{t("buy.loadError")}</AlertTitle>
          <p>{error}</p>
        </Alert>
      </div>
    );
  }

  if (!tree) {
    return (
      <div className="spinner-wrap">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  const payInvoice = selectedInvoice?.invoice;
  const payPrice = payInvoice?.amount ?? 0;
  const payCurrency = payInvoice?.currency ?? "";

  const levelLabel =
    (depth: number) =>
      depth === 0
        ? t("buy.level.tariff")
        : depth === 1
          ? t("buy.level.period")
          : t("buy.level.subcategory");

  return (
    <>
      <div className="page">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
          <button
            onClick={() => navigate("/")}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 36,
              height: 36,
              borderRadius: 12,
              background: "rgba(255,255,255,0.07)",
              border: "1px solid rgba(255,255,255,0.13)",
              color: "rgba(255,255,255,0.75)",
              cursor: "pointer",
              outline: "none",
              flexShrink: 0,
            }}
          >
            <ChevronLeft style={{ width: 16, height: 16 }} />
          </button>
          <span style={{ fontSize: 20, fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.3px" }}>
            {t("buy.title")}
          </span>
        </div>

        {balance > 0 && (
          <Alert style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <span>{t("buy.bonusBalance")}</span>
            <Badge>{formatPoints(balance)}</Badge>
          </Alert>
        )}

        {chipLevels.map((chips, depth) => (
          <div key={depth} style={{ marginBottom: 12 }}>
            <div style={{
              fontSize: 11,
              fontWeight: 600,
              color: "rgba(255,255,255,0.30)",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
              marginBottom: 8,
            }}>
              {levelLabel(depth)}
            </div>
            <div className="chip-row-wrap">
              <div className="chip-row">
                {chips.map((chip) => (
                  <button
                    key={chip.id}
                    className={`plan-chip${selections[depth] === chip.id ? " active" : ""}`}
                    onClick={() => selectChip(depth, chip.id)}
                  >
                    {chip.text}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ))}

        {chipLevels.length > 0 && invoices.length === 0 && (
          <div className="tariff-hint">{t("buy.hint.selectCategory")}</div>
        )}

        {invoices.length > 0 && (
          <>
            <div style={{
              fontSize: 11,
              fontWeight: 600,
              color: "rgba(255,255,255,0.30)",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
              marginBottom: 8,
            }}>
              {t("buy.paymentMethod")}
            </div>
            <div className="tariff-scroll-wrap">
              <div className="tariff-scroll">
                {invoices.map((n) => {
                  const inv = n.invoice!;
                  const isSelected = selectedInvoiceId === n.id;

                  return (
                    <div
                      key={n.id}
                      className={`tariff-card${isSelected ? " selected" : ""}`}
                      onClick={() => selectInvoice(n.id)}
                    >
                      <div className="tariff-card__name">{n.text}</div>
                      <div className="tariff-card__price-row">
                        <div className="tariff-card__price">{inv.amount}</div>
                        <div className="tariff-card__currency">{inv.currency}</div>
                      </div>
                      {(inv.days ?? 0) > 0 && (
                        <div style={{ fontSize: 11, opacity: 0.5, marginTop: 4 }}>
                          {t("buy.daysShort", { count: inv.days! })}
                        </div>
                      )}
                      {isSelected && (
                        <div className="tariff-card__check">
                          <Check style={{ width: 12, height: 12 }} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {chipLevels.length === 0 && invoices.length === 0 && (
          <div className="tariff-hint">{t("buy.hint.none")}</div>
        )}

        {selectedInvoice && <div style={{ height: 88 }} />}
      </div>

      {selectedInvoice && (
        <div className="pay-bar" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {canPayCredits && (
            <Button className="pay-bar-btn" onClick={handlePayCredits} disabled={!!busyId}>
              {busyId
                ? <Spinner />
                : t("buy.payCredits", { cost: `${pointsCost} ${POINTS_ICON}` })}
            </Button>
          )}
          <Button className="pay-bar-btn" variant="outline" onClick={handlePayFiat} disabled={!!busyId}>
            {busyId ? (
              <Spinner />
            ) : (
              <>
                <span>{t("buy.pay")}</span>
                <span style={{ opacity: 0.85 }}>·</span>
                <span style={{ fontWeight: 800 }}>
                  {payPrice} {payCurrency}
                </span>
              </>
            )}
          </Button>
        </div>
      )}
    </>
  );
}
