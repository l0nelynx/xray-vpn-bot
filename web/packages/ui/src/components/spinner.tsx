import { Loader2 } from "lucide-react";
import { cn } from "@xray/ui/lib/utils";

function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} {...props} />;
}

export { Spinner };
