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
  total_scans_count?: number;
  latest_job_id?: string;
  latest_job_status?: string;
  latest_job_progress_pct?: number;
  pages_crawled?: number;
  references_found?: number;
  companies_found?: number;
  contacts_found?: number;
  leads_found?: number;
  source?: string;
  created_at: string;
  updated_at: string;
}

export interface AssociatedPerson {
  contact_id?: string;
  full_name: string;
  designation?: string;
  linkedin_url?: string;
  verification_status?: string;
  confidence?: number;
}

export interface Company {
  id: string;
  name: string;
  website?: string;
  domain?: string;
  industry?: string;
  description?: string;
  address?: string;
  aliases?: string[];
  country?: string;
  city?: string;
  state?: string;
  linkedin_url?: string;
  public_contact: Record<string, string>;
  public_contact_channels?: ContactChannel[];
  social_profiles?: any;
  associated_people?: AssociatedPerson[];
  enrichment_status?: string;
  last_enriched_at?: string;
  verification_status: string;
  provider_id?: string;
  primary_provider_name?: string;
  primary_provider_website?: string;
  source_url?: string;
  source_providers?: Array<{
    provider_id: string;
    provider_name: string;
    provider_website?: string;
    source_url?: string;
  }>;
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
  website?: string;
  company_website?: string;
  email?: string;
  emails?: string[];
  phone?: string;
  phones?: string[];
  socials?: {
    linkedin?: string | null;
    instagram?: string | null;
    facebook?: string | null;
    twitter?: string | null;
    youtube?: string | null;
    [key: string]: string | null | undefined;
  };
  professional_urls: Record<string, string>;
  business_contacts: Record<string, string>;
  associated_companies?: Array<{
    company_id: string;
    company_name: string;
    designation?: string;
    source?: string;
    confidence?: number;
    verification_status?: string;
    verified_at?: string;
  }>;
  contact_channels?: ContactChannel[];
  contact_verification_status: 'discovered' | 'unverified' | 'source_reviewed' | 'company_verified' | 'contact_source_verified' | 'verified' | 'human_approved' | 'rejected';
  enrichment_status?: EnrichmentStatus;
  last_enriched_at?: string;
  enrichment_attempts?: number;
  enrichment_errors?: string[];
  is_suppressed: boolean;
  do_not_contact: boolean;
  source_references?: string[];
  provider_id?: string;
  primary_provider_name?: string;
  primary_provider_website?: string;
  source_url?: string;
  source_providers?: Array<{
    provider_id: string;
    provider_name: string;
    provider_website?: string;
    source_url?: string;
  }>;
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
  provider_name?: string;
  _id?: string;
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
    | 'enriching_companies'
    | 'generating_report'
    | 'completed'
    | 'failed'
    | 'cancelled'
    | (string & {});
  progress_pct: number;

  pages_discovered: number;
  pages_attempted: number;
  pages_crawled: number;
  pages_failed: number;
  pages_skipped: number;
  pages_analysed?: number;
  max_pages?: number;

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
  job_type?: 'full_research' | 'person_profile';
  report_mode?: 'provider' | 'person' | 'hybrid';
  person_profile?: PersonProfile;

  created_at: string;
  started_at?: string;
  updated_at?: string;
  completed_at?: string;
}

export interface PersonSocialProfile {
  platform: string;
  url: string;
  handle?: string;
  source_url?: string;
  extraction_method?: string;
  verification_status?: string;
  confidence?: number;
}

export interface AssociatedWebsite {
  url: string;
  label: string;
  source: string;
}

export interface PersonProfile {
  person_name: string;
  designation?: string;
  company_name?: string;
  location?: string;
  bio_summary?: string;
  social_profiles?: PersonSocialProfile[];
  public_emails?: string[];
  public_phones?: string[];
  associated_websites?: AssociatedWebsite[];
  source_url?: string;
  name_source?: string;
  designation_source?: string;
  company_source?: string;
  confidence_score?: number;
  confidence_reasons?: string[];
  page_category?: string;
}

export interface PageDiagnostic {
  url: string;
  is_person_profile: boolean;
  person_confidence: number;
  detection_reason: string;
  emails_found: number;
  socials_found: number;
  status: string;
}

export interface ResearchReport {
  id?: string;
  job_id: string;
  provider_id?: string;
  starting_url: string;
  job_type?: 'full_research' | 'person_profile';
  report_mode?: 'provider' | 'person' | 'hybrid';
  status: string;
  pages_discovered: number;
  pages_processed: number;
  pages_failed: number;
  references_found: number;
  person_profile?: PersonProfile;
  person_profiles?: PersonProfile[];
  page_diagnostics?: PageDiagnostic[];
  data_quality_metrics?: Record<string, any>;
  enrichment_summary?: Record<string, any>;
  rejected_candidates?: Array<any>;
  social_media_profiles?: Record<string, string[]>;
  public_emails_discovered?: string[];
  failed_urls?: Array<{ url: string; error?: string }>;
  generated_at?: string;
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
