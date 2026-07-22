import { ArrowDown, ArrowUp } from "lucide-react";
import { Button } from "@xray/ui/components/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";

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
    <div className="mb-3 flex gap-2">
      <Select value={sort} onValueChange={(v: string) => onChange(v, order)}>
        <SelectTrigger className="flex-1">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button
        variant="outline"
        size="icon"
        aria-label={order === "asc" ? "Ascending" : "Descending"}
        onClick={() => onChange(sort, order === "asc" ? "desc" : "asc")}
      >
        {order === "asc" ? <ArrowUp className="h-4 w-4" /> : <ArrowDown className="h-4 w-4" />}
      </Button>
    </div>
  );
}
