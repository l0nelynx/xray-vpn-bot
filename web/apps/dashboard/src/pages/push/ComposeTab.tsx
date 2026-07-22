import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Send, TriangleAlert } from "lucide-react";
import { Card, CardContent } from "@xray/ui/components/card";
import { Button } from "@xray/ui/components/button";
import { Input } from "@xray/ui/components/input";
import { Textarea } from "@xray/ui/components/textarea";
import { Label } from "@xray/ui/components/label";
import { Alert, AlertDescription, AlertTitle } from "@xray/ui/components/alert";
import { cn } from "@xray/ui/lib/utils";
import { ApiError } from "../../api/client";
import ConfirmButton from "../../components/ConfirmButton";
import { fetchPushStats, launchPush, previewPushCount, type PushAudience } from "./api";

interface ComposeTabProps {
  onLaunched: () => void;
}

function parseUserIds(raw: string): number[] {
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0);
}

function parseDataJson(raw: string): Record<string, string> | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const parsed = JSON.parse(trimmed) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Data must be a JSON object");
  }
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
    if (v == null) continue;
    out[String(k)] = typeof v === "string" ? v : String(v);
  }
  return out;
}

export default function ComposeTab({ onLaunched }: ComposeTabProps) {
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [tokenCount, setTokenCount] = useState<number | null>(null);
  const [fcmConfigured, setFcmConfigured] = useState(true);
  const [previewCount, setPreviewCount] = useState<number | null>(null);

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [dataJson, setDataJson] = useState("");
  const [audience, setAudience] = useState<PushAudience>("all_tokens");
  const [userIdsRaw, setUserIdsRaw] = useState("");

  const loadStats = useCallback(async () => {
    try {
      const stats = await fetchPushStats();
      setTokenCount(stats.token_count);
      setFcmConfigured(stats.fcm_configured);
    } catch {
      toast.error("Failed to load push stats");
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const runPreview = async () => {
    setPreviewLoading(true);
    try {
      const userIds = audience === "user_ids" ? parseUserIds(userIdsRaw) : undefined;
      if (audience === "user_ids" && (!userIds || userIds.length === 0)) {
        toast.warning("Enter at least one user id");
        return;
      }
      const res = await previewPushCount({ audience, user_ids: userIds });
      setPreviewCount(res.count);
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.message || "Preview failed");
      }
    } finally {
      setPreviewLoading(false);
    }
  };

  const send = async () => {
    if (!title.trim()) {
      toast.warning("Title is required");
      return;
    }
    if (!body.trim()) {
      toast.warning("Body is required");
      return;
    }
    setLoading(true);
    try {
      let data: Record<string, string> | undefined;
      try {
        data = parseDataJson(dataJson);
      } catch {
        toast.error('Data JSON is invalid — use an object like {"screen":"home"}');
        return;
      }
      const userIds = audience === "user_ids" ? parseUserIds(userIdsRaw) : undefined;
      if (audience === "user_ids" && (!userIds || userIds.length === 0)) {
        toast.warning("Enter at least one user id");
        return;
      }
      await launchPush({
        title: title.trim(),
        body: body.trim(),
        data,
        audience,
        user_ids: userIds,
      });
      toast.success("Push campaign queued");
      setTitle("");
      setBody("");
      setDataJson("");
      setUserIdsRaw("");
      setAudience("all_tokens");
      setPreviewCount(null);
      onLaunched();
      loadStats();
    } catch (err) {
      if (err instanceof ApiError) {
        toast.error(err.detail || err.message || "Launch failed");
      } else {
        toast.error("Launch failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        {!fcmConfigured && (
          <Alert variant="warning">
            <TriangleAlert className="h-4 w-4" />
            <AlertTitle>FCM is not configured</AlertTitle>
            <AlertDescription>
              Set fcm_project_id and fcm_service_account_path in config.yml (readable by dashboard
              and crm-worker).
            </AlertDescription>
          </Alert>
        )}
        <p className="text-sm text-muted-foreground">
          Registered FCM tokens:{" "}
          <span className="font-semibold text-foreground">
            {tokenCount === null ? "…" : tokenCount}
          </span>
        </p>

        <div className="space-y-1.5">
          <Label>Title *</Label>
          <Input
            maxLength={200}
            placeholder="Notification title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Body *</Label>
          <Textarea
            rows={4}
            maxLength={4000}
            placeholder="Notification body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Data JSON (optional)</Label>
          <Textarea
            rows={2}
            placeholder='{"screen":"home"}'
            value={dataJson}
            onChange={(e) => setDataJson(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Extra key/value pairs for the app, e.g. {'{"screen":"support"}'}
          </p>
        </div>
        <div className="space-y-1.5">
          <Label>Audience</Label>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={audience === "all_tokens" ? "default" : "outline"}
              onClick={() => setAudience("all_tokens")}
            >
              All with FCM
            </Button>
            <Button
              type="button"
              variant={audience === "user_ids" ? "default" : "outline"}
              onClick={() => setAudience("user_ids")}
            >
              User IDs
            </Button>
          </div>
        </div>
        {audience === "user_ids" && (
          <div className="space-y-1.5">
            <Label>User IDs *</Label>
            <Textarea
              rows={3}
              placeholder="1, 2, 3"
              value={userIdsRaw}
              onChange={(e) => setUserIdsRaw(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Comma or newline separated internal user ids
            </p>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={runPreview} disabled={previewLoading}>
            Preview count
          </Button>
          {previewCount !== null && (
            <span className="text-sm text-muted-foreground">
              Will reach <span className="font-semibold text-foreground">{previewCount}</span> device
              {previewCount === 1 ? "" : "s"}
            </span>
          )}
        </div>

        <div>
          <ConfirmButton
            title="Send this push now?"
            description="The campaign will be queued and delivered via FCM."
            confirmText="Send"
            onConfirm={send}
          >
            <Button className={cn(!fcmConfigured && "pointer-events-none opacity-50")} disabled={!fcmConfigured || loading}>
              <Send className="h-4 w-4" />
              Send push
            </Button>
          </ConfirmButton>
        </div>
      </CardContent>
    </Card>
  );
}
