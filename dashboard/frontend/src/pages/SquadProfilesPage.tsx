import { useEffect, useState, useCallback } from "react";
import {
  Typography, Table, Button, Space, Modal, Form, Input, message, Popconfirm,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import type { SquadProfile } from "../api/types";
import useIsMobile from "../hooks/useIsMobile";

export default function SquadProfilesPage() {
  const [squads, setSquads] = useState<SquadProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<SquadProfile | null>(null);
  const [form] = Form.useForm();
  const isMobile = useIsMobile();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<SquadProfile[]>("/squads");
      setSquads(data);
    } catch {
      message.error("Failed to load squad profiles");
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (record: SquadProfile) => {
    setEditing(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await api.put(`/squads/${editing.id}`, values);
        message.success("Squad updated");
      } else {
        await api.post("/squads", values);
        message.success("Squad created");
      }
      setModalOpen(false);
      await load();
    } catch {
      message.error("Failed to save");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/squads/${id}`);
      message.success("Squad deleted");
      await load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(detail || "Failed to delete");
    }
  };

  const columns = [
    { title: "Name", dataIndex: "name", key: "name" },
    { title: "Squad ID", dataIndex: "squad_id", key: "squad_id" },
    { title: "External Squad ID", dataIndex: "external_squad_id", key: "external_squad_id" },
    {
      title: "Actions",
      key: "actions",
      width: 120,
      render: (_: unknown, record: SquadProfile) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="Delete this squad profile?" onConfirm={() => handleDelete(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <Typography.Title level={isMobile ? 5 : 4} style={{ margin: 0, color: "rgba(255,255,255,0.88)" }}>
          Squad Profiles
        </Typography.Title>
        <Button icon={<PlusOutlined />} onClick={openCreate}>Add Squad</Button>
      </div>

      <Table
        dataSource={squads}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
      />

      <Modal
        title={editing ? "Edit Squad Profile" : "New Squad Profile"}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        okText="Save"
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input placeholder="e.g. France Pro" />
          </Form.Item>
          <Form.Item name="squad_id" label="Squad ID" rules={[{ required: true }]}>
            <Input placeholder="RemnaWave squad ID" />
          </Form.Item>
          <Form.Item name="external_squad_id" label="External Squad ID" rules={[{ required: true }]}>
            <Input placeholder="External squad ID" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
