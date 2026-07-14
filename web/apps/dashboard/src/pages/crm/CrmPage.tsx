import { Tabs, Typography } from "antd";
import { CalendarOutlined, CustomerServiceOutlined, HistoryOutlined, SendOutlined } from "@ant-design/icons";
import { useState } from "react";
import CampaignTab from "./CampaignTab";
import EventsTab from "./EventsTab";
import HistoryTab from "./HistoryTab";

export default function CrmPage() {
  const [activeTab, setActiveTab] = useState("campaigns");

  const items = [
    {
      key: "campaigns",
      label: (
        <span>
          <SendOutlined /> Кампании
        </span>
      ),
      children: <CampaignTab onLaunched={() => setActiveTab("history")} />,
    },
    {
      key: "events",
      label: (
        <span>
          <CalendarOutlined /> События
        </span>
      ),
      children: <EventsTab />,
    },
    {
      key: "history",
      label: (
        <span>
          <HistoryOutlined /> История
        </span>
      ),
      children: <HistoryTab />,
    },
  ];

  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        <CustomerServiceOutlined /> CRM
      </Typography.Title>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={items} />
    </div>
  );
}
