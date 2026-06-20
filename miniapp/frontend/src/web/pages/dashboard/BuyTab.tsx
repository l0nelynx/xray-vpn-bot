import {
  Alert,
  Button,
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
  FolderOutlined,
  GiftOutlined,
  LeftOutlined,
  RightOutlined,
  ShoppingCartOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { ApiError, WebInvoiceResponse, WebMenuNode, webPayments } from "../../api/client";
import { useLang } from "../../locale";

const { Title, Text } = Typography;

function findNode(nodes: WebMenuNode[], id: number): WebMenuNode | null {
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

function GroupCard({ node, onClick }: { node: WebMenuNode; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.09)",
        borderRadius: 14,
        padding: "18px 22px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        transition: "border-color 0.2s, background 0.2s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(6,214,160,0.35)";
        (e.currentTarget as HTMLDivElement).style.background = "rgba(6,214,160,0.06)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.09)";
        (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.04)";
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <FolderOutlined style={{ fontSize: 20, color: "#06D6A0" }} />
        <Text strong style={{ color: "#fff", fontSize: 16 }}>
          {node.text}
        </Text>
        <Tag style={{ marginLeft: 4, borderColor: "rgba(255,255,255,0.15)", color: "rgba(255,255,255,0.45)", background: "transparent", fontSize: 11 }}>
          {node.children.length}
        </Tag>
      </div>
      <RightOutlined style={{ color: "rgba(255,255,255,0.3)", fontSize: 13 }} />
    </div>
  );
}

function TariffCard({
  node,
  discountPct,
  onBuy,
  loading,
  L,
}: {
  node: WebMenuNode;
  discountPct: number;
  onBuy: (node: WebMenuNode) => void;
  loading: boolean;
  L: ReturnType<typeof useLang>["L"];
}) {
  const inv = node.invoice!;
  const origAmt = inv.original_amount ?? inv.amount;
  const hasDiscount = discountPct > 0 && origAmt > inv.amount;

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.09)",
        borderRadius: 16,
        padding: 24,
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Title level={4} style={{ color: "#fff", marginBottom: 6, fontSize: 16 }}>
        {node.text}
      </Title>

      <Text style={{ color: "rgba(255,255,255,0.45)", fontSize: 13, marginBottom: "auto", paddingBottom: 16 }}>
        <ThunderboltOutlined style={{ marginRight: 4 }} />
        {L.days(inv.days)}
      </Text>

      <div style={{ marginBottom: 16 }}>
        {hasDiscount && (
          <div style={{ marginBottom: 2 }}>
            <Text delete style={{ color: "rgba(255,255,255,0.3)", fontSize: 14 }}>
              {origAmt.toFixed(0)} {inv.currency}
            </Text>
            <Tag color="success" icon={<GiftOutlined />} style={{ marginLeft: 8, fontSize: 11 }}>
              -{discountPct}%
            </Tag>
          </div>
        )}
        <div style={{ fontSize: 30, fontWeight: 700, color: hasDiscount ? "#06D6A0" : "#fff", lineHeight: 1.2 }}>
          {inv.amount.toFixed(0)}{" "}
          <span style={{ fontSize: 15, fontWeight: 400, color: "rgba(255,255,255,0.45)" }}>
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
          height: 42,
          borderRadius: 10,
          fontWeight: 600,
        }}
      >
        {L.btn_pay}
      </Button>
    </div>
  );
}

export default function BuyTab() {
  const { L } = useLang();
  const [tree, setTree] = useState<WebMenuNode[]>([]);
  const [discountPct, setDiscountPct] = useState(0);
  const [promoCode, setPromoCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [path, setPath] = useState<number[]>([]);
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
      setError(L.err_load_plans);
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
      let errMsg = L.err_invoice;
      if (e instanceof ApiError) {
        if (e.status === 429) errMsg = L.err_rate_limited_inv;
        else if (e.code === "provider_unavailable") errMsg = L.err_provider;
        else if (e.code === "email_not_verified") errMsg = L.err_not_verified;
      }
      Modal.error({ title: "Error", content: errMsg, centered: true });
    } finally {
      setBuyingId(null);
    }
  }

  const currentNodes: WebMenuNode[] =
    path.length === 0 ? tree : (findNode(tree, path[path.length - 1])?.children ?? []);

  // Build breadcrumb labels
  const breadcrumb: string[] = path.map((id) => findNode(tree, id)?.text ?? "…");

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          {path.length > 0 && (
            <Button
              icon={<LeftOutlined />}
              size="small"
              onClick={() => setPath((p) => p.slice(0, -1))}
              style={{
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.12)",
                color: "rgba(255,255,255,0.75)",
                borderRadius: 8,
              }}
            >
              {L.btn_back}
            </Button>
          )}
          <Title level={4} style={{ color: "#fff", margin: 0 }}>
            <ShoppingCartOutlined style={{ marginRight: 8 }} />
            {path.length === 0 ? L.buy_title : breadcrumb[breadcrumb.length - 1]}
          </Title>
        </div>

        {/* Breadcrumb */}
        {breadcrumb.length > 0 && (
          <Space size={4} style={{ marginBottom: 4 }}>
            <Text
              style={{ color: "rgba(255,255,255,0.35)", fontSize: 12, cursor: "pointer" }}
              onClick={() => setPath([])}
            >
              {L.buy_title}
            </Text>
            {breadcrumb.map((label, i) => (
              <span key={i}>
                <Text style={{ color: "rgba(255,255,255,0.2)", fontSize: 12 }}> / </Text>
                <Text
                  style={{
                    color: i === breadcrumb.length - 1 ? "rgba(255,255,255,0.6)" : "rgba(255,255,255,0.35)",
                    fontSize: 12,
                    cursor: i < breadcrumb.length - 1 ? "pointer" : "default",
                  }}
                  onClick={() => i < breadcrumb.length - 1 && setPath(path.slice(0, i + 1))}
                >
                  {label}
                </Text>
              </span>
            ))}
          </Space>
        )}

        {promoCode && discountPct > 0 && (
          <Alert
            icon={<GiftOutlined />}
            type="success"
            message={
              <Space>
                <span>{L.promo_active}</span>
                <Tag color="green">{promoCode}</Tag>
                <span style={{ color: "rgba(255,255,255,0.7)" }}>{L.promo_applied(discountPct)}</span>
              </Space>
            }
            style={{ borderRadius: 10, marginTop: 12 }}
            showIcon
          />
        )}
      </div>

      {/* Content */}
      {loading ? (
        <Row gutter={[20, 20]}>
          {[1, 2, 3].map((i) => (
            <Col key={i} xs={24} sm={12} lg={8}>
              <Skeleton active paragraph={{ rows: 3 }} />
            </Col>
          ))}
        </Row>
      ) : error ? (
        <Alert type="error" message={error} showIcon style={{ borderRadius: 12 }} />
      ) : currentNodes.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, color: "rgba(255,255,255,0.3)" }}>
          {L.no_tariffs}
        </div>
      ) : (
        <Space direction="vertical" size={20} style={{ width: "100%" }}>
          {/* Group (buttons) nodes */}
          {currentNodes.filter((n) => n.action === "buttons").length > 0 && (
            <Space direction="vertical" size={10} style={{ width: "100%" }}>
              {currentNodes
                .filter((n) => n.action === "buttons")
                .map((n) => (
                  <GroupCard
                    key={n.id}
                    node={n}
                    onClick={() => setPath((p) => [...p, n.id])}
                  />
                ))}
            </Space>
          )}

          {/* Invoice (leaf) nodes */}
          {currentNodes.filter((n) => n.action === "invoice" && n.invoice).length > 0 && (
            <Row gutter={[16, 16]}>
              {currentNodes
                .filter((n) => n.action === "invoice" && n.invoice)
                .map((n) => (
                  <Col key={n.id} xs={24} sm={12} lg={8}>
                    <TariffCard
                      node={n}
                      discountPct={discountPct}
                      onBuy={handleBuy}
                      loading={buyingId === n.id}
                      L={L}
                    />
                  </Col>
                ))}
            </Row>
          )}
        </Space>
      )}

      {/* Payment confirm modal */}
      <Modal
        open={!!invoice}
        onCancel={() => setInvoice(null)}
        footer={null}
        centered
        title={<Text strong style={{ color: "#fff" }}>{L.invoice_title}</Text>}
      >
        {invoice && (
          <Space direction="vertical" style={{ width: "100%" }} size={16}>
            {invoice.discount_percent > 0 && (
              <Alert
                icon={<GiftOutlined />}
                type="success"
                message={L.discount_applied_msg(invoice.discount_percent)}
                showIcon
                style={{ borderRadius: 10 }}
              />
            )}
            <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 12, padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <Text style={{ color: "rgba(255,255,255,0.5)" }}>{L.to_pay}</Text>
                <Text strong style={{ color: "#06D6A0", fontSize: 18 }}>
                  {invoice.amount.toFixed(0)} {invoice.currency}
                </Text>
              </div>
              {invoice.discount_percent > 0 && (
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <Text style={{ color: "rgba(255,255,255,0.35)", fontSize: 13 }}>{L.without_discount}</Text>
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
              {L.btn_proceed}
            </Button>
          </Space>
        )}
      </Modal>
    </div>
  );
}
