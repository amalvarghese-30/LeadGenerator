import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { LogOut, User as UserIcon, Shield, Menu, ChevronRight, Settings } from 'lucide-react';
import { Button } from '../ui/Button';
import { BrandLogo } from '../ui/BrandLogo';

interface HeaderProps {
  onMenuToggle?: () => void;
  title?: string;
}

const ROUTE_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  'lead-generator': 'Lead Generator',
  'people-finder': 'People Finder',
  'company-finder': 'Company Finder',
  'auto-profile-creator': 'Auto Profile Creator',
  'website-intelligence': 'Website Intelligence',
  'competitor-intelligence': 'Competitor Intelligence',
  'rate-limit-checker': 'Rate Limit Checker',
  leads: 'Leads',
  companies: 'Companies',
  contacts: 'Contacts',
  providers: 'Providers',
  reports: 'Reports',
  tasks: 'Tasks & Activities',
  settings: 'Settings',
};

export const Header: React.FC<HeaderProps> = ({ onMenuToggle, title }) => {
  const { user, logoutUser } = useAuth();
  const location = useLocation();

  const segments = location.pathname.split('/').filter(Boolean);
  const currentLabel = segments.length > 0 ? (ROUTE_LABELS[segments[0]] || segments[0]) : 'Dashboard';

  return (
    <header className="h-16 bg-white/80 backdrop-blur-md border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        {onMenuToggle && (
          <button
            onClick={onMenuToggle}
            className="md:hidden text-slate-500 hover:text-slate-700 p-1.5 rounded-lg"
            aria-label="Toggle Navigation"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        {/* Dynamic Breadcrumbs */}
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
          <Link to="/dashboard" className="hover:text-slate-700 transition-colors flex items-center">
            <BrandLogo mode="icon" className="md:hidden" />
            <span className="hidden md:inline">Candid Digital</span>
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
          <span className="text-slate-800 font-bold">{title || currentLabel}</span>
          {segments.length > 1 && (
            <>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span className="text-blue-600 font-mono text-[11px] truncate max-w-xs">{segments[1]}</span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Link to="/settings" title="Application Settings">
          <Button variant="ghost" size="sm" className="text-slate-500 hover:text-slate-800">
            <Settings className="w-4 h-4" />
          </Button>
        </Link>

        <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200/80">
          <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 text-slate-600 flex items-center justify-center font-bold text-xs uppercase shadow-sm">
            {user?.full_name ? user.full_name.charAt(0) : <UserIcon className="w-4 h-4" />}
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-xs font-semibold text-slate-800 leading-none">{user?.full_name || 'CRM User'}</div>
            <div className="text-[10px] text-slate-400 capitalize flex items-center gap-1 mt-0.5">
              <Shield className="w-2.5 h-2.5 text-blue-500" />
              {user?.role || 'Researcher'}
            </div>
          </div>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={logoutUser}
          className="text-slate-500 hover:text-rose-600 hover:bg-rose-50"
          title="Sign out"
          leftIcon={<LogOut className="w-4 h-4" />}
        >
          <span className="hidden sm:inline">Logout</span>
        </Button>
      </div>
    </header>
  );
};
