import { apiFetch } from "./client";
import type { RunningInstance } from "../types";

export const getInstances = () => apiFetch<RunningInstance[]>("/instances");
export const launchInstance = (profile_id: string, task_id?: string) =>
  apiFetch<{ ok: boolean }>("/instances/launch", {
    method: "POST",
    body: JSON.stringify({ profile_id, task_id }),
  });
export const stopInstance = (profile_id: string) =>
  apiFetch<{ ok: boolean }>(`/instances/stop/${profile_id}`, { method: "POST" });
