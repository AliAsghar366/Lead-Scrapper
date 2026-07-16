import type {
  Lead, LeadListResponse, LeadNote, LeadList, SavedSearch,
  ActivityLog, SearchJob, SearchSubmitResponse, LeadStatus,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const API = `${BASE}/api/v1`;

export interface LeadFilters {
  has_phone?: boolean;
  has_email?: boolean;
  has_website?: boolean;
  has_address?: boolean;
  has_social?: boolean;
  status?: LeadStatus | "";
  min_score?: number;
  tags?: string;
  list_id?: number;
  search?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

function filtersToParams(f: LeadFilters): string {
  const parts: string[] = [];
  if (f.has_phone)   parts.push("has_phone=true");
  if (f.has_email)   parts.push("has_email=true");
  if (f.has_website) parts.push("has_website=true");
  if (f.has_address) parts.push("has_address=true");
  if (f.has_social)  parts.push("has_social=true");
  if (f.status)      parts.push(`status=${encodeURIComponent(f.status)}`);
  if (f.min_score != null) parts.push(`min_score=${f.min_score}`);
  if (f.tags)        parts.push(`tags=${encodeURIComponent(f.tags)}`);
  if (f.list_id != null) parts.push(`list_id=${f.list_id}`);
  if (f.search)      parts.push(`search=${encodeURIComponent(f.search)}`);
  if (f.sort_by)     parts.push(`sort_by=${f.sort_by}`);
  if (f.sort_dir)    parts.push(`sort_dir=${f.sort_dir}`);
  return parts.length ? "&" + parts.join("&") : "";
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

export const api = {
  // ── Search ──────────────────────────────────────────────────────────────
  submitSearch: (query: string, excludeExisting = false): Promise<SearchSubmitResponse> =>
    req("/search", { method: "POST", body: JSON.stringify({ query, exclude_existing: excludeExisting }) }),

  getJobStatus: (jobId: number): Promise<SearchJob> =>
    req(`/search/status/${jobId}`),

  getHistory: (): Promise<SearchJob[]> =>
    req("/search/history"),

  pauseJob: (jobId: number): Promise<{ job_id: number; status: string }> =>
    req(`/search/${jobId}/pause`, { method: "POST" }),

  resumeJob: (jobId: number): Promise<{ job_id: number; status: string }> =>
    req(`/search/${jobId}/resume`, { method: "POST" }),

  deleteJob: (jobId: number): Promise<{ deleted: number }> =>
    req(`/search/${jobId}`, { method: "DELETE" }),

  deleteAllJobs: (): Promise<{ deleted: string }> =>
    req("/search", { method: "DELETE" }),

  // ── Results (legacy + enhanced) ─────────────────────────────────────────
  getResults: (jobId: number, page = 1, pageSize = 50, filters: LeadFilters = {}): Promise<LeadListResponse> =>
    req(`/results?job_id=${jobId}&page=${page}&page_size=${pageSize}${filtersToParams(filters)}`),

  // ── Leads (advanced) ────────────────────────────────────────────────────
  getLead: (leadId: number): Promise<Lead> =>
    req(`/leads/${leadId}`),

  getLeads: (page = 1, pageSize = 50, filters: LeadFilters = {}): Promise<LeadListResponse> =>
    req(`/leads?page=${page}&page_size=${pageSize}${filtersToParams(filters)}`),

  setStatus: (leadId: number, status: LeadStatus): Promise<Lead> =>
    req(`/leads/${leadId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),

  enrichLinkedIn: (leadId: number): Promise<Lead> =>
    req(`/leads/${leadId}/enrich-linkedin`, { method: "POST" }),

  verifyEmail: (leadId: number): Promise<{ verified: boolean; email: string }> =>
    req(`/leads/${leadId}/verify-email`, { method: "POST" }),

  // ── Notes ────────────────────────────────────────────────────────────────
  getNotes: (leadId: number): Promise<LeadNote[]> =>
    req(`/leads/${leadId}/notes`),

  addNote: (leadId: number, content: string): Promise<LeadNote> =>
    req(`/leads/${leadId}/notes`, { method: "POST", body: JSON.stringify({ content }) }),

  deleteNote: (leadId: number, noteId: number): Promise<void> =>
    req(`/leads/${leadId}/notes/${noteId}`, { method: "DELETE" }),

  // ── Tags ─────────────────────────────────────────────────────────────────
  getTags: (leadId: number): Promise<string[]> =>
    req(`/leads/${leadId}/tags`),

  addTag: (leadId: number, tag: string): Promise<{ tags: string[] }> =>
    req(`/leads/${leadId}/tags`, { method: "POST", body: JSON.stringify({ tag }) }),

  removeTag: (leadId: number, tag: string): Promise<{ tags: string[] }> =>
    req(`/leads/${leadId}/tags/${encodeURIComponent(tag)}`, { method: "DELETE" }),

  getAllTags: (): Promise<string[]> =>
    req("/tags"),

  // ── Activity ─────────────────────────────────────────────────────────────
  getActivity: (leadId: number): Promise<ActivityLog[]> =>
    req(`/leads/${leadId}/activity`),

  // ── Bulk ─────────────────────────────────────────────────────────────────
  bulkAction: (lead_ids: number[], action: string, value?: string, list_id?: number) =>
    req("/leads/bulk", {
      method: "POST",
      body: JSON.stringify({ lead_ids, action, value, list_id }),
    }),

  // ── Lists ─────────────────────────────────────────────────────────────────
  getLists: (): Promise<LeadList[]> => req("/lists"),

  createList: (name: string, description = "", color = "#3b82f6"): Promise<LeadList> =>
    req("/lists", { method: "POST", body: JSON.stringify({ name, description, color }) }),

  updateList: (id: number, name: string, description = "", color = "#3b82f6"): Promise<LeadList> =>
    req(`/lists/${id}`, { method: "PATCH", body: JSON.stringify({ name, description, color }) }),

  deleteList: (id: number): Promise<void> =>
    req(`/lists/${id}`, { method: "DELETE" }),

  addLeadsToList: (listId: number, leadIds: number[]): Promise<void> =>
    req(`/lists/${listId}/leads`, { method: "POST", body: JSON.stringify(leadIds) }),

  removeLeadFromList: (listId: number, leadId: number): Promise<void> =>
    req(`/lists/${listId}/leads/${leadId}`, { method: "DELETE" }),

  // ── Saved Searches ────────────────────────────────────────────────────────
  getSavedSearches: (): Promise<SavedSearch[]> => req("/saved-searches"),

  createSavedSearch: (name: string, query: string): Promise<SavedSearch> =>
    req("/saved-searches", { method: "POST", body: JSON.stringify({ name, query }) }),

  deleteSavedSearch: (id: number): Promise<void> =>
    req(`/saved-searches/${id}`, { method: "DELETE" }),

  // ── Export ───────────────────────────────────────────────────────────────
  exportExcelUrl: (jobId: number, filters: LeadFilters = {}) =>
    `${API}/export/excel?job_id=${jobId}${filtersToParams(filters)}`,
  exportCsvUrl: (jobId: number, filters: LeadFilters = {}) =>
    `${API}/export/csv?job_id=${jobId}${filtersToParams(filters)}`,
};
