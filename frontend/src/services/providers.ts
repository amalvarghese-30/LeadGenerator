import api from './api';
import { Provider, PaginatedResponse, Reference, CrawlJob } from '../types';

export const getProviders = async (params: {
  page?: number;
  page_size?: number;
  search?: string;
  category?: string;
  country?: string;
  verification_status?: string;
}): Promise<PaginatedResponse<Provider>> => {
  const res = await api.get<PaginatedResponse<Provider>>('/providers', { params });
  return res.data;
};

export const getProvider = async (id: string): Promise<Provider> => {
  const res = await api.get<Provider>(`/providers/${id}`);
  return res.data;
};

export const createProvider = async (data: Partial<Provider>): Promise<Provider> => {
  const res = await api.post<Provider>('/providers', data);
  return res.data;
};

export const updateProvider = async (id: string, data: Partial<Provider>): Promise<Provider> => {
  const res = await api.patch<Provider>(`/providers/${id}`, data);
  return res.data;
};

export const deleteProvider = async (id: string): Promise<void> => {
  await api.delete(`/providers/${id}`);
};

export const getProviderReferences = async (providerId: string): Promise<PaginatedResponse<Reference>> => {
  const res = await api.get<PaginatedResponse<Reference>>('/references', {
    params: { provider_id: providerId, page_size: 100 }
  });
  return res.data;
};

export const getProviderJobs = async (providerId: string): Promise<PaginatedResponse<CrawlJob>> => {
  const res = await api.get<PaginatedResponse<CrawlJob>>('/discovery/jobs', {
    params: { provider_id: providerId, page_size: 20 }
  });
  return res.data;
};

export const startProviderResearch = async (providerId: string, pageLimit?: number): Promise<CrawlJob> => {
  const url = pageLimit ? `/discovery/providers/${providerId}/research?page_limit=${pageLimit}` : `/discovery/providers/${providerId}/research`;
  const res = await api.post<CrawlJob>(url);
  return res.data;
};
