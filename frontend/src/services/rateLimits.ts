import api from './api';
import { RateLimitSummary, DomainRateLimit } from '../types';

export const getRateLimitMetrics = async (): Promise<RateLimitSummary> => {
  const res = await api.get<RateLimitSummary>('/rate-limits/overview');
  return res.data;
};

export const getDomainRateLimits = async (params?: {
  search?: string;
  status?: string;
}): Promise<DomainRateLimit[]> => {
  const res = await api.get<DomainRateLimit[]>('/rate-limits/domains', { params });
  return res.data;
};

export const getDomainPolicy = async (domain: string) => {
  const res = await api.get(`/rate-limits/policy/${encodeURIComponent(domain)}`);
  return res.data;
};

export const pauseDomain = async (domain: string, reason?: string) => {
  const res = await api.post(`/rate-limits/domains/${encodeURIComponent(domain)}/pause`, { reason });
  return res.data;
};

export const resumeDomain = async (domain: string) => {
  const res = await api.post(`/rate-limits/domains/${encodeURIComponent(domain)}/resume`);
  return res.data;
};

export const resetDomainProfile = async (domain: string) => {
  const res = await api.post(`/rate-limits/domains/${encodeURIComponent(domain)}/reset-profile`);
  return res.data;
};

export const getRequestLogs = async (params?: {
  domain?: string;
  classification?: string;
  page?: number;
  limit?: number;
}): Promise<{ items: any[]; total: number; page: number; limit: number }> => {
  const res = await api.get('/rate-limits/requests', { params });
  return res.data;
};

export const getRateLimitEvents = async (limit: number = 30): Promise<any[]> => {
  const res = await api.get('/rate-limits/events', { params: { limit } });
  return res.data;
};

export const resetRateLimitMetrics = async (): Promise<void> => {
  await api.post('/rate-limits/reset');
};

// Mode B: GitHub API Provider
export const getGitHubStatus = async (): Promise<any> => {
  const res = await api.get('/rate-limits/providers/github/status');
  return res.data;
};

export const refreshGitHubQuota = async (): Promise<any> => {
  const res = await api.post('/rate-limits/providers/github/refresh');
  return res.data;
};

export const configureGitHubToken = async (token: string): Promise<any> => {
  const res = await api.post('/rate-limits/providers/github/configure', { token });
  return res.data;
};
