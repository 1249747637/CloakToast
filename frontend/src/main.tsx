import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider, App as AntdApp, theme as antdTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import "antd/dist/reset.css";

// Toasted Amber + Dark Roast 主题
const ctTheme = {
  algorithm: antdTheme.defaultAlgorithm,
  token: {
    // 品牌
    colorPrimary: "#D97706",
    colorInfo: "#D97706",
    colorSuccess: "#15803D",
    colorWarning: "#CA8A04",
    colorError: "#DC2626",
    colorLink: "#D97706",

    // 暖中性色
    colorBgLayout: "#FAF7F2",
    colorBgContainer: "#FFFFFF",
    colorBgElevated: "#FFFFFF",
    colorBorder: "#E7E2DA",
    colorBorderSecondary: "#F0EBE2",
    colorSplit: "rgba(31, 26, 23, 0.08)",
    colorText: "#1F1A17",
    colorTextSecondary: "#6B6259",
    colorTextTertiary: "#9A9089",
    colorTextDisabled: "#C4BCB2",
    colorTextLightSolid: "#FAF7F2",

    // 形状
    borderRadius: 8,
    borderRadiusLG: 12,
    borderRadiusSM: 6,
    borderRadiusXS: 4,

    // 字体
    fontFamily: `"Inter", "PingFang SC", "Microsoft YaHei", -apple-system, "Segoe UI", system-ui, sans-serif`,
    fontFamilyCode: `"JetBrains Mono", "Cascadia Code", Consolas, monospace`,
    fontSize: 14,
    fontSizeSM: 12,
    fontSizeLG: 16,
    fontSizeHeading3: 20,
    fontSizeHeading4: 16,

    // 间距
    paddingXS: 8,
    paddingSM: 12,
    padding: 16,
    paddingLG: 24,
    marginXS: 8,
    marginSM: 12,
    margin: 16,
    marginLG: 24,

    // 阴影
    boxShadowTertiary:
      "0 1px 2px rgba(31,26,23,0.04), 0 1px 3px rgba(31,26,23,0.03)",
    boxShadowSecondary:
      "0 6px 16px rgba(31,26,23,0.08), 0 3px 6px rgba(31,26,23,0.04)",

    motionDurationMid: "0.18s",
    motionDurationSlow: "0.28s",

    controlHeight: 36,
    wireframe: false,
  },
  components: {
    Layout: {
      siderBg: "#1F1A17",
      headerBg: "#FFFFFF",
      bodyBg: "#FAF7F2",
      triggerBg: "#15110F",
      triggerColor: "#FAF7F2",
    },
    Menu: {
      darkItemBg: "transparent",
      darkItemColor: "rgba(250,247,242,0.72)",
      darkItemHoverBg: "rgba(255,255,255,0.04)",
      darkItemHoverColor: "#FAF7F2",
      darkItemSelectedBg: "rgba(217,119,6,0.16)",
      darkItemSelectedColor: "#FBBF24",
      itemHeight: 40,
      itemBorderRadius: 8,
      itemMarginInline: 8,
    },
    Card: {
      headerBg: "transparent",
      headerFontSize: 15,
      paddingLG: 16,
      borderRadiusLG: 12,
      actionsBg: "transparent",
    },
    Button: {
      borderRadius: 8,
      controlHeight: 36,
      fontWeight: 500,
      primaryShadow: "0 1px 2px rgba(217,119,6,0.25)",
    },
    Tag: {
      borderRadiusSM: 6,
      defaultBg: "#F4EFE6",
      defaultColor: "#6B6259",
    },
    Tabs: {
      inkBarColor: "#D97706",
      itemSelectedColor: "#D97706",
      itemHoverColor: "#F59E0B",
    },
    Table: {
      headerBg: "#FAF7F2",
      headerColor: "#6B6259",
      rowHoverBg: "#FBF8F2",
      borderRadius: 10,
    },
    Input: {
      borderRadius: 8,
      activeShadow: "0 0 0 3px rgba(217,119,6,0.12)",
    },
    Switch: { colorPrimary: "#D97706" },
    Progress: { defaultColor: "#D97706" },
    Drawer: { paddingLG: 24 },
    Modal: { borderRadiusLG: 12 },
    Segmented: {
      itemSelectedBg: "#FFFFFF",
      trackBg: "#F0EBE2",
    },
    Badge: { statusSize: 8 },
  },
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={ctTheme}>
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>
);
