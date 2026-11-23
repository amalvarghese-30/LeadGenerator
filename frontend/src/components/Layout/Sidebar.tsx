import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Search,
  UserSearch,
  Building,
  UserCheck,
  Globe,
  Radar,
  Gauge,
  Users,
  Briefcase,
  Building2,
  BarChart3,
  CheckSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { BrandLogo } from '../ui/BrandLogo';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const navSections = [
    {
      title: 'OVERVIEW',
      items: [
        { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
      ],
    },
    {
      title: 'FIND PROSPECTS',
      items: [
        { label: 'Lead Generator', to: '/lead-generator', icon: Sparkles },
        { label: 'People Finder', to: '/people-finder', icon: UserSearch },
        { label: 'Company Finder', to: '/company-finder', icon: Building },
        { label: 'Auto Profile Creator', to: '/auto-profile-creator', icon: UserCheck },
      ],
    },
    {
      title: 'RESEARCH & INTELLIGENCE',
      items: [
        { label: 'Website Intelligence', to: '/website-intelligence', icon: Globe },
        { label: 'Competitor Intelligence', to: '/competitor-intelligence', icon: Radar },
        { label: 'Rate Limit Checker', to: '/rate-limit-checker', icon: Gauge },
        { label: 'Providers', to: '/providers', icon: Building2 },
      ],
    },
    {
      title: 'CRM WORKSPACE',
      items: [
        { label: 'Leads', to: '/leads', icon: Users },
        { label: 'Companies', to: '/companies', icon: Briefcase },
        { label: 'Contacts', to: '/contacts', icon: UserCheck },
        { label: 'Tasks & Activities', to: '/tasks', icon: CheckSquare },
      ],
    },
    {
      title: 'REPORTS & SETTINGS',
      items: [
        { label: 'Reports', to: '/reports', icon: BarChart3 },
        { label: 'Settings', to: '/settings', icon: Settings },
      ],
    },
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
          {collapsed ? (
            <BrandLogo mode="icon" />
          ) : (
            <BrandLogo mode="full" />
          )}
        </div>
      </div>

      {/* Navigation list */}
      <div className="flex-1 py-3 px-3 space-y-4 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.title} className="space-y-1">
            {!collapsed && (
              <h2 className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                {section.title}
              </h2>
            )}
            {section.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-3 py-2 rounded-xl text-xs font-semibold tracking-wide transition-all group',
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
        ))}
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
