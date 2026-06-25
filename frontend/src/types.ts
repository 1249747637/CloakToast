export interface Profile {
  id: string;
  name: string;
  color_tag: string;
  notes: string;
  proxy_type: "none" | "http" | "socks5";
  proxy_host: string;
  proxy_port: number | null;
  proxy_user: string;
  proxy_pass: string;
  timezone: string;
  locale: string;
  headless: boolean;
  humanize: boolean;
  human_preset: string;
  fingerprint_seed: number | null;
  fp_noise_enabled: boolean;
  fp_platform: string;
  fp_hardware_concurrency: number | null;
  fp_device_memory: number | null;
  fp_screen_width: number | null;
  fp_screen_height: number | null;
  fp_taskbar_height: number | null;
  fp_gpu_vendor: string;
  fp_gpu_renderer: string;
  fp_webrtc_ip: string;
  fp_location_lat: number | null;
  fp_location_lng: number | null;
  fp_storage_quota: number | null;
  fp_fonts_dir: string;
  user_agent: string;
  fp_brand: string;
  fp_brand_version: string;
  fp_platform_version: string;
  extension_paths: string[];
  user_data_dir: string;
  cdp_port: number | null;
  extra_args: string[];
  block_video: boolean;
  block_image_max_kb: number | null;
  fp_webrtc_mode: string;
  geoip: boolean;
  relay_proxy_type: "none" | "http" | "socks5";
  relay_proxy_host: string;
  relay_proxy_port: number | null;
  relay_proxy_user: string;
  relay_proxy_pass: string;
  created_at: string;
  updated_at: string;
  is_running: boolean;
  running_since: string | null;
}

export interface Bookmark {
  id: string;
  name: string;
  url: string;
  notes: string;
  sort_order: number;
  created_at: string;
}

export interface RunningInstance {
  profile_id: string;
  started_at: string;
}

export interface SystemInfo {
  installed_version: string | null;
  license_key: string | null;
}
