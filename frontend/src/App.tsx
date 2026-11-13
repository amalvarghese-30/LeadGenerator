import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { MainLayout } from './components/Layout/MainLayout';
import { Login } from './pages/Auth/Login';
import { Dashboard } from './pages/Dashboard';
import { Providers } from './pages/Providers';
import { ProviderDetail } from './pages/Providers/ProviderDetail';
import { Leads } from './pages/Leads';
import { LeadDetail } from './pages/Leads/LeadDetail';
import { Contacts } from './pages/Contacts';
import { Companies } from './pages/Companies';
import { Tasks } from './pages/Tasks';
import { Discovery } from './pages/Discovery';
import { Reports } from './pages/Reports';
import { ResearchReport } from './pages/Reports/ResearchReport';
import { Settings } from './pages/Settings';
import { LoadingSpinner } from './components/ui/LoadingSpinner';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-50">
        <LoadingSpinner message="Authenticating session..." />
      </div>
    );
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="providers" element={<Providers />} />
            <Route path="providers/:id" element={<ProviderDetail />} />
            <Route path="leads" element={<Leads />} />
            <Route path="leads/:id" element={<LeadDetail />} />
            <Route path="contacts" element={<Contacts />} />
            <Route path="companies" element={<Companies />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="discovery" element={<Discovery />} />
            <Route path="reports" element={<Reports />} />
            <Route path="reports/:jobId" element={<ResearchReport />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;