import { apiFetch } from "./client";
import type { URLTask, URLTaskDetail } from "../types";

export const getTasks = () => apiFetch<URLTask[]>("/tasks");
export const getTask = (id: string) => apiFetch<URLTaskDetail>(`/tasks/${id}`);
export const createTask = (data: Partial<URLTask>) =>
  apiFetch<URLTask>("/tasks", { method: "POST", body: JSON.stringify(data) });
export const updateTask = (id: string, data: Partial<URLTask>) =>
  apiFetch<URLTask>(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteTask = (id: string) =>
  apiFetch<{ ok: boolean }>(`/tasks/${id}`, { method: "DELETE" });
export const addProfilesToTask = (task_id: string, profile_ids: string[]) =>
  apiFetch<{ ok: boolean }>(`/tasks/${task_id}/profiles`, {
    method: "POST",
    body: JSON.stringify({ profile_ids }),
  });
export const removeProfileFromTask = (task_id: string, profile_id: string) =>
  apiFetch<{ ok: boolean }>(`/tasks/${task_id}/profiles/${profile_id}`, { method: "DELETE" });
export const updateProfileStatus = (
  task_id: string,
  profile_id: string,
  status: string,
  notes = ""
) =>
  apiFetch<{ ok: boolean }>(`/tasks/${task_id}/profiles/${profile_id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, notes }),
  });
