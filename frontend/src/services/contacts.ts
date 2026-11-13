import api from './api';
import { Contact, PaginatedResponse, ContactChannel } from '../types';

export const getContacts = async (params: {
  page?: number;
  page_size?: number;
  search?: string;
  company_id?: string;
  verification_status?: string;
  enrichment_status?: string;
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

export const enrichContact = async (id: string): Promise<{ summary: any; contact: Contact }> => {
  const res = await api.post<{ summary: any; contact: Contact }>(`/contacts/${id}/enrich`);
  return res.data;
};

export const enrichBatch = async (contact_ids: string[]): Promise<{ results: any[]; total: number }> => {
  const res = await api.post<{ results: any[]; total: number }>('/contacts/enrich-batch', { contact_ids });
  return res.data;
};

export const addContactChannel = async (id: string, channel: Partial<ContactChannel>): Promise<Contact> => {
  const res = await api.post<Contact>(`/contacts/${id}/channels`, channel);
  return res.data;
};

export const verifyContactChannel = async (id: string, channelIndex: number): Promise<Contact> => {
  const res = await api.post<Contact>(`/contacts/${id}/channels/${channelIndex}/verify`);
  return res.data;
};

export const rejectContactChannel = async (id: string, channelIndex: number, reason?: string): Promise<Contact> => {
  const res = await api.post<Contact>(`/contacts/${id}/channels/${channelIndex}/reject`, {
    reason: reason || 'Rejected by reviewer'
  });
  return res.data;
};
