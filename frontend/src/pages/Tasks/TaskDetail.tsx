import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Button, Table, Tag, Space, Typography, Form, Input,
  message, Modal, Checkbox, Spin, Popconfirm,
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import type { URLTaskDetail, TaskProfileEntry, Profile } from "../../types";
import { getTask, addProfilesToTask, removeProfileFromTask, updateProfileStatus, updateTask } from "../../api/tasks";
import { getProfiles } from "../../api/profiles";
import { launchInstance, stopInstance } from "../../api/instances";
import StatusBadge from "../../components/StatusBadge";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<URLTaskDetail | null>(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [allProfiles, setAllProfiles] = useState<Profile[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [form] = Form.useForm();

  const refresh = useCallback(async () => {
    if (!id) return;
    const data = await getTask(id);
    setTask(data);
    form.setFieldsValue({
      name: data.name,
      urls: data.urls.join("\n"),
      notes: data.notes,
    });
  }, [id, form]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  async function handleSaveTask() {
    if (!id) return;
    const values = await form.validateFields();
    const urls = (values.urls as string).split("\n").map((s: string) => s.trim()).filter(Boolean);
    await updateTask(id, { name: values.name, urls, notes: values.notes || "" });
    message.success("已保存");
    refresh();
  }

  async function openAddProfiles() {
    const profiles = await getProfiles();
    const existingIds = new Set(task?.profiles.map((p) => p.profile_id) ?? []);
    setAllProfiles(profiles.filter((p) => !existingIds.has(p.id)));
    setSelectedIds([]);
    setAddModalOpen(true);
  }

  async function handleAddProfiles() {
    if (!id || selectedIds.length === 0) return;
    await addProfilesToTask(id, selectedIds);
    setAddModalOpen(false);
    refresh();
  }

  async function handleLaunch(entry: TaskProfileEntry) {
    try {
      await launchInstance(entry.profile_id, id);
      message.success("启动成功");
      refresh();
    } catch (e: any) { message.error(e.message); }
  }

  async function handleStop(entry: TaskProfileEntry) {
    try {
      await stopInstance(entry.profile_id);
      message.success("已停止");
      refresh();
    } catch (e: any) { message.error(e.message); }
  }

  async function handleStatus(entry: TaskProfileEntry, status: "done" | "skipped" | "pending") {
    await updateProfileStatus(id!, entry.profile_id, status);
    refresh();
  }

  const statusTag: Record<string, React.ReactNode> = {
    pending: <Tag>待完成</Tag>,
    done: <Tag color="green">已完成</Tag>,
    skipped: <Tag color="orange">已跳过</Tag>,
  };

  const columns = [
    {
      title: "Profile",
      render: (_: unknown, r: TaskProfileEntry) => (
        <Space>
          <span
            style={{
              display: "inline-block",
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: r.profile?.color_tag ?? "#ccc",
            }}
          />
          {r.profile?.name ?? r.profile_id}
        </Space>
      ),
    },
    {
      title: "代理",
      render: (_: unknown, r: TaskProfileEntry) =>
        r.profile?.proxy_type === "none"
          ? "无代理"
          : `${r.profile?.proxy_type}://${r.profile?.proxy_host}:${r.profile?.proxy_port}`,
    },
    {
      title: "状态",
      render: (_: unknown, r: TaskProfileEntry) => (
        <Space>
          {statusTag[r.status]}
          {r.profile?.is_running && (
            <StatusBadge isRunning runningSince={r.profile.running_since} />
          )}
        </Space>
      ),
    },
    {
      title: "操作",
      render: (_: unknown, r: TaskProfileEntry) => (
        <Space size="small">
          {r.profile?.is_running ? (
            <Button size="small" danger onClick={() => handleStop(r)}>停止</Button>
          ) : (
            <Button size="small" type="primary" onClick={() => handleLaunch(r)}>启动</Button>
          )}
          <Button size="small" onClick={() => handleStatus(r, "done")} disabled={r.status === "done"}>
            标记完成
          </Button>
          <Button size="small" onClick={() => handleStatus(r, "skipped")} disabled={r.status === "skipped"}>
            跳过
          </Button>
          <Button size="small" onClick={() => handleStatus(r, "pending")} disabled={r.status === "pending"}>
            重置
          </Button>
          <Popconfirm title="移出任务？" onConfirm={() => removeProfileFromTask(id!, r.profile_id).then(refresh)}>
            <Button size="small" danger>移出</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (!task) return <Spin />;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/tasks")} style={{ marginBottom: 16 }}>
        返回
      </Button>
      <Form form={form} layout="vertical">
        <Form.Item label="任务名称" name="name" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="URL 列表（每行一个）" name="urls">
          <Input.TextArea rows={4} />
        </Form.Item>
        <Form.Item label="备注" name="notes">
          <Input />
        </Form.Item>
        <Button type="primary" onClick={handleSaveTask}>保存任务信息</Button>
      </Form>

      <div style={{ display: "flex", justifyContent: "space-between", margin: "24px 0 12px" }}>
        <Typography.Text strong>
          Profile 进度：{task.done_count} / {task.total_profiles} 已完成
        </Typography.Text>
        <Button onClick={openAddProfiles}>添加 Profile</Button>
      </div>

      <Table
        dataSource={task.profiles}
        columns={columns}
        rowKey="id"
        pagination={false}
        size="small"
        rowClassName={(r) => (r.profile?.is_running ? "ant-table-row-selected" : "")}
      />

      <Modal
        title="添加 Profile 到任务"
        open={addModalOpen}
        onOk={handleAddProfiles}
        onCancel={() => setAddModalOpen(false)}
        okText="添加"
      >
        <Checkbox.Group
          style={{ display: "flex", flexDirection: "column", gap: 8 }}
          options={allProfiles.map((p) => ({ label: p.name, value: p.id }))}
          value={selectedIds}
          onChange={(vals) => setSelectedIds(vals as string[])}
        />
        {allProfiles.length === 0 && <Typography.Text type="secondary">所有 Profile 已在此任务中</Typography.Text>}
      </Modal>
    </div>
  );
}
