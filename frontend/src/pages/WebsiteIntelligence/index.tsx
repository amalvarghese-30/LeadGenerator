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
  ArrowDown,
  Copy,
  Check,
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

  // Terminal scroll & streaming state
  type ConnectionStatus = 'streaming' | 'reconnecting' | 'polling' | 'finished' | 'idle';
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('idle');
  const [unseenCount, setUnseenCount] = useState(0);

  const logContainerRef = useRef<HTMLDivElement | null>(null);
  const isAtBottomRef = useRef(true);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [hasNewLogs, setHasNewLogs] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const lastEventIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const pollRef = useRef<number | null>(null);
  const isPollingRef = useRef(false);
  const scrollRafRef = useRef<number | null>(null);

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

  const handleScroll = () => {
    if (!logContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current;
    // Within 40px of bottom is considered "at bottom"
    const atBottom = scrollHeight - scrollTop - clientHeight <= 40;
    isAtBottomRef.current = atBottom;
    setIsAtBottom(atBottom);
    if (atBottom) {
      setHasNewLogs(false);
      setUnseenCount(0);
    }
  };

  const scrollToBottom = (instant = false) => {
    if (!logContainerRef.current) return;
    if (scrollRafRef.current) {
      cancelAnimationFrame(scrollRafRef.current);
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      if (logContainerRef.current) {
        logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        isAtBottomRef.current = true;
        setIsAtBottom(true);
        setHasNewLogs(false);
        setUnseenCount(0);
      }
    });
  };

  const handleCopyLogs = async () => {
    if (events.length === 0) return;
    const logText = events
      .map((ev) => `[${ev.event_timestamp ? new Date(ev.event_timestamp).toISOString() : ''}] [${ev.severity?.toUpperCase() || 'INFO'}] [${ev.stage || 'GENERAL'}] ${ev.message}`)
      .join('\n');
    try {
      await navigator.clipboard.writeText(logText);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      // ignore clipboard error
    }
  };

  // Set up resilient authenticated stream reader and status polling
  useEffect(() => {
    if (!activeJobId) {
      setConnectionStatus('idle');
      return;
    }

    let isCancelled = false;
    isAtBottomRef.current = true;
    setIsAtBottom(true);
    setHasNewLogs(false);
    setUnseenCount(0);
    reconnectAttemptRef.current = 0;

    // Helper to merge newly fetched events
    const mergeEvents = (newEvents: JobEvent[]) => {
      if (!newEvents || newEvents.length === 0) return;
      setEvents((prev) => {
        const existingIds = new Set(prev.map((p) => p.id).filter(Boolean));
        const additions: JobEvent[] = [];
        for (const ev of newEvents) {
          if (ev.id && existingIds.has(ev.id)) continue;
          if (!ev.id && prev.some((p) => p.event_timestamp === ev.event_timestamp && p.message === ev.message)) continue;
          additions.push(ev);
          if (ev.id) existingIds.add(ev.id);
        }
        if (additions.length === 0) return prev;
        const merged = [...prev, ...additions];
        const last = merged[merged.length - 1];
        if (last && last.id) {
          lastEventIdRef.current = last.id;
        }
        return merged;
      });
    };

    // Authenticated SSE Reader using fetch + ReadableStream
    const startStream = async () => {
      if (isCancelled) return;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const token = localStorage.getItem('token');
        const sinceParam = lastEventIdRef.current ? `?since_id=${encodeURIComponent(lastEventIdRef.current)}` : '';
        const url = `/api/discovery/jobs/${activeJobId}/events/stream${sinceParam}`;

        const headers: Record<string, string> = {
          'Accept': 'text/event-stream',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        if (lastEventIdRef.current) {
          headers['Last-Event-ID'] = lastEventIdRef.current;
        }

        const response = await fetch(url, {
          headers,
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        setConnectionStatus('streaming');
        reconnectAttemptRef.current = 0;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!isCancelled) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          const parsedList: JobEvent[] = [];
          for (const chunk of lines) {
            if (!chunk.trim() || chunk.startsWith(':')) continue; // Heartbeat / comment
            const rawLines = chunk.split('\n');
            let eventData = '';
            let eventType = 'message';
            let eventId = '';

            for (const line of rawLines) {
              if (line.startsWith('id:')) {
                eventId = line.slice(3).trim();
              } else if (line.startsWith('event:')) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                eventData += line.slice(5).trim();
              }
            }

            if (eventType === 'close') {
              setConnectionStatus('finished');
              return;
            }

            if (eventData) {
              try {
                const parsed: JobEvent = JSON.parse(eventData);
                if (eventId && !parsed.id) {
                  parsed.id = eventId;
                }
                parsedList.push(parsed);
                if (['job_completed', 'job_failed', 'job_cancelled'].includes(parsed.event_type)) {
                  setConnectionStatus('finished');
                }
              } catch {
                // Ignore non-json
              }
            }
          }

          if (parsedList.length > 0) {
            mergeEvents(parsedList);
          }
        }
      } catch (err: any) {
        if (isCancelled || controller.signal.aborted) return;
        setConnectionStatus('reconnecting');

        // Catch-up from REST API in case SSE dropped mid-flight
        try {
          const missed = await getJobEvents(activeJobId, { since_id: lastEventIdRef.current || undefined });
          if (missed && missed.length > 0) {
            mergeEvents(missed);
          }
        } catch {
          // ignore
        }

        // Check if job is already terminal before retrying stream
        try {
          const currentJob = await getCrawlJob(activeJobId);
          setJob(currentJob);
          if (['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(currentJob.status)) {
            setConnectionStatus('finished');
            return;
          }
        } catch {
          // ignore
        }

        // Exponential backoff reconnect
        const attempt = reconnectAttemptRef.current;
        reconnectAttemptRef.current += 1;
        const delay = Math.min(1000 * Math.pow(1.5, attempt), 10000);
        reconnectTimerRef.current = window.setTimeout(() => {
          if (!isCancelled) startStream();
        }, delay);
      }
    };

    // Initial historical events load
    const loadInitialEvents = async () => {
      try {
        const past = await getJobEvents(activeJobId, { limit: 1000 });
        if (!isCancelled && past && past.length > 0) {
          mergeEvents(past);
        }
      } catch {
        // ignore
      }
      if (!isCancelled) {
        startStream();
      }
    };

    loadInitialEvents();

    // Concurrent-safe status polling
    const pollStatus = async () => {
      if (isPollingRef.current || isCancelled) return;
      isPollingRef.current = true;
      try {
        const j = await getCrawlJob(activeJobId);
        if (!isCancelled) {
          setJob(j);
          const isTerminal = ['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(j.status);
          if (isTerminal) {
            setConnectionStatus('finished');
            if (pollRef.current) window.clearInterval(pollRef.current);
            pollRef.current = null;
            fetchRecentJobs();
          }
        }
      } catch {
        // ignore
      } finally {
        isPollingRef.current = false;
      }
    };

    pollRef.current = window.setInterval(pollStatus, 2500);
    pollStatus();

    return () => {
      isCancelled = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [activeJobId]);

  // Direct scrollTop auto-scroll via requestAnimationFrame (preserves outer page scroll)
  useEffect(() => {
    if (isAtBottomRef.current) {
      if (scrollRafRef.current) {
        cancelAnimationFrame(scrollRafRef.current);
      }
      scrollRafRef.current = requestAnimationFrame(() => {
        if (logContainerRef.current && isAtBottomRef.current) {
          logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
      });
    } else {
      setHasNewLogs(true);
      setUnseenCount((prev) => prev + 1);
    }
  }, [events]);

  const handleStartResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetUrl.trim()) return;

    setError(null);
    setIsStarting(true);
    setEvents([]);
    setIsAtBottom(true);
    setHasNewLogs(false);

    try {
      const domainName = targetUrl.replace(/https?:\/\//, '').split('/')[0];
      const provider = await createProvider({
        name: domainName,
        website: targetUrl,
        category: 'direct_competitor',
      });
      const providerId = (provider as any).id || (provider as any)._id;

      const createdJob = await startProviderResearch(providerId, pageLimit);
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
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      lastEventIdRef.current = null;
      await retryCrawlJob(id);
      setEvents([]);
      setIsAtBottom(true);
      setHasNewLogs(false);
      if (activeJobId === id) {
        setJob((prev) => prev ? { ...prev, status: 'pending', current_stage: 'queued', progress_pct: 0 } : null);
        setActiveJobId(null);
        setTimeout(() => setActiveJobId(id), 50);
      } else {
        setActiveJobId(id);
      }
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
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-slate-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  Live Execution Logs & Activity Stream
                </h3>
                <span className="text-[11px] text-slate-400 font-mono">
                  ({events.length} {events.length === 1 ? 'event' : 'events'})
                </span>
              </div>

              <div className="flex items-center gap-2">
                {connectionStatus === 'streaming' ? (
                  <div className="flex items-center gap-1.5 text-[10px] text-emerald-600 font-bold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
                    Streaming Live Events
                  </div>
                ) : connectionStatus === 'reconnecting' ? (
                  <div className="flex items-center gap-1.5 text-[10px] text-amber-600 font-bold bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                    <Loader2 className="w-3 h-3 animate-spin text-amber-600" />
                    Reconnecting Stream...
                  </div>
                ) : connectionStatus === 'polling' ? (
                  <div className="flex items-center gap-1.5 text-[10px] text-blue-600 font-semibold bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                    <Activity className="w-3 h-3 text-blue-500" />
                    Live Polling
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-semibold bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
                    <CheckCircle2 className="w-3 h-3 text-slate-400" />
                    Stream Finished
                  </div>
                )}

                {events.length > 0 && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-[11px] text-slate-600 hover:text-slate-900 flex items-center gap-1"
                    onClick={handleCopyLogs}
                    title="Copy execution logs to clipboard"
                  >
                    {isCopied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{isCopied ? 'Copied' : 'Copy'}</span>
                  </Button>
                )}

                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-[11px] text-slate-600 hover:text-slate-900 flex items-center gap-1"
                  onClick={() => scrollToBottom(true)}
                  title="Scroll to latest log entry"
                >
                  <ArrowDown className="w-3 h-3" />
                  <span>Jump to latest</span>
                </Button>
              </div>
            </div>

            <div className="relative">
              <div
                ref={logContainerRef}
                onScroll={handleScroll}
                className="h-72 sm:h-80 md:h-96 max-h-[440px] overflow-y-auto overscroll-contain p-3.5 rounded-xl bg-slate-900 text-slate-200 font-mono text-[11px] space-y-1.5 border border-slate-800 shadow-inner select-text"
              >
                {events.length === 0 ? (
                  <div className="text-slate-500 italic py-2">
                    {activeJobId ? 'Waiting for crawl engine execution logs...' : 'Select or start a job to inspect logs.'}
                  </div>
                ) : (
                  events.map((ev, idx) => {
                    const timeStr = ev.event_timestamp ? new Date(ev.event_timestamp).toLocaleTimeString() : '--:--:--';
                    const isErr = ev.severity === 'error';
                    const isWarn = ev.severity === 'warning';
                    const isSucc = ev.severity === 'success';

                    return (
                      <div key={ev.id || `${ev.event_timestamp}-${idx}`} className="flex items-start gap-2 leading-relaxed">
                        <span className="text-slate-500 shrink-0 select-none">[{timeStr}]</span>
                        <span
                          className={`font-semibold shrink-0 uppercase text-[9px] px-1 rounded select-none ${
                            isErr
                              ? 'bg-rose-900/60 text-rose-300'
                              : isWarn
                              ? 'bg-amber-900/60 text-amber-300'
                              : isSucc
                              ? 'bg-emerald-900/60 text-emerald-300'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          {ev.stage || 'info'}
                        </span>
                        <span className={`break-all ${isErr ? 'text-rose-400 font-medium' : isWarn ? 'text-amber-300' : isSucc ? 'text-emerald-300' : 'text-slate-300'}`}>
                          {ev.message}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Floating "New logs available" pill */}
              {hasNewLogs && !isAtBottom && (
                <button
                  type="button"
                  onClick={() => scrollToBottom(true)}
                  className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] font-semibold shadow-lg shadow-black/50 border border-indigo-400/40 transition-all cursor-pointer z-10 animate-bounce"
                >
                  <ArrowDown className="w-3.5 h-3.5" />
                  <span>New logs available {unseenCount > 0 ? `(${unseenCount})` : ''}</span>
                </button>
              )}
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
