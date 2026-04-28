import { Alert, Button, Empty, Space, Spin, Typography } from "antd";
import { LeftOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, MenuNode, menu, payments } from "../api/client";
import { hapticImpact, openLink, showAlert } from "../tg/webapp";

function findNode(nodes: MenuNode[], id: number): MenuNode | null {
  for (const n of nodes) {
    if (n.id === id) return n;
    const found = findNode(n.children, id);
    if (found) return found;
  }
  return null;
}

export default function BuyMenuPage() {
  const navigate = useNavigate();
  const [tree, setTree] = useState<MenuNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [path, setPath] = useState<number[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    menu
      .getTree()
      .then((r) => setTree(r.tree))
      .catch((e: ApiError | Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="page">
        <Alert type="error" message="Не удалось загрузить меню" description={error} />
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
    setBusyId(node.id);
    try {
      const res = await payments.createInvoice({
        provider: node.invoice.provider,
        amount: node.invoice.amount,
        currency: node.invoice.currency,
        days: node.invoice.days ?? 0,
        tariff_slug: node.invoice.tariff_slug ?? undefined,
        description: node.text,
      });
      openLink(res.url);
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

      {currentNodes.length === 0 ? (
        <Empty description="Здесь пока пусто" />
      ) : (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {currentNodes.map((n) => (
            <Button
              key={n.id}
              size="large"
              block
              type={n.action === "invoice" ? "primary" : "default"}
              loading={busyId === n.id}
              onClick={() => handleClick(n)}
            >
              {n.text}
              {n.action === "invoice" && n.invoice && (
                <span style={{ opacity: 0.7, marginLeft: 8 }}>
                  · {n.invoice.amount} {n.invoice.currency}
                </span>
              )}
            </Button>
          ))}
        </Space>
      )}
    </div>
  );
}
