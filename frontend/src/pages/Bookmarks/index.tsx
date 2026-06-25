import { useState, useEffect, useContext, createContext, useMemo } from "react";
import {
  Typography, Button, Table, Modal, Form, Input,
  Popconfirm, Space, message, Empty, theme,
} from "antd";
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  BookOutlined, HolderOutlined,
} from "@ant-design/icons";
import {
  DndContext, closestCenter, PointerSensor,
  useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, useSortable,
  verticalListSortingStrategy, arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Bookmark } from "../../types";
import {
  getBookmarks, createBookmark, updateBookmark,
  deleteBookmark, reorderBookmarks,
} from "../../api/bookmarks";

const { Title, Link } = Typography;

// ── drag handle context ────────────────────────────────────────────────────
interface RowCtx {
  setActivatorNodeRef?: (el: HTMLElement | null) => void;
  listeners?: Record<string, unknown>;
}
const RowContext = createContext<RowCtx>({});

function DragHandle() {
  const { token } = theme.useToken();
  const { setActivatorNodeRef, listeners } = useContext(RowContext);
  return (
    <Button
      type="text"
      size="small"
      icon={<HolderOutlined />}
      style={{ cursor: "move", touchAction: "none", color: token.colorTextTertiary }}
      ref={setActivatorNodeRef as any}
      {...(listeners as any)}
    />
  );
}

// ── draggable row ──────────────────────────────────────────────────────────
function DraggableRow({ "data-row-key": rowKey, ...props }: any) {
  const {
    attributes, listeners, setNodeRef, setActivatorNodeRef,
    transform, transition, isDragging,
  } = useSortable({ id: rowKey ?? "__placeholder__" });

  const contextValue = useMemo(
    () => ({ setActivatorNodeRef, listeners }),
    [setActivatorNodeRef, listeners],
  );

  if (!rowKey) return <tr {...props} />;

  const style: React.CSSProperties = {
    ...props.style,
    transform: CSS.Translate.toString(transform),
    transition,
    ...(isDragging ? { opacity: 0.7, boxShadow: "0 4px 16px rgba(0,0,0,0.12)", zIndex: 1 } : {}),
  };

  return (
    <RowContext.Provider value={contextValue}>
      <tr {...props} ref={setNodeRef} style={style} {...attributes} />
    </RowContext.Provider>
  );
}

// ── page ───────────────────────────────────────────────────────────────────
export default function BookmarksPage() {
  const { token } = theme.useToken();
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Bookmark | null>(null);
  const [form] = Form.useForm();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 1 } }),
  );

  async function refresh() {
    setLoading(true);
    try { setBookmarks(await getBookmarks()); }
    catch (e: any) { message.error(e.message); }
    finally { setLoading(false); }
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
        await createBookmark({ ...values, sort_order: bookmarks.length });
        message.success("已添加");
      }
      setModalOpen(false);
      refresh();
    } catch (e: any) { message.error(e.message); }
  }

  async function handleDelete(id: string) {
    try { await deleteBookmark(id); refresh(); }
    catch (e: any) { message.error(e.message); }
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) return;
    const oldIdx = bookmarks.findIndex(b => b.id === active.id);
    const newIdx = bookmarks.findIndex(b => b.id === over.id);
    const reordered = arrayMove(bookmarks, oldIdx, newIdx);
    setBookmarks(reordered);
    reorderBookmarks(reordered.map((b, i) => ({ id: b.id, sort_order: i })))
      .catch(e => { message.error(e.message); refresh(); });
  }

  const columns = [
    {
      key: "drag",
      width: 40,
      render: () => <DragHandle />,
    },
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      width: 200,
      render: (name: string) => (
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
      width: 100,
      render: (_: unknown, bm: Bookmark) => (
        <Space>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(bm)} />
          <Popconfirm
            title="确认删除此书签？"
            onConfirm={() => handleDelete(bm.id)}
            okText="删除" cancelText="取消"
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

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={bookmarks.map(b => b.id)} strategy={verticalListSortingStrategy}>
          <Table
            dataSource={bookmarks}
            columns={columns}
            rowKey="id"
            loading={loading}
            pagination={false}
            components={{ body: { row: DraggableRow } }}
            locale={{ emptyText: <Empty description="暂无书签，点击右上角添加" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
            style={{ background: token.colorBgContainer, borderRadius: token.borderRadiusLG }}
          />
        </SortableContext>
      </DndContext>

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
            name="url" label="URL"
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
