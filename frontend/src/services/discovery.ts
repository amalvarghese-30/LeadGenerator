import api from './api';
import { CrawlJob, PaginatedResponse } from '../types';

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

export const cancelCrawlJob = async (id: string): Promise<void> => {
  await api.post(`/discovery/jobs/${id}/cancel`);
};

export const retryCrawlJob = async (id: string): Promise<void> => {
  await api.post(`/discovery/jobs/${id}/retry`);
};

export const getJobEvents = async (id: string) => {
  const res = await api.get(`/discovery/jobs/${id}/events`);
  return res.data;
};

export const getJobEventsStreamUrl = (id: string) => {
  return `/api/discovery/jobs/${id}/events/stream`;
};

export const getDorkingQueries = async (domain: string, brand_name?: string) => {
  const res = await api.get('/discovery/dorking', { params: { domain, brand_name } });
  return res.data;
};