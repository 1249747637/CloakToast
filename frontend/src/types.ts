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
  created_at: string;
  updated_at: string;
  is_running: boolean;
  running_since: string | null;
}

export interface URLTask {
  id: string;
  name: string;
  urls: string[];
  notes: string;
  created_at: string;
}

export interface TaskProfileEntry {
  id: string;
  task_id: string;
  profile_id: string;
  status: "pending" | "done" | "skipped";
  notes: string;
  updated_at: string;
  profile: Profile | null;
}

export interface URLTaskDetail extends URLTask {
  profiles: TaskProfileEntry[];
  total_profiles: number;
  done_count: number;
}

export interface RunningInstance {
  profile_id: string;
  started_at: string;
  task_id: string | null;
}

export interface SystemInfo {
  installed_version: string | null;
  license_key: string | null;
}
