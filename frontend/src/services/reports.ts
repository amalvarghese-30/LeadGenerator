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

const downloadExportFile = async (endpoint: string, filename: string, params?: Record<string, string>) => {
  const res = await api.get(endpoint, {
    params,
    responseType: 'blob',
  });
  const blob = new Blob([res.data], {
    type: filename.endsWith('.xlsx')
      ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      : 'text/csv',
  });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

export const exportLeads = async (format: 'csv' | 'excel' = 'csv', crm_stage?: string) => {
  const params: Record<string, string> = { format };
  if (crm_stage) params.crm_stage = crm_stage;
  const filename = format === 'excel' ? 'leads_export.xlsx' : 'leads_export.csv';
  await downloadExportFile('/export/leads', filename, params);
};

export const exportProviders = async (category?: string) => {
  const params: Record<string, string> = {};
  if (category) params.category = category;
  await downloadExportFile('/export/providers', 'providers_export.csv', params);
};

export const exportContacts = async (verification_status?: string) => {
  const params: Record<string, string> = {};
  if (verification_status) params.verification_status = verification_status;
  await downloadExportFile('/export/contacts', 'contacts_export.csv', params);
};

export const exportCompanies = async (industry?: string, country?: string) => {
  const params: Record<string, string> = {};
  if (industry) params.industry = industry;
  if (country) params.country = country;
  await downloadExportFile('/export/companies', 'companies_export.csv', params);
};
