import { useEffect, useState } from "react";
import { Card, Form, Switch, Typography, App, Spin } from "antd";

const API_BASE = "/bot/dashboard/api/settings/features";

interface FeatureFlags {
  legacy_bot_constructor: boolean;
}

async function fetchFlags(): Promise<FeatureFlags> {
  const token = localStorage.getItem("token");
  const res = await fetch(API_BASE, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Failed to load settings");
  return res.json();
}

async function saveFlags(flags: FeatureFlags): Promise<void> {
  const token = localStorage.getItem("token");
  const res = await fetch(API_BASE, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(flags),
  });
  if (!res.ok) throw new Error("Failed to save settings");
}

export default function WebAppSettingsPage() {
  const { message } = App.useApp();
  const [flags, setFlags] = useState<FeatureFlags | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchFlags()
      .then(setFlags)
      .catch(() => message.error("Failed to load settings"));
  }, []);

  async function handleToggle(value: boolean) {
    if (!flags) return;
    const updated = { ...flags, legacy_bot_constructor: value };
    setSaving(true);
    try {
      await saveFlags(updated);
      setFlags(updated);
      message.success(
        value
          ? "Legacy bot constructor enabled. Restart the bot to apply."
          : "Legacy bot constructor disabled. Restart the bot to apply."
      );
    } catch {
      message.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <Typography.Title level={3}>WebApp Settings</Typography.Title>

      {flags === null ? (
        <Spin />
      ) : (
        <Card title="Bot Feature Flags">
          <Form layout="vertical">
            <Form.Item
              label="Legacy Bot Constructor"
              help={
                flags.legacy_bot_constructor
                  ? "In-bot tariff menus and inline payments are active. Users can pay directly in Telegram."
                  : "Disabled — the bot directs users to the MiniApp for all purchases. Restart the bot after changing."
              }
            >
              <Switch
                checked={flags.legacy_bot_constructor}
                onChange={handleToggle}
                loading={saving}
                checkedChildren="ON"
                unCheckedChildren="OFF"
              />
            </Form.Item>
          </Form>
        </Card>
      )}
    </div>
  );
}
