import { useEffect } from "react";
import {
  Drawer, Form, Input, Select, Switch, InputNumber, Button,
  Space, Tabs, Divider, message, ColorPicker, Collapse,
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

const SCREEN_WIDTHS = [1280, 1366, 1440, 1600, 1920, 2560, 3840];
const SCREEN_HEIGHTS = [768, 800, 900, 1024, 1080, 1200, 1440, 2160];
const TASKBAR_HEIGHTS = [0, 40, 48, 56, 80];

const SCREEN_PRESETS = [
  { label: "1920×1080", w: 1920, h: 1080 },
  { label: "2560×1440", w: 2560, h: 1440 },
  { label: "1366×768",  w: 1366, h: 768  },
  { label: "1440×900",  w: 1440, h: 900  },
  { label: "1280×800",  w: 1280, h: 800  },
];

const BRAND_VERSIONS: Record<string, string[]> = {
  "Google Chrome":   ["138", "137", "136", "135", "134", "133", "132"],
  "Microsoft Edge":  ["138", "137", "136", "135", "134", "133", "132"],
  "Brave":           ["1.77", "1.76", "1.75", "1.74", "1.73"],
  "Opera":           ["118", "117", "116", "115"],
  "Vivaldi":         ["7.3", "7.2", "7.1", "7.0"],
};

const PLATFORM_VERSIONS: Record<string, string[]> = {
  windows: ["10.0.0", "15.0.0"],
  macos:   ["15.0", "14.0", "13.0", "12.0"],
};

export default function ProfileForm({ open, profile, onClose }: Props) {
  const [form] = Form.useForm();
  const isEdit = !!profile;

  useEffect(() => {
    if (open) {
      if (profile) {
        form.setFieldsValue({
          ...profile,
          extra_args: profile.extra_args?.join("\n") ?? "",
          // 旧数据兼容：有 webrtc_ip 但无 webrtc_mode 时自动推断为 custom
          fp_webrtc_mode: profile.fp_webrtc_mode || (profile.fp_webrtc_ip ? "custom" : ""),
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          color_tag: "#1677ff",
          proxy_type: "none",
          relay_proxy_type: "none",
          locale: "zh-CN",
          humanize: true,
          human_preset: "default",
          fp_noise_enabled: true,
          headless: false,
          block_video: false,
          geoip: false,
          fp_webrtc_mode: "",
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

  // 中继代理折叠面板内容（抽出以减少 JSX 嵌套层级）
  const relayPanelChildren = (
    <>
      <Form.Item label="中继类型" name="relay_proxy_type">
        <Select options={[
          { value: "none",   label: "不使用" },
          { value: "http",   label: "HTTP" },
          { value: "socks5", label: "SOCKS5" },
        ]} />
      </Form.Item>
      <Form.Item noStyle shouldUpdate={(p, c) => p.relay_proxy_type !== c.relay_proxy_type}>
        {({ getFieldValue }) =>
          getFieldValue("relay_proxy_type") !== "none" && (
            <>
              <Form.Item label="中继 Host" name="relay_proxy_host">
                <Input placeholder="127.0.0.1" />
              </Form.Item>
              <Form.Item label="中继 Port" name="relay_proxy_port">
                <InputNumber style={{ width: "100%" }} min={1} max={65535} />
              </Form.Item>
              <Form.Item label="中继用户名" name="relay_proxy_user">
                <Input />
              </Form.Item>
              <Form.Item label="中继密码" name="relay_proxy_pass">
                <Input.Password />
              </Form.Item>
            </>
          )
        }
      </Form.Item>
    </>
  );

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
          { value: "none",   label: "不使用" },
          { value: "http",   label: "HTTP" },
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
              <Collapse
                ghost
                size="small"
                style={{ marginBottom: 8 }}
                items={[{
                  key: "relay",
                  label: "中继代理（链式，可选）",
                  children: relayPanelChildren,
                }]}
              />
            </>
          )
        }
      </Form.Item>

      <Divider>浏览器设置</Divider>
      <Form.Item noStyle shouldUpdate={(p, c) =>
        p.proxy_type !== c.proxy_type || p.relay_proxy_type !== c.relay_proxy_type}>
        {({ getFieldValue }) => {
          const hasProxy = getFieldValue("proxy_type") !== "none";
          const hasRelay = getFieldValue("relay_proxy_type") !== "none";
          const tip = !hasProxy
            ? "需先配置代理才能启用"
            : hasRelay
            ? "中继代理激活时不支持 GeoIP（IP 归属地为中继出口，而非目标代理）"
            : "自动从代理出口 IP 推断时区、语言、地理位置（需 pip install cloakbrowser[geoip]）";
          return (
            <Form.Item
              label="GeoIP 跟随代理"
              name="geoip"
              valuePropName="checked"
              tooltip={tip}
              extra="启用后时区/语言将由代理出口 IP 自动推断，手动填写可覆盖"
            >
              <Switch disabled={!hasProxy || hasRelay} />
            </Form.Item>
          );
        }}
      </Form.Item>
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
          { value: "macos",   label: "macOS" },
        ]} />
      </Form.Item>
      <Form.Item label="CPU 核心数" name="fp_hardware_concurrency" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} min={1} max={256} />
      </Form.Item>
      <Form.Item label="设备内存(GB)" name="fp_device_memory" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} min={1} max={512} />
      </Form.Item>

      <Form.Item label="分辨率预设" extra="点击快速填充下方宽/高">
        <Space wrap size={[4, 4]}>
          {SCREEN_PRESETS.map((p) => (
            <Button
              key={p.label}
              size="small"
              onClick={() => form.setFieldsValue({ fp_screen_width: p.w, fp_screen_height: p.h })}
            >
              {p.label}
            </Button>
          ))}
        </Space>
      </Form.Item>
      <Space.Compact block>
        <Form.Item label="屏幕宽度" name="fp_screen_width" style={{ width: "50%" }}>
          <Select
            allowClear
            showSearch
            placeholder="留空=真实分辨率"
            style={{ width: "100%" }}
            filterOption={(input, opt) => String(opt?.value ?? "").includes(input)}
            options={SCREEN_WIDTHS.map((v) => ({ value: v, label: `${v}px` }))}
          />
        </Form.Item>
        <Form.Item label="屏幕高度" name="fp_screen_height" style={{ width: "50%" }}>
          <Select
            allowClear
            showSearch
            placeholder="留空=真实分辨率"
            style={{ width: "100%" }}
            filterOption={(input, opt) => String(opt?.value ?? "").includes(input)}
            options={SCREEN_HEIGHTS.map((v) => ({ value: v, label: `${v}px` }))}
          />
        </Form.Item>
      </Space.Compact>
      <Form.Item label="任务栏高度" name="fp_taskbar_height" extra="留空=跟随种子">
        <Select
          allowClear
          placeholder="留空=跟随种子"
          options={TASKBAR_HEIGHTS.map((v) => ({ value: v, label: `${v}px` }))}
        />
      </Form.Item>

      <Form.Item label="WebGL 厂商" name="fp_gpu_vendor" extra="留空=跟随种子">
        <Input placeholder="如 Intel Inc." />
      </Form.Item>
      <Form.Item label="WebGL 渲染器" name="fp_gpu_renderer" extra="留空=跟随种子">
        <Input placeholder="如 Intel Iris OpenGL Engine" />
      </Form.Item>

      <Form.Item label="WebRTC 模式" name="fp_webrtc_mode">
        <Select
          allowClear
          placeholder="默认（不干预）"
          options={[
            { value: "custom", label: "自定义 IP — 替换为指定地址" },
            { value: "mask",   label: "掩盖 — 覆盖为 10.0.0.1（WebRTC 可用）" },
            { value: "block",  label: "禁止 — 完全禁用 RTCPeerConnection" },
          ]}
        />
      </Form.Item>
      <Form.Item noStyle shouldUpdate={(p, c) => p.fp_webrtc_mode !== c.fp_webrtc_mode}>
        {({ getFieldValue }) =>
          getFieldValue("fp_webrtc_mode") === "custom" && (
            <Form.Item label="WebRTC IP" name="fp_webrtc_ip" extra="替换所有 WebRTC ICE 候选中的 IP">
              <Input placeholder="如 192.168.1.1" />
            </Form.Item>
          )
        }
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
        <Select
          allowClear
          placeholder="留空=自动"
          options={Object.keys(BRAND_VERSIONS).map((b) => ({ value: b, label: b }))}
          onChange={() => form.setFieldValue("fp_brand_version", undefined)}
        />
      </Form.Item>
      <Form.Item noStyle shouldUpdate={(p, c) => p.fp_brand !== c.fp_brand}>
        {({ getFieldValue }) => {
          const brand = getFieldValue("fp_brand") as string | undefined;
          const versions = brand ? (BRAND_VERSIONS[brand] ?? []) : [];
          return (
            <Form.Item label="品牌版本" name="fp_brand_version" extra="留空=自动">
              <Select
                allowClear
                placeholder={brand ? "选择版本" : "请先选择品牌"}
                disabled={!brand}
                options={versions.map((v) => ({ value: v, label: v }))}
              />
            </Form.Item>
          );
        }}
      </Form.Item>
      <Form.Item noStyle shouldUpdate={(p, c) => p.fp_platform !== c.fp_platform}>
        {({ getFieldValue }) => {
          const platform = getFieldValue("fp_platform") as string | undefined;
          const versions = platform ? (PLATFORM_VERSIONS[platform] ?? []) : [];
          return versions.length > 0 ? (
            <Form.Item label="系统版本" name="fp_platform_version" extra="留空=自动">
              <Select
                allowClear
                placeholder="选择常见版本"
                options={versions.map((v) => ({ value: v, label: v }))}
              />
            </Form.Item>
          ) : (
            <Form.Item label="系统版本" name="fp_platform_version" extra="留空=自动">
              <Input placeholder={platform ? "手动输入版本号" : "请先在指纹页选择平台"} />
            </Form.Item>
          );
        }}
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
            { key: "common",      label: "常用",  children: commonTab },
            { key: "fingerprint", label: "指纹",  children: fingerprintTab },
            { key: "advanced",    label: "高级",  children: advancedTab },
          ]}
        />
      </Form>
    </Drawer>
  );
}
