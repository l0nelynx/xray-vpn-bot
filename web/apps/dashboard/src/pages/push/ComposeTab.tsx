import {
  Alert,
  App,
  Button,
  Card,
  Form,
  Input,
  Popconfirm,
  Radio,
  Space,
  Typography,
} from "antd";
import { SendOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import { ApiError } from "../../api/client";
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
  const { message } = App.useApp();
  const isMobile = useIsMobile();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [tokenCount, setTokenCount] = useState<number | null>(null);
  const [fcmConfigured, setFcmConfigured] = useState(true);
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const audience: PushAudience = Form.useWatch("audience", form) ?? "all_tokens";

  const loadStats = useCallback(async () => {
    try {
      const stats = await fetchPushStats();
      setTokenCount(stats.token_count);
      setFcmConfigured(stats.fcm_configured);
    } catch {
      message.error("Failed to load push stats");
    }
  }, [message]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const runPreview = async () => {
    setPreviewLoading(true);
    try {
      const values = await form.validateFields(["audience", "user_ids"]);
      const userIds =
        values.audience === "user_ids" ? parseUserIds(values.user_ids || "") : undefined;
      if (values.audience === "user_ids" && (!userIds || userIds.length === 0)) {
        message.warning("Enter at least one user id");
        return;
      }
      const res = await previewPushCount({
        audience: values.audience,
        user_ids: userIds,
      });
      setPreviewCount(res.count);
    } catch (err) {
      if (err instanceof ApiError) {
        message.error(err.message || "Preview failed");
      }
    } finally {
      setPreviewLoading(false);
    }
  };

  const send = async () => {
    setLoading(true);
    try {
      const values = await form.validateFields();
      let data: Record<string, string> | undefined;
      try {
        data = parseDataJson(values.data_json || "");
      } catch {
        message.error("Data JSON is invalid — use an object like {\"screen\":\"home\"}");
        return;
      }
      const userIds =
        values.audience === "user_ids" ? parseUserIds(values.user_ids || "") : undefined;
      if (values.audience === "user_ids" && (!userIds || userIds.length === 0)) {
        message.warning("Enter at least one user id");
        return;
      }
      await launchPush({
        title: values.title.trim(),
        body: values.body.trim(),
        data,
        audience: values.audience,
        user_ids: userIds,
      });
      message.success("Push campaign queued");
      form.resetFields(["title", "body", "data_json", "user_ids"]);
      form.setFieldsValue({ audience: "all_tokens" });
      setPreviewCount(null);
      onLaunched();
      loadStats();
    } catch (err) {
      if (err instanceof ApiError) {
        message.error(err.detail || err.message || "Launch failed");
      } else if (err && typeof err === "object" && "errorFields" in err) {
        // antd validation
      } else {
        message.error("Launch failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card size="small" styles={{ body: { padding: isMobile ? 12 : 16 } }}>
      {!fcmConfigured && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="FCM is not configured"
          description="Set fcm_project_id and fcm_service_account_path in config.yml (readable by dashboard and crm-worker)."
        />
      )}
      <Typography.Paragraph type="secondary" style={{ marginBottom: 16 }}>
        Registered FCM tokens:{" "}
        <Typography.Text strong>
          {tokenCount === null ? "…" : tokenCount}
        </Typography.Text>
      </Typography.Paragraph>

      <Form
        form={form}
        layout="vertical"
        initialValues={{ audience: "all_tokens", title: "", body: "", data_json: "", user_ids: "" }}
      >
        <Form.Item
          name="title"
          label="Title"
          rules={[{ required: true, message: "Title is required" }]}
        >
          <Input maxLength={200} placeholder="Notification title" />
        </Form.Item>
        <Form.Item
          name="body"
          label="Body"
          rules={[{ required: true, message: "Body is required" }]}
        >
          <Input.TextArea rows={4} maxLength={4000} placeholder="Notification body" />
        </Form.Item>
        <Form.Item
          name="data_json"
          label="Data JSON (optional)"
          tooltip='Extra key/value pairs for the app, e.g. {"screen":"support"}'
        >
          <Input.TextArea rows={2} placeholder='{"screen":"home"}' />
        </Form.Item>
        <Form.Item name="audience" label="Audience">
          <Radio.Group>
            <Radio.Button value="all_tokens">All with FCM</Radio.Button>
            <Radio.Button value="user_ids">User IDs</Radio.Button>
          </Radio.Group>
        </Form.Item>
        {audience === "user_ids" && (
          <Form.Item
            name="user_ids"
            label="User IDs"
            rules={[{ required: true, message: "Enter user ids" }]}
            extra="Comma or newline separated internal user ids"
          >
            <Input.TextArea rows={3} placeholder="1, 2, 3" />
          </Form.Item>
        )}

        <Space wrap style={{ marginBottom: 12 }}>
          <Button onClick={runPreview} loading={previewLoading}>
            Preview count
          </Button>
          {previewCount !== null && (
            <Typography.Text type="secondary">
              Will reach <Typography.Text strong>{previewCount}</Typography.Text> device
              {previewCount === 1 ? "" : "s"}
            </Typography.Text>
          )}
        </Space>

        <div>
          <Popconfirm
            title="Send this push now?"
            description="The campaign will be queued and delivered via FCM."
            onConfirm={send}
            okText="Send"
            disabled={!fcmConfigured}
          >
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={loading}
              disabled={!fcmConfigured}
            >
              Send push
            </Button>
          </Popconfirm>
        </div>
      </Form>
    </Card>
  );
}
