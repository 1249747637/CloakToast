import { Layout, Menu, Button, Popconfirm, Tooltip, Typography, theme, App as AntdApp } from "antd";
import {
  PoweroffOutlined,
  AppstoreOutlined,
  BookOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import ProfilesPage from "./pages/Profiles";
import BookmarksPage from "./pages/Bookmarks";
import SettingsPage from "./pages/Settings";
import { shutdown } from "./api/system";

const { Sider, Content } = Layout;

const NAV_ITEMS = [
  { key: "/", label: "Profile 管理", icon: <AppstoreOutlined /> },
  { key: "/bookmarks", label: "书签", icon: <BookOutlined /> },
  { key: "/settings", label: "系统设置", icon: <SettingOutlined /> },
];

// 内联 SVG: 烤吐司金棕 + 半透明披风
function LogoMark({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      {/* 吐司轮廓 */}
      <path
        d="M4 9 C4 6.5 6 4.5 8.5 4.5 L15.5 4.5 C18 4.5 20 6.5 20 9 L20 18 C20 19.1 19.1 20 18 20 L6 20 C4.9 20 4 19.1 4 18 Z"
        fill="#D97706"
      />
      {/* 披风 */}
      <path
        d="M7 7 L17 7 L13 14 L9 14 Z"
        fill="rgba(255,255,255,0.55)"
      />
    </svg>
  );
}

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const { message } = AntdApp.useApp();
  const selectedKey = location.pathname.startsWith("/bookmarks") ? "/bookmarks" : location.pathname;

  async function handleShutdown() {
    try {
      await shutdown();
    } catch {
      // 服务器关闭后连接会断开，忽略错误
    }
    message.success("程序已退出");
    setTimeout(() => window.close(), 800);
  }

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={220} collapsible collapsedWidth={64} breakpoint="lg">
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Brand header */}
          <div
            style={{
              height: 56,
              padding: "14px 20px",
              borderBottom: "1px solid rgba(255,255,255,0.06)",
              display: "flex",
              alignItems: "center",
              gap: 12,
              flex: "0 0 auto",
            }}
          >
            <LogoMark size={22} />
            <Typography.Title
              level={5}
              style={{
                color: "#fff",
                margin: 0,
                letterSpacing: 0.3,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              CloakToast
            </Typography.Title>
          </div>

          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[selectedKey]}
            items={NAV_ITEMS}
            onClick={({ key }) => navigate(key)}
            style={{ flex: 1, borderInlineEnd: "none", paddingTop: 8 }}
          />

          {/* Sider footer: 退出按钮降级为 icon-only */}
          <div
            style={{
              padding: "12px 16px",
              borderTop: "1px solid rgba(255,255,255,0.06)",
              display: "flex",
              justifyContent: "flex-start",
            }}
          >
            <Popconfirm
              title="确认退出 CloakToast？"
              onConfirm={handleShutdown}
              okText="退出"
              cancelText="取消"
              placement="rightBottom"
            >
              <Tooltip title="关闭后端" placement="right">
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<PoweroffOutlined />}
                  style={{ color: "rgba(250,247,242,0.72)" }}
                />
              </Tooltip>
            </Popconfirm>
          </div>
        </div>
      </Sider>
      <Layout style={{ background: token.colorBgLayout }}>
        <Content style={{ background: token.colorBgLayout }}>
          <div style={{ maxWidth: 1440, margin: "0 auto", padding: "24px 32px" }}>
            <Routes>
              <Route path="/" element={<ProfilesPage />} />
              <Route path="/bookmarks" element={<BookmarksPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
