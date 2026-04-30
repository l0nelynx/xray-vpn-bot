import { theme } from "antd";
import type { ConfigProviderProps } from "antd";

const tokens = {
  colorPrimary: "#7C9CFF",
  colorSuccess: "#5DD3A8",
  colorWarning: "#FFD479",
  colorError: "#FF8A8A",
  colorInfo: "#9DB8FF",

  colorText: "rgba(255, 255, 255, 0.92)",
  colorTextSecondary: "rgba(255, 255, 255, 0.65)",
  colorTextTertiary: "rgba(255, 255, 255, 0.45)",
  colorTextQuaternary: "rgba(255, 255, 255, 0.30)",

  colorBgBase: "#0B0B14",
  colorBgContainer: "rgba(255, 255, 255, 0.06)",
  colorBgElevated: "rgba(255, 255, 255, 0.10)",
  colorBgLayout: "transparent",
  colorBgSpotlight: "rgba(28, 28, 38, 0.92)",

  colorBorder: "rgba(255, 255, 255, 0.14)",
  colorBorderSecondary: "rgba(255, 255, 255, 0.08)",
  colorFill: "rgba(255, 255, 255, 0.06)",
  colorFillSecondary: "rgba(255, 255, 255, 0.04)",
  colorFillTertiary: "rgba(255, 255, 255, 0.03)",
  colorFillQuaternary: "rgba(255, 255, 255, 0.02)",

  borderRadius: 16,
  borderRadiusLG: 22,
  borderRadiusSM: 10,
  borderRadiusXS: 6,

  controlHeight: 44,
  controlHeightSM: 36,
  controlHeightLG: 52,

  fontSize: 15,
  fontWeightStrong: 600,

  boxShadow: "0 8px 32px rgba(0, 0, 0, 0.35)",
  boxShadowSecondary: "0 4px 16px rgba(0, 0, 0, 0.25)",
};

export const liquidGlassConfig: ConfigProviderProps = {
  theme: {
    algorithm: theme.darkAlgorithm,
    token: tokens,
    components: {
      Card: {
        colorBgContainer: "rgba(255, 255, 255, 0.06)",
        boxShadowTertiary: "0 8px 32px rgba(0, 0, 0, 0.35)",
      },
      Button: {
        defaultShadow: "none",
        primaryShadow: "none",
        dangerShadow: "none",
        defaultBg: "rgba(255, 255, 255, 0.08)",
        defaultBorderColor: "rgba(255, 255, 255, 0.16)",
        defaultColor: "rgba(255, 255, 255, 0.92)",
        defaultHoverBg: "rgba(255, 255, 255, 0.14)",
        defaultHoverBorderColor: "rgba(255, 255, 255, 0.24)",
        defaultHoverColor: "#FFFFFF",
        defaultActiveBg: "rgba(255, 255, 255, 0.10)",
      },
      Modal: {
        contentBg: "rgba(28, 28, 38, 0.78)",
        headerBg: "transparent",
        titleColor: "rgba(255, 255, 255, 0.92)",
      },
      Input: {
        activeShadow: "none",
        colorBgContainer: "rgba(255, 255, 255, 0.06)",
        hoverBorderColor: "rgba(255, 255, 255, 0.28)",
        activeBorderColor: "#7C9CFF",
      },
      Tag: {
        defaultBg: "rgba(255, 255, 255, 0.10)",
        defaultColor: "rgba(255, 255, 255, 0.92)",
      },
      Alert: {
        colorInfoBg: "rgba(125, 156, 255, 0.14)",
        colorInfoBorder: "rgba(125, 156, 255, 0.32)",
        colorWarningBg: "rgba(255, 212, 121, 0.14)",
        colorWarningBorder: "rgba(255, 212, 121, 0.32)",
        colorErrorBg: "rgba(255, 138, 138, 0.14)",
        colorErrorBorder: "rgba(255, 138, 138, 0.32)",
        colorSuccessBg: "rgba(93, 211, 168, 0.14)",
        colorSuccessBorder: "rgba(93, 211, 168, 0.32)",
      },
      Progress: {
        defaultColor: "#7C9CFF",
        remainingColor: "rgba(255, 255, 255, 0.10)",
      },
      Descriptions: {
        labelBg: "transparent",
      },
      Result: {
        colorTextHeading: "rgba(255, 255, 255, 0.92)",
        colorTextDescription: "rgba(255, 255, 255, 0.65)",
      },
      Empty: {
        colorTextDescription: "rgba(255, 255, 255, 0.55)",
      },
    },
  },
};
