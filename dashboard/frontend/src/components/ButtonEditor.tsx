import { useEffect, useState } from "react";
import { Modal, Form, Input, Select, Switch, Typography, Divider } from "antd";
import type { MenuButton, MenuScreen } from "../api/types";
import { api } from "../api/client";

const KNOWN_CALLBACKS = [
  { value: "Premium", label: "Premium — Buy premium menu" },
  { value: "Extend_Month", label: "Extend_Month — Extend subscription" },
  { value: "Others", label: "Others — Instructions" },
  { value: "Free", label: "Free — Free version" },
  { value: "Sub_Info", label: "Sub_Info — Subscription info" },
  { value: "Devices", label: "Devices — Devices list" },
  { value: "Invite_Friends", label: "Invite_Friends — Referral" },
  { value: "Settings", label: "Settings — Settings menu" },
  { value: "Change_Language", label: "Change_Language — Language picker" },
  { value: "Agreement", label: "Agreement — User agreement" },
  { value: "Privacy", label: "Privacy — Privacy policy" },
  { value: "Main", label: "Main — Back to main menu" },
  { value: "Stars_Plans", label: "Stars_Plans — Stars tariffs" },
  { value: "Crypto_Plans", label: "Crypto_Plans — Crypto tariffs" },
  { value: "Crystal_plans", label: "Crystal_plans — Crystal tariffs" },
  { value: "SBP_Apay", label: "SBP_Apay — SBP/Apple Pay tariffs" },
  { value: "Enter_Promo", label: "Enter_Promo — Promo code input" },
  { value: "Migrate_RemnaWave", label: "Migrate_RemnaWave — Migration" },
];

interface ButtonEditorProps {
  open: boolean;
  button: Partial<MenuButton> | null;
  onSave: (values: Partial<MenuButton>) => void;
  onCancel: () => void;
}

export default function ButtonEditor({ open, button, onSave, onCancel }: ButtonEditorProps) {
  const [form] = Form.useForm();
  const [screens, setScreens] = useState<MenuScreen[]>([]);
  const buttonType = Form.useWatch("button_type", form);

  useEffect(() => {
    if (open) {
      api.get<MenuScreen[]>("/menus/screens").then(setScreens).catch(() => {});
    }
  }, [open]);

  const screenOptions = screens.map((s) => ({
    value: `screen:${s.slug}`,
    label: `${s.name} (${s.slug})`,
  }));

  const allCallbackOptions = [
    {
      label: "Open Screen (dynamic)",
      options: screenOptions,
    },
    {
      label: "Bot Handlers (hardcoded)",
      options: KNOWN_CALLBACKS,
    },
  ];

  const handleOk = async () => {
    const values = await form.validateFields();
    onSave({ ...button, ...values });
  };

  return (
    <Modal
      title={button?.id ? "Edit Button" : "New Button"}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={button || {
          text_ru: "",
          text_en: "",
          callback_data: "",
          url: "",
          button_type: "callback",
          is_active: true,
          visibility_condition: "always",
        }}
        preserve={false}
      >
        <Form.Item name="text_ru" label="Text (RU)" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="text_en" label="Text (EN)" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="button_type" label="Type">
          <Select
            options={[
              { value: "callback", label: "Callback" },
              { value: "url", label: "URL" },
              { value: "webapp", label: "WebApp" },
              { value: "tariff", label: "Tariff" },
            ]}
          />
        </Form.Item>

        {buttonType !== "url" && buttonType !== "webapp" && (
          <>
            <Form.Item
              name="callback_data"
              label="Callback Data"
              tooltip="Select a bot handler or a screen from the constructor"
            >
              <Select
                showSearch
                allowClear
                options={allCallbackOptions}
                placeholder="Select handler or screen..."
                filterOption={(input, option) =>
                  (option?.value ?? "").toLowerCase().includes(input.toLowerCase()) ||
                  (option?.label ?? "").toLowerCase().includes(input.toLowerCase())
                }
              />
            </Form.Item>
            <Typography.Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: -16, marginBottom: 12 }}>
              "Open Screen" items use prefix <code>screen:</code> — the bot renders them dynamically from the constructor.
            </Typography.Text>
          </>
        )}

        {(buttonType === "url" || buttonType === "webapp") && (
          <Form.Item name="url" label="URL" rules={[{ required: true }]}>
            <Input placeholder="https://..." />
          </Form.Item>
        )}

        <Form.Item name="visibility_condition" label="Visibility">
          <Select
            options={[
              { value: "always", label: "Always" },
              { value: "show_promo", label: "Show Promo Only" },
            ]}
          />
        </Form.Item>
        <Form.Item name="is_active" label="Active" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}
