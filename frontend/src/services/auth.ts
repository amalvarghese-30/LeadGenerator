import api from './api';
import { User } from '../types';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const login = async (username_or_email: string, password: string): Promise<LoginResponse> => {
  const res = await api.post<LoginResponse>('/auth/login', {
    email: username_or_email,
    password,
  });
  return res.data;
};

export const getMe = async (): Promise<User> => {
  const res = await api.get<User>('/auth/me');
  return res.data;
};
