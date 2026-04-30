import { Alert, Button, Empty, Space, Spin, Tag, Typography } from "antd";
import { LeftOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, MeResponse, MenuNode, PromoState, api, menu, payments, promo as promoApi } from "../api/client";
import { hapticImpact, openLink, showAlert } from "../tg/webapp";

function findNode(nodes: MenuNode[], id: number): MenuNode | null {
  for (const n of nodes) {
    if (n.id === id) return n;
    const found = findNode(n.children, id);
    if (found) return found;
  }
  return null;
}

function discountedAmount(amount: number, pct: number): number {
  return Math.round(amount * (1 - pct / 100) * 100) / 100;
}

export default function BuyMenuPage() {
  const navigate = useNavigate();
  const [tree, setTree] = useState<MenuNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [path, setPath] = useState<number[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [promoState, setPromoState] = useState<PromoState | null>(null);

  useEffect(() => {
    menu
      .getTree()
      .then((r) => setTree(r.tree))
      .catch((e: ApiError | Error) => setError(e.message));
    promoApi.getState().then(setPromoState).catch(() => {});
  }, []);

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

  const currentNodes: MenuNode[] = path.length === 0
    ? tree
    : (findNode(tree, path[path.length - 1])?.children ?? []);

  const goBack = () => {
    if (path.length === 0) navigate("/");
    else setPath((p) => p.slice(0, -1));
  };

  const activeDiscount = promoState?.active_promo && promoState.discount_percent > 0
    ? promoState.discount_percent
    : 0;

  const handleClick = async (node: MenuNode) => {
    hapticImpact("light");
    if (node.action === "buttons") {
      setPath((p) => [...p, node.id]);
      return;
    }
    if (!node.invoice) {
      showAlert("Узел оплаты не настроен");
      return;
    }
    if (!node.invoice.days || node.invoice.days <= 0) {
      showAlert("Тариф не настроен: отсутствует количество дней");
      return;
    }
    setBusyId(node.id);
    try {
      let baselineExpireIso: string | null = null;
      let baselineDaysLeft = 0;
      try {
        const snapshot = await api.get<MeResponse>("/me");
        baselineExpireIso = snapshot.subscription?.expire_iso ?? null;
        baselineDaysLeft = snapshot.subscription?.days_left ?? 0;
      } catch {
        /* polling will work even without baseline */
      }

      const res = await payments.createInvoice({
        provider: node.invoice.provider,
        amount: node.invoice.amount,
        currency: node.invoice.currency,
        days: node.invoice.days,
        tariff_slug: node.invoice.tariff_slug ?? undefined,
        description: node.text,
      });
      openLink(res.url);
      // Promo is consumed after delivery — refresh state optimistically
      setPromoState((prev) => prev ? { ...prev, can_activate: true, active_promo: null, discount_percent: 0 } : prev);
      navigate("/buy/success", {
        state: {
          paymentUrl: res.url,
          baselineExpireIso,
          baselineDaysLeft,
        },
      });
    } catch (e) {
      showAlert(`Ошибка создания счёта: ${(e as Error).message}`);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="page">
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<LeftOutlined />} onClick={goBack} size="small">
          Назад
        </Button>
      </Space>
      <Typography.Title level={3} style={{ marginBottom: 16 }}>
        Тарифы
      </Typography.Title>

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

      {currentNodes.length === 0 ? (
        <Empty description="Здесь пока пусто" />
      ) : (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {currentNodes.map((n) => {
            const hasInvoice = n.action === "invoice" && n.invoice;
            const origAmt = hasInvoice ? n.invoice!.amount : 0;
            const discAmt = activeDiscount > 0 && hasInvoice
              ? discountedAmount(origAmt, activeDiscount)
              : null;

            return (
              <Button
                key={n.id}
                size="large"
                block
                type={hasInvoice ? "primary" : "default"}
                loading={busyId === n.id}
                onClick={() => handleClick(n)}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "space-between", width: "100%" }}>
                  <span>{n.text}</span>
                  {hasInvoice && (
                    <span style={{ opacity: 0.85, display: "inline-flex", alignItems: "center", gap: 6 }}>
                      {discAmt !== null ? (
                        <>
                          <span style={{ textDecoration: "line-through", opacity: 0.5, fontSize: 12 }}>
                            {origAmt} {n.invoice!.currency}
                          </span>
                          <span style={{ fontWeight: 700 }}>
                            {discAmt} {n.invoice!.currency}
                          </span>
                        </>
                      ) : (
                        <span>· {origAmt} {n.invoice!.currency}</span>
                      )}
                    </span>
                  )}
                </span>
              </Button>
            );
          })}
        </Space>
      )}
    </div>
  );
}
