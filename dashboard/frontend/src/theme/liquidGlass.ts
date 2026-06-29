import { buildLiquidGlassConfig } from "@xray/ui";

const tokens = {
  colorPrimary: "#6C8EFF",
  colorSuccess: "#34D399",
  colorWarning: "#FBBF24",
  colorError: "#F87171",
  colorInfo: "#8AABFF",

  colorText: "rgba(255, 255, 255, 0.88)",
  colorTextSecondary: "rgba(255, 255, 255, 0.55)",
  colorTextTertiary: "rgba(255, 255, 255, 0.35)",
  colorTextQuaternary: "rgba(255, 255, 255, 0.22)",

  colorBgBase: "#0C0F1A",
  colorBgContainer: "#111827",
  colorBgElevated: "#161D2F",
  colorBgLayout: "transparent",
  colorBgSpotlight: "#141928",

  colorBorder: "#1E2540",
  colorBorderSecondary: "#141928",
  colorFill: "rgba(255, 255, 255, 0.05)",
  colorFillSecondary: "rgba(255, 255, 255, 0.03)",
  colorFillTertiary: "rgba(255, 255, 255, 0.02)",
  colorFillQuaternary: "rgba(255, 255, 255, 0.01)",

  borderRadius: 8,
  borderRadiusLG: 12,
  borderRadiusSM: 6,
  borderRadiusXS: 4,

  controlHeight: 34,
  controlHeightSM: 26,
  controlHeightLG: 42,

  fontSize: 13,
  fontWeightStrong: 600,

  boxShadow: "0 4px 16px rgba(0, 0, 0, 0.4)",
  boxShadowSecondary: "0 2px 8px rgba(0, 0, 0, 0.3)",
};

const components = {
      Card: {
        colorBgContainer: "#111827",
        boxShadowTertiary: "none",
        headerBg: "transparent",
        colorTextHeading: "rgba(255, 255, 255, 0.88)",
        paddingLG: 18,
      },
      Button: {
        defaultShadow: "none",
        primaryShadow: "none",
        dangerShadow: "none",
        defaultBg: "rgba(255, 255, 255, 0.05)",
        defaultBorderColor: "#1E2540",
        defaultColor: "rgba(255, 255, 255, 0.82)",
        defaultHoverBg: "rgba(255, 255, 255, 0.09)",
        defaultHoverBorderColor: "#2A3558",
        defaultHoverColor: "#FFFFFF",
        defaultActiveBg: "rgba(255, 255, 255, 0.07)",
        colorBgTextHover: "rgba(255, 255, 255, 0.05)",
      },
      Modal: {
        contentBg: "#141928",
        headerBg: "transparent",
        titleColor: "rgba(255, 255, 255, 0.92)",
      },
      Drawer: {
        colorBgElevated: "#111827",
      },
      Input: {
        activeShadow: "none",
        colorBgContainer: "rgba(255, 255, 255, 0.04)",
        hoverBorderColor: "#2A3558",
        activeBorderColor: "#6C8EFF",
      },
      Select: {
        colorBgContainer: "rgba(255, 255, 255, 0.04)",
        colorBgElevated: "#161D2F",
        optionSelectedBg: "rgba(108, 142, 255, 0.12)",
      },
      Table: {
        colorBgContainer: "transparent",
        headerBg: "rgba(255, 255, 255, 0.025)",
        headerColor: "rgba(255, 255, 255, 0.40)",
        headerSplitColor: "transparent",
        rowHoverBg: "rgba(108, 142, 255, 0.045)",
        borderColor: "#14192C",
        colorText: "rgba(255, 255, 255, 0.82)",
        fontSize: 13,
      },
      Menu: {
        darkItemBg: "transparent",
        darkSubMenuItemBg: "transparent",
        darkItemSelectedBg: "rgba(108, 142, 255, 0.12)",
        darkItemHoverBg: "rgba(255, 255, 255, 0.04)",
        darkItemColor: "rgba(255, 255, 255, 0.52)",
        darkItemSelectedColor: "#8AABFF",
        darkItemHoverColor: "rgba(255, 255, 255, 0.82)",
        groupTitleColor: "rgba(255, 255, 255, 0.22)",
        groupTitleFontSize: 10,
        itemHeight: 36,
        iconSize: 15,
        iconMarginInlineEnd: 9,
      },
      Tag: {
        defaultBg: "rgba(255, 255, 255, 0.07)",
        defaultColor: "rgba(255, 255, 255, 0.82)",
        borderRadiusSM: 6,
      },
      Alert: {
        colorInfoBg: "rgba(108, 142, 255, 0.10)",
        colorInfoBorder: "rgba(108, 142, 255, 0.28)",
        colorWarningBg: "rgba(251, 191, 36, 0.10)",
        colorWarningBorder: "rgba(251, 191, 36, 0.28)",
        colorErrorBg: "rgba(248, 113, 113, 0.10)",
        colorErrorBorder: "rgba(248, 113, 113, 0.28)",
        colorSuccessBg: "rgba(52, 211, 153, 0.10)",
        colorSuccessBorder: "rgba(52, 211, 153, 0.28)",
      },
      Progress: {
        defaultColor: "#6C8EFF",
        remainingColor: "rgba(255, 255, 255, 0.07)",
      },
      Descriptions: {
        labelBg: "transparent",
        colorTextLabel: "rgba(255, 255, 255, 0.42)",
        colorText: "rgba(255, 255, 255, 0.88)",
      },
      Statistic: {
        colorTextDescription: "rgba(255, 255, 255, 0.45)",
        colorTextHeading: "#E2E8F8",
      },
      Result: {
        colorTextHeading: "rgba(255, 255, 255, 0.92)",
        colorTextDescription: "rgba(255, 255, 255, 0.55)",
      },
      Empty: {
        colorTextDescription: "rgba(255, 255, 255, 0.40)",
      },
      Tabs: {
        inkBarColor: "#6C8EFF",
        itemSelectedColor: "#8AABFF",
        itemColor: "rgba(255, 255, 255, 0.42)",
        itemHoverColor: "rgba(255, 255, 255, 0.75)",
      },
      Pagination: {
        itemBg: "rgba(255, 255, 255, 0.04)",
        itemActiveBg: "rgba(108, 142, 255, 0.15)",
      },
};

export const liquidGlassConfig = buildLiquidGlassConfig(tokens, components);
