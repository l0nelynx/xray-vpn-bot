import { App, Button, Card, Descriptions, Form, InputNumber, Select, Space, Table, Tag, Typography } from "antd";
import type { TableRowSelection } from "antd/es/table/interface";
import { ScanOutlined } from "@ant-design/icons";
import { useState } from "react";
import { api } from "../../api/client";
import { getSegmentCondition, segmentParamDefaults } from "./helpers";
import type { CrmCondition, ScanResult, ScanUser, SegmentDef, SegmentParams } from "./types";
import { USER_TYPE_OPTIONS } from "./types";

interface ConditionsBuilderProps {
  conditions: CrmCondition[];
  onChange: (conditions: CrmCondition[]) => void;
  segmentTypes: SegmentDef[];
  selectedTgIds: number[];
  onSelectedTgIdsChange: (ids: number[]) => void;
  onScanComplete?: (total: number) => void;
}

function SegmentParamField({
  param,
  value,
  onChange,
}: {
  param: SegmentDef["params"][0];
  value?: number | string;
  onChange: (v: number | string) => void;
}) {
  if (param.type === "select") {
    return (
      <Select
        style={{ minWidth: 160 }}
        value={(value as string) ?? (param.default as string)}
        options={param.options}
        onChange={onChange}
      />
    );
  }
  return (
    <InputNumber
      min={param.min}
      max={param.max}
      step={param.type === "float" ? 0.05 : 1}
      value={value as number | undefined}
      onChange={(v) => onChange(v ?? (param.default as number))}
    />
  );
}

export default function ConditionsBuilder({
  conditions,
  onChange,
  segmentTypes,
  selectedTgIds,
  onSelectedTgIdsChange,
  onScanComplete,
}: ConditionsBuilderProps) {
  const { message } = App.useApp();
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);

  const segmentCond = getSegmentCondition(conditions);
  const userTypeCond = conditions.find((c) => c.type === "user_type");
  const segmentDef = segmentTypes.find((s) => s.id === segmentCond?.segment_id);

  const updateSegment = (patch: Partial<CrmCondition>) => {
    onChange(
      conditions.map((c) => (c.type === "segment" ? { ...c, ...patch } : c))
    );
  };

  const updateSegmentParams = (params: SegmentParams) => {
    updateSegment({ params });
  };

  const updateUserType = (value: string) => {
    const has = conditions.some((c) => c.type === "user_type");
    if (has) {
      onChange(
        conditions.map((c) => (c.type === "user_type" ? { ...c, value } : c))
      );
    } else {
      onChange([...conditions, { type: "user_type", value }]);
    }
  };

  const onSegmentIdChange = (segmentId: string) => {
    const seg = segmentTypes.find((s) => s.id === segmentId);
    updateSegment({
      segment_id: segmentId,
      params: seg ? segmentParamDefaults(seg) : {},
    });
    setScanResult(null);
    onSelectedTgIdsChange([]);
  };

  const runScan = async () => {
    if (!segmentCond?.segment_id) {
      message.warning("Выберите сегмент");
      return;
    }
    setScanning(true);
    setScanResult(null);
    try {
      const res = await api.post<ScanResult>("/crm/conditions/evaluate", {
        conditions,
      });
      setScanResult(res);
      onSelectedTgIdsChange(res.users.map((u) => u.tg_id));
      onScanComplete?.(res.total);
      if (res.warning) message.warning(res.warning);
    } catch {
      message.error("Ошибка сканирования");
    } finally {
      setScanning(false);
    }
  };

  const rowSelection: TableRowSelection<ScanUser> = {
    selectedRowKeys: selectedTgIds,
    onChange: (keys) => onSelectedTgIdsChange(keys as number[]),
  };

  const columns = [
    { title: "TG ID", dataIndex: "tg_id", key: "tg_id", width: 120 },
    {
      title: "Username",
      dataIndex: "username",
      key: "username",
      render: (v: string | null) => v ?? "—",
    },
    {
      title: "Метрики",
      key: "meta",
      render: (_: unknown, row: ScanUser) => {
        const m = row.meta || {};
        const parts: string[] = [];
        if (m.status) parts.push(`status: ${m.status}`);
        if (m.days_left !== undefined) parts.push(`дней: ${m.days_left}`);
        if (m.traffic_percent !== undefined) parts.push(`трафик: ${m.traffic_percent}%`);
        return parts.length ? parts.join(", ") : "—";
      },
    },
  ];

  return (
    <Card title="1. Условия" size="small" style={{ marginBottom: 16 }}>
      <Space direction="vertical" style={{ width: "100%" }} size={12}>
        <Form layout="vertical">
          <Form.Item label="1.1 Сегмент" required>
            <Select
              placeholder="Выберите сегмент"
              value={segmentCond?.segment_id}
              onChange={onSegmentIdChange}
              options={segmentTypes.map((s) => ({ value: s.id, label: s.title }))}
              style={{ maxWidth: 400 }}
            />
          </Form.Item>

          {segmentDef && segmentDef.params.filter((p) => p.name !== "user_type").length > 0 && (
            <Form.Item label="Параметры сегмента">
              <Space wrap>
                {segmentDef.params
                  .filter((p) => p.name !== "user_type")
                  .map((p) => (
                    <Form.Item key={p.name} label={p.label} style={{ marginBottom: 0 }}>
                      <SegmentParamField
                        param={p}
                        value={segmentCond?.params?.[p.name]}
                        onChange={(v) =>
                          updateSegmentParams({
                            ...(segmentCond?.params || {}),
                            [p.name]: v,
                          })
                        }
                      />
                    </Form.Item>
                  ))}
              </Space>
            </Form.Item>
          )}

          <Form.Item label="1.2 Тип пользователя">
            <Select
              style={{ maxWidth: 240 }}
              value={userTypeCond?.value ?? "all"}
              options={USER_TYPE_OPTIONS}
              onChange={updateUserType}
            />
          </Form.Item>
        </Form>

        <Button type="primary" icon={<ScanOutlined />} loading={scanning} onClick={runScan}>
          Preview / сканирование
        </Button>

        {scanResult && (
          <>
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="Всего в сегменте">
                <Tag color="blue">{scanResult.total}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="В превью">
                {scanResult.users.length}
                {scanResult.total > scanResult.users.length && " (первые 500)"}
              </Descriptions.Item>
            </Descriptions>
            {scanResult.users.length > 0 && (
              <>
                <Typography.Text type="secondary">
                  1.3 Ручной отбор (опционально) — {selectedTgIds.length} выбрано
                </Typography.Text>
                <Table
                  rowKey="tg_id"
                  rowSelection={rowSelection}
                  columns={columns}
                  dataSource={scanResult.users}
                  size="small"
                  pagination={{ pageSize: 10, showSizeChanger: false }}
                  scroll={{ y: 240 }}
                />
              </>
            )}
          </>
        )}
      </Space>
    </Card>
  );
}
