import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { ToastProvider } from './context/ToastContext';
import { MainLayout } from './components/Layout/MainLayout';
import { Login } from './pages/Auth/Login';
import { Dashboard } from './pages/Dashboard';
import { LeadGenerator } from './pages/LeadGenerator';
import { PeopleFinder } from './pages/PeopleFinder';
import { CompanyFinder } from './pages/CompanyFinder';
import { AutoProfileCreator } from './pages/AutoProfileCreator';
import { WebsiteIntelligence } from './pages/WebsiteIntelligence';
import { CompetitorIntelligence } from './pages/CompetitorIntelligence';
import { RateLimitChecker } from './pages/RateLimitChecker';
import { Providers } from './pages/Providers';
import { ProviderDetail } from './pages/Providers/ProviderDetail';
import { Leads } from './pages/Leads';
import { LeadDetail } from './pages/Leads/LeadDetail';
import { Contacts } from './pages/Contacts';
import { Companies } from './pages/Companies';
import { Tasks } from './pages/Tasks';
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
      <ToastProvider>
        <BrowserRouter>
          <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<ProtectedRoute><MainLayout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            {/* 1. Dashboard */}
            <Route path="dashboard" element={<Dashboard />} />

            {/* 2. Lead Generator */}
            <Route path="lead-generator" element={<LeadGenerator />} />

            {/* 3. People Finder */}
            <Route path="people-finder" element={<PeopleFinder />} />

            {/* 4. Company Finder */}
            <Route path="company-finder" element={<CompanyFinder />} />

            {/* 5. Auto Profile Creator */}
            <Route path="auto-profile-creator" element={<AutoProfileCreator />} />

            {/* 6. Website Intelligence */}
            <Route path="website-intelligence" element={<WebsiteIntelligence />} />
            {/* Backward-compatible alias for discovery */}
            <Route path="discovery" element={<WebsiteIntelligence />} />

            {/* 7. Competitor Intelligence */}
            <Route path="competitor-intelligence" element={<CompetitorIntelligence />} />

            {/* 8. Rate Limit Checker */}
            <Route path="rate-limit-checker" element={<RateLimitChecker />} />

            {/* 9. Leads CRM */}
            <Route path="leads" element={<Leads />} />
            <Route path="leads/:id" element={<LeadDetail />} />

            {/* 10. Companies CRM */}
            <Route path="companies" element={<Companies />} />

            {/* 11. Contacts CRM */}
            <Route path="contacts" element={<Contacts />} />

            {/* 12. Providers */}
            <Route path="providers" element={<Providers />} />
            <Route path="providers/:id" element={<ProviderDetail />} />

            {/* 13. Reports */}
            <Route path="reports" element={<Reports />} />
            <Route path="reports/:jobId" element={<ResearchReport />} />

            {/* 14. Tasks & Activities */}
            <Route path="tasks" element={<Tasks />} />

            {/* 15. Settings */}
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  </AuthProvider>
);
};

export default App;
