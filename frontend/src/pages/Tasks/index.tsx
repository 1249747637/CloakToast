import { useEffect, useState } from "react";
import { Table, Button, Popconfirm, Typography, Modal, Form, Input, message } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { URLTaskDetail } from "../../types";
import { getTasks, createTask, deleteTask } from "../../api/tasks";

export default function TasksPage() {
  const [tasks, setTasks] = useState<URLTaskDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  async function refresh() {
    try {
      setTasks(await getTasks());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function handleCreate() {
    try {
      const values = await form.validateFields();
      const urls = ((values.urls as string) || "").split("\n").map((s: string) => s.trim()).filter(Boolean);
      await createTask({ name: values.name, urls, notes: values.notes || "" });
      message.success("创建成功");
      setModalOpen(false);
      form.resetFields();
      refresh();
    } catch (e: any) {
      if (!e?.errorFields) message.error(e.message);
    }
  }

  async function handleDelete(id: string) {
    await deleteTask(id);
    refresh();
  }

  const columns = [
    {
      title: "任务名称",
      dataIndex: "name",
      render: (name: string, r: URLTaskDetail) => (
        <Button type="link" onClick={() => navigate(`/tasks/${r.id}`)}>{name}</Button>
      ),
    },
    { title: "URL 数量", dataIndex: "urls", render: (urls: string[]) => urls.length },
    { title: "Profile 总数", dataIndex: "total_profiles" },
    {
      title: "完成进度",
      render: (_: unknown, r: URLTaskDetail) => `${r.done_count} / ${r.total_profiles}`,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      render: (_: unknown, r: URLTaskDetail) => (
        <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
          <Button type="link" danger>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>URL 任务</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建任务
        </Button>
      </div>
      <Table
        dataSource={tasks}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
      />
      <Modal
        title="新建任务"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="创建"
      >
        <Form form={form} layout="vertical">
          <Form.Item label="任务名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="URL 列表（每行一个）" name="urls">
            <Input.TextArea rows={5} placeholder={"https://example.com\nhttps://another.com"} />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
