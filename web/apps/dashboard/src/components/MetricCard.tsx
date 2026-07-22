import type { ReactNode } from "react";
import { Skeleton } from "@xray/ui/components/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";
import { cn } from "@xray/ui/lib/utils";

interface Props {
  label: string;
  value: number;
  prev?: number;
  icon?: ReactNode;
  /** Formats the main value (e.g. currency). Defaults to grouped integer. */
  format?: (v: number) => string;
  suffix?: string;
  loading?: boolean;
}

const defaultFormat = (v: number) => Math.round(v).toLocaleString("en-US");

export default function MetricCard({
  label,
  value,
  prev,
  icon,
  format = defaultFormat,
  suffix,
  loading,
}: Props) {
  if (loading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-4 rounded-full" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-8 w-28" />
          <Skeleton className="h-3 w-36" />
        </CardContent>
      </Card>
    );
  }

  let deltaPct: number | null = null;
  let isNew = false;
  if (prev != null) {
    if (prev === 0) {
      isNew = value > 0;
    } else {
      deltaPct = ((value - prev) / Math.abs(prev)) * 100;
    }
  }
  const up = deltaPct != null && deltaPct > 0.05;
  const down = deltaPct != null && deltaPct < -0.05;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        {icon && (
          <span className="text-muted-foreground [&_svg]:h-4 [&_svg]:w-4" aria-hidden>
            {icon}
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tracking-tight tabular-nums">
          {format(value)}
          {suffix && (
            <span className="ml-1 text-base font-medium text-muted-foreground">{suffix}</span>
          )}
        </div>
        {(deltaPct != null || isNew) && (
          <p
            className={cn(
              "mt-2 flex items-center gap-1 text-xs",
              isNew || up ? "text-emerald-500" : down ? "text-red-500" : "text-muted-foreground",
            )}
          >
            {isNew ? (
              <>New this period</>
            ) : (
              <>
                {up ? (
                  <ArrowUp className="h-3 w-3" />
                ) : down ? (
                  <ArrowDown className="h-3 w-3" />
                ) : (
                  <Minus className="h-3 w-3" />
                )}
                {Math.abs(deltaPct!).toFixed(deltaPct! >= 100 || deltaPct! <= -100 ? 0 : 1)}%
                <span className="text-muted-foreground">vs previous period</span>
              </>
            )}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
