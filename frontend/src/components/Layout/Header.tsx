import React from 'react';
import { useAuth } from '../../hooks/useAuth';
import { LogOut, User as UserIcon, Shield, Menu } from 'lucide-react';
import { Button } from '../ui/Button';

interface HeaderProps {
  onMenuToggle?: () => void;
  title?: string;
}

export const Header: React.FC<HeaderProps> = ({ onMenuToggle, title }) => {
  const { user, logoutUser } = useAuth();

  return (
    <header className="h-16 bg-white/80 backdrop-blur-md border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        {onMenuToggle && (
          <button
            onClick={onMenuToggle}
            className="md:hidden text-slate-500 hover:text-slate-700 p-1.5 rounded-lg"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        {title && <h2 className="text-base font-bold text-slate-800 tracking-tight">{title}</h2>}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
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
