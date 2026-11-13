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
