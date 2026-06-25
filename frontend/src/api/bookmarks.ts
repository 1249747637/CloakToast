import { apiFetch } from "./client";
import type { Bookmark } from "../types";

export const getBookmarks = () => apiFetch<Bookmark[]>("/bookmarks");
export const createBookmark = (data: Omit<Bookmark, "id" | "created_at">) =>
  apiFetch<Bookmark>("/bookmarks", { method: "POST", body: JSON.stringify(data) });
export const updateBookmark = (id: string, data: Omit<Bookmark, "id" | "created_at">) =>
  apiFetch<Bookmark>(`/bookmarks/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteBookmark = (id: string) =>
  apiFetch<{ ok: boolean }>(`/bookmarks/${id}`, { method: "DELETE" });
export const reorderBookmarks = (items: { id: string; sort_order: number }[]) =>
  apiFetch<{ ok: boolean }>("/bookmarks/reorder", { method: "POST", body: JSON.stringify(items) });
