import { Tabs } from "antd";
import { HistoryOutlined, SendOutlined } from "@ant-design/icons";
import { useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import ComposeTab from "./ComposeTab";
import HistoryTab from "./HistoryTab";

export default function PushPage() {
  const [activeTab, setActiveTab] = useState("compose");
  const isMobile = useIsMobile();

  const items = [
    {
      key: "compose",
      label: (
        <span>
          <SendOutlined />
          <span style={{ marginLeft: 6 }}>Compose</span>
        </span>
      ),
      children: <ComposeTab onLaunched={() => setActiveTab("history")} />,
    },
    {
      key: "history",
      label: (
        <span>
          <HistoryOutlined />
          <span style={{ marginLeft: 6 }}>History</span>
        </span>
      ),
      children: <HistoryTab />,
    },
  ];

  return (
    <Tabs
      activeKey={activeTab}
      onChange={setActiveTab}
      items={items}
      size={isMobile ? "small" : "middle"}
      destroyOnHidden
    />
  );
}
