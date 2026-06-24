import { Tag, Tooltip, theme } from "antd";
import { CheckCircleFilled } from "@ant-design/icons";

interface Props {
  isRunning: boolean;
  runningSince?: string | null;
}

function elapsed(since: string): string {
  const secs = Math.floor((Date.now() - new Date(since).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m`;
  if (secs < 86400) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  return `${Math.floor(secs / 86400)}d`;
}

export default function StatusBadge({ isRunning, runningSince }: Props) {
  const { token } = theme.useToken();

  if (isRunning) {
    const label = runningSince ? `运行 ${elapsed(runningSince)}` : "运行中";
    return (
      <Tooltip title={runningSince ? `自 ${new Date(runningSince).toLocaleString()}` : "运行中"}>
        <Tag
          color="success"
          bordered={false}
          icon={<CheckCircleFilled />}
          style={{ margin: 0, fontWeight: 500 }}
        >
          {label}
        </Tag>
      </Tooltip>
    );
  }

  return (
    <Tag
      bordered={false}
      style={{
        margin: 0,
        background: token.colorFillTertiary,
        color: token.colorTextSecondary,
        fontWeight: 500,
      }}
    >
      已停止
    </Tag>
  );
}
