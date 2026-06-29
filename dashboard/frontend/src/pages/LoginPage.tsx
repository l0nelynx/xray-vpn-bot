import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Form, Input, Button, App } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { api, setToken } from "../api/client";

export default function LoginPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
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
        padding: 24,
        background: "#0C0F1A",
      }}
    >
      <div style={{ width: "100%", maxWidth: 360 }}>
        {/* Logo mark */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 14,
              background: "linear-gradient(135deg, #6C8EFF, #A78BFF)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              fontWeight: 700,
              color: "#fff",
              marginBottom: 16,
              boxShadow: "0 8px 24px rgba(108, 142, 255, 0.30)",
            }}
          >
            VP
          </div>
          <div
            style={{
              fontSize: 20,
              fontWeight: 700,
              color: "#E2E8F8",
              letterSpacing: -0.3,
              marginBottom: 6,
            }}
          >
            VPN Admin
          </div>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.35)" }}>
            Sign in to continue
          </div>
        </div>

        {/* Card */}
        <div
          style={{
            background: "#111827",
            border: "1px solid #1E2540",
            borderRadius: 14,
            padding: "28px 24px",
          }}
        >
          <Form onFinish={onFinish} autoComplete="off" size="large">
            <Form.Item
              name="login"
              style={{ marginBottom: 12 }}
              rules={[{ required: true, message: "Enter login" }]}
            >
              <Input
                prefix={<UserOutlined style={{ color: "rgba(255,255,255,0.22)", fontSize: 14 }} />}
                placeholder="Login"
              />
            </Form.Item>
            <Form.Item
              name="password"
              style={{ marginBottom: 20 }}
              rules={[{ required: true, message: "Enter password" }]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: "rgba(255,255,255,0.22)", fontSize: 14 }} />}
                placeholder="Password"
              />
            </Form.Item>
            <Form.Item style={{ marginBottom: 0 }}>
              <Button type="primary" htmlType="submit" loading={loading} block>
                Sign In
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>
    </div>
  );
}
