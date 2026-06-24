import { apiFetch } from "./client";
import type { Profile } from "../types";

export const getProfiles = () => apiFetch<Profile[]>("/profiles");
export const getProfile = (id: string) => apiFetch<Profile>(`/profiles/${id}`);
export const createProfile = (data: Partial<Profile>) =>
  apiFetch<Profile>("/profiles", { method: "POST", body: JSON.stringify(data) });
export const updateProfile = (id: string, data: Partial<Profile>) =>
  apiFetch<Profile>(`/profiles/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteProfile = (id: string) =>
  apiFetch<{ ok: boolean }>(`/profiles/${id}`, { method: "DELETE" });
export const duplicateProfile = (id: string) =>
  apiFetch<Profile>(`/profiles/${id}/duplicate`, { method: "POST" });
