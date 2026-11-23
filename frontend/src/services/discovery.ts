import api from './api';
import { CrawlJob, JobEvent, PaginatedResponse } from '../types';

export interface SearchProviderResult {
  title: string;
  url: string;
  snippet: string;
  domain?: string;
  source: string;
}

export interface SearchProviderResponse {
  query: string;
  count: number;
  results: SearchProviderResult[];
}

export interface ScanResultContact {
  email?: string | null;
  emails?: string[];
  phone?: string | null;
  phones?: string[];
  linkedin?: string | null;
  socials?: {
    linkedin?: string | null;
    instagram?: string | null;
    facebook?: string | null;
    twitter?: string | null;
    youtube?: string | null;
    [key: string]: string | null | undefined;
  };
  channels?: any[];
}

export interface ScanResultItem {
  id: string;
  company_name?: string | null;
  company_website?: string | null;
  website?: string | null;
  emails?: string[];
  phones?: string[];
  socials?: {
    linkedin?: string | null;
    instagram?: string | null;
    facebook?: string | null;
    twitter?: string | null;
    youtube?: string | null;
    [key: string]: string | null | undefined;
  };
  industry?: string | null;
  person_name?: string | null;
  designation?: string | null;
  relationship_type: string;
  confidence: number;
  evidence_quote?: string | null;
  source_url?: string | null;
  verification_status: string;
  contacts: ScanResultContact;
}

export interface JobResultsResponse {
  job_id: string;
  status: string;
  total_results: number;
  results: ScanResultItem[];
}

export const searchProviders = async (query: string, country_filter?: string): Promise<SearchProviderResponse> => {
  const res = await api.post<SearchProviderResponse>('/discovery/providers', {
    query, max_results: 15, country_filter,
  });
  return res.data;
};

export const getCrawlJobs = async (params: {
  page?: number; page_size?: number; provider_id?: string; status?: string;
}): Promise<PaginatedResponse<CrawlJob>> => {
  const res = await api.get<PaginatedResponse<CrawlJob>>('/discovery/jobs', { params });
  return res.data;
};

export const getCrawlJob = async (id: string): Promise<CrawlJob> => {
  const res = await api.get<CrawlJob>(`/discovery/jobs/${id}`);
  return res.data;
};

export const getJobReport = async (id: string): Promise<any> => {
  const res = await api.get(`/discovery/jobs/${id}/report`);
  return res.data;
};

export const getJobResults = async (id: string): Promise<JobResultsResponse> => {
  const res = await api.get<JobResultsResponse>(`/discovery/jobs/${id}/results`);
  return res.data;
};

export const cancelCrawlJob = async (id: string): Promise<void> => {
  await api.post(`/discovery/jobs/${id}/cancel`);
};

export const retryCrawlJob = async (id: string): Promise<void> => {
  await api.post(`/discovery/jobs/${id}/retry`);
};

export const getJobEvents = async (
  id: string,
  params?: { since_id?: string; limit?: number; latest?: boolean }
): Promise<JobEvent[]> => {
  const res = await api.get<JobEvent[]>(`/discovery/jobs/${id}/events`, { params });
  return res.data;
};

export const getJobEventsStreamUrl = (id: string) => {
  return `/api/discovery/jobs/${id}/events/stream`;
};

export const getDorkingQueries = async (domain: string, brand_name?: string) => {
  const res = await api.get('/discovery/dorking', { params: { domain, brand_name } });
  return res.data;
};

export interface BatchResearchRequest {
  urls: string[];
  names?: string[];
  page_limit?: number;
  job_type?: string;
}

export interface BatchResearchResponse {
  total_submitted: number;
  queued_jobs: number;
  already_active: number;
  jobs: Array<{
    provider_id: string;
    provider_name: string;
    job_id: string;
    starting_url: string;
    status: string;
  }>;
}

export interface BatchQueueItem {
  id: string;
  provider_id?: string;
  provider_name?: string;
  starting_url?: string;
  status: string;
  current_stage: string;
  progress_pct: number;
  pages_crawled: number;
  max_pages: number;
  references_found: number;
  contacts_created: number;
  companies_created: number;
  created_at: string;
  completed_at?: string;
}

export const startBatchResearch = async (data: BatchResearchRequest): Promise<BatchResearchResponse> => {
  const res = await api.post<BatchResearchResponse>('/discovery/batch-research', data);
  return res.data;
};

export const getBatchQueue = async (limit: number = 100): Promise<{ queue: BatchQueueItem[] }> => {
  const res = await api.get<{ queue: BatchQueueItem[] }>('/discovery/batch-queue', { params: { limit } });
  return res.data;
};
