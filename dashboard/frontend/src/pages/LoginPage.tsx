import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, Button, Card, message, Typography } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { api, setToken } from "../api/client";

export default function LoginPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { login: string; password: string }) => {
    setLoading(true);
    try {
      const res = await api.post<{ access_token: string }>("/auth/login", values);
      setToken(res.access_token);
      navigate("/", { replace: true });
    } catch {
      message.error("Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        background: "linear-gradient(135deg, #0a0a0f 0%, #0f0f1e 50%, #0a0a0f 100%)",
      }}
    >
      <Card
        style={{
          width: "100%",
          maxWidth: 400,
          background: "#13131d",
          border: "1px solid rgba(255,255,255,0.06)",
          borderTop: "2px solid #4f8cff",
        }}
        styles={{
          body: { padding: "32px 24px 24px" },
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Typography.Title
            level={3}
            style={{
              margin: 0,
              color: "rgba(255,255,255,0.92)",
              fontWeight: 700,
              letterSpacing: 1,
            }}
          >
            XRAY VPN
          </Typography.Title>
          <Typography.Text style={{ color: "rgba(255,255,255,0.4)", fontSize: 13 }}>
            Sign in to dashboard
          </Typography.Text>
        </div>
        <Form onFinish={onFinish} autoComplete="off">
          <Form.Item name="login" rules={[{ required: true, message: "Enter login" }]}>
            <Input prefix={<UserOutlined style={{ color: "rgba(255,255,255,0.3)" }} />} placeholder="Login" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "Enter password" }]}>
            <Input.Password prefix={<LockOutlined style={{ color: "rgba(255,255,255,0.3)" }} />} placeholder="Password" size="large" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              Sign In
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
