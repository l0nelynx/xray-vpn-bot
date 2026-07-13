import { Typography } from "antd";
import UsersTable from "../components/UsersTable";

export default function UsersPage() {
  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 20, color: "rgba(255,255,255,0.88)" }}>
        Users
      </Typography.Title>
      <UsersTable />
    </div>
  );
}
