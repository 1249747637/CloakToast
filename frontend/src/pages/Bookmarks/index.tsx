import { useState, useEffect } from "react";
import {
  Typography,
  Button,
  Table,
  Modal,
  Form,
  Input,
  Popconfirm,
  Space,
  message,
  Empty,
  theme,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined, BookOutlined } from "@ant-design/icons";
import type { Bookmark } from "../../types";
import { getBookmarks, createBookmark, updateBookmark, deleteBookmark } from "../../api/bookmarks";

const { Title, Link } = Typography;

export default function BookmarksPage() {
  const { token } = theme.useToken();
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Bookmark | null>(null);
  const [form] = Form.useForm();

  async function refresh() {
    setLoading(true);
    try {
      setBookmarks(await getBookmarks());
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  function openAdd() {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  }

  function openEdit(bm: Bookmark) {
    setEditing(bm);
    form.setFieldsValue({ name: bm.name, url: bm.url, notes: bm.notes });
    setModalOpen(true);
  }

  async function handleSubmit() {
    const values = await form.validateFields();
    try {
      if (editing) {
        await updateBookmark(editing.id, { ...values, sort_order: editing.sort_order });
        message.success("已更新");
      } else {
        await createBookmark({ ...values, sort_order: 0 });
        message.success("已添加");
      }
      setModalOpen(false);
      refresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteBookmark(id);
      refresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  const columns = [
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      width: 200,
      render: (name: string, bm: Bookmark) => (
        <Space>
          <BookOutlined style={{ color: token.colorPrimary }} />
          <span>{name}</span>
        </Space>
      ),
    },
    {
      title: "URL",
      dataIndex: "url",
      key: "url",
      render: (url: string) => (
        <Link href={url} target="_blank" ellipsis style={{ maxWidth: 400, display: "inline-block" }}>
          {url}
        </Link>
      ),
    },
    {
      title: "备注",
      dataIndex: "notes",
      key: "notes",
      render: (notes: string) => (
        <Typography.Text type="secondary" ellipsis style={{ maxWidth: 200 }}>
          {notes || "—"}
        </Typography.Text>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (_: unknown, bm: Bookmark) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(bm)}
          />
          <Popconfirm
            title="确认删除此书签？"
            onConfirm={() => handleDelete(bm.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0 }}>书签</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          添加书签
        </Button>
      </div>

      <Table
        dataSource={bookmarks}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        locale={{ emptyText: <Empty description="暂无书签，点击右上角添加" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        style={{ background: token.colorBgContainer, borderRadius: token.borderRadiusLG }}
      />

      <Modal
        title={editing ? "编辑书签" : "添加书签"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editing ? "保存" : "添加"}
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入书签名称" }]}>
            <Input placeholder="例：Google" />
          </Form.Item>
          <Form.Item
            name="url"
            label="URL"
            rules={[
              { required: true, message: "请输入 URL" },
              { type: "url", message: "请输入有效的 URL（含 http:// 或 https://）" },
            ]}
          >
            <Input placeholder="https://www.example.com" />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input.TextArea rows={2} placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
