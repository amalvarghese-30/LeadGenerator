import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { ToastProvider } from './context/ToastContext';
import { MainLayout } from './components/Layout/MainLayout';
import { Login } from './pages/Auth/Login';
import { Scanner } from './pages/Scanner';
import { Directory } from './pages/Directory';
import { RateLimitChecker } from './pages/RateLimitChecker';
import { Settings } from './pages/Settings';
import { Providers } from './pages/Providers';
import { ProviderDetail } from './pages/Providers/ProviderDetail';
import { LoadingSpinner } from './components/ui/LoadingSpinner';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-slate-950 text-slate-100">
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
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              {/* Core Workspace 1: Scanner (Competitor Client Finder) */}
              <Route index element={<Scanner />} />
              <Route path="scanner" element={<Scanner />} />

              {/* Core Workspace 2: Client & Contact Directory */}
              <Route path="directory" element={<Directory />} />

              {/* Core Workspace 3: Scanned Providers */}
              <Route path="providers" element={<Providers />} />
              <Route path="providers/:id" element={<ProviderDetail />} />

              {/* Core Workspace 4: Rate Limit Profiler */}
              <Route path="rate-limits" element={<RateLimitChecker />} />

              {/* Settings */}
              <Route path="settings" element={<Settings />} />

              {/* Backward-Compatible Redirects */}
              <Route path="dashboard" element={<Navigate to="/" replace />} />
              <Route path="website-intelligence" element={<Navigate to="/" replace />} />
              <Route path="discovery" element={<Navigate to="/" replace />} />
              <Route path="competitor-intelligence" element={<Navigate to="/" replace />} />
              <Route path="lead-generator" element={<Navigate to="/" replace />} />
              <Route path="people-finder" element={<Navigate to="/directory" replace />} />
              <Route path="company-finder" element={<Navigate to="/directory" replace />} />
              <Route path="contacts" element={<Navigate to="/directory" replace />} />
              <Route path="companies" element={<Navigate to="/directory" replace />} />
              <Route path="leads" element={<Navigate to="/directory" replace />} />
              <Route path="providers" element={<Navigate to="/" replace />} />
              <Route path="reports" element={<Navigate to="/" replace />} />
              <Route path="tasks" element={<Navigate to="/" replace />} />
              <Route path="rate-limit-checker" element={<Navigate to="/rate-limits" replace />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
};

export default App;
