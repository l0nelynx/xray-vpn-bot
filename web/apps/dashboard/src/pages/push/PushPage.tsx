import { useState } from "react";
import { History, Send } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@xray/ui/components/tabs";
import ComposeTab from "./ComposeTab";
import HistoryTab from "./HistoryTab";

export default function PushPage() {
  const [activeTab, setActiveTab] = useState("compose");

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab}>
      <TabsList className="mb-4 flex-wrap">
        <TabsTrigger value="compose">
          <Send className="h-4 w-4" /> Compose
        </TabsTrigger>
        <TabsTrigger value="history">
          <History className="h-4 w-4" /> History
        </TabsTrigger>
      </TabsList>
      <TabsContent value="compose">
        <ComposeTab onLaunched={() => setActiveTab("history")} />
      </TabsContent>
      <TabsContent value="history">
        <HistoryTab />
      </TabsContent>
    </Tabs>
  );
}
