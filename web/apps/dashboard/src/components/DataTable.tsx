import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@xray/ui/components/table";
import { Spinner } from "@xray/ui/components/spinner";
import { cn } from "@xray/ui/lib/utils";
import type { SortOrder } from "./MobileSortControl";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    sortKey?: string;
    headClassName?: string;
    cellClassName?: string;
    width?: string | number;
  }
}

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  loading?: boolean;
  rowKey: (row: T) => string | number;
  sort?: string;
  order?: SortOrder;
  onSortChange?: (key: string) => void;
  empty?: ReactNode;
  onRowClick?: (row: T) => void;
  minWidth?: number;
  /** When true, skip outer border/bg (use inside an existing Card). */
  embedded?: boolean;
}

export default function DataTable<T>({
  columns,
  data,
  loading,
  rowKey,
  sort,
  order,
  onSortChange,
  empty = "No data",
  onRowClick,
  minWidth,
  embedded = false,
}: DataTableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
  });

  return (
    <div
      className={cn(
        "relative w-full overflow-auto",
        embedded ? "rounded-md border border-border" : "rounded-xl border border-border bg-card",
      )}
    >
      <Table style={minWidth ? { minWidth } : undefined}>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id} className="hover:bg-transparent">
              {hg.headers.map((header) => {
                const meta = header.column.columnDef.meta;
                const sortKey = meta?.sortKey;
                const isSortable = Boolean(sortKey && onSortChange);
                const active = sortKey && sort === sortKey;
                return (
                  <TableHead
                    key={header.id}
                    className={cn("whitespace-nowrap", meta?.headClassName)}
                    style={meta?.width ? { width: meta.width } : undefined}
                  >
                    {header.isPlaceholder ? null : isSortable ? (
                      <button
                        type="button"
                        onClick={() => onSortChange!(sortKey!)}
                        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {active ? (
                          order === "asc" ? (
                            <ArrowUp className="h-3.5 w-3.5" />
                          ) : (
                            <ArrowDown className="h-3.5 w-3.5" />
                          )
                        ) : (
                          <ChevronsUpDown className="h-3.5 w-3.5 opacity-40" />
                        )}
                      </button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow className="hover:bg-transparent">
              <TableCell colSpan={columns.length} className="h-32 text-center">
                <Spinner className="mx-auto h-6 w-6" />
              </TableCell>
            </TableRow>
          ) : data.length === 0 ? (
            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={columns.length}
                className="h-24 text-center text-muted-foreground"
              >
                {empty}
              </TableCell>
            </TableRow>
          ) : (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={rowKey(row.original)}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                className={onRowClick ? "cursor-pointer" : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={cn("align-middle", cell.column.columnDef.meta?.cellClassName)}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
