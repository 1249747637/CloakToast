import { apiFetch } from "./client";
import type { SystemInfo } from "../types";

export const getSystemInfo = () => apiFetch<SystemInfo>("/system/info");
export const saveLicense = (license_key: string) =>
  apiFetch<{ ok: boolean }>("/system/license", {
    method: "PUT",
    body: JSON.stringify({ license_key }),
  });

export const shutdown = () =>
  apiFetch<{ ok: boolean }>("/system/shutdown", { method: "POST" });
