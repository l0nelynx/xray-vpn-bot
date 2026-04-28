import { Card, Empty, Typography } from "antd";

export default function WebAppSettingsPage() {
  return (
    <div>
      <Typography.Title level={3}>WebApp Settings</Typography.Title>
      <Card>
        <Empty description="WebApp settings will live here." />
      </Card>
    </div>
  );
}
