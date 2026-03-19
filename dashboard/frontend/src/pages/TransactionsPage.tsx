import { Typography } from "antd";
import TransactionsTable from "../components/TransactionsTable";

export default function TransactionsPage() {
  return (
    <div>
      <Typography.Title level={4} style={{ marginBottom: 16 }}>
        Transactions
      </Typography.Title>
      <TransactionsTable />
    </div>
  );
}
