import { theme } from "antd";
import type { ConfigProviderProps } from "antd";

const tokens = {
  colorPrimary: "#7C9CFF",
  colorSuccess: "#4ECBA8",
  colorWarning: "#FFD479",
  colorError: "#FF8A8A",
  colorInfo: "#9DB8FF",

  colorText: "rgba(255, 255, 255, 0.92)",
  colorTextSecondary: "rgba(255, 255, 255, 0.62)",
  colorTextTertiary: "rgba(255, 255, 255, 0.42)",
  colorTextQuaternary: "rgba(255, 255, 255, 0.28)",

  colorBgBase: "#0B0B14",
  colorBgContainer: "rgba(255, 255, 255, 0.06)",
  colorBgElevated: "rgba(255, 255, 255, 0.10)",
  colorBgLayout: "transparent",
  colorBgSpotlight: "rgba(18, 18, 30, 0.92)",

  colorBorder: "rgba(255, 255, 255, 0.13)",
  colorBorderSecondary: "rgba(255, 255, 255, 0.07)",
  colorFill: "rgba(255, 255, 255, 0.06)",
  colorFillSecondary: "rgba(255, 255, 255, 0.04)",
  colorFillTertiary: "rgba(255, 255, 255, 0.03)",
  colorFillQuaternary: "rgba(255, 255, 255, 0.02)",

  borderRadius: 14,
  borderRadiusLG: 20,
  borderRadiusSM: 10,
  borderRadiusXS: 6,

  controlHeight: 44,
  controlHeightSM: 36,
  controlHeightLG: 52,

  fontSize: 15,
  fontWeightStrong: 600,

  boxShadow: "0 4px 24px rgba(0, 0, 0, 0.30)",
  boxShadowSecondary: "0 2px 12px rgba(0, 0, 0, 0.22)",
};

export const liquidGlassConfig: ConfigProviderProps = {
  theme: {
    algorithm: theme.darkAlgorithm,
    token: tokens,
    components: {
      Card: {
        colorBgContainer: "rgba(255, 255, 255, 0.06)",
        boxShadowTertiary: "0 4px 24px rgba(0, 0, 0, 0.28)",
        borderRadiusLG: 20,
      },
      Button: {
        defaultShadow: "none",
        primaryShadow: "none",
        dangerShadow: "none",
        defaultBg: "rgba(255, 255, 255, 0.07)",
        defaultBorderColor: "rgba(255, 255, 255, 0.13)",
        defaultColor: "rgba(255, 255, 255, 0.88)",
        defaultHoverBg: "rgba(255, 255, 255, 0.12)",
        defaultHoverBorderColor: "rgba(255, 255, 255, 0.22)",
        defaultHoverColor: "#FFFFFF",
        defaultActiveBg: "rgba(255, 255, 255, 0.09)",
      },
      Modal: {
        contentBg: "rgba(18, 18, 30, 0.85)",
        headerBg: "transparent",
        titleColor: "rgba(255, 255, 255, 0.92)",
      },
      Input: {
        activeShadow: "none",
        colorBgContainer: "rgba(255, 255, 255, 0.06)",
        hoverBorderColor: "rgba(255, 255, 255, 0.24)",
        activeBorderColor: "#7C9CFF",
      },
      Tag: {
        defaultBg: "rgba(255, 255, 255, 0.09)",
        defaultColor: "rgba(255, 255, 255, 0.88)",
      },
      Alert: {
        colorInfoBg: "rgba(124, 156, 255, 0.12)",
        colorInfoBorder: "rgba(124, 156, 255, 0.30)",
        colorWarningBg: "rgba(255, 212, 121, 0.12)",
        colorWarningBorder: "rgba(255, 212, 121, 0.30)",
        colorErrorBg: "rgba(255, 138, 138, 0.12)",
        colorErrorBorder: "rgba(255, 138, 138, 0.30)",
        colorSuccessBg: "rgba(78, 203, 168, 0.12)",
        colorSuccessBorder: "rgba(78, 203, 168, 0.30)",
      },
      Progress: {
        defaultColor: "#7C9CFF",
        remainingColor: "rgba(255, 255, 255, 0.09)",
      },
      Descriptions: {
        labelBg: "transparent",
        colorTextLabel: "rgba(255, 255, 255, 0.45)",
        colorText: "rgba(255, 255, 255, 0.88)",
      },
      Result: {
        colorTextHeading: "rgba(255, 255, 255, 0.92)",
        colorTextDescription: "rgba(255, 255, 255, 0.58)",
      },
      Empty: {
        colorTextDescription: "rgba(255, 255, 255, 0.48)",
      },
    },
  },
};
