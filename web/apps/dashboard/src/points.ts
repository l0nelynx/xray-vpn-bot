/** Bonus wallet units shown in admin UI (virtual, not fiat). */
export const POINTS_ICON = "🪙";

export function formatPoints(value: number): string {
  return `${value} ${POINTS_ICON}`;
}
