export const STATUS_COLORS: Record<string, string> = {
  created: "blue",
  confirmed: "green",
  delivered: "cyan",
  failed: "red",
  cancelled: "orange",
};

type BadgeVariant = "default" | "secondary" | "destructive" | "outline" | "success" | "warning";

export const STATUS_BADGE_VARIANT: Record<string, BadgeVariant> = {
  created: "secondary",
  confirmed: "success",
  delivered: "default",
  failed: "destructive",
  cancelled: "warning",
};

export function statusBadgeVariant(status: string): BadgeVariant {
  return STATUS_BADGE_VARIANT[status] ?? "outline";
}

export const PERIOD_OPTIONS = [
  { value: "today", label: "Today" },
  { value: "yesterday", label: "Yesterday" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "6month", label: "6 Months" },
];
