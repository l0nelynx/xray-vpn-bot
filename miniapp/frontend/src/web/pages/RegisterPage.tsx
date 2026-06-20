import { Alert, Button, Card, Form, Input, Space, Spin, Tag, Typography } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  GiftOutlined,
  LockOutlined,
  MailOutlined,
  KeyOutlined,
} from "@ant-design/icons";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, auth, invite, ValidateInviteResponse } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useLang } from "../locale";
import BrandLogo from "../components/BrandLogo";
import { BRAND_NAME } from "../branding";

const { Title, Text } = Typography;

interface InviteStatus {
  checked: boolean;
  valid: boolean | null;
  data: ValidateInviteResponse | null;
  checking: boolean;
}

export default function RegisterPage() {
  const { setUserAfterRegister } = useAuth();
  const { L } = useLang();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inviteStatus, setInviteStatus] = useState<InviteStatus>({
    checked: false, valid: null, data: null, checking: false,
  });
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function onInviteChange(e: React.ChangeEvent<HTMLInputElement>) {
    const code = e.target.value.trim().toUpperCase();
    if (!code) {
      setInviteStatus({ checked: false, valid: null, data: null, checking: false });
      return;
    }
    if (code.length < 4) return;
    setInviteStatus((s) => ({ ...s, checking: true }));
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(async () => {
      try {
        const result = await invite.validate(code);
        setInviteStatus({ checked: true, valid: result.valid, data: result, checking: false });
      } catch (e) {
        if (e instanceof ApiError && (e.status === 429 || e.code === "rate_limited")) {
          setError(L.err_rate_limited);
        }
        setInviteStatus({ checked: true, valid: false, data: null, checking: false });
      }
    }, 600);
  }

  useEffect(() => {
    return () => { if (debounceTimer.current) clearTimeout(debounceTimer.current); };
  }, []);

  async function onFinish(values: { email: string; password: string; confirm: string; invite_code: string }) {
    if (!inviteStatus.valid) { setError(L.err_req_invite); return; }
    setLoading(true);
    setError(null);
    try {
      const resp = await auth.register(
        values.email.trim().toLowerCase(),
        values.password,
        values.invite_code.trim().toUpperCase()
      );
      setUserAfterRegister(resp.user, resp.tokens);
      navigate("/verify-email", { replace: true });
    } catch (e) {
      if (e instanceof ApiError) {
        const map: Record<string, string> = {
          email_taken: L.err_email_taken,
          invalid_invite: L.err_invalid_invite,
          rate_limited: L.err_rate_limited,
          http_429: L.err_rate_limited,
        };
        setError(map[e.code] || L.err_reg);
      } else {
        setError(L.err_network);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0B0B14", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ position: "fixed", top: "20%", left: "50%", transform: "translateX(-50%)", width: 600, height: 400, background: "radial-gradient(ellipse, rgba(6,214,160,0.07) 0%, transparent 70%)", pointerEvents: "none" }} />

      <div style={{ width: "100%", maxWidth: 440, position: "relative" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Link to="/" style={{ textDecoration: "none" }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
              <BrandLogo size={38} />
              <Text strong style={{ fontSize: 20, color: "#fff" }}>{BRAND_NAME}</Text>
            </div>
          </Link>
        </div>

        <Card
          style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 20 }}
          styles={{ body: { padding: 36 } }}
        >
          <Title level={3} style={{ color: "#fff", margin: "0 0 8px", textAlign: "center" }}>
            {L.reg_title}
          </Title>
          <Text style={{ color: "rgba(255,255,255,0.5)", display: "block", textAlign: "center", marginBottom: 28, fontSize: 14 }}>
            {L.reg_subtitle}
          </Text>

          {error && (
            <Alert type="error" message={error} style={{ marginBottom: 20, borderRadius: 10 }} showIcon closable onClose={() => setError(null)} />
          )}

          {inviteStatus.valid && inviteStatus.data?.discount_percent && (
            <Alert
              type="success"
              icon={<GiftOutlined />}
              message={
                <Space>
                  <span>{L.discount_accepted}</span>
                  <Tag color="green">{L.discount_text(inviteStatus.data.discount_percent)}</Tag>
                </Space>
              }
              style={{ marginBottom: 20, borderRadius: 10 }}
              showIcon
            />
          )}

          <Form layout="vertical" form={form} onFinish={onFinish} size="large">
            <Form.Item
              name="invite_code"
              label={<Text style={{ color: "rgba(255,255,255,0.75)" }}>{L.invite_label}</Text>}
              rules={[{ required: true, message: L.val_invite_req }]}
              validateStatus={inviteStatus.checking ? "validating" : inviteStatus.checked ? (inviteStatus.valid ? "success" : "error") : ""}
              help={
                inviteStatus.checking ? (
                  <Space><Spin size="small" /><span style={{ color: "rgba(255,255,255,0.4)", fontSize: 12 }}>{L.invite_checking}</span></Space>
                ) : inviteStatus.checked && !inviteStatus.valid ? (
                  <Space style={{ color: "#ff7875" }}><CloseCircleOutlined /><span>{L.invite_invalid}</span></Space>
                ) : inviteStatus.valid ? (
                  <Space style={{ color: "#52c41a" }}><CheckCircleOutlined /><span>{L.invite_valid}</span></Space>
                ) : null
              }
            >
              <Input
                prefix={<KeyOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder={L.invite_placeholder}
                onChange={onInviteChange}
                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", borderRadius: 12, textTransform: "uppercase", letterSpacing: "1px" }}
                maxLength={20}
              />
            </Form.Item>

            <Form.Item
              name="email"
              label={<Text style={{ color: "rgba(255,255,255,0.75)" }}>Email</Text>}
              rules={[{ required: true, message: L.val_email_req }, { type: "email", message: L.val_email_format }]}
            >
              <Input
                prefix={<MailOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder="your@email.com"
                autoComplete="email"
                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", borderRadius: 12 }}
              />
            </Form.Item>

            <Form.Item
              name="password"
              label={<Text style={{ color: "rgba(255,255,255,0.75)" }}>{L.pwd_label}</Text>}
              rules={[{ required: true, message: L.val_pwd_req }, { min: 8, message: L.val_pwd_min }]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder={L.pwd_placeholder}
                autoComplete="new-password"
                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", borderRadius: 12 }}
              />
            </Form.Item>

            <Form.Item
              name="confirm"
              label={<Text style={{ color: "rgba(255,255,255,0.75)" }}>{L.confirm_label}</Text>}
              dependencies={["password"]}
              rules={[
                { required: true, message: L.val_confirm_req },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue("password") === value) return Promise.resolve();
                    return Promise.reject(new Error(L.val_confirm_match));
                  },
                }),
              ]}
              style={{ marginBottom: 24 }}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder={L.confirm_placeholder}
                autoComplete="new-password"
                style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", borderRadius: 12 }}
              />
            </Form.Item>

            <Button
              type="primary"
              htmlType="submit"
              block
              loading={loading}
              disabled={!inviteStatus.valid}
              style={{
                background: inviteStatus.valid ? "linear-gradient(135deg, #06D6A0, #0096C7)" : "rgba(255,255,255,0.1)",
                border: "none", height: 48, borderRadius: 12, fontSize: 16, fontWeight: 600,
              }}
            >
              {L.btn_create}
            </Button>
          </Form>

          <div style={{ textAlign: "center", marginTop: 24 }}>
            <Text style={{ color: "rgba(255,255,255,0.35)", fontSize: 12 }}>
              {L.have_account}{" "}
              <Link to="/login" style={{ color: "#06D6A0" }}>{L.sign_in}</Link>
            </Text>
          </div>
        </Card>
      </div>
    </div>
  );
}
