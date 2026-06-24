import { Alert, Spin, Tag } from "antd";
import { CheckOutlined, LeftOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  MeResponse,
  MenuNode,
  PromoState,
  api,
  menu,
  payments,
  promo as promoApi,
} from "../api/client";
import { hapticImpact, openLink, showAlert } from "../tg/webapp";

function discountedAmount(amount: number, pct: number): number {
  return Math.round(amount * (1 - pct / 100) * 100) / 100;
}

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

  const activeDiscount =
    promoState?.active_promo && promoState.discount_percent > 0
      ? promoState.discount_percent
      : 0;

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

  const handlePay = async () => {
    if (!selectedInvoice?.invoice) return;
    const inv = selectedInvoice.invoice;

    if (!inv.days || inv.days <= 0) {
      showAlert("Тариф не настроен: отсутствует количество дней");
      return;
    }

    setBusyId(selectedInvoice.id);
    try {
      let baselineExpireIso: string | null = null;
      let baselineDaysLeft = 0;
      try {
        const snapshot = await api.get<MeResponse>("/me");
        baselineExpireIso = snapshot.subscription?.expire_iso ?? null;
        baselineDaysLeft = snapshot.subscription?.days_left ?? 0;
      } catch {
        /* polling works without baseline */
      }

      const res = await payments.createInvoice({
        provider: inv.provider,
        amount: inv.amount,
        currency: inv.currency,
        days: inv.days,
        tariff_slug: inv.tariff_slug ?? undefined,
        description: selectedInvoice.text,
        method: inv.method ?? undefined,
      });
      openLink(res.url);
      setPromoState((prev) =>
        prev ? { ...prev, can_activate: true, active_promo: null, discount_percent: 0 } : prev
      );
      navigate("/buy/success", {
        state: { paymentUrl: res.url, baselineExpireIso, baselineDaysLeft },
      });
    } catch (e) {
      showAlert(`Ошибка создания счёта: ${(e as Error).message}`);
    } finally {
      setBusyId(null);
    }
  };

  if (error) {
    return (
      <div className="page">
        <Alert type="error" title="Не удалось загрузить меню" description={error} />
      </div>
    );
  }

  if (!tree) {
    return (
      <div className="spinner-wrap">
        <Spin size="large" />
      </div>
    );
  }

  const payInvoice = selectedInvoice?.invoice;
  const payOrig = payInvoice?.amount ?? 0;
  const payDisc = activeDiscount > 0 && payInvoice
    ? discountedAmount(payOrig, activeDiscount)
    : null;
  const payPrice = payDisc ?? payOrig;
  const payCurrency = payInvoice?.currency ?? "";

  return (
    <>
      <div className="page">
        {/* Back + title */}
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
            <LeftOutlined style={{ fontSize: 14 }} />
          </button>
          <span style={{ fontSize: 20, fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.3px" }}>
            Тарифы
          </span>
        </div>

        {/* Promo banner */}
        {activeDiscount > 0 && (
          <Alert
            type="success"
            showIcon
            style={{ marginBottom: 16 }}
            title={
              <span>
                Промокод <strong>{promoState!.active_promo}</strong> активен —{" "}
                скидка <Tag color="success">−{activeDiscount}%</Tag> применится при оплате
              </span>
            }
          />
        )}

        {/* Chip levels */}
        {chipLevels.map((chips, depth) => (
          <div key={depth} style={{ marginBottom: 12 }}>
            {depth === 0 && (
              <div style={{
                fontSize: 11,
                fontWeight: 600,
                color: "rgba(255,255,255,0.30)",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
                marginBottom: 8,
              }}>
                Категория
              </div>
            )}
            {depth === 1 && (
              <div style={{
                fontSize: 11,
                fontWeight: 600,
                color: "rgba(255,255,255,0.30)",
                textTransform: "uppercase",
                letterSpacing: "0.5px",
                marginBottom: 8,
              }}>
                Тип
              </div>
            )}
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

        {/* Tariff cards */}
        {chipLevels.length > 0 && invoices.length === 0 && (
          <div className="tariff-hint">Выберите категорию выше</div>
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
              Период
            </div>
            <div className="tariff-scroll-wrap">
              <div className="tariff-scroll">
                {invoices.map((n) => {
                  const inv = n.invoice!;
                  const origAmt = inv.amount;
                  const discAmt = activeDiscount > 0
                    ? discountedAmount(origAmt, activeDiscount)
                    : null;
                  const isSelected = selectedInvoiceId === n.id;

                  return (
                    <div
                      key={n.id}
                      className={`tariff-card${isSelected ? " selected" : ""}`}
                      onClick={() => selectInvoice(n.id)}
                    >
                      <div className="tariff-card__label">
                        {inv.days ? `${inv.days} дн.` : "—"}
                      </div>
                      <div className="tariff-card__name">{n.text}</div>
                      <div className="tariff-card__price-row">
                        {discAmt !== null && (
                          <div className="tariff-card__price-orig">
                            {origAmt} {inv.currency}
                          </div>
                        )}
                        <div className="tariff-card__price">
                          {discAmt ?? origAmt}
                        </div>
                        <div className="tariff-card__currency">{inv.currency}</div>
                      </div>
                      {isSelected && (
                        <div className="tariff-card__check">
                          <CheckOutlined />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {/* If tree has only invoices at root (no button categories) */}
        {chipLevels.length === 0 && invoices.length === 0 && (
          <div className="tariff-hint">Тарифы не найдены</div>
        )}

        {/* Spacer so content isn't hidden behind the pay bar */}
        {selectedInvoice && <div style={{ height: 68 }} />}
      </div>

      {/* Floating pay button */}
      {selectedInvoice && (
        <div className="pay-bar">
          <button
            className="ant-btn ant-btn-primary pay-bar-btn"
            onClick={handlePay}
            disabled={!!busyId}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
            }}
          >
            {busyId ? (
              <Spin size="small" />
            ) : (
              <>
                <span>Оплатить</span>
                <span style={{ opacity: 0.85 }}>·</span>
                <span style={{ fontWeight: 800 }}>
                  {payPrice} {payCurrency}
                </span>
                {payDisc !== null && (
                  <span style={{
                    fontSize: 12,
                    opacity: 0.6,
                    textDecoration: "line-through",
                    fontWeight: 400,
                  }}>
                    {payOrig}
                  </span>
                )}
              </>
            )}
          </button>
        </div>
      )}
    </>
  );
}
