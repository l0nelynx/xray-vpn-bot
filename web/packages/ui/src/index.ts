/**
 * Shared antd "liquid glass" theme builder.
 *
 * The dashboard and the miniapp use deliberately different design languages
 * (dense/solid admin vs. translucent/large touch UI), so the token *values*
 * stay in each app. What they share is the wiring: dark algorithm + token +
 * components assembled into a ConfigProviderProps. Each app passes its own
 * tokens/components, so appearance is unchanged.
 */
import { theme } from "antd";
import type { ConfigProviderProps, ThemeConfig } from "antd";

export type ThemeTokens = NonNullable<ThemeConfig["token"]>;
export type ThemeComponents = NonNullable<ThemeConfig["components"]>;

export function buildLiquidGlassConfig(
  tokens: ThemeTokens,
  components: ThemeComponents,
): ConfigProviderProps {
  return {
    theme: {
      algorithm: theme.darkAlgorithm,
      token: tokens,
      components,
    },
  };
}
