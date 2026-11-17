import React, { useState, useEffect } from 'react';
import {
  Gauge,
  Activity,
  AlertTriangle,
  ShieldCheck,
  RefreshCw,
  Clock,
  RotateCcw,
  Zap,
  Globe,
  Sliders,
  Download,
  Search,
  Filter,
  CheckCircle2,
  XCircle,
  Pause,
  Play,
  Key,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from 'recharts';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import { Modal } from '../../components/ui/Modal';
import { useToast } from '../../context/ToastContext';
import {
  getRateLimitMetrics,
  getDomainRateLimits,
  resetRateLimitMetrics,
  pauseDomain,
  resumeDomain,
  resetDomainProfile,
  getRequestLogs,
  getRateLimitEvents,
  getGitHubStatus,
  refreshGitHubQuota,
  configureGitHubToken,
} from '../../services/rateLimits';
import { RateLimitSummary, DomainRateLimit } from '../../types';

export const RateLimitChecker: React.FC = () => {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<'overview' | 'logs' | 'incidents' | 'github'>('overview');

  // Overview state
  const [summary, setSummary] = useState<RateLimitSummary | null>(null);
  const [domains, setDomains] = useState<DomainRateLimit[]>([]);
  const [domainSearch, setDomainSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  // Modals
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [domainToReset, setDomainToReset] = useState<string | null>(null);

  // Request logs state
  const [requestLogs, setRequestLogs] = useState<any[]>([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsPage, setLogsPage] = useState(1);
  const [logsLoading, setLogsLoading] = useState(false);

  // Incidents state
  const [incidents, setIncidents] = useState<any[]>([]);
  const [incidentsLoading, setIncidentsLoading] = useState(false);

  // GitHub Provider state
  const [gitHubProfile, setGitHubProfile] = useState<any>(null);
  const [gitHubLoading, setGitHubLoading] = useState(false);
  const [isTokenModalOpen, setIsTokenModalOpen] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const [isSavingToken, setIsSavingToken] = useState(false);

  const fetchOverview = async () => {
    setIsLoading(true);
    try {
      const [sumRes, domRes] = await Promise.all([
        getRateLimitMetrics(),
        getDomainRateLimits({ search: domainSearch || undefined, status: statusFilter || undefined }),
      ]);
      setSummary(sumRes);
      setDomains(domRes);
    } catch (err: any) {
      console.error('Failed to fetch rate limit metrics:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchLogs = async () => {
    setLogsLoading(true);
    try {
      const res = await getRequestLogs({ page: logsPage, limit: 30 });
      setRequestLogs(res.items);
      setLogsTotal(res.total);
    } catch (err: any) {
      toast.error('Failed to load request logs');
    } finally {
      setLogsLoading(false);
    }
  };

  const fetchIncidents = async () => {
    setIncidentsLoading(true);
    try {
      const data = await getRateLimitEvents(40);
      setIncidents(data);
    } catch (err: any) {
      toast.error('Failed to load incidents');
    } finally {
      setIncidentsLoading(false);
    }
  };

  const fetchGitHub = async () => {
    setGitHubLoading(true);
    try {
      const data = await getGitHubStatus();
      setGitHubProfile(data);
    } catch (err: any) {
      toast.error('Failed to load GitHub quota status');
    } finally {
      setGitHubLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'overview') fetchOverview();
    if (activeTab === 'logs') fetchLogs();
    if (activeTab === 'incidents') fetchIncidents();
    if (activeTab === 'github') fetchGitHub();
  }, [activeTab, domainSearch, statusFilter, logsPage]);

  // Periodic polling for overview
  useEffect(() => {
    if (activeTab !== 'overview') return;
    const interval = setInterval(fetchOverview, 15000);
    return () => clearInterval(interval);
  }, [activeTab, domainSearch, statusFilter]);

  const handleResetAll = async () => {
    setIsResetting(true);
    try {
      await resetRateLimitMetrics();
      setIsResetModalOpen(false);
      toast.success('All rate limit metrics, request logs, and domain profiles reset');
      fetchOverview();
    } catch (err: any) {
      toast.error('Failed to reset metrics');
    } finally {
      setIsResetting(false);
    }
  };

  const handleTogglePause = async (domain: string, isCurrentlyPaused: boolean) => {
    try {
      if (isCurrentlyPaused) {
        await resumeDomain(domain);
        toast.success(`Resumed crawler requests for ${domain}`);
      } else {
        await pauseDomain(domain, 'Administrative manual hold');
        toast.warning(`Paused crawler requests for ${domain}`);
      }
      fetchOverview();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update domain status');
    }
  };

  const handleResetSingleDomain = async () => {
    if (!domainToReset) return;
    try {
      await resetDomainProfile(domainToReset);
      toast.success(`Learned schedule reset for ${domainToReset}`);
      setDomainToReset(null);
      fetchOverview();
    } catch (err: any) {
      toast.error('Failed to reset domain');
    }
  };

  const handleRefreshGitHub = async () => {
    setGitHubLoading(true);
    try {
      const updated = await refreshGitHubQuota();
      setGitHubProfile(updated);
      toast.success('GitHub API quota refreshed');
    } catch (err: any) {
      toast.error('Failed to refresh GitHub quota');
    } finally {
      setGitHubLoading(false);
    }
  };

  const handleSaveGitHubToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    setIsSavingToken(true);
    try {
      const updated = await configureGitHubToken(tokenInput.trim());
      setGitHubProfile(updated);
      setIsTokenModalOpen(false);
      setTokenInput('');
      toast.success('GitHub personal access token securely configured');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save token');
    } finally {
      setIsSavingToken(false);
    }
  };

  const chartData = domains.slice(0, 8).map((d) => ({
    name: d.domain,
    Success: d.successful_requests ?? d.success ?? 0,
    Throttled: d.blocked_requests ?? d.throttled_429 ?? 0,
    Forbidden: d.forbidden_403 ?? 0,
    Errors: d.errors ?? 0,
  }));

  const getStatusBadge = (status?: string, isPaused?: boolean) => {
    if (isPaused) return <Badge variant="warning">Paused</Badge>;
    switch (status) {
      case 'normal':
        return <Badge variant="success">Normal</Badge>;
      case 'cautious':
        return <Badge variant="warning">Cautious</Badge>;
      case 'attention_required':
        return <Badge variant="danger">Attention Required</Badge>;
      default:
        return <Badge variant="default">Insufficient Data</Badge>;
    }
  };

  const getClassificationBadge = (classification: string) => {
    switch (classification) {
      case 'SUCCESS':
        return <Badge variant="success">SUCCESS</Badge>;
      case 'RATE_LIMITED':
        return <Badge variant="danger">429 THROTTLED</Badge>;
      case 'BOT_PROTECTION':
        return <Badge variant="warning">WAF / CLOUDFLARE</Badge>;
      case 'ACCESS_FORBIDDEN':
        return <Badge variant="danger">403 FORBIDDEN</Badge>;
      case 'TIMEOUT':
        return <Badge variant="warning">TIMEOUT</Badge>;
      default:
        return <Badge variant="default">{classification}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Rate Limit Checker</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time crawler telemetry, per-domain backoff pacing, 429 restriction detection & GitHub API quota monitoring.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setIsResetModalOpen(true)}>
            <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
            Reset All Telemetry
          </Button>
          <Button variant="primary" size="sm" onClick={activeTab === 'overview' ? fetchOverview : activeTab === 'logs' ? fetchLogs : activeTab === 'github' ? handleRefreshGitHub : fetchIncidents}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200/80 pb-3">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'overview' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Gauge className="w-3.5 h-3.5" />
          Overview & Domains
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'logs' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Request Logs
        </button>
        <button
          onClick={() => setActiveTab('incidents')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'incidents' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <AlertTriangle className="w-3.5 h-3.5" />
          Rate Limit Incidents
        </button>
        <button
          onClick={() => setActiveTab('github')}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
            activeTab === 'github' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          GitHub API Quotas
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
            <Card className="p-4 bg-white border border-slate-200/80">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Requests</span>
              <div className="text-xl font-bold text-slate-900 mt-1">{summary?.total_requests ?? 0}</div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">Recorded crawl calls</span>
            </Card>

            <Card className="p-4 bg-white border border-slate-200/80">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Successful</span>
              <div className="text-xl font-bold text-emerald-600 mt-1">{summary?.successful_requests ?? 0}</div>
              <span className="text-[10px] text-emerald-700/80 mt-0.5 block">2xx OK responses</span>
            </Card>

            <Card className="p-4 bg-white border border-slate-200/80">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Throttled (429)</span>
              <div className="text-xl font-bold text-rose-600 mt-1">{summary?.throttled_429_count ?? 0}</div>
              <span className="text-[10px] text-rose-700/80 mt-0.5 block">Rate-limit incidents</span>
            </Card>

            <Card className="p-4 bg-white border border-slate-200/80">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Blocking Rate</span>
              <div className="text-xl font-bold text-slate-900 mt-1">{summary?.blocking_percentage ?? 0}%</div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">Throttled / total</span>
            </Card>

            <Card className="p-4 bg-white border border-slate-200/80">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Avg Latency</span>
              <div className="text-xl font-bold text-indigo-600 mt-1">{summary?.average_response_time_ms ?? 0} ms</div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">Round-trip response</span>
            </Card>

            <Card className="p-4 bg-white border border-slate-200/80">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Monitored Domains</span>
              <div className="text-xl font-bold text-blue-600 mt-1">{summary?.active_monitored_domains ?? 0}</div>
              <span className="text-[10px] text-slate-500 mt-0.5 block">
                {summary?.paused_domains ?? 0} paused
              </span>
            </Card>
          </div>

          {/* Activity Chart */}
          {chartData.length > 0 && (
            <Card className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Domain Request Distribution</h3>
                  <p className="text-xs text-slate-500">HTTP status response volume for most active target websites</p>
                </div>
              </div>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} angle={-15} textAnchor="end" />
                    <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: '0.75rem',
                        border: '1px solid #e2e8f0',
                        fontSize: '12px',
                        boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                    <Bar dataKey="Success" fill="#10b981" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Throttled" fill="#ef4444" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Forbidden" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Errors" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          {/* Monitored Domains Table */}
          <Card className="p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Observed Domain Profiles & Backoff Policies</h3>
                <p className="text-xs text-slate-500">
                  Shared across crawler workers and API via MongoDB persistence.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Filter domain..."
                  value={domainSearch}
                  onChange={(e) => setDomainSearch(e.target.value)}
                  leftIcon={<Search className="w-3.5 h-3.5 text-slate-400" />}
                  className="w-48 text-xs py-1"
                />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="text-xs bg-slate-50 border border-slate-200 rounded-xl px-2.5 py-1.5 text-slate-700"
                >
                  <option value="">All Statuses</option>
                  <option value="normal">Normal</option>
                  <option value="cautious">Cautious</option>
                  <option value="attention_required">Attention Required</option>
                  <option value="paused">Paused</option>
                </select>
              </div>
            </div>

            {isLoading ? (
              <div className="py-12 flex justify-center">
                <LoadingSpinner message="Querying domain telemetry from MongoDB..." />
              </div>
            ) : domains.length === 0 ? (
              <EmptyState
                title="No Domain Metrics Recorded Yet"
                description="Start a research scan in Website Intelligence or Lead Generator to populate real-time crawler telemetry."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                      <th className="py-2.5 px-3">Domain</th>
                      <th className="py-2.5 px-3">Total Reqs</th>
                      <th className="py-2.5 px-3">Success</th>
                      <th className="py-2.5 px-3">Throttled (429)</th>
                      <th className="py-2.5 px-3">Blocking %</th>
                      <th className="py-2.5 px-3">Active Delay</th>
                      <th className="py-2.5 px-3">Confidence</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {domains.map((d) => {
                      const totalReqs = d.total_requests ?? d.requests ?? 0;
                      const succReqs = d.successful_requests ?? d.success ?? 0;
                      const throttled = d.blocked_requests ?? d.throttled_429 ?? 0;
                      const blockPct = d.blocking_percentage ?? d.error_rate_pct ?? 0;
                      const delaySec = d.active_interval_ms ? (d.active_interval_ms / 1000).toFixed(1) : d.configured_delay_seconds ? d.configured_delay_seconds.toFixed(1) : '1.0';

                      return (
                        <tr key={d.domain} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3 px-3 font-bold text-slate-900 flex items-center gap-1.5">
                            <Globe className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <span>{d.domain}</span>
                          </td>
                          <td className="py-3 px-3 font-mono">{totalReqs}</td>
                          <td className="py-3 px-3 text-emerald-600 font-semibold">{succReqs}</td>
                          <td className="py-3 px-3 text-rose-600 font-semibold">{throttled}</td>
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                              blockPct > 20 ? 'bg-rose-50 text-rose-700' : blockPct > 5 ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'
                            }`}>
                              {blockPct}%
                            </span>
                          </td>
                          <td className="py-3 px-3 font-mono text-slate-700">
                            {delaySec}s ({d.active_concurrency ?? d.concurrency ?? 3} conc)
                          </td>
                          <td className="py-3 px-3 text-[10px] text-slate-500 font-semibold">
                            {d.confidence || 'INSUFFICIENT DATA'}
                          </td>
                          <td className="py-3 px-3">
                            {getStatusBadge(d.status, d.is_paused)}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => handleTogglePause(d.domain, !!d.is_paused)}
                                title={d.is_paused ? 'Resume crawler requests' : 'Pause crawler requests'}
                              >
                                {d.is_paused ? <Play className="w-3 h-3 text-emerald-600" /> : <Pause className="w-3 h-3 text-amber-600" />}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setDomainToReset(d.domain)}
                                title="Reset learned statistics"
                              >
                                <RotateCcw className="w-3 h-3 text-slate-400 hover:text-slate-700" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* TAB 2: REQUEST LOGS */}
      {activeTab === 'logs' && (
        <Card className="p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Crawler Request Stream & Responses</h3>
              <p className="text-xs text-slate-500">Live operational telemetry captured from outgoing HTTP clients.</p>
            </div>
            <a
              href="/api/rate-limits/export/csv"
              download="rate_limit_logs.csv"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </a>
          </div>

          {logsLoading ? (
            <div className="py-12 flex justify-center">
              <LoadingSpinner message="Fetching request logs..." />
            </div>
          ) : requestLogs.length === 0 ? (
            <EmptyState
              title="No Request Logs Recorded"
              description="Outgoing HTTP requests made by the crawler will be logged here with status codes, classifications, and latency."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3">Timestamp</th>
                    <th className="py-2.5 px-3">Domain</th>
                    <th className="py-2.5 px-3">Endpoint</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Classification</th>
                    <th className="py-2.5 px-3">Latency</th>
                    <th className="py-2.5 px-3">Retry-After</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {requestLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-2.5 px-3 text-[11px] text-slate-500 font-mono">
                        {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-800">{log.domain}</td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-500 max-w-xs truncate">
                        {log.endpoint || '/'}
                      </td>
                      <td className="py-2.5 px-3 font-bold font-mono">
                        <span className={log.status_code === 429 ? 'text-rose-600' : log.status_code === 403 ? 'text-amber-600' : log.status_code < 400 ? 'text-emerald-600' : 'text-slate-600'}>
                          {log.status_code || 'ERR'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">{getClassificationBadge(log.classification)}</td>
                      <td className="py-2.5 px-3 font-mono text-slate-600">{log.response_time_ms} ms</td>
                      <td className="py-2.5 px-3 font-mono text-slate-500">
                        {log.retry_after ? `${log.retry_after}s` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {/* TAB 3: INCIDENTS */}
      {activeTab === 'incidents' && (
        <Card className="p-5 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Rate Limit Incidents & Cooldown History</h3>
            <p className="text-xs text-slate-500">Persistent timeline of HTTP 429 throttles, domain pauses, and backoff triggers.</p>
          </div>

          {incidentsLoading ? (
            <div className="py-12 flex justify-center">
              <LoadingSpinner message="Loading incident timeline..." />
            </div>
          ) : incidents.length === 0 ? (
            <EmptyState
              title="No Incidents Detected"
              description="No HTTP 429 or restriction incidents have been logged. The crawler is running within normal limits."
            />
          ) : (
            <div className="space-y-3">
              {incidents.map((ev) => (
                <div key={ev.id} className="p-4 rounded-xl border border-slate-200/80 bg-white flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-xs text-slate-900">{ev.domain}</span>
                      <Badge variant={ev.severity === 'critical' ? 'danger' : 'warning'}>
                        {ev.event_type.replace(/_/g, ' ').toUpperCase()}
                      </Badge>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {ev.timestamp ? new Date(ev.timestamp).toLocaleString() : ''}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600">{ev.reason}</p>
                    {ev.cooldown_until && (
                      <div className="text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded font-mono inline-block">
                        Active Cooldown Until: {new Date(ev.cooldown_until).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* TAB 4: GITHUB API QUOTA (MODE B) */}
      {activeTab === 'github' && (
        <div className="space-y-6">
          <Card className="p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-slate-900" /> Mode B: GitHub REST API Quota Monitor
                </h3>
                <p className="text-xs text-slate-500">
                  Authoritative rate-limit inspection via GET /rate_limit. Secondary rate-limit detection and token security.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={() => setIsTokenModalOpen(true)}>
                  <Key className="w-3.5 h-3.5 mr-1.5" />
                  Configure Token
                </Button>
                <Button variant="primary" size="sm" onClick={handleRefreshGitHub} isLoading={gitHubLoading}>
                  <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
                  Refresh Quota
                </Button>
              </div>
            </div>

            {/* Authentication Status Banner */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-4 h-4 text-blue-600" />
                <span className="text-slate-700 font-medium">
                  Authentication Profile:
                  <strong className="ml-1 text-slate-900 capitalize">
                    {gitHubProfile?.auth_status || 'Unauthenticated'}
                  </strong>
                  {gitHubProfile?.token_masked && (
                    <code className="ml-2 bg-slate-200 px-1.5 py-0.5 rounded text-[10px]">
                      {gitHubProfile.token_masked}
                    </code>
                  )}
                </span>
              </div>
              <span className="text-[11px] text-slate-400">
                Last Refreshed: {gitHubProfile?.last_refreshed_at ? new Date(gitHubProfile.last_refreshed_at).toLocaleTimeString() : 'Never'}
              </span>
            </div>

            {/* Dynamic Resource Quota Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
              {gitHubProfile?.resources && Object.keys(gitHubProfile.resources).length > 0 ? (
                Object.entries(gitHubProfile.resources).map(([rName, q]: [string, any]) => {
                  const util = q.utilization_pct || 0;
                  return (
                    <Card key={rName} className="p-4 bg-white border border-slate-200/80 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-900 uppercase tracking-wide">
                          {rName}
                        </span>
                        <Badge variant={util > 80 ? 'danger' : util > 50 ? 'warning' : 'success'}>
                          {util}% used
                        </Badge>
                      </div>

                      {/* Quota Bar */}
                      <div>
                        <div className="flex items-center justify-between text-xs text-slate-600 mb-1">
                          <span>Remaining: <strong className="text-slate-900">{q.remaining}</strong></span>
                          <span className="text-slate-400">/ {q.limit}</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                          <div
                            className={`h-full transition-all ${
                              util > 80 ? 'bg-rose-500' : util > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                            }`}
                            style={{ width: `${Math.min(100, util)}%` }}
                          />
                        </div>
                      </div>

                      <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-100 flex items-center justify-between">
                        <span>Reset: {new Date(q.reset_at).toLocaleTimeString()}</span>
                        <span>Used: {q.used}</span>
                      </div>
                    </Card>
                  );
                })
              ) : (
                <div className="col-span-full py-8 text-center text-xs text-slate-400">
                  No GitHub API quota data loaded yet. Click "Refresh Quota" to poll GitHub REST endpoints.
                </div>
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Reset Confirmation Modal */}
      <ConfirmModal
        isOpen={isResetModalOpen}
        title="Reset All Telemetry"
        message="Are you sure you want to delete all recorded rate-limit request metrics, incident logs, and domain profiles? This cannot be undone."
        confirmText="Reset All Data"
        confirmVariant="danger"
        isLoading={isResetting}
        onConfirm={handleResetAll}
        onCancel={() => setIsResetModalOpen(false)}
      />

      {/* Single Domain Reset Confirmation Modal */}
      <ConfirmModal
        isOpen={!!domainToReset}
        title={`Reset Learned Schedule for ${domainToReset}`}
        message="Are you sure you want to reset the learned request interval and backoff statistics for this domain? Active server cooldowns will not be bypassed."
        confirmText="Reset Domain Profile"
        confirmVariant="warning"
        onConfirm={handleResetSingleDomain}
        onCancel={() => setDomainToReset(null)}
      />

      {/* GitHub Token Modal */}
      <Modal
        isOpen={isTokenModalOpen}
        onClose={() => setIsTokenModalOpen(false)}
        title="Configure GitHub Personal Access Token"
      >
        <form onSubmit={handleSaveGitHubToken} className="space-y-4">
          <p className="text-xs text-slate-600">
            Enter a GitHub personal access token (classic or fine-grained) with read access to increase your REST API quota from 60 to 5,000 requests per hour. The secret is encrypted and masked on the backend.
          </p>
          <Input
            label="Personal Access Token"
            type="password"
            placeholder="ghp_..."
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            required
            helperText="Stored securely in MongoDB api_rate_limit_profiles with strict masking."
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setIsTokenModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSavingToken}>
              Save Token
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
