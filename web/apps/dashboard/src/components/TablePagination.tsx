import { Button } from "@xray/ui/components/button";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  page: number;
  perPage: number;
  total: number;
  onPageChange: (page: number) => void;
}

export default function TablePagination({ page, perPage, total, onPageChange }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  return (
    <div className="flex items-center justify-between gap-2 pt-4">
      <p className="text-sm text-muted-foreground">
        Page {page} of {totalPages} · {total.toLocaleString("en-US")} total
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
