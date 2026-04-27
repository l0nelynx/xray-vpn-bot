import {
  FileTextOutlined,
  KeyOutlined,
  RightOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import { Card, List, Tag, Typography, theme } from "antd";
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

      <div
        style={{
          border: `1px solid ${token.colorBorderSecondary}`,
          borderRadius: token.borderRadiusLG,
          overflow: "hidden",
          background: token.colorBgContainer,
        }}
      >
        <List
          dataSource={items}
          renderItem={(item) => (
            <List.Item
              style={{
                cursor: "pointer",
                background: token.colorBgContainer,
                paddingInline: 16,
              }}
              onClick={item.onClick}
            >
              <List.Item.Meta avatar={item.icon} title={item.title} />
              <RightOutlined style={{ color: token.colorTextTertiary }} />
            </List.Item>
          )}
        />
      </div>
    </div>
  );
}
