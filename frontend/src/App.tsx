import { Layout, Menu, Button, Popconfirm, message } from "antd";
import { PoweroffOutlined } from "@ant-design/icons";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import ProfilesPage from "./pages/Profiles";
import TasksPage from "./pages/Tasks";
import TaskDetailPage from "./pages/Tasks/TaskDetail";
import SettingsPage from "./pages/Settings";
import { shutdown } from "./api/system";

const { Sider, Content } = Layout;

const NAV_ITEMS = [
  { key: "/", label: "Profile 管理" },
  { key: "/tasks", label: "URL 任务" },
  { key: "/settings", label: "系统设置" },
];

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const selectedKey = location.pathname.startsWith("/tasks") ? "/tasks" : location.pathname;

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
      <Sider>
        <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
          <div style={{ padding: "16px 24px", color: "white", fontWeight: "bold", fontSize: 16 }}>
            CloakToast
          </div>
          <Menu
            theme="dark"
            selectedKeys={[selectedKey]}
            items={NAV_ITEMS}
            onClick={({ key }) => navigate(key)}
            style={{ flex: 1 }}
          />
          <div style={{ padding: 12 }}>
            <Popconfirm
              title="确认退出 CloakToast？"
              onConfirm={handleShutdown}
              okText="退出"
              cancelText="取消"
              placement="rightBottom"
            >
              <Button icon={<PoweroffOutlined />} danger block>
                退出程序
              </Button>
            </Popconfirm>
          </div>
        </div>
      </Sider>
      <Layout>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<ProfilesPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/tasks/:id" element={<TaskDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
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
