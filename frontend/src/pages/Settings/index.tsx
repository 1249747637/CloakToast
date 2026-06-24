import { useEffect, useState, useRef } from "react";
import { Card, Button, Input, Typography, Space, message, Spin } from "antd";
import type { SystemInfo } from "../../types";
import { getSystemInfo, saveLicense } from "../../api/system";

export default function SettingsPage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [licenseInput, setLicenseInput] = useState("");
  const [updating, setUpdating] = useState(false);
  const [updateLog, setUpdateLog] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSystemInfo().then((data) => {
      setInfo(data);
      setLicenseInput(data.license_key ?? "");
    });
  }, []);

  async function handleSaveLicense() {
    try {
      await saveLicense(licenseInput);
      message.success("License Key 已保存");
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleUpdate() {
    setUpdating(true);
    setUpdateLog([]);
    try {
      const res = await fetch("/api/system/update", { method: "POST" });
      if (!res.body) throw new Error("No response body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const text = line.slice(6);
            if (text !== "[DONE]") {
              setUpdateLog((prev) => [...prev, text]);
            }
            setTimeout(() => logRef.current?.scrollTo(0, logRef.current.scrollHeight), 0);
          }
        }
      }
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setUpdating(false);
      getSystemInfo().then(setInfo);
    }
  }

  if (!info) return <Spin />;

  return (
    <div style={{ maxWidth: 600 }}>
      <Typography.Title level={4}>系统设置</Typography.Title>

      <Card title="CloakBrowser" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Typography.Text>
            当前版本：<Typography.Text strong>{info.installed_version ?? "未安装"}</Typography.Text>
          </Typography.Text>
          <Button type="primary" loading={updating} onClick={handleUpdate}>
            执行更新
          </Button>
          {updateLog.length > 0 && (
            <div
              ref={logRef}
              style={{
                background: "#000",
                color: "#0f0",
                fontFamily: "monospace",
                fontSize: 12,
                padding: 12,
                borderRadius: 4,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {updateLog.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          )}
        </Space>
      </Card>

      <Card title="License Key">
        <Space.Compact style={{ width: "100%" }}>
          <Input.Password
            value={licenseInput}
            onChange={(e) => setLicenseInput(e.target.value)}
            placeholder="输入 CloakBrowser License Key"
          />
          <Button type="primary" onClick={handleSaveLicense}>
            保存
          </Button>
        </Space.Compact>
        <Typography.Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: "block" }}>
          保存后将在启动浏览器实例时自动注入
        </Typography.Text>
      </Card>
    </div>
  );
}
