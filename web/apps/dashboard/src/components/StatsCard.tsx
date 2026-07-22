import { Skeleton } from "@xray/ui/components/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@xray/ui/components/card";
import type { ReactNode } from "react";

interface Props {
  title: string;
  value: number | string;
  prefix?: ReactNode;
  suffix?: string;
  loading?: boolean;
  /** @deprecated ignored — cards use theme tokens */
  color?: string;
}

export default function StatsCard({ title, value, prefix, suffix, loading }: Props) {
  const formattedValue =
    typeof value === "number" ? Math.round(value).toLocaleString("en-US") : value;

  if (loading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-4 rounded-full" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-24" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {prefix && (
          <span className="text-muted-foreground [&_svg]:h-4 [&_svg]:w-4" aria-hidden>
            {prefix}
          </span>
        )}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tracking-tight tabular-nums">
          {formattedValue}
          {suffix && (
            <span className="ml-1 text-base font-medium text-muted-foreground">{suffix}</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
