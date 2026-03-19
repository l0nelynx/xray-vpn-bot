import { Typography } from "antd";
import UsersTable from "../components/UsersTable";

export default function UsersPage() {
  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        Users
      </Typography.Title>
      <UsersTable />
    </div>
  );
}
