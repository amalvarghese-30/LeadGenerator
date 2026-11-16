import api from './api';
import { SearchResultCandidate } from '../types';

export interface CompanySearchPayload {
  company_name: string;
  website?: string;
  industry?: string;
  country?: string;
  additional_terms?: string;
  max_results?: number;
}

export interface IndividualSearchPayload {
  full_name: string;
  company?: string;
  job_title?: string;
  location?: string;
  max_results?: number;
}

export interface SearchResponse {
  mode: 'company' | 'individual';
  query: string;
  sources_status: Record<string, string>;
  total_results: number;
  results: SearchResultCandidate[];
}

export const searchCompany = async (payload: CompanySearchPayload): Promise<SearchResponse> => {
  const res = await api.post<SearchResponse>('/lead-generator/company', payload);
  return res.data;
};

export const searchIndividual = async (payload: IndividualSearchPayload): Promise<SearchResponse> => {
  const res = await api.post<SearchResponse>('/lead-generator/individual', payload);
  return res.data;
};

export const classifyEntity = async (payload: { title: string; snippet: string; url: string }) => {
  const res = await api.post('/lead-generator/classify', payload);
  return res.data;
};

export const getSearchHistory = async (limit: number = 20) => {
  const res = await api.get('/lead-generator/history', { params: { limit } });
  return res.data;
};

export const saveSearchResultToCrm = async (payload: {
  entity_type: string;
  name: string;
  website?: string;
  domain?: string;
  title?: string;
  company_name?: string;
  snippet?: string;
  social_platform?: string;
  url?: string;
  create_lead?: boolean;
}) => {
  const res = await api.post('/lead-generator/save', payload);
  return res.data;
};
