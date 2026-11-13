import api from './api';
import { DashboardStats } from '../types';

export const getDashboardStats = async (): Promise<DashboardStats> => {
  const res = await api.get<DashboardStats>('/reports/dashboard');
  return res.data;
};

export const getProviderReports = async (): Promise<any> => {
  const res = await api.get('/reports/providers');
  return res.data;
};

export const getLeadsReports = async (): Promise<any> => {
  const res = await api.get('/reports/leads');
  return res.data;
};

export const getPipelineReports = async (): Promise<any> => {
  const res = await api.get('/reports/pipeline');
  return res.data;
};

export const exportLeads = (format: 'csv' | 'excel' = 'csv', crm_stage?: string) => {
  const params = new URLSearchParams({ format });
  if (crm_stage) params.append('crm_stage', crm_stage);
  window.open(`${api.defaults.baseURL}/export/leads?${params.toString()}`, '_blank');
};

export const exportProviders = (category?: string) => {
  const params = new URLSearchParams();
  if (category) params.append('category', category);
  window.open(`${api.defaults.baseURL}/export/providers?${params.toString()}`, '_blank');
};

export const exportContacts = (verification_status?: string) => {
  const params = new URLSearchParams();
  if (verification_status) params.append('verification_status', verification_status);
  window.open(`${api.defaults.baseURL}/export/contacts?${params.toString()}`, '_blank');
};
