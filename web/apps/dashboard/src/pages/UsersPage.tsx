import UsersTable from "../components/UsersTable";

export default function UsersPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Users</h2>
          <p className="text-sm text-muted-foreground">
            Manage subscribers, VIP status, balances and access.
          </p>
        </div>
      </div>
      <UsersTable />
    </div>
  );
}
