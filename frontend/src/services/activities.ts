import api from './api';
import { Activity, Task, PaginatedResponse } from '../types';

export const getActivities = async (params: {
  page?: number;
  page_size?: number;
  lead_id?: string;
  contact_id?: string;
  company_id?: string;
  provider_id?: string;
  activity_type?: string;
}): Promise<PaginatedResponse<Activity>> => {
  const res = await api.get<PaginatedResponse<Activity>>('/activities', { params });
  return res.data;
};

export const createActivity = async (data: Partial<Activity>): Promise<Activity> => {
  const res = await api.post<Activity>('/activities', data);
  return res.data;
};

// Tasks
export const getTasks = async (params: {
  page?: number;
  page_size?: number;
  lead_id?: string;
  assigned_to?: string;
  status?: string;
  priority?: string;
  overdue_only?: boolean;
}): Promise<PaginatedResponse<Task>> => {
  const res = await api.get<PaginatedResponse<Task>>('/tasks', { params });
  return res.data;
};

export const createTask = async (data: Partial<Task>): Promise<Task> => {
  const res = await api.post<Task>('/tasks', data);
  return res.data;
};

export const updateTask = async (id: string, data: Partial<Task>): Promise<Task> => {
  const res = await api.patch<Task>(`/tasks/${id}`, data);
  return res.data;
};

export const deleteTask = async (id: string): Promise<void> => {
  await api.delete(`/tasks/${id}`);
};
