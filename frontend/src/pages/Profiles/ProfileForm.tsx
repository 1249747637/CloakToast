import { useEffect } from "react";
import {
  Drawer, Form, Input, Select, Switch, InputNumber, Button,
  Space, Tabs, Divider, message, ColorPicker,
} from "antd";
import { PlusOutlined, MinusCircleOutlined } from "@ant-design/icons";
import type { Profile } from "../../types";
import { createProfile, updateProfile } from "../../api/profiles";

interface Props {
  open: boolean;
  profile: Profile | null;
  onClose: () => void;
}

const TIMEZONES = [
  "Asia/Shanghai", "Asia/Tokyo", "Asia/Seoul", "Asia/Singapore",
  "America/New_York", "America/Los_Angeles", "Europe/London",
  "Europe/Berlin", "Europe/Moscow", "UTC",
];

const LOCALES = [
  { value: "zh-CN", label: "中文（简体）" },
  { value: "zh-TW", label: "中文（繁体）" },
  { value: "en-US", label: "English (US)" },
  { value: "ja-JP", label: "日本語" },
  { value: "ko-KR", label: "한국어" },
  { value: "ru-RU", label: "Русский" },
  { value: "de-DE", label: "Deutsch" },
  { value: "fr-FR", label: "Français" },
];

export default function ProfileForm({ open, profile, onClose }: Props) {
  const [form] = Form.useForm();
  const isEdit = !!profile;

  useEffect(() => {
    if (open) {
      if (profile) {
        form.setFieldsValue({
          ...profile,
          extra_args: profile.extra_args?.join("\n") ?? "",
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          color_tag: "#1677ff",
          proxy_type: "none",
          locale: "zh-CN",
          humanize: true,
          human_preset: "default",
          fp_noise_enabled: true,
          headless: false,
          block_video: false,
        });
      }
    }
  }, [open, profile, form]);

  async function onSubmit() {
    try {
      const values = await form.validateFields();
      const extra_args = ((values.extra_args as string) || "")
        .split("\n")
        .map((s: string) => s.trim())
        .filter(Boolean);
      const payload = { ...values, extra_args };
      if (typeof payload.color_tag === "object") {
        payload.color_tag = (payload.color_tag as any).toHexString?.() ?? payload.color_tag;
      }
      if (isEdit) {
        await updateProfile(profile!.id, payload);
        message.success("已保存");
      } else {
        await createProfile(payload);
        message.success("创建成功");
      }
      onClose();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message);
    }
  }

  const commonTab = (
    <>
      <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
        <Input placeholder="Profile 名称" />
      </Form.Item>
      <Form.Item label="颜色标签" name="color_tag">
        <ColorPicker format="hex" />
      </Form.Item>
      <Form.Item label="备注" name="notes">
        <Input.TextArea rows={2} />
      </Form.Item>
      <Divider>代理设置</Divider>
      <Form.Item label="代理类型" name="proxy_type">
        <Select options={[
          { value: "none", label: "不使用" },
          { value: "http", label: "HTTP" },
          { value: "socks5", label: "SOCKS5" },
        ]} />
      </Form.Item>
      <Form.Item noStyle shouldUpdate={(p, c) => p.proxy_type !== c.proxy_type}>
        {({ getFieldValue }) =>
          getFieldValue("proxy_type") !== "none" && (
            <>
              <Form.Item label="Host" name="proxy_host">
                <Input placeholder="127.0.0.1" />
              </Form.Item>
              <Form.Item label="Port" name="proxy_port">
                <InputNumber style={{ width: "100%" }} min={1} max={65535} />
              </Form.Item>
              <Form.Item label="用户名" name="proxy_user">
                <Input />
              </Form.Item>
              <Form.Item label="密码" name="proxy_pass">
                <Input.Password />
              </Form.Item>
            </>
          )
        }
      </Form.Item>
      <Divider>浏览器设置</Divider>
      <Form.Item label="时区" name="timezone">
        <Select
          allowClear
          placeholder="留空=跟随代理 GeoIP"
          options={TIMEZONES.map((tz) => ({ value: tz, label: tz }))}
        />
      </Form.Item>
      <Form.Item label="语言" name="locale">
        <Select options={LOCALES} />
      </Form.Item>
      <Divider>省流设置</Divider>
      <Form.Item
        label="屏蔽视频"
        name="block_video"
        valuePropName="checked"
        tooltip="同时屏蔽 <video>/<audio> 和 HLS/DASH (.m3u8/.mpd/.ts) 流量。适合只需要浏览页面、不需要看视频的代理场景。"
        extra="拦截页面内的视频/音频与流媒体请求，显著降低带宽占用。"
      >
        <Switch checkedChildren="拦截" unCheckedChildren="放行" />
      </Form.Item>
      <Form.Item
        label="图片大小上限 (KB)"
        name="block_image_max_kb"
        extra="留空=不限制；0=屏蔽所有图片；填正数=超过该 KB 的图片直接 abort（HEAD 先探）"
      >
        <InputNumber
          style={{ width: "100%" }}
          min={0}
          max={102400}
          step={50}
          placeholder="留空=不限制"
        />
      </Form.Item>
      <Form.Item label="无头模式" name="headless" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item label="Humanize" name="humanize" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item label="Humanize 预设" name="human_preset">
        <Select options={[
          { value: "default", label: "Default" },
          { value: "careful", label: "Careful（更谨慎）" },
        ]} />
      </Form.Item>
    </>
  );

  const fingerprintTab = (
    <>
      <Form.Item label="指纹 Seed" name="fingerprint_seed" extra="留空=每次随机">
        <InputNumber style={{ width: "100%" }} min={1} />
      </Form.Item>
      <Form.Item label="噪声注入" name="fp_noise_enabled" valuePropName="checked">
        <Switch checkedChildren="开启" unCheckedChildren="关闭" />
      </Form.Item>
      <Form.Item label="平台伪装" name="fp_platform">
        <Select allowClear placeholder="跟随种子" options={[
          { value: "windows", label: "Windows" },
          { value: "macos", label: "macOS" },
        ]} />
      </Form.Item>
      <Form.Item label="CPU 核心数" name="fp_hardware_concurrency" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} min={1} max={256} />
      </Form.Item>
      <Form.Item label="设备内存(GB)" name="fp_device_memory" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} min={1} max={512} />
      </Form.Item>
      <Space.Compact block>
        <Form.Item label="屏幕宽度" name="fp_screen_width" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=随机" />
        </Form.Item>
        <Form.Item label="屏幕高度" name="fp_screen_height" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=随机" />
        </Form.Item>
      </Space.Compact>
      <Form.Item label="任务栏高度" name="fp_taskbar_height" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="WebGL 厂商" name="fp_gpu_vendor" extra="留空=跟随种子">
        <Input placeholder="如 Intel Inc." />
      </Form.Item>
      <Form.Item label="WebGL 渲染器" name="fp_gpu_renderer" extra="留空=跟随种子">
        <Input placeholder="如 Intel Iris OpenGL Engine" />
      </Form.Item>
      <Form.Item label="WebRTC IP" name="fp_webrtc_ip" extra="留空=不覆盖">
        <Input placeholder="如 192.168.1.1" />
      </Form.Item>
      <Space.Compact block>
        <Form.Item label="纬度" name="fp_location_lat" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=不覆盖" />
        </Form.Item>
        <Form.Item label="经度" name="fp_location_lng" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=不覆盖" />
        </Form.Item>
      </Space.Compact>
      <Form.Item label="存储配额(MB)" name="fp_storage_quota" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="字体目录" name="fp_fonts_dir" extra="留空=不覆盖">
        <Input placeholder="C:\fonts" />
      </Form.Item>
    </>
  );

  const advancedTab = (
    <>
      <Form.Item label="User Agent" name="user_agent" extra="留空=自动">
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item label="浏览器品牌" name="fp_brand" extra="留空=自动">
        <Input />
      </Form.Item>
      <Form.Item label="品牌版本" name="fp_brand_version">
        <Input />
      </Form.Item>
      <Form.Item label="系统版本" name="fp_platform_version">
        <Input />
      </Form.Item>
      <Divider>扩展路径</Divider>
      <Form.List name="extension_paths">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...rest }) => (
              <Form.Item key={key} {...rest} name={name} style={{ marginBottom: 8 }}>
                <Input
                  placeholder="扩展目录路径"
                  suffix={
                    <MinusCircleOutlined onClick={() => remove(name)} style={{ color: "red" }} />
                  }
                />
              </Form.Item>
            ))}
            <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />} block>
              添加扩展路径
            </Button>
          </>
        )}
      </Form.List>
      <Divider />
      <Form.Item label="User Data Dir" name="user_data_dir" extra="留空=自动管理">
        <Input />
      </Form.Item>
      <Form.Item label="CDP 端口" name="cdp_port" extra="留空=自动分配">
        <InputNumber style={{ width: "100%" }} min={1024} max={65535} />
      </Form.Item>
      <Form.Item label="额外启动参数" name="extra_args" extra="每行一条">
        <Input.TextArea rows={4} placeholder={"--disable-web-security\n--no-sandbox"} />
      </Form.Item>
    </>
  );

  return (
    <Drawer
      title={isEdit ? "编辑 Profile" : "新建 Profile"}
      open={open}
      onClose={onClose}
      width={520}
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={onSubmit}>
            保存
          </Button>
        </Space>
      }
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Tabs
          items={[
            { key: "common", label: "常用", children: commonTab },
            { key: "fingerprint", label: "指纹", children: fingerprintTab },
            { key: "advanced", label: "高级", children: advancedTab },
          ]}
        />
      </Form>
    </Drawer>
  );
}
