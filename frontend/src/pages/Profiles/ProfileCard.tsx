import { Card, Button, Popconfirm, Space, Typography, message } from "antd";
import {
  PlayCircleOutlined,
  StopOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import type { Profile } from "../../types";
import StatusBadge from "../../components/StatusBadge";
import { launchInstance, stopInstance } from "../../api/instances";
import { deleteProfile, duplicateProfile } from "../../api/profiles";

interface Props {
  profile: Profile;
  onEdit: (profile: Profile) => void;
  onRefresh: () => void;
}

export default function ProfileCard({ profile, onEdit, onRefresh }: Props) {
  const proxyLabel =
    profile.proxy_type === "none"
      ? "无代理"
      : `${profile.proxy_type}://${profile.proxy_host}:${profile.proxy_port}`;

  async function handleLaunch() {
    try {
      await launchInstance(profile.id);
      message.success("启动成功");
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleStop() {
    try {
      await stopInstance(profile.id);
      message.success("已停止");
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleDuplicate() {
    try {
      await duplicateProfile(profile.id);
      message.success("已复制");
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleDelete() {
    try {
      await deleteProfile(profile.id);
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  return (
    <Card
      size="small"
      title={
        <Space>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: profile.color_tag,
            }}
          />
          <Typography.Text strong>{profile.name}</Typography.Text>
        </Space>
      }
      extra={<StatusBadge isRunning={profile.is_running} runningSince={profile.running_since} />}
      actions={[
        profile.is_running ? (
          <Button
            key="stop"
            type="text"
            danger
            icon={<StopOutlined />}
            onClick={handleStop}
          >
            停止
          </Button>
        ) : (
          <Button key="launch" type="text" icon={<PlayCircleOutlined />} onClick={handleLaunch}>
            启动
          </Button>
        ),
        <Button key="edit" type="text" icon={<EditOutlined />} onClick={() => onEdit(profile)}>
          编辑
        </Button>,
        <Button key="copy" type="text" icon={<CopyOutlined />} onClick={handleDuplicate}>
          复制
        </Button>,
        <Popconfirm
          key="delete"
          title="确认删除此 Profile？"
          onConfirm={handleDelete}
          okText="删除"
          cancelText="取消"
        >
          <Button type="text" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>,
      ]}
    >
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {proxyLabel}
      </Typography.Text>
      {profile.notes && (
        <Typography.Paragraph
          type="secondary"
          style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}
          ellipsis={{ rows: 1 }}
        >
          {profile.notes}
        </Typography.Paragraph>
      )}
    </Card>
  );
}
