import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Send } from "lucide-react";
import { Card, CardContent } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import ActionsBuilder from "./ActionsBuilder";
import ConditionsBuilder from "./ConditionsBuilder";
import ConfirmButton from "../../components/ConfirmButton";
import { defaultActions, defaultConditions, getSegmentCondition } from "./helpers";
import { fetchSegments, launchCampaign } from "./api";
import type { CrmAction, CrmCondition, SegmentDef } from "./types";

interface CampaignTabProps {
  onLaunched: () => void;
}

export default function CampaignTab({ onLaunched }: CampaignTabProps) {
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
      .catch(() => toast.error("Failed to load segments"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const segmentCond = getSegmentCondition(conditions);
  const segmentId = segmentCond?.segment_id ?? null;
  const isAllUsers = segmentId === "all_users";

  const hasEnabledAction = actions.some((a) => a.enabled);
  const canLaunch = !!segmentId && hasEnabledAction && (isAllUsers || selectedTgIds.length > 0);

  const launch = async () => {
    if (!segmentId) {
      toast.warning("Select a segment");
      return;
    }
    if (!hasEnabledAction) {
      toast.warning("Enable at least one action");
      return;
    }
    if (!isAllUsers && selectedTgIds.length === 0) {
      toast.warning("Run a scan and select recipients");
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
      toast.success(
        isAllUsers
          ? `Campaign queued (${scanTotal ?? "all"} users)`
          : `Campaign queued for ${selectedTgIds.length} users`,
      );
      setName("");
      setSelectedTgIds([]);
      setScanTotal(null);
      onLaunched();
    } catch {
      toast.error("Failed to launch campaign");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Input
        placeholder="Campaign name (optional)"
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="max-w-full md:max-w-[480px]"
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

      <Card>
        <CardContent className="space-y-2 p-4">
          <ConfirmButton
            title="Launch campaign?"
            description={`Recipients: ${isAllUsers ? scanTotal ?? "all" : selectedTgIds.length}`}
            confirmText="Launch"
            onConfirm={launch}
          >
            <Button className="w-full md:w-auto" disabled={!canLaunch || loading}>
              <Send className="h-4 w-4" />
              Launch campaign
            </Button>
          </ConfirmButton>
          {!hasEnabledAction && (
            <p className="text-sm text-muted-foreground">Enable at least one action</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
