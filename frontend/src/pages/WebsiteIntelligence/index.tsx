import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Globe,
  Sparkles,
  ExternalLink,
  Loader2,
  AlertCircle,
  ChevronRight,
  ShieldAlert,
  RotateCcw,
  Sliders,
  Terminal,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Radio,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { createProvider, startProviderResearch } from '../../services/providers';
import {
  getCrawlJob,
  getCrawlJobs,
  cancelCrawlJob,
  retryCrawlJob,
  getJobEvents,
  getJobEventsStreamUrl,
} from '../../services/discovery';
import { CrawlJob, JobEvent } from '../../types';

export const WebsiteIntelligence: React.FC = () => {
  const navigate = useNavigate();

  // Launcher state
  const [targetUrl, setTargetUrl] = useState('https://theperson.in/');
  const [pageLimit, setPageLimit] = useState(30);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active Job state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [job, setJob] = useState<CrawlJob | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);

  // Cancellation modal state
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);

  // Historical Jobs table
  const [recentJobs, setRecentJobs] = useState<CrawlJob[]>([]);
  const [isJobsLoading, setIsJobsLoading] = useState(false);

  const pollRef = useRef<number | null>(null);
  const sseRef = useRef<EventSource | null>(null);
  const logsEndRef = useRef<HTMLDivElement | null>(null);

  const fetchRecentJobs = async () => {
    setIsJobsLoading(true);
    try {
      const res = await getCrawlJobs({ page: 1, page_size: 10 });
      setRecentJobs(res.items);
    } catch (err) {
      console.error('Failed to fetch recent jobs:', err);
    } finally {
      setIsJobsLoading(false);
    }
  };

  useEffect(() => {
    fetchRecentJobs();
  }, []);

  // Set up SSE or event polling for active job
  useEffect(() => {
    if (!activeJobId) {
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
      return;
    }

    // Try EventSource
    try {
      const eventSource = new EventSource(getJobEventsStreamUrl(activeJobId));
      sseRef.current = eventSource;

      eventSource.onmessage = (e) => {
        try {
          const ev: JobEvent = JSON.parse(e.data);
          setEvents((prev) => {
            if (prev.some((p) => p.id === ev.id && p.event_timestamp === ev.event_timestamp)) {
              return prev;
            }
            return [...prev, ev];
          });
        } catch {
          // heartbeat or non-json
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        sseRef.current = null;
      };
    } catch {
      // fallback to poll
    }

    // Job state polling
    const tick = async () => {
      try {
        const j = await getCrawlJob(activeJobId);
        setJob(j);

        // Also fetch events periodically in case SSE missed any
        try {
          const evList = await getJobEvents(activeJobId);
          if (evList && evList.length > 0) {
            setEvents(evList);
          }
        } catch {
          // ignore
        }

        const terminal = ['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(j.status);
        if (terminal) {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
          fetchRecentJobs();
        }
      } catch {
        // transient poll error
      }
    };

    pollRef.current = window.setInterval(tick, 2000);
    tick();

    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
    };
  }, [activeJobId]);

  // Auto-scroll log to bottom
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events]);

  const handleStartResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetUrl.trim()) return;

    setError(null);
    setIsStarting(true);
    setEvents([]);
    try {
      const domainName = targetUrl.replace(/https?:\/\//, '').split('/')[0];
      const provider = await createProvider({
        name: domainName,
        website: targetUrl,
        category: 'direct_competitor',
      });
      const providerId = (provider as any).id || (provider as any)._id;

      const createdJob = await startProviderResearch(providerId);
      const jId = createdJob.id || (createdJob as any)._id;
      setActiveJobId(jId);
      setJob(createdJob);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to start research');
    } finally {
      setIsStarting(false);
    }
  };

  const handleConfirmCancel = async () => {
    if (!activeJobId) return;
    setIsCancelling(true);
    try {
      await cancelCrawlJob(activeJobId);
      setIsCancelModalOpen(false);
      // Update local status
      if (job) {
        setJob({ ...job, status: 'cancelled', current_stage: 'cancelled' });
      }
      fetchRecentJobs();
    } catch (err) {
      console.error('Cancel job failed:', err);
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetryJob = async (id: string) => {
    try {
      await retryCrawlJob(id);
      setActiveJobId(id);
      setEvents([]);
      fetchRecentJobs();
    } catch (err) {
      console.error('Retry failed:', err);
    }
  };

  const getStageLabel = (stage?: string) => {
    switch (stage) {
      case 'queued': return 'Queued';
      case 'discovering': return 'Discovering Target URLs';
      case 'crawling': return 'Crawling Webpages';
      case 'extracting': return 'Extracting Client References';
      case 'enriching_contacts': return 'Enriching Public Channels';
      case 'generating_report': return 'Synthesizing Report';
      case 'completed': return 'Completed';
      case 'cancelled': return 'Cancelled';
      case 'failed': return 'Failed';
      default: return stage || 'Working...';
    }
  };

  const isJobTerminal = job && ['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(job.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">Website Intelligence</h1>
        <p className="text-xs text-slate-500 mt-1">
          Deep automated website crawling, multi-source URL discovery (sitemaps, RSS, CMS, dorking), and client reference extraction.
        </p>
      </div>

      {/* Target Launch Card */}
      <Card className="p-5">
        <form onSubmit={handleStartResearch} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3.5 items-end">
            <div className="sm:col-span-8">
              <Input
                label="Target Provider Website URL *"
                type="url"
                required
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="https://theperson.in/"
                disabled={Boolean(activeJobId && !isJobTerminal)}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                Page Limit
              </label>
              <select
                value={pageLimit}
                onChange={(e) => setPageLimit(Number(e.target.value))}
                disabled={Boolean(activeJobId && !isJobTerminal)}
                className="w-full text-xs font-semibold py-2.5 px-3 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:ring-2 focus:ring-blue-500/20"
              >
                <option value={10}>10 pages</option>
                <option value={20}>20 pages</option>
                <option value={30}>30 pages (Default)</option>
                <option value={50}>50 pages (Deep)</option>
              </select>
            </div>
            <div className="sm:col-span-2">
              <Button
                type="submit"
                variant="primary"
                className="w-full"
                isLoading={isStarting}
                disabled={Boolean(activeJobId && !isJobTerminal)}
              >
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                Start Scan
              </Button>
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-100 flex items-start gap-2 text-rose-700 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </form>
      </Card>

      {/* Active Research Job Console */}
      {job && (
        <Card className="p-6 space-y-6 border-2 border-blue-500/20 shadow-lg">
          {/* Progress Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-100">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                  {!isJobTerminal && <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />}
                  {getStageLabel(job.current_stage)}
                </span>
                <Badge
                  variant={
                    job.status.startsWith('completed')
                      ? 'success'
                      : job.status === 'failed'
                      ? 'danger'
                      : job.status === 'cancelled'
                      ? 'warning'
                      : 'info'
                  }
                >
                  {job.status.replace(/_/g, ' ')}
                </Badge>
              </div>
              <p className="text-xs text-slate-500 font-mono truncate">{job.starting_url}</p>
            </div>

            <div className="flex items-center gap-2">
              {!isJobTerminal && (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => setIsCancelModalOpen(true)}
                >
                  <XCircle className="w-3.5 h-3.5 mr-1" />
                  Cancel Crawl Job
                </Button>
              )}

              {(job.status === 'failed' || job.status === 'cancelled') && (
                <Button variant="secondary" size="sm" onClick={() => handleRetryJob(job.id)}>
                  <RotateCcw className="w-3.5 h-3.5 mr-1" />
                  Retry Job
                </Button>
              )}

              {job.status.startsWith('completed') && (
                <Button
                  variant="success"
                  size="sm"
                  onClick={() => navigate(`/reports/${job.id}`)}
                >
                  View Full Report
                  <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              )}
            </div>
          </div>

          {/* Progress Bar */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-slate-500">Job Completion</span>
              <span className="text-blue-600 font-bold">{job.progress_pct}%</span>
            </div>
            <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  job.status === 'failed'
                    ? 'bg-rose-500'
                    : job.status === 'cancelled'
                    ? 'bg-amber-500'
                    : 'bg-gradient-to-r from-blue-600 to-indigo-600'
                }`}
                style={{ width: `${job.progress_pct}%` }}
              />
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 text-center">
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Discovered</span>
              <span className="text-sm font-bold text-slate-900">{job.pages_discovered}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Attempted</span>
              <span className="text-sm font-bold text-slate-900">{job.pages_attempted}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-50/60 border border-emerald-100">
              <span className="text-[10px] uppercase font-bold text-emerald-600 block">Crawled</span>
              <span className="text-sm font-bold text-emerald-700">{job.pages_crawled}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-rose-50/60 border border-rose-100">
              <span className="text-[10px] uppercase font-bold text-rose-600 block">Failed</span>
              <span className="text-sm font-bold text-rose-700">{job.pages_failed}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-indigo-50/60 border border-indigo-100">
              <span className="text-[10px] uppercase font-bold text-indigo-600 block">References</span>
              <span className="text-sm font-bold text-indigo-700">{job.references_found}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Contacts</span>
              <span className="text-sm font-bold text-slate-900">{job.contacts_created}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Companies</span>
              <span className="text-sm font-bold text-slate-900">{job.companies_created}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Leads</span>
              <span className="text-sm font-bold text-slate-900">{job.leads_created}</span>
            </div>
          </div>

          {/* Live Activity Stream (SSE) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-slate-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  Live Execution Logs & Activity Stream
                </h3>
              </div>
              {!isJobTerminal && (
                <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 font-bold">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  Streaming Live Events
                </div>
              )}
            </div>

            <div className="h-60 overflow-y-auto p-3.5 rounded-xl bg-slate-900 text-slate-200 font-mono text-[11px] space-y-1.5 border border-slate-800 shadow-inner">
              {events.length === 0 ? (
                <span className="text-slate-500 italic">Connecting to activity event stream...</span>
              ) : (
                events.map((ev, idx) => {
                  const timeStr = new Date(ev.event_timestamp).toLocaleTimeString();
                  const isErr = ev.severity === 'error';
                  const isWarn = ev.severity === 'warning';
                  const isSucc = ev.severity === 'success';

                  return (
                    <div key={idx} className="flex items-start gap-2 leading-relaxed">
                      <span className="text-slate-500 shrink-0">[{timeStr}]</span>
                      <span
                        className={`font-semibold shrink-0 uppercase text-[9px] px-1 rounded ${
                          isErr
                            ? 'bg-rose-900/60 text-rose-300'
                            : isWarn
                            ? 'bg-amber-900/60 text-amber-300'
                            : isSucc
                            ? 'bg-emerald-900/60 text-emerald-300'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {ev.stage}
                      </span>
                      <span className={isErr ? 'text-rose-400' : isWarn ? 'text-amber-300' : 'text-slate-300'}>
                        {ev.message}
                      </span>
                    </div>
                  );
                })
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        </Card>
      )}

      {/* Historical Jobs Table */}
      <Card className="p-5">
        <h2 className="text-sm font-bold text-slate-800 mb-3.5">Recent Intelligence Scan Jobs</h2>
        {isJobsLoading ? (
          <div className="py-8 flex justify-center">
            <LoadingSpinner message="Loading historical jobs..." />
          </div>
        ) : recentJobs.length === 0 ? (
          <EmptyState
            title="No Research Jobs Yet"
            description="Launch a website intelligence scan to crawl providers, extract client references, and generate verified leads."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-400 uppercase text-[10px] font-bold border-b border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Target URL</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Progress</th>
                  <th className="py-2.5 px-3">Pages</th>
                  <th className="py-2.5 px-3">References</th>
                  <th className="py-2.5 px-3">Leads</th>
                  <th className="py-2.5 px-3">Created</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {recentJobs.map((j) => (
                  <tr key={j.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-3 font-mono font-medium max-w-xs truncate text-slate-900">
                      {j.starting_url}
                    </td>
                    <td className="py-3 px-3">
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
                    </td>
                    <td className="py-3 px-3 font-semibold">{j.progress_pct}%</td>
                    <td className="py-3 px-3">{j.pages_crawled} / {j.pages_discovered}</td>
                    <td className="py-3 px-3 font-semibold text-indigo-700">{j.references_found}</td>
                    <td className="py-3 px-3 font-semibold text-emerald-700">{j.leads_created}</td>
                    <td className="py-3 px-3 text-[11px] text-slate-400">
                      {new Date(j.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-3 text-right space-x-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setActiveJobId(j.id);
                          setJob(j);
                        }}
                      >
                        Inspect
                      </Button>
                      {j.status.startsWith('completed') && (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => navigate(`/reports/${j.id}`)}
                        >
                          Report
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Cancel Confirmation Modal (Part 9) */}
      <ConfirmModal
        isOpen={isCancelModalOpen}
        onClose={() => setIsCancelModalOpen(false)}
        onConfirm={handleConfirmCancel}
        title="Cancel Active Research Job?"
        message="This will immediately stop active background workers, terminate browser rendering, abort pending page fetches, and release worker locks. Any leads, contacts, or references already saved will be preserved."
        confirmLabel="Yes, Cancel Research Job"
        isLoading={isCancelling}
      />
    </div>
  );
};
