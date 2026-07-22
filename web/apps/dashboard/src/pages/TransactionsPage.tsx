import TransactionsTable from "../components/TransactionsTable";

export default function TransactionsPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Transactions</h2>
          <p className="text-sm text-muted-foreground">
            Track payments, order status and clean up stale records.
          </p>
        </div>
      </div>
      <TransactionsTable />
    </div>
  );
}
