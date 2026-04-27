import { Alert, Button, Form, Input, Space, Typography } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TicketDetail } from "../api/client";

interface FormValues {
  subject: string;
  message: string;
}

export default function SupportCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (values: FormValues) => {
    setError(null);
    setSubmitting(true);
    try {
      const t = await api.post<TicketDetail>("/support/tickets", {
        subject: values.subject.trim(),
        message: values.message.trim(),
      });
      navigate(`/support/${t.id}`, { replace: true });
    } catch (e: any) {
      setError(e?.detail || String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="page">
      <Typography.Title level={3} style={{ marginBottom: 20 }}>
        Новое обращение
      </Typography.Title>

      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} />}

      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item
          label="Тема"
          name="subject"
          rules={[
            { required: true, message: "Введите тему" },
            { max: 200, message: "Не более 200 символов" },
          ]}
        >
          <Input placeholder="Тема обращения" maxLength={200} />
        </Form.Item>

        <Form.Item
          label="Сообщение"
          name="message"
          rules={[
            { required: true, message: "Опишите проблему" },
            { max: 4000, message: "Не более 4000 символов" },
          ]}
        >
          <Input.TextArea
            placeholder="Опишите проблему"
            rows={6}
            maxLength={4000}
            showCount
          />
        </Form.Item>

        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Button type="primary" size="large" block htmlType="submit" loading={submitting}>
            Отправить
          </Button>
          <Button size="large" block onClick={() => navigate(-1)}>
            Отмена
          </Button>
        </Space>
      </Form>
    </div>
  );
}
