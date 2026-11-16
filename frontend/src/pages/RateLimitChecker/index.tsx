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
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import {
  getRateLimitMetrics,
  getDomainRateLimits,
  resetRateLimitMetrics,
} from '../../services/rateLimits';
import { RateLimitSummary, DomainRateLimit } from '../../types';

export const RateLimitChecker: React.FC = () => {
  const [summary, setSummary] = useState<RateLimitSummary | null>(null);
  const [domains, setDomains] = useState<DomainRateLimit[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [sumRes, domRes] = await Promise.all([
        getRateLimitMetrics(),
        getDomainRateLimits(),
      ]);
      setSummary(sumRes);
      setDomains(domRes);
    } catch (err) {
      console.error('Failed to fetch rate limit metrics:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      await resetRateLimitMetrics();
      setIsResetModalOpen(false);
      fetchData();
    } catch (err) {
      console.error('Reset metrics failed:', err);
    } finally {
      setIsResetting(false);
    }
  };

  const chartData = domains.slice(0, 8).map((d) => ({
    name: d.domain,
    Success: d.success,
    Throttled: d.throttled_429,
    Forbidden: d.forbidden_403,
    Errors: d.errors,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Rate Limit Checker</h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time crawler telemetry, HTTP 429 throttling metrics, and adaptive backoff scheduling recommendations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setIsResetModalOpen(true)}>
            <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
            Reset Metrics
          </Button>
          <Button variant="primary" size="sm" onClick={fetchData}>
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
            Refresh Telemetry
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3.5">
        <Card className="p-4 border-l-4 border-l-blue-500">
          <p className="text-[11px] font-semibold text-slate-400">Total Requests</p>
          <p className="text-xl font-black text-slate-900 mt-1">
            {summary?.total_requests || 0}
          </p>
          <span className="text-[10px] text-slate-500">All outbound crawl HTTP</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-emerald-500">
          <p className="text-[11px] font-semibold text-slate-400">Successful 2xx</p>
          <p className="text-xl font-black text-emerald-600 mt-1">
            {summary?.successful_requests || 0}
          </p>
          <span className="text-[10px] text-emerald-700">Healthy responses</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-amber-500">
          <p className="text-[11px] font-semibold text-slate-400">429 Throttled</p>
          <p className="text-xl font-black text-amber-600 mt-1">
            {summary?.throttled_429_count || 0}
          </p>
          <span className="text-[10px] text-amber-700">Too Many Requests</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-rose-500">
          <p className="text-[11px] font-semibold text-slate-400">403 Forbidden</p>
          <p className="text-xl font-black text-rose-600 mt-1">
            {summary?.forbidden_403_count || 0}
          </p>
          <span className="text-[10px] text-rose-700">Access Denied / WAF</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-indigo-500">
          <p className="text-[11px] font-semibold text-slate-400">Avg Latency</p>
          <p className="text-xl font-black text-indigo-600 mt-1">
            {summary?.average_response_time_ms || 0} ms
          </p>
          <span className="text-[10px] text-slate-500">Response time</span>
        </Card>

        <Card className="p-4 border-l-4 border-l-purple-500">
          <p className="text-[11px] font-semibold text-slate-400">Error Rate</p>
          <p className="text-xl font-black text-purple-600 mt-1">
            {summary?.error_percentage || 0}%
          </p>
          <span className="text-[10px] text-slate-500">Throttled / failed</span>
        </Card>
      </div>

      {/* Adaptive Scheduler Recommendation Card */}
      <Card className="p-5 bg-gradient-to-r from-blue-50/60 to-indigo-50/40 border border-blue-100">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-md shadow-blue-500/20">
            <Sliders className="w-5 h-5 stroke-[2.2]" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900">Adaptive Scheduler Active</h2>
              <Badge variant="success">Robots.txt & Retry-After Enforced</Badge>
            </div>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              When target domains emit HTTP 429 or 403 responses, the crawler automatically throttles down concurrency to 1,
              honors published <code className="bg-white/80 px-1 py-0.5 rounded border border-blue-200">Retry-After</code> headers,
              and applies exponential backoff with random jitter to prevent IP blocks.
            </p>
          </div>
        </div>
      </Card>

      {/* Visual Chart */}
      {chartData.length > 0 && (
        <Card className="p-6">
          <h2 className="text-sm font-bold text-slate-800 mb-4">Request Distribution by Domain</h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} interval={0} angle={-15} textAnchor="end" />
                <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
                <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e2e8f0' }} />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
                <Bar dataKey="Success" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Throttled" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Forbidden" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Errors" fill="#94a3b8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      {/* Per-Domain Telemetry Table */}
      <Card className="p-5">
        <h2 className="text-sm font-bold text-slate-800 mb-4">
          Per-Domain Telemetry & Safe Scheduling Status ({domains.length})
        </h2>

        {isLoading ? (
          <div className="py-8 flex justify-center">
            <LoadingSpinner message="Loading telemetry..." />
          </div>
        ) : domains.length === 0 ? (
          <EmptyState
            title="No Telemetry Logged Yet"
            description="Outbound crawl requests from Website Intelligence will log real-time rate limit metrics here."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-400 uppercase text-[10px] font-bold border-b border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Domain</th>
                  <th className="py-2.5 px-3">Requests</th>
                  <th className="py-2.5 px-3">Success</th>
                  <th className="py-2.5 px-3">429s</th>
                  <th className="py-2.5 px-3">Avg Latency</th>
                  <th className="py-2.5 px-3">Safe Delay</th>
                  <th className="py-2.5 px-3">Concurrency</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {domains.map((d) => (
                  <tr key={d.domain} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-3 font-bold text-slate-900 flex items-center gap-1.5">
                      <Globe className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span>{d.domain}</span>
                    </td>
                    <td className="py-3 px-3 font-semibold">{d.requests}</td>
                    <td className="py-3 px-3 text-emerald-600 font-semibold">{d.success}</td>
                    <td className="py-3 px-3 text-amber-600 font-semibold">{d.throttled_429}</td>
                    <td className="py-3 px-3">{d.avg_response_time_ms} ms</td>
                    <td className="py-3 px-3 font-mono font-bold text-blue-600">
                      {d.configured_delay_seconds}s
                    </td>
                    <td className="py-3 px-3 font-semibold">{d.concurrency} worker(s)</td>
                    <td className="py-3 px-3">
                      {d.throttled_429 > 0 ? (
                        <Badge variant="warning">Throttled (Backing off)</Badge>
                      ) : (
                        <Badge variant="success">Normal Pacing</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Reset Confirmation Modal */}
      <ConfirmModal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        onConfirm={handleReset}
        title="Reset Rate Limit Metrics?"
        message="This will clear in-memory telemetry and MongoDB rate limit metrics. Crawlers will return to default starting pacing."
        confirmLabel="Reset Telemetry"
        isLoading={isResetting}
      />
    </div>
  );
};
