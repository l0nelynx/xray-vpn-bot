import type { TableProps } from "antd";
import type { SortOrder } from "../components/MobileSortControl";

type PaginatedTableChangeOptions = {
  page: number;
  sort: string;
  order: SortOrder;
  setPage: (page: number) => void;
  setSort: (sort: string) => void;
  setOrder: (order: SortOrder) => void;
  perPage?: number;
  setPerPage?: (size: number) => void;
  sortKey?: (sorter: { columnKey?: unknown; field?: unknown; order?: string | null }) => string | undefined;
};

function defaultSortKey(sorter: { columnKey?: unknown; field?: unknown }): string | undefined {
  if (sorter.columnKey != null && !Array.isArray(sorter.columnKey)) {
    return String(sorter.columnKey);
  }
  if (sorter.field != null && !Array.isArray(sorter.field)) {
    return String(sorter.field);
  }
  return undefined;
}

/** Ant Design Table onChange that does not reset page on pagination clicks. */
export function makePaginatedTableChange<T>(
  options: PaginatedTableChangeOptions,
): NonNullable<TableProps<T>["onChange"]> {
  const resolveSortKey = options.sortKey ?? defaultSortKey;

  return (pagination, _filters, sorter) => {
    const s = Array.isArray(sorter) ? sorter[0] : sorter;

    if (s?.order) {
      const newSort = resolveSortKey(s);
      if (newSort) {
        const newOrder: SortOrder = s.order === "ascend" ? "asc" : "desc";
        if (newSort !== options.sort || newOrder !== options.order) {
          options.setSort(newSort);
          options.setOrder(newOrder);
          options.setPage(1);
          return;
        }
      }
    }

    if (pagination?.current != null && pagination.current !== options.page) {
      options.setPage(pagination.current);
    }

    if (
      options.setPerPage &&
      options.perPage != null &&
      pagination?.pageSize != null &&
      pagination.pageSize !== options.perPage
    ) {
      options.setPerPage(pagination.pageSize);
      options.setPage(1);
    }
  };
}
