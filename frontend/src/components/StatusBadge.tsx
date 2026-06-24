import { Badge, Tooltip } from "antd";

interface Props {
  isRunning: boolean;
  runningSince?: string | null;
}

function elapsed(since: string): string {
  const secs = Math.floor((Date.now() - new Date(since).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m`;
  return `${Math.floor(secs / 3600)}h${Math.floor((secs % 3600) / 60)}m`;
}

export default function StatusBadge({ isRunning, runningSince }: Props) {
  if (isRunning) {
    return (
      <Tooltip title={runningSince ? `已运行 ${elapsed(runningSince)}` : "运行中"}>
        <Badge status="processing" text="运行中" />
      </Tooltip>
    );
  }
  return <Badge status="default" text="已停止" />;
}
