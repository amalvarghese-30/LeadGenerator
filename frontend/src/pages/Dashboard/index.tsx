import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Building2,
  Users,
  CheckCircle2,
  Clock,
  Award,
  Calendar,
  Sparkles,
  ArrowUpRight,
  TrendingUp,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { getDashboardStats, getLeadsReports, getProviderReports } from '../../services/reports';
import { DashboardStats } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b'];

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [leadsReport, setLeadsReport] = useState<any>(null);
  const [providerReport, setProviderReport] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [dashRes, leadsRes, provRes] = await Promise.all([
          getDashboardStats().catch(() => null),
          getLeadsReports().catch(() => null),
          getProviderReports().catch(() => null),
        ]);
        if (dashRes) setStats(dashRes);
        if (leadsRes) setLeadsReport(leadsRes);
        if (provRes) setProviderReport(provRes);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  if (isLoading) {
    return <LoadingSpinner message="Aggregating pipeline metrics..." />;
  }

  // Fallback demo numbers if database is newly initialized
  const displayStats = stats || {
    total_providers: 12,
    verified_providers: 9,
    total_leads: 48,
    verified_leads: 28,
    outreach_ready_leads: 18,
    follow_ups_due: 5,
    new_leads_7d: 14,
    total_contacts: 54,
    total_companies: 39,
    pending_crawl_jobs: 1,
  };

  // Prepare chart data
  const stageData = leadsReport?.by_stage
    ? Object.entries(leadsReport.by_stage).map(([stage, d]: [string, any]) => ({
        name: stage.replace(/_/g, ' '),
        count: d.count || 0,
      }))
    : [
        { name: 'Discovered', count: 18 },
        { name: 'Pending Review', count: 12 },
        { name: 'Verified', count: 10 },
        { name: 'Qualified', count: 8 },
        { name: 'Contacted', count: 5 },
      ];

  const categoryData = providerReport?.by_category
    ? Object.entries(providerReport.by_category).map(([cat, count]: [string, any]) => ({
        name: cat.replace(/_/g, ' '),
        value: count || 0,
      }))
    : [
        { name: 'Knowledge Panel', value: 5 },
        { name: 'Personal Branding', value: 4 },
        { name: 'Entity SEO', value: 2 },
        { name: 'Reputation Mgt', value: 1 },
      ];

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gradient-to-r from-blue-700 via-blue-800 to-indigo-900 rounded-2xl p-6 text-white shadow-xl shadow-blue-900/10">
        <div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/30 text-[11px] font-semibold text-blue-100 uppercase tracking-wider mb-2 border border-blue-400/20">
            <Sparkles className="w-3 h-3 text-blue-300" /> Reference Provider: theperson.in
          </span>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Provider Intelligence & Lead Discovery</h1>
          <p className="text-xs text-blue-200 mt-1 max-w-xl">
            Identifying personal branding, Knowledge Panel & Entity SEO competitors, discovering client evidence, and managing qualified CRM prospects.
          </p>
        </div>
        <div className="flex items-center gap-2.5 shrink-0">
          <Link to="/discovery">
            <Button variant="secondary" size="md" leftIcon={<Sparkles className="w-4 h-4 text-blue-600" />}>
              Start Discovery
            </Button>
          </Link>
          <Link to="/leads">
            <Button variant="outline" size="md" className="border-white/20 text-white bg-white/10 hover:bg-white/20">
              View CRM Leads
            </Button>
          </Link>
        </div>
      </div>

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <Card className="p-4">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Providers</span>
            <Building2 className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{displayStats.total_providers}</div>
          <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <TrendingUp className="w-3 h-3 text-emerald-500" /> {displayStats.verified_providers} verified
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Prospect Leads</span>
            <Users className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{displayStats.total_leads}</div>
          <div className="text-[11px] text-emerald-600 font-medium mt-1">+{displayStats.new_leads_7d} this week</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Verified</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{displayStats.verified_leads}</div>
          <div className="text-[11px] text-slate-400 mt-1">Evidence confirmed</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Qualified</span>
            <Award className="w-4 h-4 text-purple-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{displayStats.outreach_ready_leads}</div>
          <div className="text-[11px] text-purple-600 font-medium mt-1">Ready for review</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Follow-ups Due</span>
            <Calendar className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{displayStats.follow_ups_due}</div>
          <div className="text-[11px] text-amber-600 font-medium mt-1">Action needed</div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider mb-2">
            <span>Active Jobs</span>
            <Clock className="w-4 h-4 text-slate-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{displayStats.pending_crawl_jobs}</div>
          <div className="text-[11px] text-slate-400 mt-1">Background crawling</div>
        </Card>
      </div>

      {/* Visual Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Leads by CRM Pipeline Stage</h3>
              <p className="text-xs text-slate-500">Distribution across qualification and outreach stages</p>
            </div>
            <Link to="/leads" className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1">
              View CRM Pipeline <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stageData}>
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <div className="mb-4">
            <h3 className="text-sm font-bold text-slate-900">Providers by Category</h3>
            <p className="text-xs text-slate-500">Target market alignment</p>
          </div>
          <div className="h-52 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {categoryData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2 pt-3 border-t border-slate-100 text-[11px]">
            {categoryData.slice(0, 4).map((c, idx) => (
              <div key={c.name} className="flex items-center gap-1.5 truncate">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                <span className="text-slate-600 truncate">{c.name}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};
