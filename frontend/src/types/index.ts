export interface SearchJob {
  job_id: number;
  query: string;
  entity_type: string | null;
  location: string | null;
  status: "pending" | "running" | "paused" | "done" | "failed";
  result_count: number;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export type LeadStatus = "new" | "contacted" | "qualified" | "rejected" | "won" | "lost";

export interface Lead {
  id: number;
  job_id: number;
  name: string | null;
  category: string | null;
  description: string | null;
  industry: string | null;
  employee_count: string | null;
  founded_year: string | null;
  city: string | null;
  country: string | null;
  website: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  facebook: string | null;
  instagram: string | null;
  linkedin: string | null;
  twitter: string | null;
  youtube: string | null;
  status: LeadStatus;
  score: number;
  email_verified: boolean | null;
  source: string | null;
  source_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SearchSubmitResponse {
  job_id: number;
  message: string;
  entity_type: string;
  location: string;
  keywords: string[];
}

export interface LeadNote {
  id: number;
  lead_id: number;
  content: string;
  created_at: string | null;
}

export interface LeadList {
  id: number;
  name: string;
  description: string | null;
  color: string;
  member_count: number;
  created_at: string | null;
}

export interface SavedSearch {
  id: number;
  name: string;
  query: string;
  last_run_at: string | null;
  last_result_count: number;
  created_at: string | null;
}

export interface ActivityLog {
  id: number;
  lead_id: number;
  action: string;
  detail: string | null;
  created_at: string | null;
}
