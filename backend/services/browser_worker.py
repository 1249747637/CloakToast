"""
独立子进程脚本，由 browser.py 以 subprocess 启动。
用法: python browser_worker.py <base64_json_payload>
"""
import sys
import json
import base64


def build_fingerprint_args(profile: dict) -> list[str]:
    args = []
    if profile.get("fingerprint_seed"):
        args.append(f"--fingerprint={profile['fingerprint_seed']}")
    if not profile.get("fp_noise_enabled", True):
        args.append("--fingerprint-noise=false")
    if profile.get("fp_platform"):
        args.append(f"--fingerprint-platform={profile['fp_platform']}")
    if profile.get("fp_hardware_concurrency"):
        args.append(f"--fingerprint-hardware-concurrency={profile['fp_hardware_concurrency']}")
    if profile.get("fp_device_memory"):
        args.append(f"--fingerprint-device-memory={profile['fp_device_memory']}")
    if profile.get("fp_screen_width"):
        args.append(f"--fingerprint-screen-width={profile['fp_screen_width']}")
    if profile.get("fp_screen_height"):
        args.append(f"--fingerprint-screen-height={profile['fp_screen_height']}")
    if profile.get("fp_taskbar_height"):
        args.append(f"--fingerprint-taskbar-height={profile['fp_taskbar_height']}")
    if profile.get("fp_gpu_vendor"):
        args.append(f"--fingerprint-gpu-vendor={profile['fp_gpu_vendor']}")
    if profile.get("fp_gpu_renderer"):
        args.append(f"--fingerprint-gpu-renderer={profile['fp_gpu_renderer']}")
    if profile.get("fp_webrtc_ip"):
        args.append(f"--fingerprint-webrtc-ip={profile['fp_webrtc_ip']}")
    lat = profile.get("fp_location_lat")
    lng = profile.get("fp_location_lng")
    if lat is not None and lng is not None:
        args.append(f"--fingerprint-location={lat},{lng}")
    if profile.get("fp_storage_quota"):
        args.append(f"--fingerprint-storage-quota={profile['fp_storage_quota']}")
    if profile.get("fp_fonts_dir"):
        args.append(f"--fingerprint-fonts-dir={profile['fp_fonts_dir']}")
    if profile.get("fp_brand"):
        args.append(f"--fingerprint-brand={profile['fp_brand']}")
    if profile.get("fp_brand_version"):
        args.append(f"--fingerprint-brand-version={profile['fp_brand_version']}")
    if profile.get("fp_platform_version"):
        args.append(f"--fingerprint-platform-version={profile['fp_platform_version']}")
    return args + (profile.get("extra_args") or [])


def build_proxy(profile: dict) -> str | None:
    if profile.get("proxy_type", "none") == "none" or not profile.get("proxy_host"):
        return None
    creds = ""
    if profile.get("proxy_user"):
        creds = f"{profile['proxy_user']}:{profile['proxy_pass']}@"
    return f"{profile['proxy_type']}://{creds}{profile['proxy_host']}:{profile['proxy_port']}"


def main():
    payload = json.loads(base64.b64decode(sys.argv[1]))
    profile = payload["profile"]
    urls = payload.get("urls", [])

    from cloakbrowser import launch_persistent_context

    context = launch_persistent_context(
        user_data_dir=profile["udd"],
        proxy=build_proxy(profile),
        timezone=profile.get("timezone") or None,
        locale=profile.get("locale") or None,
        humanize=profile.get("humanize", True),
        human_preset=profile.get("human_preset", "default"),
        headless=profile.get("headless", False),
        user_agent=profile.get("user_agent") or None,
        args=build_fingerprint_args(profile),
    )

    for url in urls:
        page = context.new_page()
        page.goto(url)

    context.wait_for_close()


if __name__ == "__main__":
    main()
