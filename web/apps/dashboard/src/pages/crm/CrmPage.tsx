import { Tabs, Typography } from "antd";
import {
  ApiOutlined,
  CalendarOutlined,
  CustomerServiceOutlined,
  HistoryOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { useState } from "react";
import useIsMobile from "../../hooks/useIsMobile";
import CampaignTab from "./CampaignTab";
import EventsTab from "./EventsTab";
import HistoryTab from "./HistoryTab";
import WebhooksTab from "./WebhooksTab";

export default function CrmPage() {
  const [activeTab, setActiveTab] = useState("campaigns");
  const isMobile = useIsMobile();

  const items = [
    {
      key: "campaigns",
      label: isMobile ? (
        <span>
          <SendOutlined />
          <span style={{ marginLeft: 6 }}>Campaigns</span>
        </span>
      ) : (
        <span>
          <SendOutlined /> Campaigns
        </span>
      ),
      children: <CampaignTab onLaunched={() => setActiveTab("history")} />,
    },
    {
      key: "events",
      label: isMobile ? (
        <span>
          <CalendarOutlined />
          <span style={{ marginLeft: 6 }}>Events</span>
        </span>
      ) : (
        <span>
          <CalendarOutlined /> Events
        </span>
      ),
      children: <EventsTab />,
    },
    {
      key: "webhooks",
      label: isMobile ? (
        <span>
          <ApiOutlined />
          <span style={{ marginLeft: 6 }}>Webhooks</span>
        </span>
      ) : (
        <span>
          <ApiOutlined /> Webhooks
        </span>
      ),
      children: <WebhooksTab />,
    },
    {
      key: "history",
      label: isMobile ? (
        <span>
          <HistoryOutlined />
          <span style={{ marginLeft: 6 }}>History</span>
        </span>
      ) : (
        <span>
          <HistoryOutlined /> History
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
