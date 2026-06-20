import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  GiftOutlined,
  LockOutlined,
  MailOutlined,
  KeyOutlined,
} from "@ant-design/icons";
import CheezyLogo from "../components/CheezyLogo";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, auth, invite, ValidateInviteResponse } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const { Title, Text } = Typography;

const ERROR_MESSAGES: Record<string, string> = {
  email_taken: "Этот email уже зарегистрирован",
  invalid_invite: "Код приглашения недействителен",
  rate_limited: "Слишком много попыток. Подождите и попробуйте снова",
  http_429: "Слишком много запросов. Подождите немного",
};

interface InviteStatus {
  checked: boolean;
  valid: boolean | null;
  data: ValidateInviteResponse | null;
  checking: boolean;
}

export default function RegisterPage() {
  const { setUserAfterRegister } = useAuth();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inviteStatus, setInviteStatus] = useState<InviteStatus>({
    checked: false,
    valid: null,
    data: null,
    checking: false,
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
          setError("Слишком много проверок кода. Подождите минуту.");
        }
        setInviteStatus({ checked: true, valid: false, data: null, checking: false });
      }
    }, 600);
  }

  useEffect(() => {
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, []);

  async function onFinish(values: {
    email: string;
    password: string;
    confirm: string;
    invite_code: string;
  }) {
    if (!inviteStatus.valid) {
      setError("Введите действительный код приглашения");
      return;
    }
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
        setError(ERROR_MESSAGES[e.code] || "Ошибка регистрации. Попробуйте снова.");
      } else {
        setError("Ошибка сети. Проверьте соединение.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0B0B14",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          position: "fixed",
          top: "20%",
          left: "50%",
          transform: "translateX(-50%)",
          width: 600,
          height: 400,
          background: "radial-gradient(ellipse, rgba(6,214,160,0.07) 0%, transparent 70%)",
          pointerEvents: "none",
        }}
      />

      <div style={{ width: "100%", maxWidth: 440, position: "relative" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Link to="/" style={{ textDecoration: "none" }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
              <CheezyLogo size={38} />
              <Text strong style={{ fontSize: 20, color: "#fff" }}>
                Cheeze Networks
              </Text>
            </div>
          </Link>
        </div>

        <Card
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 20,
          }}
          styles={{ body: { padding: 36 } }}
        >
          <Title level={3} style={{ color: "#fff", margin: "0 0 8px", textAlign: "center" }}>
            Регистрация
          </Title>
          <Text
            style={{
              color: "rgba(255,255,255,0.5)",
              display: "block",
              textAlign: "center",
              marginBottom: 28,
              fontSize: 14,
            }}
          >
            Для регистрации необходим код приглашения
          </Text>

          {error && (
            <Alert
              type="error"
              message={error}
              style={{ marginBottom: 20, borderRadius: 10 }}
              showIcon
              closable
              onClose={() => setError(null)}
            />
          )}

          {/* Invite discount banner */}
          {inviteStatus.valid && inviteStatus.data?.discount_percent && (
            <Alert
              type="success"
              icon={<GiftOutlined />}
              message={
                <Space>
                  <span>Код принят!</span>
                  <Tag color="green">
                    Скидка {inviteStatus.data.discount_percent}% на первую оплату
                  </Tag>
                </Space>
              }
              style={{ marginBottom: 20, borderRadius: 10 }}
              showIcon
            />
          )}

          <Form layout="vertical" form={form} onFinish={onFinish} size="large">
            {/* Invite code — first and prominent */}
            <Form.Item
              name="invite_code"
              label={
                <Text style={{ color: "rgba(255,255,255,0.75)" }}>Код приглашения</Text>
              }
              rules={[{ required: true, message: "Введите код приглашения" }]}
              validateStatus={
                inviteStatus.checking
                  ? "validating"
                  : inviteStatus.checked
                  ? inviteStatus.valid
                    ? "success"
                    : "error"
                  : ""
              }
              help={
                inviteStatus.checking ? (
                  <Space>
                    <Spin size="small" />
                    <span style={{ color: "rgba(255,255,255,0.4)", fontSize: 12 }}>
                      Проверка кода…
                    </span>
                  </Space>
                ) : inviteStatus.checked && !inviteStatus.valid ? (
                  <Space style={{ color: "#ff7875" }}>
                    <CloseCircleOutlined />
                    <span>Недействительный код</span>
                  </Space>
                ) : inviteStatus.valid ? (
                  <Space style={{ color: "#52c41a" }}>
                    <CheckCircleOutlined />
                    <span>Код действителен</span>
                  </Space>
                ) : null
              }
            >
              <Input
                prefix={<KeyOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder="Например: ABCD1234"
                onChange={onInviteChange}
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  borderRadius: 12,
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                }}
                maxLength={20}
              />
            </Form.Item>

            <Form.Item
              name="email"
              label={<Text style={{ color: "rgba(255,255,255,0.75)" }}>Email</Text>}
              rules={[
                { required: true, message: "Введите email" },
                { type: "email", message: "Некорректный email" },
              ]}
            >
              <Input
                prefix={<MailOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder="your@email.com"
                autoComplete="email"
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  borderRadius: 12,
                }}
              />
            </Form.Item>

            <Form.Item
              name="password"
              label={<Text style={{ color: "rgba(255,255,255,0.75)" }}>Пароль</Text>}
              rules={[
                { required: true, message: "Введите пароль" },
                { min: 8, message: "Минимум 8 символов" },
              ]}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder="Минимум 8 символов"
                autoComplete="new-password"
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  borderRadius: 12,
                }}
              />
            </Form.Item>

            <Form.Item
              name="confirm"
              label={
                <Text style={{ color: "rgba(255,255,255,0.75)" }}>Повтор пароля</Text>
              }
              dependencies={["password"]}
              rules={[
                { required: true, message: "Повторите пароль" },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue("password") === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error("Пароли не совпадают"));
                  },
                }),
              ]}
              style={{ marginBottom: 24 }}
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: "rgba(255,255,255,0.3)" }} />}
                placeholder="Повторите пароль"
                autoComplete="new-password"
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#fff",
                  borderRadius: 12,
                }}
              />
            </Form.Item>

            <Button
              type="primary"
              htmlType="submit"
              block
              loading={loading}
              disabled={!inviteStatus.valid}
              style={{
                background: inviteStatus.valid
                  ? "linear-gradient(135deg, #06D6A0, #0096C7)"
                  : "rgba(255,255,255,0.1)",
                border: "none",
                height: 48,
                borderRadius: 12,
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              Создать аккаунт
            </Button>
          </Form>

          <div style={{ textAlign: "center", marginTop: 24 }}>
            <Text style={{ color: "rgba(255,255,255,0.35)", fontSize: 12 }}>
              Уже есть аккаунт?{" "}
              <Link to="/login" style={{ color: "#06D6A0" }}>
                Войти
              </Link>
            </Text>
          </div>
        </Card>
      </div>
    </div>
  );
}
