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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Operations Command Center</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time pipeline analytics, cross-provider intelligence, and autonomous discovery health.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/lead-generator">
            <Button variant="primary" size="sm">
              <Sparkles className="w-3.5 h-3.5 mr-1.5" />
              Launch Lead Generator
            </Button>
          </Link>
          <Link to="/scanner">
            <Button variant="secondary" size="sm">
              <Globe className="w-3.5 h-3.5 mr-1.5" />
              Scan Website
            </Button>
          </Link>
        </div>
      </div>

      {/* Prominent Live Scan Monitor */}
      <CurrentScanMonitor />

      {/* Top Level Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <Card className="p-4 border-l-4 border-l-blue-600">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Leads</span>
          <p className="text-xl font-black text-slate-900 mt-1">{displayStats.total_leads}</p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">{displayStats.new_leads_7d} new past 7 days</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-emerald-600">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Contacts</span>
          <p className="text-xl font-black text-emerald-600 mt-1">{displayStats.total_contacts}</p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Verified profiles</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-indigo-600">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Companies</span>
          <p className="text-xl font-black text-indigo-600 mt-1">{displayStats.total_companies}</p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">Unique organizations</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-purple-600">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Providers</span>
          <p className="text-xl font-black text-purple-600 mt-1">{displayStats.total_providers}</p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">{displayStats.verified_providers} verified</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-amber-600">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Outreach Ready</span>
          <p className="text-xl font-black text-amber-600 mt-1">{displayStats.outreach_ready_leads}</p>
          <span className="text-[10px] text-slate-500 mt-0.5 block">{displayStats.follow_ups_due} follow-ups</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-sky-600">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Queue & Discovery</span>
          <p className="text-xl font-black text-sky-600 mt-1">
            {displayStats.pending_crawl_jobs ?? 0}
          </p>
          <span className="text-[10px] text-sky-700 mt-0.5 block">
            Pending research jobs
          </span>
        </Card>
      </div>

      {/* Intelligence Modules Fast Jump Grid */}
      <div>
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
          Intelligence & Discovery Workspaces
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          <Link to="/lead-generator" className="group">
            <Card className="p-4 h-full border border-slate-200/80 hover:border-blue-400 hover:shadow-md transition-all">
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Sparkles className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-slate-900 group-hover:text-blue-600 transition-colors">
                Lead Generator
              </h3>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Company & individual search with entity classification and direct CRM saving.
              </p>
            </Card>
          </Link>

          <Link to="/auto-profile-creator" className="group">
            <Card className="p-4 h-full border border-slate-200/80 hover:border-indigo-400 hover:shadow-md transition-all">
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <UserCheck className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-600 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors">
                Auto Profile Creator
              </h3>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Cross-platform executive profile synthesis with corroborated identity evidence.
              </p>
            </Card>
          </Link>

          <Link to="/scanner" className="group">
            <Card className="p-4 h-full border border-slate-200/80 hover:border-purple-400 hover:shadow-md transition-all">
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                  <Radar className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-purple-600 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-slate-900 group-hover:text-purple-600 transition-colors">
                Competitor Intelligence
              </h3>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Scan provider competitors, discover client references, and monitor services.
              </p>
            </Card>
          </Link>

          <Link to="/providers" className="group">
            <Card className="p-4 h-full border border-slate-200/80 hover:border-emerald-400 hover:shadow-md transition-all">
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <Building2 className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-emerald-600 transition-colors" />
              </div>
              <h3 className="text-xs font-bold text-slate-900 group-hover:text-emerald-600 transition-colors">
                Scanned Providers
              </h3>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                Audit crawled provider domains, verify discovery status, and review extracted metrics.
              </p>
            </Card>
          </Link>
        </div>
      </div>

      {/* Visual Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Pipeline Stage Distribution */}
        <div className="lg:col-span-8">
          <Card className="p-5 h-full">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-900">Lead Pipeline Distribution</h2>
              <Link to="/leads" className="text-xs font-semibold text-blue-600 hover:underline">
                View CRM Leads
              </Link>
            </div>
            {stageData.length === 0 ? (
              <div className="h-60 flex items-center justify-center text-xs text-slate-400">
                No active leads in pipeline yet.
              </div>
            ) : (
              <div className="h-60 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stageData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} interval={0} angle={-15} textAnchor="end" />
                    <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
                    <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e2e8f0' }} />
                    <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </div>

        {/* Category Share */}
        <div className="lg:col-span-4">
          <Card className="p-5 h-full flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-bold text-slate-900">Provider Categories</h2>
                <Link to="/providers" className="text-xs font-semibold text-blue-600 hover:underline">
                  All Providers
                </Link>
              </div>
              {categoryData.length === 0 ? (
                <div className="h-48 flex items-center justify-center text-xs text-slate-400">
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
                      <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e2e8f0' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="space-y-1.5 pt-3 border-t border-slate-100">
              {categoryData.slice(0, 4).map((c, i) => (
                <div key={c.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: COLORS[i % COLORS.length] }}
                    />
                    <span className="text-slate-600 capitalize">{c.name}</span>
                  </div>
                  <span className="font-bold text-slate-800">{c.value}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* Recent Intelligence Jobs */}
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-600" />
            <h2 className="text-sm font-bold text-slate-900">Recent Intelligence Scans</h2>
          </div>
          <Link to="/website-intelligence" className="text-xs font-semibold text-blue-600 hover:underline">
            All Scans
          </Link>
        </div>

        {recentJobs.length === 0 ? (
          <div className="py-6 text-center text-xs text-slate-400">
            No intelligence scans executed yet. Start one from Website Intelligence.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {recentJobs.map((j) => (
              <div key={j.id} className="py-3 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900 font-mono truncate">
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
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {j.pages_crawled} crawled • {j.references_found} references • {j.leads_created} leads •{' '}
                    {new Date(j.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {j.status.startsWith('completed') && (
                    <Link to={`/reports/${j.id}`}>
                      <Button variant="secondary" size="sm">
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
