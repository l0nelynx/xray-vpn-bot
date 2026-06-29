import { Select, Button } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";

export type SortOrder = "asc" | "desc";

interface SortOption {
  value: string;
  label: string;
}

interface Props {
  options: SortOption[];
  sort: string;
  order: SortOrder;
  onChange: (sort: string, order: SortOrder) => void;
}

export default function MobileSortControl({ options, sort, order, onChange }: Props) {
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
      <Select
        value={sort}
        onChange={(v) => onChange(v, order)}
        options={options}
        style={{ flex: 1 }}
      />
      <Button
        aria-label={order === "asc" ? "Ascending" : "Descending"}
        icon={order === "asc" ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
        onClick={() => onChange(sort, order === "asc" ? "desc" : "asc")}
      />
    </div>
  );
}
