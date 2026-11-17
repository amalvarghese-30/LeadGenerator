import api from './api';
import { IntegrationStatus } from '../types';

export const getAppSettings = async (): Promise<any> => {
  const res = await api.get('/settings');
  return res.data;
};

export const getIntegrationsHealth = async (): Promise<{ integrations: IntegrationStatus[] }> => {
  const res = await api.get<{ integrations: IntegrationStatus[] }>('/settings/integrations');
  return res.data;
};

export const updateAppSettings = async (data: {
  app_name?: string;
  crawler?: {
    delay_seconds?: number;
    max_pages?: number;
    max_concurrent?: number;
    request_timeout?: number;
    max_retries?: number;
  };
}): Promise<{ message: string }> => {
  const res = await api.put<{ message: string }>('/settings', data);
  return res.data;
};
