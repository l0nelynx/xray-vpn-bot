import {
  FileTextOutlined,
  KeyOutlined,
  RightOutlined,
  SafetyOutlined,
} from "@ant-design/icons";
import { Card, List, Tag, Typography } from "antd";
import { LinksInfo } from "../api/client";
import { openLink, showAlert } from "../tg/webapp";

interface Props {
  links: LinksInfo;
  username: string;
}

export default function SettingsPage({ links, username }: Props) {
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

      <List
        bordered
        dataSource={items}
        renderItem={(item) => (
          <List.Item
            style={{ cursor: "pointer", background: "#FFFFFF" }}
            onClick={item.onClick}
          >
            <List.Item.Meta avatar={item.icon} title={item.title} />
            <RightOutlined style={{ color: "#999" }} />
          </List.Item>
        )}
      />
    </div>
  );
}
