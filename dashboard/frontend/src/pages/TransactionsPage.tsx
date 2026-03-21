import { Typography } from "antd";
import TransactionsTable from "../components/TransactionsTable";

export default function TransactionsPage() {
  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 20, color: "rgba(255,255,255,0.88)" }}>
        Transactions
      </Typography.Title>
      <TransactionsTable />
    </div>
  );
}
