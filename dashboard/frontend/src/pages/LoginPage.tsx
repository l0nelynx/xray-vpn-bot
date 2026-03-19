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
        background: "#141414",
      }}
    >
      <Card style={{ width: 380 }}>
        <Typography.Title level={3} style={{ textAlign: "center", marginBottom: 24 }}>
          XRAY VPN Dashboard
        </Typography.Title>
        <Form onFinish={onFinish} autoComplete="off">
          <Form.Item name="login" rules={[{ required: true, message: "Enter login" }]}>
            <Input prefix={<UserOutlined />} placeholder="Login" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "Enter password" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              Sign In
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
