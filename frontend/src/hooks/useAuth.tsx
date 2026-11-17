import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { getMe } from '../services/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginUser: (accessToken: string, refreshToken: string, user: User) => void;
  logoutUser: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        try {
          const userData = await getMe();
          setUser(userData);
          localStorage.setItem('user', JSON.stringify(userData));
        } catch {
          // Token invalid or expired
          logoutUser();
        }
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const loginUser = (newAccessToken: string, newRefreshToken: string, newUser: User) => {
    localStorage.setItem('token', newAccessToken);
    if (newRefreshToken) {
      localStorage.setItem('refresh_token', newRefreshToken);
    }
    localStorage.setItem('user', JSON.stringify(newUser));
    setToken(newAccessToken);
    setUser(newUser);
  };

  const logoutUser = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token,
        isLoading,
        loginUser,
        logoutUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
