export type CRMStage =
  | 'discovered'
  | 'pending_verification'
  | 'verified'
  | 'qualified'
  | 'ready_for_outreach_review'
  | 'contacted'
  | 'replied'
  | 'interested'
  | 'converted'
  | 'closed'
  | 'disqualified'
  | 'do_not_contact';

export interface Provider {
  id: string;
  name: string;
  website?: string;
  domain?: string;
  description?: string;
  services: string[];
  location?: string;
  country?: string;
  social_profiles: Record<string, string>;
  category: 'direct_competitor' | 'close_competitor' | 'adjacent_provider' | 'irrelevant' | 'pending_review';
  similarity_score: number;
  similarity_reasons?: string[];
  discovery_status: 'discovered' | 'approved' | 'rejected' | 'researching' | 'researched' | 'error';
  verification_status: 'unverified' | 'verified' | 'rejected';
  last_crawled_at?: string;
  crawl_job_id?: string;
  source?: string;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: string;
  name: string;
  website?: string;
  domain?: string;
  industry?: string;
  country?: string;
  city?: string;
  linkedin_url?: string;
  public_contact: Record<string, string>;
  verification_status: string;
  created_at: string;
  updated_at?: string;
}

export interface Contact {
  id: string;
  full_name: string;
  designation?: string;
  company_id?: string;
  company_name?: string;
  linkedin_url?: string;
  email?: string;
  phone?: string;
  professional_urls: Record<string, string>;
  business_contacts: Record<string, string>;
  contact_verification_status: 'discovered' | 'unverified' | 'verified' | 'human_approved' | 'rejected';
  is_suppressed: boolean;
  do_not_contact: boolean;
  source_references?: string[];
  created_at: string;
  updated_at?: string;
}

export interface Lead {
  id: string;
  contact_id: string;
  contact?: Contact;
  company_id?: string;
  company?: Company;
  lead_score: number;
  lead_priority: 'high' | 'medium' | 'low';
  crm_stage: CRMStage;
  owner?: string;
  lead_source?: string;
  provider?: Provider;
  qualification_status: string;
  outreach_eligible: boolean;
  last_activity?: string;
  next_follow_up?: string;
  score_breakdown?: Record<string, number>;
  created_at: string;
  updated_at: string;
}

export interface Reference {
  id: string;
  provider_id: string;
  provider?: Provider;
  contact_id?: string;
  company_id?: string;
  person_name?: string;
  company_name?: string;
  designation?: string;
  industry?: string;
  relationship_type: string;
  service_category?: string;
  source_url: string;
  evidence_quote?: string;
  ai_confidence?: number;
  verification_status: 'pending' | 'verified' | 'rejected';
  rejection_reason?: string;
  collected_at?: string;
  created_at: string;
}

export interface Activity {
  id: string;
  lead_id?: string;
  contact_id?: string;
  company_id?: string;
  provider_id?: string;
  activity_type: 'note' | 'call' | 'email_recorded' | 'meeting' | 'follow_up' | 'verification' | 'status_change';
  title?: string;
  description?: string;
  created_at: string;
  due_date?: string;
  assigned_user?: string;
  outcome?: string;
  created_by?: string;
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  task_type: string;
  priority: 'low' | 'medium' | 'urgent' | 'high';
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  due_date?: string;
  assigned_to?: string;
  lead_id?: string;
  contact_id?: string;
  company_id?: string;
  provider_id?: string;
  completed_at?: string;
  created_at: string;
}

// --- UPDATED: canonical CrawlJob shape ---
export interface CrawlJob {
  id: string;
  provider_id: string;
  starting_url: string;
  status:
  | 'pending'
  | 'running'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'
  | 'cancelled'
  | 'paused';
  current_stage:
  | 'queued'
  | 'discovering'
  | 'crawling'
  | 'extracting'
  | 'verifying'
  | 'creating_crm_records'
  | 'generating_report'
  | 'completed'
  | 'failed';
  progress_pct: number;

  pages_discovered: number;
  pages_attempted: number;
  pages_crawled: number;
  pages_failed: number;
  pages_skipped: number;

  references_found: number;
  contacts_created: number;
  companies_created: number;
  leads_created: number;

  errors: Array<{
    stage: string;
    message: string;
    error_type: string;
    url?: string;
    timestamp: string;
  }>;
  warnings: Array<{
    stage: string;
    message: string;
    error_type: string;
    url?: string;
    timestamp: string;
  }>;

  discovery_stats?: Record<string, number>;

  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DashboardStats {
  total_providers: number;
  verified_providers: number;
  total_leads: number;
  verified_leads: number;
  outreach_ready_leads: number;
  follow_ups_due: number;
  new_leads_7d: number;
  total_contacts: number;
  total_companies: number;
  pending_crawl_jobs: number;
}

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  role: 'admin' | 'researcher';
  is_active: boolean;
}

export interface IntegrationStatus {
  name: string;
  id: string;
  status: 'active' | 'not_configured' | 'error' | 'connected';
  is_optional: boolean;
  message: string;
  model?: string;
}