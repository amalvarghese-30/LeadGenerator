import api from './api';
import { ProfileCandidate } from '../types';

export interface DiscoverProfilePayload {
  full_name: string;
  company?: string;
  designation?: string;
  location?: string;
}

export const discoverProfile = async (payload: DiscoverProfilePayload): Promise<ProfileCandidate> => {
  const res = await api.post<ProfileCandidate>('/profile-creator/discover', payload);
  return res.data;
};

export const saveProfileToCrm = async (candidate_data: ProfileCandidate, create_lead: boolean = true) => {
  const res = await api.post('/profile-creator/save', { candidate_data, create_lead });
  return res.data;
};

export const getRecentProfileCandidates = async (limit: number = 20): Promise<ProfileCandidate[]> => {
  const res = await api.get<ProfileCandidate[]>('/profile-creator/candidates', { params: { limit } });
  return res.data;
};
