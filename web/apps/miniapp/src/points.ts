/** In-app bonus points — virtual currency, not fiat. */
export const POINTS_ICON = "🪙";

export function formatPoints(value: number): string {
  return `${value} ${POINTS_ICON}`;
}
