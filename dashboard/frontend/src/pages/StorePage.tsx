import { useEffect, useState, useCallback } from "react";
import {
  Typography, Button, Space, Modal, Form, Input, InputNumber,
  Select, message, Popconfirm, Tag, Spin, Empty, Collapse,
} from "antd";
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined,
  RightOutlined, DownOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import type { OrderParam } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

const TYPE_OPTIONS = [
  { value: "days", label: "days" },
  { value: "hwid", label: "hwid" },
  { value: "location", label: "location" },
  { value: "internal_sq", label: "internal_sq" },
  { value: "external_sq", label: "external_sq" },
];

const TYPE_COLORS: Record<string, string> = {
  days: "blue",
  hwid: "green",
  location: "orange",
  internal_sq: "purple",
  external_sq: "cyan",
};

interface TreeItemGroup {
  itemId: number;
  paramGroups: {
    paramId: number;
    userDataGroups: {
      userDataId: number;
      params: OrderParam[];
    }[];
  }[];
}

function buildTree(params: OrderParam[]): TreeItemGroup[] {
  const itemMap = new Map<number, Map<number, Map<number, OrderParam[]>>>();

  for (const p of params) {
    if (!itemMap.has(p.item_id)) itemMap.set(p.item_id, new Map());
    const paramMap = itemMap.get(p.item_id)!;
    if (!paramMap.has(p.param_id)) paramMap.set(p.param_id, new Map());
    const udMap = paramMap.get(p.param_id)!;
    if (!udMap.has(p.user_data_id)) udMap.set(p.user_data_id, []);
    udMap.get(p.user_data_id)!.push(p);
  }

  const tree: TreeItemGroup[] = [];
  for (const [itemId, paramMap] of [...itemMap.entries()].sort((a, b) => a[0] - b[0])) {
    const paramGroups = [];
    for (const [paramId, udMap] of [...paramMap.entries()].sort((a, b) => a[0] - b[0])) {
      const userDataGroups = [];
      for (const [userDataId, ps] of [...udMap.entries()].sort((a, b) => a[0] - b[0])) {
        userDataGroups.push({ userDataId, params: ps });
      }
      paramGroups.push({ paramId, userDataGroups });
    }
    tree.push({ itemId, paramGroups });
  }
  return tree;
}

const nodeStyle: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: 8,
  border: "1px solid rgba(255,255,255,0.06)",
  marginBottom: 8,
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  width: "100%",
  padding: "8px 0",
};

const labelStyle: React.CSSProperties = {
  color: "rgba(255,255,255,0.45)",
  fontSize: 12,
  marginRight: 6,
};

const valueStyle: React.CSSProperties = {
  color: "rgba(255,255,255,0.88)",
  fontWeight: 600,
  fontFamily: "monospace",
  fontSize: 14,
};

const paramRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "8px 12px",
  background: "rgba(255,255,255,0.02)",
  borderRadius: 6,
  border: "1px solid rgba(255,255,255,0.04)",
  marginBottom: 4,
};

export default function StorePage() {
  const [params, setParams] = useState<OrderParam[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<OrderParam | null>(null);
  const [filterItemId, setFilterItemId] = useState<string>("");
  const [form] = Form.useForm();
  const isMobile = useIsMobile();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = filterItemId ? `?item_id=${filterItemId}` : "";
      const data = await api.get<OrderParam[]>(`/store/order-params${query}`);
      setParams(data);
    } catch {
      message.error("Failed to load order params");
    }
    setLoading(false);
  }, [filterItemId]);

  useEffect(() => { load(); }, [load]);

  const openCreate = (prefill?: Partial<OrderParam>) => {
    setEditing(null);
    form.resetFields();
    if (prefill) form.setFieldsValue(prefill);
    setModalOpen(true);
  };

  const openEdit = (record: OrderParam) => {
    setEditing(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await api.put(`/store/order-params/${editing.id}`, values);
        message.success("Parameter updated");
      } else {
        await api.post("/store/order-params", values);
        message.success("Parameter created");
      }
      setModalOpen(false);
      await load();
    } catch {
      message.error("Failed to save");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/store/order-params/${id}`);
      message.success("Parameter deleted");
      await load();
    } catch {
      message.error("Failed to delete");
    }
  };

  const tree = buildTree(params);

  const renderParamRow = (p: OrderParam) => (
    <div key={p.id} style={paramRowStyle}>
      <Space size="middle">
        <Tag color={TYPE_COLORS[p.type] || "default"} style={{ margin: 0 }}>{p.type}</Tag>
        <span style={{ color: "rgba(255,255,255,0.88)", fontFamily: "monospace" }}>{p.data}</span>
        <span style={{ color: "rgba(255,255,255,0.25)", fontSize: 11 }}>#{p.id}</span>
      </Space>
      <Space size="small">
        <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEdit(p)} />
        <Popconfirm title="Delete this parameter?" onConfirm={() => handleDelete(p.id)}>
          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    </div>
  );

  const renderUserDataLevel = (
    itemId: number,
    paramId: number,
    groups: { userDataId: number; params: OrderParam[] }[],
  ) =>
    groups.map((udg) => (
      <div key={udg.userDataId} style={{ marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4, padding: "4px 0" }}>
          <span>
            <span style={labelStyle}>user_data_id</span>
            <span style={valueStyle}>{udg.userDataId}</span>
            <span style={{ color: "rgba(255,255,255,0.25)", fontSize: 11, marginLeft: 8 }}>
              ({udg.params.length} param{udg.params.length !== 1 ? "s" : ""})
            </span>
          </span>
          <Button
            size="small"
            type="text"
            icon={<PlusOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              openCreate({ item_id: itemId, param_id: paramId, user_data_id: udg.userDataId });
            }}
            style={{ color: "rgba(255,255,255,0.35)" }}
          />
        </div>
        <div style={{ paddingLeft: isMobile ? 8 : 16 }}>
          {udg.params.map(renderParamRow)}
        </div>
      </div>
    ));

  const renderParamLevel = (itemId: number, paramGroups: TreeItemGroup["paramGroups"]) => (
    <Collapse
      ghost
      expandIcon={({ isActive }) =>
        isActive ? <DownOutlined style={{ color: "rgba(255,255,255,0.35)", fontSize: 10 }} />
                 : <RightOutlined style={{ color: "rgba(255,255,255,0.35)", fontSize: 10 }} />
      }
      items={paramGroups.map((pg) => {
        const totalParams = pg.userDataGroups.reduce((s, u) => s + u.params.length, 0);
        return {
          key: pg.paramId,
          style: { ...nodeStyle, background: "rgba(255,255,255,0.02)" },
          label: (
            <div style={headerStyle}>
              <span>
                <span style={labelStyle}>param_id</span>
                <span style={valueStyle}>{pg.paramId}</span>
                <span style={{ color: "rgba(255,255,255,0.25)", fontSize: 11, marginLeft: 8 }}>
                  {pg.userDataGroups.length} variant{pg.userDataGroups.length !== 1 ? "s" : ""} / {totalParams} param{totalParams !== 1 ? "s" : ""}
                </span>
              </span>
              <Button
                size="small"
                type="text"
                icon={<PlusOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  openCreate({ item_id: itemId, param_id: pg.paramId });
                }}
                style={{ color: "rgba(255,255,255,0.35)" }}
              />
            </div>
          ),
          children: (
            <div style={{ paddingLeft: isMobile ? 4 : 12 }}>
              {renderUserDataLevel(itemId, pg.paramId, pg.userDataGroups)}
            </div>
          ),
        };
      })}
    />
  );

  const renderTree = () => {
    if (loading) return <div style={{ textAlign: "center", padding: 48 }}><Spin size="large" /></div>;
    if (tree.length === 0) return <Empty description="No order parameters found" style={{ padding: 48 }} />;

    return (
      <Collapse
        ghost
        expandIcon={({ isActive }) =>
          isActive ? <DownOutlined style={{ color: "rgba(255,255,255,0.35)", fontSize: 11 }} />
                   : <RightOutlined style={{ color: "rgba(255,255,255,0.35)", fontSize: 11 }} />
        }
        items={tree.map((item) => {
          const totalParams = item.paramGroups.reduce(
            (s, pg) => s + pg.userDataGroups.reduce((s2, u) => s2 + u.params.length, 0), 0,
          );
          return {
            key: item.itemId,
            style: nodeStyle,
            label: (
              <div style={headerStyle}>
                <span>
                  <span style={labelStyle}>item_id</span>
                  <span style={{ ...valueStyle, fontSize: 15 }}>{item.itemId}</span>
                  <span style={{ color: "rgba(255,255,255,0.25)", fontSize: 11, marginLeft: 8 }}>
                    {item.paramGroups.length} option{item.paramGroups.length !== 1 ? "s" : ""} / {totalParams} param{totalParams !== 1 ? "s" : ""}
                  </span>
                </span>
                <Button
                  size="small"
                  type="text"
                  icon={<PlusOutlined />}
                  onClick={(e) => {
                    e.stopPropagation();
                    openCreate({ item_id: item.itemId });
                  }}
                  style={{ color: "rgba(255,255,255,0.35)" }}
                />
              </div>
            ),
            children: (
              <div style={{ paddingLeft: isMobile ? 4 : 12 }}>
                {renderParamLevel(item.itemId, item.paramGroups)}
              </div>
            ),
          };
        })}
      />
    );
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0, color: "rgba(255,255,255,0.88)" }}>
          Order Parameters
        </Typography.Title>
        <Space wrap>
          <Input
            placeholder="Filter by Item ID"
            prefix={<SearchOutlined />}
            value={filterItemId}
            onChange={(e) => setFilterItemId(e.target.value)}
            onPressEnter={load}
            style={{ width: 180 }}
            allowClear
          />
          <Button icon={<PlusOutlined />} onClick={() => openCreate()}>Add Parameter</Button>
        </Space>
      </div>

      {renderTree()}

      <Modal
        title={editing ? "Edit Order Parameter" : "New Order Parameter"}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        okText="Save"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="item_id" label="Item ID" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} placeholder="Product ID (e.g. 12345)" />
          </Form.Item>
          <Form.Item name="param_id" label="Param ID" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} placeholder="Option ID (e.g. 35060)" />
          </Form.Item>
          <Form.Item name="user_data_id" label="User Data ID" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} placeholder="Variant ID (e.g. 161578)" />
          </Form.Item>
          <Form.Item name="type" label="Type" rules={[{ required: true }]}>
            <Select options={TYPE_OPTIONS} placeholder="Select parameter type" />
          </Form.Item>
          <Form.Item name="data" label="Data" rules={[{ required: true }]}>
            <Input placeholder="Value (e.g. 30, UUID, etc.)" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
