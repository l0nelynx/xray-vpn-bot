import {
  Alert,
  Button,
  Card,
  Col,
  Modal,
  Row,
  Skeleton,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  GiftOutlined,
  ShoppingCartOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { ApiError, WebInvoiceResponse, WebMenuNode, webPayments } from "../../api/client";

const { Title, Text } = Typography;

function flattenLeafNodes(nodes: WebMenuNode[]): WebMenuNode[] {
  const leaves: WebMenuNode[] = [];
  function walk(n: WebMenuNode) {
    if (n.action === "invoice" && n.invoice) {
      leaves.push(n);
    } else {
      n.children.forEach(walk);
    }
  }
  nodes.forEach(walk);
  return leaves;
}

function TariffCard({
  node,
  discountPct,
  onBuy,
  loading,
}: {
  node: WebMenuNode;
  discountPct: number;
  onBuy: (node: WebMenuNode) => void;
  loading: boolean;
}) {
  const inv = node.invoice!;
  const hasDiscount = discountPct > 0 && inv.original_amount !== inv.amount;

  return (
    <Card
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.09)",
        borderRadius: 16,
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
      styles={{ body: { padding: 24, flex: 1, display: "flex", flexDirection: "column" } }}
    >
      <Title level={4} style={{ color: "#fff", marginBottom: 8, fontSize: 17 }}>
        {node.text}
      </Title>

      <div style={{ flex: 1, marginBottom: 20 }}>
        <Text style={{ color: "rgba(255,255,255,0.5)", fontSize: 13 }}>
          <ThunderboltOutlined style={{ marginRight: 4 }} />
          {inv.days} дней доступа
        </Text>
      </div>

      <div style={{ marginBottom: 20 }}>
        {hasDiscount && (
          <div>
            <Text
              delete
              style={{ color: "rgba(255,255,255,0.3)", fontSize: 14 }}
            >
              {inv.original_amount.toFixed(0)} {inv.currency}
            </Text>
            <Tag
              color="success"
              style={{ marginLeft: 8, fontSize: 11 }}
              icon={<GiftOutlined />}
            >
              -{discountPct}%
            </Tag>
          </div>
        )}
        <div
          style={{
            fontSize: 32,
            fontWeight: 700,
            color: hasDiscount ? "#06D6A0" : "#fff",
            lineHeight: 1.2,
            marginTop: hasDiscount ? 4 : 0,
          }}
        >
          {inv.amount.toFixed(0)}{" "}
          <span style={{ fontSize: 16, fontWeight: 400, color: "rgba(255,255,255,0.5)" }}>
            {inv.currency}
          </span>
        </div>
      </div>

      <Button
        type="primary"
        block
        loading={loading}
        icon={<ShoppingCartOutlined />}
        onClick={() => onBuy(node)}
        style={{
          background: "linear-gradient(135deg, #06D6A0, #0096C7)",
          border: "none",
          height: 44,
          borderRadius: 10,
          fontWeight: 600,
        }}
      >
        Оплатить
      </Button>
    </Card>
  );
}

export default function BuyTab() {
  const [tree, setTree] = useState<WebMenuNode[]>([]);
  const [discountPct, setDiscountPct] = useState(0);
  const [promoCode, setPromoCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [buyingId, setBuyingId] = useState<number | null>(null);
  const [invoice, setInvoice] = useState<WebInvoiceResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await webPayments.getMenu();
      setTree(resp.tree);
      setDiscountPct(resp.discount_percent);
      setPromoCode(resp.promo_code);
    } catch {
      setError("Не удалось загрузить тарифы. Попробуйте позже.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleBuy(node: WebMenuNode) {
    setBuyingId(node.id);
    try {
      const resp = await webPayments.createInvoice(node.id);
      setInvoice(resp);
    } catch (e) {
      let msg = "Ошибка создания счёта. Попробуйте позже.";
      if (e instanceof ApiError) {
        if (e.code === "rate_limited" || e.status === 429) msg = "Слишком много запросов";
        else if (e.code === "provider_unavailable") msg = "Платёжный провайдер недоступен";
        else if (e.code === "email_not_verified") msg = "Сначала подтвердите email";
      }
      Modal.error({ title: "Ошибка", content: msg, centered: true });
    } finally {
      setBuyingId(null);
    }
  }

  const leaves = flattenLeafNodes(tree);

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ color: "#fff", margin: "0 0 8px" }}>
          <ShoppingCartOutlined style={{ marginRight: 8 }} />
          Купить подписку
        </Title>
        {promoCode && discountPct > 0 && (
          <Alert
            icon={<GiftOutlined />}
            type="success"
            message={
              <Space>
                <span>Промокод активен:</span>
                <Tag color="green">{promoCode}</Tag>
                <span style={{ color: "rgba(255,255,255,0.7)" }}>
                  Скидка {discountPct}% применена к ценам ниже
                </span>
              </Space>
            }
            style={{ borderRadius: 10 }}
            showIcon
          />
        )}
      </div>

      {loading ? (
        <Row gutter={[20, 20]}>
          {[1, 2, 3].map((i) => (
            <Col key={i} xs={24} sm={12} lg={8}>
              <Skeleton active paragraph={{ rows: 4 }} />
            </Col>
          ))}
        </Row>
      ) : error ? (
        <Alert type="error" message={error} showIcon style={{ borderRadius: 12 }} />
      ) : leaves.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            color: "rgba(255,255,255,0.3)",
          }}
        >
          Тарифы не настроены
        </div>
      ) : (
        <Row gutter={[20, 20]}>
          {leaves.map((node) => (
            <Col key={node.id} xs={24} sm={12} lg={8}>
              <TariffCard
                node={node}
                discountPct={discountPct}
                onBuy={handleBuy}
                loading={buyingId === node.id}
              />
            </Col>
          ))}
        </Row>
      )}

      {/* Payment modal */}
      <Modal
        open={!!invoice}
        onCancel={() => setInvoice(null)}
        footer={null}
        centered
        title={
          <Text strong style={{ color: "#fff" }}>
            Счёт на оплату
          </Text>
        }
        style={{
          background: "rgba(20,20,30,0.98)",
          border: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        {invoice && (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            {invoice.discount_percent > 0 && (
              <Alert
                icon={<GiftOutlined />}
                type="success"
                message={`Скидка ${invoice.discount_percent}% применена`}
                showIcon
                style={{ borderRadius: 10 }}
              />
            )}
            <div
              style={{
                background: "rgba(255,255,255,0.04)",
                borderRadius: 12,
                padding: 16,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 8,
                }}
              >
                <Text style={{ color: "rgba(255,255,255,0.5)" }}>К оплате:</Text>
                <Text strong style={{ color: "#06D6A0", fontSize: 18 }}>
                  {invoice.amount.toFixed(0)} {invoice.currency}
                </Text>
              </div>
              {invoice.discount_percent > 0 && (
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <Text style={{ color: "rgba(255,255,255,0.35)", fontSize: 13 }}>
                    Без скидки:
                  </Text>
                  <Text delete style={{ color: "rgba(255,255,255,0.3)", fontSize: 13 }}>
                    {invoice.original_amount.toFixed(0)} {invoice.currency}
                  </Text>
                </div>
              )}
            </div>
            <Button
              type="primary"
              block
              size="large"
              icon={<CheckCircleOutlined />}
              onClick={() => {
                window.open(invoice.url, "_blank");
                setInvoice(null);
              }}
              style={{
                background: "linear-gradient(135deg, #06D6A0, #0096C7)",
                border: "none",
                height: 48,
                borderRadius: 12,
                fontWeight: 600,
              }}
            >
              Перейти к оплате
            </Button>
          </Space>
        )}
      </Modal>
    </div>
  );
}
