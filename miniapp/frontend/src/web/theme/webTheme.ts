import { theme } from "antd";
import type { ConfigProviderProps } from "antd";

const tokens = {
  colorPrimary: "#06D6A0",
  colorSuccess: "#06D6A0",
  colorWarning: "#FFD479",
  colorError: "#FF8A8A",
  colorInfo: "#0096C7",

  colorText: "rgba(255, 255, 255, 0.92)",
  colorTextSecondary: "rgba(255, 255, 255, 0.65)",
  colorTextTertiary: "rgba(255, 255, 255, 0.45)",
  colorTextQuaternary: "rgba(255, 255, 255, 0.30)",

  colorBgBase: "#0B0B14",
  colorBgContainer: "rgba(255, 255, 255, 0.05)",
  colorBgElevated: "rgba(20, 20, 30, 0.98)",
  colorBgLayout: "#0B0B14",
  colorBgSpotlight: "rgba(20, 20, 30, 0.92)",

  colorBorder: "rgba(255, 255, 255, 0.12)",
  colorBorderSecondary: "rgba(255, 255, 255, 0.07)",
  colorFill: "rgba(255, 255, 255, 0.06)",
  colorFillSecondary: "rgba(255, 255, 255, 0.04)",

  borderRadius: 12,
  borderRadiusLG: 16,
  borderRadiusSM: 8,

  controlHeight: 42,
  controlHeightLG: 48,

  fontSize: 14,
  fontWeightStrong: 600,

  boxShadow: "0 8px 32px rgba(0, 0, 0, 0.4)",
};

export const webThemeConfig: ConfigProviderProps = {
  theme: {
    algorithm: theme.darkAlgorithm,
    token: tokens,
    components: {
      Layout: {
        siderBg: "rgba(255,255,255,0.03)",
        headerBg: "rgba(255,255,255,0.02)",
        bodyBg: "#0B0B14",
      },
      Menu: {
        darkItemBg: "transparent",
        darkSubMenuItemBg: "transparent",
        darkItemSelectedBg: "rgba(6,214,160,0.12)",
        darkItemSelectedColor: "#06D6A0",
        darkItemHoverBg: "rgba(255,255,255,0.05)",
        itemSelectedBg: "rgba(6,214,160,0.12)",
        itemSelectedColor: "#06D6A0",
        itemBorderRadius: 10,
      },
      Card: {
        colorBgContainer: "rgba(255, 255, 255, 0.04)",
      },
      Button: {
        defaultShadow: "none",
        primaryShadow: "none",
        defaultBg: "rgba(255, 255, 255, 0.06)",
        defaultBorderColor: "rgba(255, 255, 255, 0.12)",
        defaultColor: "rgba(255, 255, 255, 0.85)",
      },
      Input: {
        activeShadow: "none",
        colorBgContainer: "rgba(255, 255, 255, 0.06)",
        hoverBorderColor: "rgba(255, 255, 255, 0.25)",
        activeBorderColor: "#06D6A0",
      },
      Table: {
        colorBgContainer: "transparent",
        borderColor: "rgba(255,255,255,0.07)",
        headerBg: "rgba(255,255,255,0.03)",
        rowHoverBg: "rgba(255,255,255,0.04)",
        headerColor: "rgba(255,255,255,0.55)",
        colorText: "rgba(255,255,255,0.85)",
      },
      Modal: {
        contentBg: "rgba(20, 20, 30, 0.98)",
        headerBg: "transparent",
        titleColor: "rgba(255, 255, 255, 0.92)",
      },
      Alert: {
        colorInfoBg: "rgba(0,150,199,0.12)",
        colorInfoBorder: "rgba(0,150,199,0.3)",
        colorSuccessBg: "rgba(6,214,160,0.10)",
        colorSuccessBorder: "rgba(6,214,160,0.28)",
        colorWarningBg: "rgba(255,212,121,0.12)",
        colorWarningBorder: "rgba(255,212,121,0.3)",
        colorErrorBg: "rgba(255,138,138,0.12)",
        colorErrorBorder: "rgba(255,138,138,0.3)",
      },
      Descriptions: {
        labelBg: "transparent",
      },
      Progress: {
        defaultColor: "#06D6A0",
        remainingColor: "rgba(255,255,255,0.08)",
      },
      Tag: {
        defaultBg: "rgba(255,255,255,0.09)",
        defaultColor: "rgba(255,255,255,0.85)",
      },
    },
  },
};
