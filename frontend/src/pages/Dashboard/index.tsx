import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Building2,
  Users,
  CheckCircle2,
  Clock,
  Sparkles,
  ArrowUpRight,
  TrendingUp,
  UserCheck,
  Briefcase,
  Globe,
  Radar,
  Activity,
  Layers,
  ChevronRight,
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
  CartesianGrid,
} from 'recharts';
import { getDashboardStats, getLeadsReports, getProviderReports } from '../../services/reports';
import { getCrawlJobs } from '../../services/discovery';
import { DashboardStats, CrawlJob } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { CurrentScanMonitor } from '../../components/Dashboard/CurrentScanMonitor';

const COLORS = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b'];

export const Dashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [leadsReport, setLeadsReport] = useState<any>(null);
  const [providerReport, setProviderReport] = useState<any>(null);
  const [recentJobs, setRecentJobs] = useState<CrawlJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [dashRes, leadsRes, provRes, jobsRes] = await Promise.all([
          getDashboardStats().catch(() => null),
          getLeadsReports().catch(() => null),
          getProviderReports().catch(() => null),
          getCrawlJobs({ page: 1, page_size: 5 }).catch(() => null),
        ]);
        if (dashRes) setStats(dashRes);
        if (leadsRes) setLeadsReport(leadsRes);
        if (provRes) setProviderReport(provRes);
        if (jobsRes) setRecentJobs(jobsRes.items || []);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  if (isLoading) {
    return <LoadingSpinner message="Aggregating pipeline telemetry and intelligence..." />;
  }

  // Exact real metrics
  const displayStats = stats || {
    total_providers: 0,
    verified_providers: 0,
    total_leads: 0,
    verified_leads: 0,
    outreach_ready_leads: 0,
    follow_ups_due: 0,
    new_leads_7d: 0,
    total_contacts: 0,
    total_companies: 0,
    pending_crawl_jobs: 0,
  };

  const stageData = leadsReport?.by_stage
    ? Object.entries(leadsReport.by_stage).map(([stage, d]: [string, any]) => ({
        name: stage.replace(/_/g, ' '),
        count: d.count || 0,
      }))
    : [];

  const categoryData = providerReport?.by_category
    ? Object.entries(providerReport.by_category).map(([cat, count]: [string, any]) => ({
        name: cat.replace(/_/g, ' '),
        value: count || 0,
      }))
    : [];

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-slate-900 border border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-cyan-950 text-cyan-400 border border-cyan-800 uppercase tracking-wider">
              Control Center
            </span>
            <span className="text-xs text-slate-400 font-mono">v2.5</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-white">Operations Command Center</h1>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Real-time pipeline analytics, cross-provider intelligence, and autonomous discovery health.
          </p>
        </div>
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 relative z-10 shrink-0">
          <Link to="/lead-generator" className="w-full sm:w-auto">
            <Button variant="primary" size="sm" className="w-full sm:w-auto">
              <Sparkles className="w-3.5 h-3.5 mr-1.5 text-slate-950" />
              Launch Lead Generator
            </Button>
          </Link>
          <Link to="/scanner" className="w-full sm:w-auto">
            <Button variant="secondary" size="sm" className="w-full sm:w-auto">
              <Globe className="w-3.5 h-3.5 mr-1.5" />
              Scan Website
            </Button>
          </Link>
        </div>
      </div>

      {/* Prominent Live Scan Monitor */}
      <CurrentScanMonitor />

      {/* Top Level Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-3.5">
        <Card className="p-3.5 sm:p-4 bg-slate-900 border border-slate-800 border-l-4 border-l-blue-500 shadow-md">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Leads</span>
          <p className="text-lg sm:text-2xl font-black text-white mt-1">{displayStats.total_leads}</p>
          <span className="text-[10px] text-slate-400 mt-0.5 block truncate">{displayStats.new_leads_7d} new past 7 days</span>
        </Card>

        <Card className="p-3.5 sm:p-4 bg-slate-900 border border-slate-800 border-l-4 border-l-emerald-500 shadow-md">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Contacts</span>
          <p className="text-lg sm:text-2xl font-black text-emerald-400 mt-1">{displayStats.total_contacts}</p>
          <span className="text-[10px] text-slate-400 mt-0.5 block truncate">Verified profiles</span>
        </Card>

        <Card className="p-3.5 sm:p-4 bg-slate-900 border border-slate-800 border-l-4 border-l-indigo-500 shadow-md">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Companies</span>
          <p className="text-lg sm:text-2xl font-black text-indigo-400 mt-1">{displayStats.total_companies}</p>
          <span className="text-[10px] text-slate-400 mt-0.5 block truncate">Unique organizations</span>
        </Card>

        <Card className="p-3.5 sm:p-4 bg-slate-900 border border-slate-800 border-l-4 border-l-purple-500 shadow-md">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Providers</span>
          <p className="text-lg sm:text-2xl font-black text-purple-400 mt-1">{displayStats.total_providers}</p>
          <span className="text-[10px] text-slate-400 mt-0.5 block truncate">{displayStats.verified_providers} verified</span>
        </Card>

        <Card className="p-3.5 sm:p-4 bg-slate-900 border border-slate-800 border-l-4 border-l-amber-500 shadow-md">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Outreach Ready</span>
          <p className="text-lg sm:text-2xl font-black text-amber-400 mt-1">{displayStats.outreach_ready_leads}</p>
          <span className="text-[10px] text-slate-400 mt-0.5 block truncate">{displayStats.follow_ups_due} follow-ups</span>
        </Card>

        <Card className="p-3.5 sm:p-4 bg-slate-900 border border-slate-800 border-l-4 border-l-cyan-500 shadow-md">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Queue & Discovery</span>
          <p className="text-lg sm:text-2xl font-black text-cyan-400 mt-1">
            {displayStats.pending_crawl_jobs ?? 0}
          </p>
          <span className="text-[10px] text-cyan-300 mt-0.5 block truncate">
            Pending research jobs
          </span>
        </Card>
      </div>

      {/* Intelligence Modules Fast Jump Grid */}
      <div>
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          Intelligence & Discovery Workspaces
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <Link to="/lead-generator" className="group">
            <Card className="p-4 h-full bg-slate-900 border border-slate-800 hover:border-cyan-500/60 hover:bg-slate-850 hover:shadow-lg hover:shadow-cyan-500/5 transition-all">
              <div className="flex items-center justify-between mb-2.5">
                <div className="w-8 h-8 rounded-xl bg-cyan-950 text-cyan-400 border border-cyan-800 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Sparkles className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-white group-hover:text-cyan-400 transition-colors">
                Lead Generator
              </h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                Company & individual search with entity classification and direct CRM saving.
              </p>
            </Card>
          </Link>

          <Link to="/auto-profile-creator" className="group">
            <Card className="p-4 h-full bg-slate-900 border border-slate-800 hover:border-indigo-500/60 hover:bg-slate-850 hover:shadow-lg hover:shadow-indigo-500/5 transition-all">
              <div className="flex items-center justify-between mb-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-950 text-indigo-400 border border-indigo-800 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <UserCheck className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-white group-hover:text-indigo-400 transition-colors">
                Auto Profile Creator
              </h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                Cross-platform executive profile synthesis with corroborated identity evidence.
              </p>
            </Card>
          </Link>

          <Link to="/scanner" className="group">
            <Card className="p-4 h-full bg-slate-900 border border-slate-800 hover:border-purple-500/60 hover:bg-slate-850 hover:shadow-lg hover:shadow-purple-500/5 transition-all">
              <div className="flex items-center justify-between mb-2.5">
                <div className="w-8 h-8 rounded-xl bg-purple-950 text-purple-400 border border-purple-800 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Radar className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-purple-400 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-white group-hover:text-purple-400 transition-colors">
                Competitor Intelligence
              </h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                Scan provider competitors, discover client references, and monitor services.
              </p>
            </Card>
          </Link>

          <Link to="/providers" className="group">
            <Card className="p-4 h-full bg-slate-900 border border-slate-800 hover:border-emerald-500/60 hover:bg-slate-850 hover:shadow-lg hover:shadow-emerald-500/5 transition-all">
              <div className="flex items-center justify-between mb-2.5">
                <div className="w-8 h-8 rounded-xl bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Building2 className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-500 group-hover:text-emerald-400 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-white group-hover:text-emerald-400 transition-colors">
                Scanned Providers
              </h3>
              <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                Audit crawled provider domains, verify discovery status, and review extracted metrics.
              </p>
            </Card>
          </Link>
        </div>
      </div>

      {/* Visual Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6">
        {/* Pipeline Stage Distribution */}
        <div className="lg:col-span-8">
          <Card className="p-4 sm:p-5 h-full bg-slate-900 border border-slate-800 shadow-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-white">Lead Pipeline Distribution</h2>
              <Link to="/leads" className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 hover:underline">
                View CRM Leads
              </Link>
            </div>
            {stageData.length === 0 ? (
              <div className="h-60 flex items-center justify-center text-xs text-slate-500">
                No active leads in pipeline yet.
              </div>
            ) : (
              <div className="h-60 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stageData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1e293b" />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} interval={0} angle={-15} textAnchor="end" />
                    <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} />
                    <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: 12, fontSize: 12 }} />
                    <Bar dataKey="count" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </div>

        {/* Category Share */}
        <div className="lg:col-span-4">
          <Card className="p-4 sm:p-5 h-full flex flex-col justify-between bg-slate-900 border border-slate-800 shadow-md">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-white">Provider Categories</h2>
                <Link to="/providers" className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 hover:underline">
                  All Providers
                </Link>
              </div>
              {categoryData.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-xs text-slate-500">
                  No providers categorized yet.
                </div>
              ) : (
                <div className="h-48 w-full flex items-center justify-center">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={categoryData}
                        innerRadius={45}
                        outerRadius={70}
                        paddingAngle={4}
                        dataKey="value"
                      >
                        {categoryData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc', borderRadius: 12, fontSize: 12 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="space-y-1.5 pt-3 border-t border-slate-800">
              {categoryData.slice(0, 4).map((c, i) => (
                <div key={c.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: COLORS[i % COLORS.length] }}
                    />
                    <span className="text-slate-300 capitalize">{c.name}</span>
                  </div>
                  <span className="font-bold text-white">{c.value}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Recent Intelligence Jobs */}
      <Card className="p-4 sm:p-5 bg-slate-900 border border-slate-800 shadow-md">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-bold text-white">Recent Intelligence Scans</h2>
          </div>
          <Link to="/website-intelligence" className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 hover:underline">
            All Scans
          </Link>
        </div>

        {recentJobs.length === 0 ? (
          <div className="py-6 text-center text-xs text-slate-500">
            No intelligence scans executed yet. Start one from Website Intelligence.
          </div>
        ) : (
          <div className="divide-y divide-slate-800/80">
            {recentJobs.map((j) => (
              <div key={j.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 sm:gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-white font-mono truncate max-w-full">
                      {j.starting_url}
                    </span>
                    <Badge
                      variant={
                        j.status.startsWith('completed')
                          ? 'success'
                          : j.status === 'failed'
                          ? 'danger'
                          : j.status === 'cancelled'
                          ? 'warning'
                          : 'info'
                      }
                    >
                      {j.status.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {j.pages_crawled} crawled • {j.references_found} references • {j.leads_created} leads •{' '}
                    {new Date(j.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
                  {j.status.startsWith('completed') && (
                    <Link to={`/reports/${j.id}`} className="w-full sm:w-auto">
                      <Button variant="secondary" size="sm" className="w-full sm:w-auto">
                        View Report
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};
