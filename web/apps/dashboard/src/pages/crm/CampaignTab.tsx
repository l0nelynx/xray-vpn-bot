import { App, Button, Card, Input, Popconfirm, Space, Typography } from "antd";
import { SendOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
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
  const isMobile = useIsMobile();
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
      .catch(() => message.error("Failed to load segments"));
  }, [message]);

  const segmentCond = getSegmentCondition(conditions);
  const segmentId = segmentCond?.segment_id ?? null;
  const isAllUsers = segmentId === "all_users";

  const hasEnabledAction = actions.some((a) => a.enabled);

  const launch = async () => {
    if (!segmentId) {
      message.warning("Select a segment");
      return;
    }
    if (!hasEnabledAction) {
      message.warning("Enable at least one action");
      return;
    }
    if (!isAllUsers && selectedTgIds.length === 0) {
      message.warning("Run a scan and select recipients");
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
          ? `Campaign queued (${scanTotal ?? "all"} users)`
          : `Campaign queued for ${selectedTgIds.length} users`
      );
      setName("");
      setSelectedTgIds([]);
      setScanTotal(null);
      onLaunched();
    } catch {
      message.error("Failed to launch campaign");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Input
        placeholder="Campaign name (optional)"
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ width: "100%", maxWidth: isMobile ? undefined : 480 }}
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
        <Space direction="vertical" style={{ width: "100%" }} size={8}>
          <Popconfirm
            title="Launch campaign?"
            description={`Recipients: ${
              isAllUsers ? scanTotal ?? "all" : selectedTgIds.length
            }`}
            onConfirm={launch}
            okText="Launch"
            cancelText="Cancel"
            disabled={!segmentId || !hasEnabledAction || (!isAllUsers && !selectedTgIds.length)}
          >
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={loading}
              disabled={!segmentId || !hasEnabledAction || (!isAllUsers && !selectedTgIds.length)}
              block={isMobile}
            >
              Launch campaign
            </Button>
          </Popconfirm>
          {!hasEnabledAction && (
            <Typography.Text type="secondary">
              Enable at least one action
            </Typography.Text>
          )}
        </Space>
      </Card>
    </Space>
  );
}
