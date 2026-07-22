import type { SortOrder } from "../components/MobileSortControl";

type SortToggleOptions = {
  sort: string;
  order: SortOrder;
  setSort: (sort: string) => void;
  setOrder: (order: SortOrder) => void;
  setPage: (page: number) => void;
  /** Default order applied when switching to a new column. */
  defaultOrder?: SortOrder;
};

/**
 * Toggles server-side sort state for a clicked column header.
 * Clicking the active column flips the direction; clicking a new column
 * selects it (defaulting to descending) and resets to the first page.
 */
export function makeSortToggle(options: SortToggleOptions) {
  const { sort, order, setSort, setOrder, setPage, defaultOrder = "desc" } = options;
  return (key: string) => {
    if (key === sort) {
      setOrder(order === "asc" ? "desc" : "asc");
    } else {
      setSort(key);
      setOrder(defaultOrder);
    }
    setPage(1);
  };
}
