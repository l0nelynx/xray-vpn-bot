import {
  FileTextOutlined,
  KeyOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import { Button, Card, Space, Tag, Typography, theme } from "antd";
import { LinksInfo } from "../api/client";
import { openLink, showAlert } from "../tg/webapp";

interface Props {
  links: LinksInfo;
  username: string;
}

export default function SettingsPage({ links, username }: Props) {
  const { token } = theme.useToken();

  const items = [
    {
      key: "policy",
      icon: <SafetyOutlined />,
      title: "Политика конфиденциальности",
      onClick: () => openLink(links.policy_url),
    },
    {
      key: "agreement",
      icon: <FileTextOutlined />,
      title: "Пользовательское соглашение",
      onClick: () => openLink(links.agreement_url),
    },
    {
      key: "login",
      icon: <KeyOutlined />,
      title: "Вход в аккаунт",
      onClick: () =>
        showAlert("Раздел «Вход в аккаунт» появится в следующей версии."),
    },
  ];

  return (
    <div className="page">
      <Typography.Title level={3} style={{ marginBottom: 20 }}>
        Аккаунт
      </Typography.Title>

      {username && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Typography.Text type="secondary">Telegram</Typography.Text>
            <Tag color="processing">@{username}</Tag>
          </div>
        </Card>
      )}

      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        {items.map((item) => (
          <Button
            key={item.key}
            block
            size="large"
            onClick={item.onClick}
            style={{
              height: "auto",
              minHeight: token.controlHeightLG,
              paddingInline: 16,
              paddingBlock: 12,
              justifyContent: "flex-start",
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              {item.icon}
              <span>{item.title}</span>
            </span>
          </Button>
        ))}
      </Space>
    </div>
  );
}
