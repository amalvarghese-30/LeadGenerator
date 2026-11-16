import api from './api';
import { RateLimitSummary, DomainRateLimit } from '../types';

export const getRateLimitMetrics = async (): Promise<RateLimitSummary> => {
  const res = await api.get<RateLimitSummary>('/rate-limits/metrics');
  return res.data;
};

export const getDomainRateLimits = async (): Promise<DomainRateLimit[]> => {
  const res = await api.get<DomainRateLimit[]>('/rate-limits/domains');
  return res.data;
};

export const getDomainPolicy = async (domain: string) => {
  const res = await api.get(`/rate-limits/policy/${encodeURIComponent(domain)}`);
  return res.data;
};

export const resetRateLimitMetrics = async (): Promise<void> => {
  await api.post('/rate-limits/reset');
};
