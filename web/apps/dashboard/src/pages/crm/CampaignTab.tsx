import { App, Button, Card, Input, Popconfirm, Space, Typography } from "antd";
import { SendOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import ActionsBuilder from "./ActionsBuilder";
import ConditionsBuilder from "./ConditionsBuilder";
import { defaultActions, defaultConditions, getSegmentCondition } from "./helpers";
import { fetchSegments, launchCampaign } from "./api";
import type { CrmAction, CrmCondition, SegmentDef } from "./types";

interface CampaignTabProps {
  onLaunched: () => void;
}

export default function CampaignTab({ onLaunched }: CampaignTabProps) {
  const { message } = App.useApp();
  const [segments, setSegments] = useState<SegmentDef[]>([]);
  const [conditions, setConditions] = useState<CrmCondition[]>([]);
  const [actions, setActions] = useState<CrmAction[]>(defaultActions());
  const [selectedTgIds, setSelectedTgIds] = useState<number[]>([]);
  const [scanTotal, setScanTotal] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSegments()
      .then((segs) => {
        setSegments(segs);
        if (segs.length && !conditions.length) {
          setConditions(defaultConditions(segs[0].id, segs[0]));
        }
      })
      .catch(() => message.error("Не удалось загрузить сегменты"));
  }, [message]);

  const segmentCond = getSegmentCondition(conditions);
  const segmentId = segmentCond?.segment_id ?? null;
  const isAllUsers = segmentId === "all_users";

  const hasEnabledAction = actions.some((a) => a.enabled);

  const launch = async () => {
    if (!segmentId) {
      message.warning("Выберите сегмент");
      return;
    }
    if (!hasEnabledAction) {
      message.warning("Включите хотя бы одно действие");
      return;
    }
    if (!isAllUsers && selectedTgIds.length === 0) {
      message.warning("Выполните сканирование и выберите получателей");
      return;
    }
    setLoading(true);
    try {
      await launchCampaign({
        name: name || undefined,
        conditions,
        actions,
        target_tg_ids: isAllUsers ? undefined : selectedTgIds,
      });
      message.success(
        isAllUsers
          ? `Кампания поставлена в очередь (${scanTotal ?? "все"} пользователей)`
          : `Кампания поставлена в очередь для ${selectedTgIds.length} пользователей`
      );
      setName("");
      setSelectedTgIds([]);
      setScanTotal(null);
      onLaunched();
    } catch {
      message.error("Ошибка запуска кампании");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Input
        placeholder="Название кампании (необязательно)"
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ maxWidth: 480 }}
      />

      <ConditionsBuilder
        conditions={conditions}
        onChange={setConditions}
        segmentTypes={segments}
        selectedTgIds={selectedTgIds}
        onSelectedTgIdsChange={setSelectedTgIds}
        onScanComplete={setScanTotal}
      />

      <ActionsBuilder actions={actions} onChange={setActions} segmentId={segmentId} />

      <Card size="small">
        <Popconfirm
          title="Запустить кампанию?"
          description={`Получателей: ${
            isAllUsers ? scanTotal ?? "все" : selectedTgIds.length
          }`}
          onConfirm={launch}
          okText="Запустить"
          cancelText="Отмена"
          disabled={!segmentId || !hasEnabledAction || (!isAllUsers && !selectedTgIds.length)}
        >
          <Button
            type="primary"
            icon={<SendOutlined />}
            loading={loading}
            disabled={!segmentId || !hasEnabledAction || (!isAllUsers && !selectedTgIds.length)}
          >
            Запустить кампанию
          </Button>
        </Popconfirm>
        {!hasEnabledAction && (
          <Typography.Text type="secondary" style={{ marginLeft: 12 }}>
            Включите хотя бы одно действие
          </Typography.Text>
        )}
      </Card>
    </Space>
  );
}
