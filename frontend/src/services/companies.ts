import api from './api';
import { Company, PaginatedResponse } from '../types';

export const getCompanies = async (params: {
  page?: number;
  page_size?: number;
  search?: string;
  industry?: string;
  country?: string;
  provider_id?: string;
}): Promise<PaginatedResponse<Company>> => {
  const res = await api.get<PaginatedResponse<Company>>('/companies', { params });
  return res.data;
};

export const getCompany = async (id: string): Promise<Company> => {
  const res = await api.get<Company>(`/companies/${id}`);
  return res.data;
};

export const createCompany = async (data: Partial<Company>): Promise<Company> => {
  const res = await api.post<Company>('/companies', data);
  return res.data;
};

export const updateCompany = async (id: string, data: Partial<Company>): Promise<Company> => {
  const res = await api.patch<Company>(`/companies/${id}`, data);
  return res.data;
};

export const deleteCompany = async (id: string): Promise<void> => {
  await api.delete(`/companies/${id}`);
};

export const getCompanyPeople = async (id: string): Promise<{
  company_id: string;
  company_name: string;
  total_people: number;
  people: Array<{
    id: string;
    full_name: string;
    designation: string;
    email?: string;
    phone?: string;
    linkedin_url?: string;
    verification_status?: string;
    evidence_quote?: string;
    source?: string;
    confidence?: number;
  }>;
}> => {
  const res = await api.get(`/companies/${id}/people`);
  return res.data;
};
