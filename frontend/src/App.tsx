import { Layout, Menu } from "antd";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import ProfilesPage from "./pages/Profiles";
import TasksPage from "./pages/Tasks";
import TaskDetailPage from "./pages/Tasks/TaskDetail";
import SettingsPage from "./pages/Settings";

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

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider>
        <div style={{ padding: "16px 24px", color: "white", fontWeight: "bold", fontSize: 16 }}>
          CloakToast
        </div>
        <Menu
          theme="dark"
          selectedKeys={[selectedKey]}
          items={NAV_ITEMS}
          onClick={({ key }) => navigate(key)}
        />
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
