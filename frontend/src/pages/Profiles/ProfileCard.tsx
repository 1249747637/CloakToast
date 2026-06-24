import { Card, Button, Popconfirm, Space, Tag, Tooltip, Typography, message, theme } from "antd";
import {
  PlayCircleFilled,
  PoweroffOutlined,
  EditOutlined,
  CopyOutlined,
  DeleteOutlined,
  GlobalOutlined,
  DisconnectOutlined,
  EnvironmentOutlined,
  ThunderboltOutlined,
  VideoCameraOutlined,
  PictureOutlined,
  MessageOutlined,
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
  const { token } = theme.useToken();

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

  const hasProxy = profile.proxy_type !== "none";
  const hasBandwidth =
    profile.block_video || profile.block_image_max_kb !== null;

  const localeTzText = (() => {
    const locale = profile.locale || "未设置";
    if (profile.timezone) return `${locale} · ${profile.timezone}`;
    return `${locale} · 跟随代理 GeoIP`;
  })();

  function stopBubble(e: React.MouseEvent | React.KeyboardEvent) {
    e.stopPropagation();
  }

  function handleCardClick() {
    onEdit(profile);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.target !== e.currentTarget) return;
    if (e.key === "Enter") {
      e.preventDefault();
      onEdit(profile);
    } else if (e.key === " ") {
      e.preventDefault();
      profile.is_running ? handleStop() : handleLaunch();
    }
  }

  return (
    <Card
      hoverable
      bordered={false}
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      style={{
        borderRadius: 12,
        overflow: "hidden",
        boxShadow: token.boxShadowTertiary,
        minHeight: 196,
        borderLeft: `4px solid ${profile.color_tag || token.colorBorderSecondary}`,
        transition: "transform 150ms ease, box-shadow 150ms ease",
      }}
      styles={{ body: { padding: 0 } }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 16px 8px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
        }}
      >
        <Typography.Text
          strong
          style={{ fontSize: token.fontSizeLG, flex: 1, minWidth: 0 }}
          ellipsis={{ tooltip: profile.name }}
        >
          {profile.name}
        </Typography.Text>
        <div onClick={stopBubble}>
          <StatusBadge isRunning={profile.is_running} runningSince={profile.running_since} />
        </div>
      </div>

      {/* Body — 迷你定义网格 */}
      <div
        style={{
          padding: "4px 16px 12px 16px",
          display: "grid",
          gridTemplateColumns: "16px 1fr",
          rowGap: 6,
          columnGap: 10,
          alignItems: "center",
        }}
      >
        {/* 代理行 */}
        {hasProxy ? (
          <>
            <Tooltip title="代理">
              <GlobalOutlined style={{ color: token.colorTextSecondary }} />
            </Tooltip>
            <Space size={6} style={{ minWidth: 0 }}>
              <Typography.Text
                code
                style={{ fontFamily: token.fontFamilyCode, fontSize: 12 }}
                ellipsis
              >
                {profile.proxy_host}:{profile.proxy_port ?? ""}
              </Typography.Text>
              <Tag bordered={false} style={{ margin: 0, fontSize: 11 }}>
                {profile.proxy_type.toUpperCase()}
              </Tag>
            </Space>
          </>
        ) : (
          <>
            <Tooltip title="无代理">
              <DisconnectOutlined style={{ color: token.colorTextDisabled }} />
            </Tooltip>
            <Typography.Text type="secondary">直连</Typography.Text>
          </>
        )}

        {/* Locale / Timezone 行 */}
        <Tooltip title="Locale / Timezone">
          <EnvironmentOutlined style={{ color: token.colorTextSecondary }} />
        </Tooltip>
        <Typography.Text
          type="secondary"
          ellipsis={{ tooltip: localeTzText }}
          style={{ fontSize: 13 }}
        >
          {localeTzText}
        </Typography.Text>

        {/* 省流行 */}
        {hasBandwidth && (
          <>
            <Tooltip title="省流设置">
              <ThunderboltOutlined style={{ color: token.colorWarning }} />
            </Tooltip>
            <Space size={4} wrap>
              {profile.block_video && (
                <Tag color="geekblue" bordered={false} icon={<VideoCameraOutlined />} style={{ margin: 0 }}>
                  禁视频
                </Tag>
              )}
              {profile.block_image_max_kb === 0 && (
                <Tag color="geekblue" bordered={false} icon={<PictureOutlined />} style={{ margin: 0 }}>
                  禁图
                </Tag>
              )}
              {profile.block_image_max_kb !== null && profile.block_image_max_kb > 0 && (
                <Tag color="geekblue" bordered={false} icon={<PictureOutlined />} style={{ margin: 0 }}>
                  图≤{profile.block_image_max_kb}KB
                </Tag>
              )}
            </Space>
          </>
        )}

        {/* 辅助行 */}
        {(profile.headless || profile.humanize === false || profile.notes) && (
          <>
            <span />
            <Space size={4} wrap>
              {profile.headless && (
                <Tag bordered={false} style={{ margin: 0 }}>
                  无头
                </Tag>
              )}
              {profile.humanize === false && (
                <Tag color="warning" bordered={false} style={{ margin: 0 }}>
                  无拟人
                </Tag>
              )}
              {profile.notes && (
                <Tooltip title={profile.notes}>
                  <Tag bordered={false} icon={<MessageOutlined />} style={{ margin: 0 }}>
                    备注
                  </Tag>
                </Tooltip>
              )}
            </Space>
          </>
        )}
      </div>

      {/* Footer 工具栏 — 自渲染,不用 actions prop */}
      <div
        onClick={stopBubble}
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "8px 12px 12px 12px",
          borderTop: `1px solid ${token.colorSplit}`,
          marginTop: 8,
        }}
      >
        {/* 左 — 主操作 */}
        {profile.is_running ? (
          <Button danger icon={<PoweroffOutlined />} onClick={handleStop}>
            停止
          </Button>
        ) : (
          <Button type="primary" icon={<PlayCircleFilled />} onClick={handleLaunch}>
            启动
          </Button>
        )}

        {/* 右 — 次操作 (圆形 icon-only) */}
        <Space size={4}>
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              shape="circle"
              icon={<EditOutlined />}
              onClick={() => onEdit(profile)}
            />
          </Tooltip>
          <Tooltip title="复制">
            <Button
              type="text"
              size="small"
              shape="circle"
              icon={<CopyOutlined />}
              onClick={handleDuplicate}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除此 Profile？"
            onConfirm={handleDelete}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="删除">
              <Button
                type="text"
                size="small"
                shape="circle"
                danger
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      </div>
    </Card>
  );
}
