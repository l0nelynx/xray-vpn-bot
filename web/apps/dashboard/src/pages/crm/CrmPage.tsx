import { Tabs, Typography } from "antd";
import { CalendarOutlined, CustomerServiceOutlined, HistoryOutlined, SendOutlined } from "@ant-design/icons";
import { useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import CampaignTab from "./CampaignTab";
import EventsTab from "./EventsTab";
import HistoryTab from "./HistoryTab";

export default function CrmPage() {
  const [activeTab, setActiveTab] = useState("campaigns");
  const isMobile = useIsMobile();

  const items = [
    {
      key: "campaigns",
      label: isMobile ? (
        <span>
          <SendOutlined />
          <span style={{ marginLeft: 6 }}>Кампании</span>
        </span>
      ) : (
        <span>
          <SendOutlined /> Кампании
        </span>
      ),
      children: <CampaignTab onLaunched={() => setActiveTab("history")} />,
    },
    {
      key: "events",
      label: isMobile ? (
        <span>
          <CalendarOutlined />
          <span style={{ marginLeft: 6 }}>События</span>
        </span>
      ) : (
        <span>
          <CalendarOutlined /> События
        </span>
      ),
      children: <EventsTab />,
    },
    {
      key: "history",
      label: isMobile ? (
        <span>
          <HistoryOutlined />
          <span style={{ marginLeft: 6 }}>История</span>
        </span>
      ) : (
        <span>
          <HistoryOutlined /> История
        </span>
      ),
      children: <HistoryTab />,
    },
  ];

  return (
    <div>
      <Typography.Title level={isMobile ? 5 : 4} style={{ marginBottom: isMobile ? 12 : 16 }}>
        <CustomerServiceOutlined /> CRM
      </Typography.Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={items}
        size={isMobile ? "small" : "middle"}
        tabBarGutter={isMobile ? 12 : 24}
        tabBarStyle={{ marginBottom: isMobile ? 8 : 16 }}
      />
    </div>
  );
}
