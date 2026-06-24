import { useEffect, useState, useCallback } from "react";
import { Button, Row, Col, Typography, Empty, Spin } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { Profile } from "../../types";
import { getProfiles } from "../../api/profiles";
import ProfileCard from "./ProfileCard";
import ProfileForm from "./ProfileForm";

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Profile | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getProfiles();
      setProfiles(data);
    } finally {
      setLoading(false);
    }
  }, []);

  // 每 5 秒轮询更新运行状态
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(profile: Profile) {
    setEditing(profile);
    setDrawerOpen(true);
  }

  function onFormClose() {
    setDrawerOpen(false);
    setEditing(null);
    refresh();
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Profile 管理
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建 Profile
        </Button>
      </div>

      {loading ? (
        <Spin />
      ) : profiles.length === 0 ? (
        <Empty description="暂无 Profile，点击右上角新建" />
      ) : (
        <Row gutter={[16, 16]}>
          {profiles.map((p) => (
            <Col key={p.id} xs={24} sm={12} lg={8} xl={6}>
              <ProfileCard profile={p} onEdit={openEdit} onRefresh={refresh} />
            </Col>
          ))}
        </Row>
      )}

      <ProfileForm open={drawerOpen} profile={editing} onClose={onFormClose} />
    </div>
  );
}
