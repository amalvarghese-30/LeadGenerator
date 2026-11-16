import api from './api';
import { Competitor } from '../types';

export interface CompetitorListResponse {
  items: Competitor[];
  total: number;
  skip: number;
  limit: number;
}

export const getCompetitors = async (params?: {
  skip?: number;
  limit?: number;
  category?: string;
  search?: string;
}): Promise<CompetitorListResponse> => {
  const res = await api.get<CompetitorListResponse>('/competitors', { params });
  return res.data;
};

export const getCompetitor = async (id: string): Promise<Competitor> => {
  const res = await api.get<Competitor>(`/competitors/${id}`);
  return res.data;
};

export const createCompetitor = async (data: Partial<Competitor>): Promise<Competitor> => {
  const res = await api.post<Competitor>('/competitors', data);
  return res.data;
};

export const updateCompetitor = async (id: string, data: Partial<Competitor>): Promise<Competitor> => {
  const res = await api.put<Competitor>(`/competitors/${id}`, data);
  return res.data;
};

export const deleteCompetitor = async (id: string): Promise<void> => {
  await api.delete(`/competitors/${id}`);
};

export const discoverCompetitors = async (data: {
  seed_terms: string;
  category?: string;
  region?: string;
  max_results?: number;
}) => {
  const res = await api.post('/competitors/discover', data);
  return res.data;
};

export const runCompetitorResearch = async (id: string) => {
  const res = await api.post(`/competitors/${id}/research`);
  return res.data;
};
