import type { ReactNode } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@xray/ui/components/card";
import { Alert, AlertDescription } from "@xray/ui/components/alert";
import { Button } from "@xray/ui/components/button";
import { Spinner } from "@xray/ui/components/spinner";

interface Props {
  title: string;
  description?: string;
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyText?: string;
  onRetry?: () => void;
  height: number;
  children: ReactNode;
}

export default function ChartCard({
  title,
  description,
  loading,
  error,
  empty,
  emptyText = "No data for this period",
  onRetry,
  height,
  children,
}: Props) {
  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center" style={{ height }}>
            <Spinner className="h-6 w-6" />
          </div>
        ) : error ? (
          <Alert variant="destructive" className="flex items-center justify-between gap-3">
            <AlertDescription>{error}</AlertDescription>
            {onRetry && (
              <Button size="sm" variant="outline" onClick={onRetry}>
                Retry
              </Button>
            )}
          </Alert>
        ) : empty ? (
          <div
            className="flex items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground"
            style={{ height }}
          >
            {emptyText}
          </div>
        ) : (
          <div className="w-full overflow-hidden" style={{ height }}>
            {children}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
