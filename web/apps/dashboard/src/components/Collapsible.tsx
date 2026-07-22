import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@xray/ui/lib/utils";

interface Props {
  title: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}

export default function Collapsible({ title, defaultOpen = false, children, className }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={cn("rounded-lg border border-border", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm font-medium"
      >
        <span>{title}</span>
        <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && <div className="border-t border-border p-3">{children}</div>}
    </div>
  );
}
