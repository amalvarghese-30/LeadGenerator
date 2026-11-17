import api from './api';
import { Lead, PaginatedResponse, CRMStage } from '../types';

export const getLeads = async (params: {
  page?: number;
  page_size?: number;
  crm_stage?: string;
  lead_priority?: string;
  outreach_eligible?: boolean;
  qualification_status?: string;
  sort_by?: string;
  sort_dir?: number;
}): Promise<PaginatedResponse<Lead>> => {
  const res = await api.get<PaginatedResponse<Lead>>('/leads', { params });
  return res.data;
};

export const getLead = async (id: string): Promise<Lead> => {
  const res = await api.get<Lead>(`/leads/${id}`);
  return res.data;
};

export const createLead = async (data: Partial<Lead>): Promise<Lead> => {
  const res = await api.post<Lead>('/leads', data);
  return res.data;
};

export const updateLead = async (id: string, data: Partial<Lead>): Promise<Lead> => {
  const res = await api.patch<Lead>(`/leads/${id}`, data);
  return res.data;
};

export const updateLeadStage = async (id: string, newStage: CRMStage, note?: string): Promise<Lead> => {
  const res = await api.post<Lead>(`/leads/${id}/status`, {
    crm_stage: newStage,
    new_stage: newStage,
    reason: note,
    note,
  });
  return res.data;
};

export const qualifyLead = async (id: string, qualificationStatus: string, reason?: string): Promise<Lead> => {
  const res = await api.post<Lead>(`/leads/${id}/qualify`, {
    qualification_status: qualificationStatus,
    disqualification_reason: reason
  });
  return res.data;
};

export const deleteLead = async (id: string): Promise<void> => {
  await api.delete(`/leads/${id}`);
};

export const getKanbanData = async (): Promise<Record<string, Lead[]>> => {
  const res = await api.get<Record<string, Lead[]>>('/reports/pipeline');
  return res.data as any;
};
