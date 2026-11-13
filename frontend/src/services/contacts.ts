import api from './api';
import { Contact, PaginatedResponse } from '../types';

export const getContacts = async (params: {
  page?: number;
  page_size?: number;
  search?: string;
  company_id?: string;
  verification_status?: string;
  is_suppressed?: boolean;
}): Promise<PaginatedResponse<Contact>> => {
  const res = await api.get<PaginatedResponse<Contact>>('/contacts', { params });
  return res.data;
};

export const getContact = async (id: string): Promise<Contact> => {
  const res = await api.get<Contact>(`/contacts/${id}`);
  return res.data;
};

export const createContact = async (data: Partial<Contact>): Promise<Contact> => {
  const res = await api.post<Contact>('/contacts', data);
  return res.data;
};

export const updateContact = async (id: string, data: Partial<Contact>): Promise<Contact> => {
  const res = await api.patch<Contact>(`/contacts/${id}`, data);
  return res.data;
};

export const deleteContact = async (id: string): Promise<void> => {
  await api.delete(`/contacts/${id}`);
};

export const suppressContact = async (id: string, reason?: string): Promise<Contact> => {
  const res = await api.post<Contact>(`/contacts/${id}/suppress`, null, {
    params: { reason }
  });
  return res.data;
};
