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

export interface ContactChannel {
  type: 'email' | 'phone' | 'contact_form' | 'social' | 'website';
  scope: 'person_direct_work' | 'company_generic' | 'company_switchboard' | 'department' | 'media_enquiry' | 'sales_enquiry' | 'unclassified';
  value: string;
  source_url?: string;
  source_type?: string;
  evidence_quote?: string;
  collected_at?: string;
  last_checked_at?: string;
  syntax_valid?: boolean;
  mx_record_found?: boolean;
  domain_valid?: boolean;
  source_verified?: boolean;
  human_reviewed?: boolean;
  confidence?: number;
  verification_status: 'not_found' | 'discovered' | 'published' | 'format_checked' | 'source_verified' | 'human_reviewed' | 'rejected';
  notes?: string;
}

export type EnrichmentStatus =
  | 'not_started'
  | 'in_progress'
  | 'enriched'
  | 'partially_enriched'
  | 'no_public_contacts_found'
  | 'failed';

export interface Contact {
  id: string;
  full_name: string;
  first_name?: string;
  last_name?: string;
  designation?: string;
  company_id?: string;
  company_name?: string;
  linkedin_url?: string;
  email?: string;
  phone?: string;
  professional_urls: Record<string, string>;
  business_contacts: Record<string, string>;
  contact_channels?: ContactChannel[];
  contact_verification_status: 'discovered' | 'unverified' | 'source_reviewed' | 'company_verified' | 'contact_source_verified' | 'verified' | 'human_approved' | 'rejected';
  enrichment_status?: EnrichmentStatus;
  last_enriched_at?: string;
  enrichment_attempts?: number;
  enrichment_errors?: string[];
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
  | 'enriching_contacts'
  | 'generating_report'
  | 'completed'
  | 'failed'
  | 'cancelled';
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

export interface JobEvent {
  id?: string;
  job_id: string;
  event_timestamp: string;
  stage: string;
  severity: 'info' | 'warning' | 'error' | 'success';
  event_type: string;
  message: string;
  url?: string;
  metadata?: Record<string, any>;
}

export interface Competitor {
  id: string;
  name: string;
  website?: string;
  domain?: string;
  business_category?: string;
  social_profiles?: Array<{ platform: string; url: string }>;
  services?: string[];
  ad_references?: Array<Record<string, any>>;
  client_references?: Array<Record<string, any>>;
  evidence?: Array<Record<string, any>>;
  notes?: string;
  last_research_date?: string;
  created_at: string;
  updated_at: string;
}

export interface RateLimitMetric {
  id?: string;
  domain: string;
  timestamp: string;
  status_code?: number;
  response_time_ms: number;
  is_throttled: boolean;
  retry_after?: number;
  rate_limit_headers?: Record<string, string>;
  error_type?: string;
  action_taken?: string;
}

export interface DomainRateLimit {
  id?: string;
  domain: string;
  total_requests?: number;
  requests?: number;
  successful_requests?: number;
  success?: number;
  blocked_requests?: number;
  throttled_429?: number;
  forbidden_403?: number;
  errors?: number;
  error_rate_pct?: number;
  blocking_percentage?: number;
  average_response_time?: number;
  avg_response_time_ms?: number;
  active_interval_ms?: number;
  estimated_interval_ms?: number;
  configured_delay_seconds?: number;
  active_concurrency?: number;
  concurrency?: number;
  confidence?: string;
  status?: string;
  is_paused?: boolean;
  cooldown_until?: string;
  last_throttled_at?: string;
  last_retry_after?: number;
}

export interface RateLimitSummary {
  total_requests: number;
  successful_requests: number;
  throttled_429_count: number;
  forbidden_403_count: number;
  other_error_count: number;
  error_percentage: number;
  blocking_percentage?: number;
  average_response_time_ms: number;
  active_monitored_domains: number;
  paused_domains?: number;
  recent_events: any[];
}

export interface SearchResultCandidate {
  title: string;
  url: string;
  domain?: string;
  snippet?: string;
  entity_type: 'individual' | 'company' | 'organisation' | 'unknown';
  classification_reason?: string;
  needs_review?: boolean;
  social_platform?: string;
  is_official_website?: boolean;
  confidence: number;
  evidence_points?: string[];
  corroborated_company?: boolean;
  corroborated_title?: boolean;
  is_duplicate_domain?: boolean;
}

export interface ProfileCandidate {
  id?: string;
  full_name: string;
  company_name?: string;
  designation?: string;
  location?: string;
  confidence_score: number;
  confidence_level: 'low' | 'medium' | 'high';
  platform_profiles: Record<string, string>;
  professional_biography?: string;
  evidence_items: Array<{
    type: string;
    platform?: string;
    url?: string;
    source_url?: string;
    title?: string;
    evidence_quote?: string;
    confidence?: number;
  }>;
  verification_status: 'pending_review' | 'confirmed' | 'rejected';
  created_at?: string;
}
