import React from 'react';
import { NavLink, Link, useNavigate } from 'react-router-dom';
import {
  Radar,
  Users,
  Gauge,
  Settings,
  LogOut,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

export const Navbar: React.FC = () => {
  const { user, logoutUser } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logoutUser();
    navigate('/login');
  };

  const navLinks = [
    {
      to: '/',
      label: 'Scanner',
      sublabel: 'Competitor Client Finder',
      icon: Radar,
    },
    {
      to: '/directory',
      label: 'Directory',
      sublabel: 'Verified Clients & Contacts',
      icon: Users,
    },
    {
      to: '/rate-limits',
      label: 'Rate Limits',
      sublabel: 'Adaptive Pacing Engine',
      icon: Gauge,
    },
  ];

  return (
    <header className="bg-slate-950 border-b border-slate-800 text-slate-100 sticky top-0 z-30 shadow-lg select-none">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo & Tag */}
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-white shadow-md shadow-cyan-500/20 group-hover:scale-105 transition-transform">
                <Sparkles className="w-5 h-5" />
              </div>
              <div className="flex flex-col">
                <div className="flex items-center gap-2">
                  <span className="font-extrabold text-lg tracking-tight text-white group-hover:text-cyan-400 transition-colors">
                    LeadIntel
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-mono uppercase font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">
                    Pro
                  </span>
                </div>
                <span className="text-[10px] font-medium text-slate-400 hidden sm:inline -mt-0.5">
                  Client Discovery & Intelligence
                </span>
              </div>
            </Link>

            {/* Workspace Navigation Tabs */}
            <nav className="flex items-center gap-1 sm:gap-2 ml-4">
              {navLinks.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                      isActive
                        ? 'bg-slate-800 text-cyan-400 border border-slate-700 shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{label}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          {/* Right Tools & User Profile */}
          <div className="flex items-center gap-3">
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 border transition-all ${
                  isActive ? 'bg-slate-800 text-cyan-400 border-slate-700' : 'border-transparent'
                }`
              }
              title="Platform Settings"
            >
              <Settings className="w-4 h-4" />
            </NavLink>

            <div className="h-5 w-px bg-slate-800" />

            <div className="flex items-center gap-2.5">
              <div className="hidden md:flex flex-col text-right">
                <span className="text-xs font-bold text-slate-200 truncate max-w-[140px]">
                  {user?.full_name || 'Admin'}
                </span>
                <span className="text-[10px] font-mono text-slate-400 truncate max-w-[140px]">
                  {user?.email || 'admin@leadintel.local'}
                </span>
              </div>

              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-950/40 border border-red-900/30 transition-all"
                title="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
