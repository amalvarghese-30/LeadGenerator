import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Building2,
  Users,
  UserCheck,
  Briefcase,
  CheckSquare,
  Sparkles,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { cn } from '../../utils/cn';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const navItems = [
    { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
    { label: 'Providers', to: '/providers', icon: Building2 },
    { label: 'Leads', to: '/leads', icon: Users },
    { label: 'Contacts', to: '/contacts', icon: UserCheck },
    { label: 'Companies', to: '/companies', icon: Briefcase },
    { label: 'Discovery', to: '/discovery', icon: Sparkles },
    { label: 'Reports', to: '/reports', icon: BarChart3 },
    { label: 'Settings', to: '/settings', icon: Settings },
  ];

  return (
    <aside
      className={cn(
        'relative bg-white border-r border-slate-200/80 flex flex-col transition-all duration-200 z-30 select-none shadow-[1px_0_4px_rgba(0,0,0,0.02)]',
        collapsed ? 'w-18' : 'w-64'
      )}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-slate-100">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-700 to-indigo-600 flex items-center justify-center text-white font-bold shadow-md shadow-blue-500/20 shrink-0">
            <ShieldCheck className="w-5 h-5 stroke-[2.2]" />
          </div>
          {!collapsed && (
            <div className="truncate">
              <h1 className="text-sm font-bold tracking-tight text-slate-900 leading-none">LeadIntel</h1>
              <span className="text-[10px] font-semibold text-blue-600 tracking-wider uppercase">CRM Platform</span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation list */}
      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold tracking-wide transition-all group',
                  isActive
                    ? 'bg-blue-50 text-blue-700 shadow-sm shadow-blue-500/5 font-bold'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                )
              }
              title={collapsed ? item.label : undefined}
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={cn(
                      'w-4 h-4 shrink-0 transition-colors',
                      isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'
                    )}
                  />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </>
              )}
            </NavLink>
          );
        })}
      </div>

      {/* Footer / Collapse Button */}
      <div className="p-3 border-t border-slate-100">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-2 p-2 rounded-xl text-xs font-medium text-slate-500 hover:bg-slate-100 transition-colors"
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : (
            <>
              <ChevronLeft className="w-4 h-4" />
              <span>Collapse Sidebar</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
