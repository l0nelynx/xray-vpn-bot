import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Divider,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Tag,
  Typography,
} from "antd";
import {
  CheckCircleOutlined,
  LockOutlined,
  LogoutOutlined,
  MailOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, email, password, sessions } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";

const { Title, Text } = Typography;

const PWD_ERRORS: Record<string, string> = {
  invalid_credentials: "Неверный текущий пароль",
  rate_limited: "Слишком много попыток",
  http_429: "Слишком много запросов",
};

export default function SettingsTab() {
  const { message: msg } = App.useApp();
  const { user, profile, logout, refreshProfile } = useAuth();
  const navigate = useNavigate();
  const [pwdForm] = Form.useForm();
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [revokeLoading, setRevokeLoading] = useState(false);
  const [verifyLoading, setVerifyLoading] = useState(false);

  async function onPasswordChange(values: {
    current: string;
    next: string;
  }) {
    setPwdLoading(true);
    setPwdError(null);
    try {
      await password.change(values.current, values.next);
      msg.success("Пароль изменён. Выполните вход снова.");
      pwdForm.resetFields();
      await logout();
      navigate("/login", { replace: true });
    } catch (e) {
      if (e instanceof ApiError) {
        setPwdError(PWD_ERRORS[e.code] || "Ошибка смены пароля");
      } else {
        setPwdError("Ошибка сети");
      }
    } finally {
      setPwdLoading(false);
    }
  }

  async function revokeAllSessions() {
    Modal.confirm({
      title: "Завершить все сессии?",
      content: "Все устройства будут отключены, потребуется повторный вход.",
      okText: "Завершить",
      cancelText: "Отмена",
      okButtonProps: { danger: true },
      centered: true,
      async onOk() {
        setRevokeLoading(true);
        try {
          await sessions.revokeAll();
          msg.success("Все сессии завершены");
          await logout();
          navigate("/login", { replace: true });
        } catch {
          msg.error("Не удалось завершить сессии");
        } finally {
          setRevokeLoading(false);
        }
      },
    });
  }

  async function sendVerifyEmail() {
    setVerifyLoading(true);
    try {
      await email.sendCode();
      msg.success("Код отправлен на ваш email");
      navigate("/verify-email");
    } catch {
      msg.error("Не удалось отправить код");
    } finally {
      setVerifyLoading(false);
    }
  }

  return (
    <div>
      <Title level={4} style={{ color: "#fff", marginBottom: 24 }}>
        <SafetyCertificateOutlined style={{ marginRight: 8 }} />
        Настройки аккаунта
      </Title>

      <Row gutter={[24, 24]}>
        {/* Account info */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Text style={{ color: "#fff" }}>
                <MailOutlined style={{ marginRight: 8 }} />
                Аккаунт
              </Text>
            }
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.09)",
              borderRadius: 16,
            }}
            styles={{ header: { borderBottom: "1px solid rgba(255,255,255,0.07)", color: "#fff" } }}
          >
            <Descriptions
              column={1}
              size="small"
              colon={false}
              styles={{ label: { color: "rgba(255,255,255,0.5)", width: 140 } }}
            >
              <Descriptions.Item label="Email">
                <Text style={{ color: "#fff" }}>{user?.email || "—"}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="Статус email">
                {user?.email_verified ? (
                  <Tag color="success" icon={<CheckCircleOutlined />}>
                    Подтверждён
                  </Tag>
                ) : (
                  <Space>
                    <Tag color="warning" icon={<WarningOutlined />}>
                      Не подтверждён
                    </Tag>
                    <Button
                      size="small"
                      loading={verifyLoading}
                      onClick={sendVerifyEmail}
                      style={{
                        fontSize: 11,
                        borderRadius: 6,
                        background: "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        color: "rgba(255,255,255,0.7)",
                      }}
                    >
                      Подтвердить
                    </Button>
                  </Space>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Telegram">
                {profile?.user.tg_id ? (
                  <Tag color="processing">Привязан</Tag>
                ) : (
                  <Tag>Не привязан</Tag>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        {/* Change password */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Text style={{ color: "#fff" }}>
                <LockOutlined style={{ marginRight: 8 }} />
                Смена пароля
              </Text>
            }
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.09)",
              borderRadius: 16,
            }}
            styles={{ header: { borderBottom: "1px solid rgba(255,255,255,0.07)" } }}
          >
            {pwdError && (
              <Alert
                type="error"
                message={pwdError}
                style={{ marginBottom: 16, borderRadius: 10 }}
                showIcon
                closable
                onClose={() => setPwdError(null)}
              />
            )}

            <Form form={pwdForm} layout="vertical" onFinish={onPasswordChange}>
              <Form.Item
                name="current"
                label={<Text style={{ color: "rgba(255,255,255,0.7)" }}>Текущий пароль</Text>}
                rules={[{ required: true, message: "Введите текущий пароль" }]}
              >
                <Input.Password
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: 10,
                  }}
                />
              </Form.Item>
              <Form.Item
                name="next"
                label={<Text style={{ color: "rgba(255,255,255,0.7)" }}>Новый пароль</Text>}
                rules={[
                  { required: true, message: "Введите новый пароль" },
                  { min: 8, message: "Минимум 8 символов" },
                ]}
              >
                <Input.Password
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: 10,
                  }}
                />
              </Form.Item>
              <Form.Item
                name="confirm"
                label={<Text style={{ color: "rgba(255,255,255,0.7)" }}>Повтор пароля</Text>}
                dependencies={["next"]}
                rules={[
                  { required: true, message: "Повторите пароль" },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue("next") === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error("Пароли не совпадают"));
                    },
                  }),
                ]}
              >
                <Input.Password
                  style={{
                    background: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: 10,
                  }}
                />
              </Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={pwdLoading}
                style={{
                  background: "linear-gradient(135deg, #06D6A0, #0096C7)",
                  border: "none",
                  borderRadius: 10,
                }}
              >
                Сменить пароль
              </Button>
            </Form>
          </Card>
        </Col>

        {/* Security actions */}
        <Col xs={24}>
          <Card
            title={<Text style={{ color: "#fff" }}>Безопасность</Text>}
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.09)",
              borderRadius: 16,
            }}
            styles={{ header: { borderBottom: "1px solid rgba(255,255,255,0.07)" } }}
          >
            <Space wrap>
              <Button
                danger
                icon={<LogoutOutlined />}
                loading={revokeLoading}
                onClick={revokeAllSessions}
                style={{ borderRadius: 10 }}
              >
                Завершить все сессии
              </Button>
              <Button
                icon={<LogoutOutlined />}
                onClick={() => {
                  logout();
                  navigate("/login", { replace: true });
                }}
                style={{
                  background: "rgba(255,255,255,0.06)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  color: "rgba(255,255,255,0.7)",
                  borderRadius: 10,
                }}
              >
                Выйти из аккаунта
              </Button>
            </Space>
            <Divider style={{ borderColor: "rgba(255,255,255,0.07)" }} />
            <Text style={{ color: "rgba(255,255,255,0.35)", fontSize: 12 }}>
              «Завершить все сессии» отзывает все refresh-токены и выходит из системы на всех устройствах.
            </Text>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
