import { Alert, Spin, Tag } from "antd";
import { CheckOutlined, LeftOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  MenuNode,
  PromoState,
  menu,
  payments,
  promo as promoApi,
} from "../api/client";
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
      showAlert("Тариф не настроен: отсутствует количество дней");
      return;
    }

    setBusyId(selectedInvoice.id);
    try {
      const res = await payments.createInvoice({
        node_id: selectedInvoice.id,
        description: selectedInvoice.text,
      });
      openLink(res.url);
      navigate("/buy/success", { state: { paymentUrl: res.url } });
    } catch (e) {
      showAlert(`Ошибка создания счёта: ${(e as Error).message}`);
    } finally {
      setBusyId(null);
    }
  };

  const handlePayCredits = async () => {
    if (!selectedInvoice?.invoice || !canPayCredits) return;
    setBusyId(selectedInvoice.id);
    try {
      const res = await payments.payWithCredits({ node_id: selectedInvoice.id });
      if (res.ok) {
        setPromoState((prev) =>
          prev ? { ...prev, balance: res.balance_after ?? prev.balance } : prev
        );
        navigate("/buy/success", { state: { paidWithCredits: true } });
      }
    } catch (e) {
      showAlert(`Ошибка оплаты баллами: ${(e as Error).message}`);
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
  const payPrice = payInvoice?.amount ?? 0;
  const payCurrency = payInvoice?.currency ?? "";

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
            <LeftOutlined style={{ fontSize: 14 }} />
          </button>
          <span style={{ fontSize: 20, fontWeight: 700, color: "#FFFFFF", letterSpacing: "-0.3px" }}>
            Тарифы
          </span>
        </div>

        {balance > 0 && (
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            title={
              <span>
                Бонусный баланс: <Tag color="blue">{balance} ₽</Tag>
              </span>
            }
          />
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
              {depth === 0 ? "Тариф" : depth === 1 ? "Период" : "Подкатегория"}
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
              Метод оплаты
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
                          {inv.days} дн.
                        </div>
                      )}
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

        {chipLevels.length === 0 && invoices.length === 0 && (
          <div className="tariff-hint">Тарифы не найдены</div>
        )}

        {selectedInvoice && <div style={{ height: 88 }} />}
      </div>

      {selectedInvoice && (
        <div className="pay-bar" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {canPayCredits && (
            <button
              className="ant-btn ant-btn-primary pay-bar-btn"
              onClick={handlePayCredits}
              disabled={!!busyId}
            >
              {busyId ? <Spin size="small" /> : `Оплатить баллами · ${pointsCost} ₽`}
            </button>
          )}
          <button
            className="ant-btn pay-bar-btn"
            onClick={handlePayFiat}
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
              </>
            )}
          </button>
        </div>
      )}
    </>
  );
}
