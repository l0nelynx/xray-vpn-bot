import { useState } from "react";
import { Plug, Calendar, Headphones, History, Send } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@xray/ui/components/tabs";
import CampaignTab from "./CampaignTab";
import EventsTab from "./EventsTab";
import HistoryTab from "./HistoryTab";
import WebhooksTab from "./WebhooksTab";

export default function CrmPage() {
  const [activeTab, setActiveTab] = useState("campaigns");

  return (
    <div>
      <h1 className="mb-3 flex items-center gap-2 text-lg font-semibold text-foreground md:mb-4 md:text-xl">
        <Headphones className="h-5 w-5" /> CRM
      </h1>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="campaigns">
            <Send className="h-4 w-4" /> Campaigns
          </TabsTrigger>
          <TabsTrigger value="events">
            <Calendar className="h-4 w-4" /> Events
          </TabsTrigger>
          <TabsTrigger value="webhooks">
            <Plug className="h-4 w-4" /> Webhooks
          </TabsTrigger>
          <TabsTrigger value="history">
            <History className="h-4 w-4" /> History
          </TabsTrigger>
        </TabsList>
        <TabsContent value="campaigns">
          <CampaignTab onLaunched={() => setActiveTab("history")} />
        </TabsContent>
        <TabsContent value="events">
          <EventsTab />
        </TabsContent>
        <TabsContent value="webhooks">
          <WebhooksTab />
        </TabsContent>
        <TabsContent value="history">
          <HistoryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
