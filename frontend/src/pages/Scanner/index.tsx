import React, { useState, useEffect, useRef } from 'react';
import {
  Radar,
  Sparkles,
  ExternalLink,
  Loader2,
  AlertCircle,
  ChevronRight,
  ShieldAlert,
  RotateCcw,
  Terminal,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Radio,
  ArrowDown,
  Copy,
  Check,
  Building2,
  User,
  Mail,
  Phone,
  Download,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import {
  LinkedinIcon,
  InstagramIcon,
  TwitterIcon,
  FacebookIcon,
  YoutubeIcon,
} from '../../components/ui/SocialIcons';
import { createProvider, startProviderResearch } from '../../services/providers';
import {
  getCrawlJob,
  getCrawlJobs,
  cancelCrawlJob,
  retryCrawlJob,
  getJobEvents,
  getJobResults,
  getJobEventsStreamUrl,
  ScanResultItem,
} from '../../services/discovery';
import { CrawlJob, JobEvent } from '../../types';

export const Scanner: React.FC = () => {
  // Input bar state
  const [targetUrl, setTargetUrl] = useState('https://theperson.in/');
  const [pageLimit, setPageLimit] = useState(50);
  const [isCustomLimit, setIsCustomLimit] = useState(false);
  const [customLimitInput, setCustomLimitInput] = useState('');
  const [limitError, setLimitError] = useState<string | null>(null);
  const [isDeepScan, setIsDeepScan] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCustomLimitChange = (val: string) => {
    setCustomLimitInput(val);
    const num = parseInt(val, 10);
    if (!val || isNaN(num) || num < 1 || num > 500) {
      setLimitError('Page limit must be between 1 and 500');
    } else {
      setLimitError(null);
      setPageLimit(num);
    }
  };

  // Active Job & Results
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [job, setJob] = useState<CrawlJob | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [results, setResults] = useState<ScanResultItem[]>([]);
  const [isResultsLoading, setIsResultsLoading] = useState(false);
  const [tableFilter, setTableFilter] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  const handleCopyChannel = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(key);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // UI state: Collapsible panels
  const [isTerminalExpanded, setIsTerminalExpanded] = useState(true);
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
      const res = await getCrawlJobs({ page: 1, page_size: 8 });
      setRecentJobs(res.items);
      // Auto-select latest running or completed job if none active
      if (!activeJobId && res.items.length > 0) {
        const latest = res.items[0];
        setActiveJobId(latest.id);
        setJob(latest);
      }
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
    const atBottom = scrollHeight - scrollTop - clientHeight <= 40;
    isAtBottomRef.current = atBottom;
    setIsAtBottom(atBottom);
    if (atBottom) {
      setHasNewLogs(false);
      setUnseenCount(0);
    }
  };

  const scrollToBottom = () => {
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
      .map(
        (ev) =>
          `[${ev.event_timestamp ? new Date(ev.event_timestamp).toISOString() : ''}] [${
            ev.severity?.toUpperCase() || 'INFO'
          }] [${ev.stage || 'GENERAL'}] ${ev.message}`
      )
      .join('\n');
    try {
      await navigator.clipboard.writeText(logText);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  // Fetch job results
  const fetchJobResults = async (jobId: string) => {
    setIsResultsLoading(true);
    try {
      const res = await getJobResults(jobId);
      setResults(res.results || []);
    } catch (err) {
      console.error('Failed to fetch scan results:', err);
    } finally {
      setIsResultsLoading(false);
    }
  };

  useEffect(() => {
    if (activeJobId) {
      fetchJobResults(activeJobId);
    }
  }, [activeJobId]);

  // Set up resilient stream reader and status polling
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

    const stopPolling = () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };

    const mergeEvents = (newEvents: JobEvent[]) => {
      if (!newEvents || newEvents.length === 0) return;
      setEvents((prev) => {
        const existingIds = new Set(prev.map((p) => p.id).filter(Boolean));
        const additions: JobEvent[] = [];
        for (const ev of newEvents) {
          if (ev.id && existingIds.has(ev.id)) continue;
          if (!ev.id && prev.some((p) => p.event_timestamp === ev.event_timestamp && p.message === ev.message))
            continue;
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

    const startStream = async () => {
      if (isCancelled) return;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      setConnectionStatus('streaming');

      try {
        const token = localStorage.getItem('leadintel_token');
        const url = `${getJobEventsStreamUrl(activeJobId)}${
          lastEventIdRef.current ? `?since_id=${lastEventIdRef.current}` : ''
        }`;

        const response = await fetch(url, {
          headers: {
            Accept: 'text/event-stream',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error(`SSE stream connection failed: HTTP ${response.status}`);
        }

        reconnectAttemptRef.current = 0;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!isCancelled) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split('\n\n');
          buffer = messages.pop() || '';

          const batchEvents: JobEvent[] = [];
          for (const msg of messages) {
            if (!msg.trim() || msg.startsWith(':')) continue;
            let eventData = '';
            let currentEventId: string | null = null;
            let currentEventType = 'message';

            const lines = msg.split('\n');
            for (const line of lines) {
              if (line.startsWith('id:')) currentEventId = line.substring(3).trim();
              else if (line.startsWith('event:')) currentEventType = line.substring(6).trim();
              else if (line.startsWith('data:')) eventData = line.substring(5).trim();
            }

            if (currentEventType === 'close') {
              setConnectionStatus('finished');
              stopPolling();
              fetchRecentJobs();
              fetchJobResults(activeJobId);
              return;
            }

            if (eventData) {
              try {
                const parsed = JSON.parse(eventData);
                if (currentEventId && !parsed.id) parsed.id = currentEventId;
                batchEvents.push(parsed);
                if (['job_completed', 'job_failed', 'job_cancelled'].includes(parsed.event_type)) {
                  setConnectionStatus('finished');
                  stopPolling();
                  fetchRecentJobs();
                  fetchJobResults(activeJobId);
                }
              } catch {
                // ignore malformed line
              }
            }
          }

          if (batchEvents.length > 0) {
            mergeEvents(batchEvents);
          }
        }
      } catch (err: any) {
        if (isCancelled || err.name === 'AbortError') return;
        setConnectionStatus('reconnecting');
        reconnectAttemptRef.current += 1;
        const delay = Math.min(1000 * Math.pow(1.5, reconnectAttemptRef.current), 10000);
        reconnectTimerRef.current = window.setTimeout(() => {
          if (!isCancelled) startStream();
        }, delay);
      }
    };

    const pollJobStatus = async () => {
      if (isCancelled || isPollingRef.current) return;
      isPollingRef.current = true;
      try {
        const updated = await getCrawlJob(activeJobId);
        if (!isCancelled) {
          setJob(updated);
          if (
            ['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(updated.status)
          ) {
            setConnectionStatus('finished');
            stopPolling();
            fetchJobResults(activeJobId);
            fetchRecentJobs();
          }
        }
      } catch {
        // ignore polling error
      } finally {
        isPollingRef.current = false;
      }
    };

    getCrawlJob(activeJobId)
      .then((initialJob) => {
        if (!isCancelled) {
          setJob(initialJob);
          getJobEvents(activeJobId, { limit: 200 })
            .then((res: any) => {
              if (!isCancelled && res.events) {
                mergeEvents(res.events);
                setTimeout(() => scrollToBottom(), 50);
              }
            })
            .catch(() => {});

          const isTerminal = ['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(
            initialJob.status
          );

          if (!isTerminal) {
            startStream();
            if (!pollRef.current) {
              pollRef.current = window.setInterval(pollJobStatus, 3000);
            }
          } else {
            setConnectionStatus('finished');
            stopPolling();
          }
        }
      })
      .catch(() => {});

    return () => {
      isCancelled = true;
      if (abortControllerRef.current) abortControllerRef.current.abort();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      stopPolling();
      if (scrollRafRef.current) cancelAnimationFrame(scrollRafRef.current);
    };
  }, [activeJobId]);

  // Maintain scroll lock
  useEffect(() => {
    if (isAtBottomRef.current) {
      scrollToBottom();
    } else {
      setHasNewLogs(true);
      setUnseenCount((prev) => prev + 1);
    }
  }, [events]);

  // Start new competitor scan
  const handleStartScan = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    let cleanUrl = targetUrl.trim();
    if (!cleanUrl) {
      setError('Please provide a valid competitor website URL');
      return;
    }
    if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
      cleanUrl = `https://${cleanUrl}`;
    }

    try {
      new URL(cleanUrl);
    } catch {
      setError('Invalid URL format. Please include a domain (e.g., https://competitor.com)');
      return;
    }

    if (isCustomLimit) {
      const num = parseInt(customLimitInput, 10);
      if (isNaN(num) || num < 1 || num > 500) {
        setError('Page crawl limit must be an integer between 1 and 500.');
        return;
      }
    } else if (!pageLimit || pageLimit < 1 || pageLimit > 500) {
      setError('Page crawl limit must be between 1 and 500.');
      return;
    }

    setIsStarting(true);
    setEvents([]);
    setResults([]);
    lastEventIdRef.current = null;

    try {
      const hostname = new URL(cleanUrl).hostname.replace(/^www\./, '');
      const providerName = hostname
        .split('.')[0]
        .replace(/[-_]/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());

      const provider = await createProvider({
        name: providerName,
        website: cleanUrl,
        category: 'direct_competitor',
      });

      const initiatedJob = await startProviderResearch(
        provider.id,
        pageLimit,
        isDeepScan ? 'full_research' : 'full_research'
      );
      setActiveJobId(initiatedJob.id);
      setJob(initiatedJob);
      setIsTerminalExpanded(true);
      fetchRecentJobs();
    } catch (err: any) {
      console.error('Scan startup failed:', err);
      setError(
        err.response?.data?.detail || err.message || 'Failed to start competitor intelligence scan.'
      );
    } finally {
      setIsStarting(false);
    }
  };

  const handleCancelConfirm = async () => {
    if (!activeJobId) return;
    setIsCancelling(true);
    try {
      await cancelCrawlJob(activeJobId);
      setIsCancelModalOpen(false);
      setJob((prev) => (prev ? { ...prev, status: 'cancelled' } : null));
      setConnectionStatus('finished');
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      fetchRecentJobs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to cancel scan.');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    try {
      await retryCrawlJob(jobId);
      if (activeJobId === jobId) {
        setJob((prev) =>
          prev ? { ...prev, status: 'pending', current_stage: 'queued', progress_pct: 0 } : null
        );
        setActiveJobId(null);
        setTimeout(() => setActiveJobId(jobId), 50);
      } else {
        setActiveJobId(jobId);
      }
      setEvents([]);
      lastEventIdRef.current = null;
      fetchRecentJobs();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to retry job.');
    }
  };

  // Determine current active step in progress stepper
  const getActiveStep = () => {
    if (!job) return 0;
    const stage = job.current_stage?.toLowerCase() || '';
    if (stage.includes('rate') || stage === 'startup' || stage === 'queued') return 1;
    if (stage.includes('discover') || stage.includes('crawl')) return 2;
    if (stage.includes('extract') || stage.includes('page')) return 3;
    if (stage.includes('enrich') || stage.includes('contact') || stage === 'completed') return 4;
    return 1;
  };

  // Filter results for the table
  const filteredResults = results.filter((item) => {
    if (!tableFilter) return true;
    const q = tableFilter.toLowerCase();
    return (
      item.company_name?.toLowerCase().includes(q) ||
      item.person_name?.toLowerCase().includes(q) ||
      item.designation?.toLowerCase().includes(q) ||
      item.contacts?.email?.toLowerCase().includes(q) ||
      item.evidence_quote?.toLowerCase().includes(q)
    );
  });

  // Export CSV
  const handleExportCSV = () => {
    if (filteredResults.length === 0) return;
    const headers = [
      'Company Name',
      'Website',
      'Industry',
      'Decision Maker',
      'Title',
      'Email',
      'Phone',
      'LinkedIn',
      'Contact Forms',
      'All Channels',
      'Confidence',
      'Relationship Type',
      'Source URL',
      'Evidence Quote',
    ];
    const rows = filteredResults.map((r) => {
      const forms = (r.contacts?.channels || []).filter((c: any) => c.type === 'contact_form').map((c: any) => c.value).join('; ');
      const allCh = (r.contacts?.channels || []).map((c: any) => `${c.type}: ${c.value}`).join('; ');
      return [
        `"${(r.company_name || '').replace(/"/g, '""')}"`,
        `"${(r.company_website || '').replace(/"/g, '""')}"`,
        `"${(r.industry || '').replace(/"/g, '""')}"`,
        `"${(r.person_name || '').replace(/"/g, '""')}"`,
        `"${(r.designation || '').replace(/"/g, '""')}"`,
        `"${(r.contacts?.email || '').replace(/"/g, '""')}"`,
        `"${(r.contacts?.phone || '').replace(/"/g, '""')}"`,
        `"${(r.contacts?.linkedin || '').replace(/"/g, '""')}"`,
        `"${(forms || '').replace(/"/g, '""')}"`,
        `"${(allCh || '').replace(/"/g, '""')}"`,
        r.confidence,
        `"${r.relationship_type}"`,
        `"${(r.source_url || '').replace(/"/g, '""')}"`,
        `"${(r.evidence_quote || '').replace(/"/g, '""')}"`,
      ];
    });
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `competitor_clients_${job?.id || 'scan'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. HERO SCANNER INPUT BAR */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="max-w-3xl space-y-2 mb-6">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-cyan-950 text-cyan-400 border border-cyan-800">
              Stealth Crawler & Rate-Limit Engine
            </span>
            <span className="text-xs text-slate-400">v2.5 Production</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Competitor Client Finder & Contact Intelligence
          </h1>
          <p className="text-sm text-slate-300">
            Scan competitor agencies and consultancies to uncover their published client case studies,
            portfolio references, and verified decision-maker emails.
          </p>
        </div>

        <form onSubmit={handleStartScan} className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Radar className="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="https://competitor-agency.com"
                disabled={isStarting}
                className="w-full bg-slate-950 border border-slate-700 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 rounded-xl pl-11 pr-4 py-3.5 text-sm text-white placeholder-slate-500 font-mono transition-all"
              />
            </div>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              <div
                className="flex items-center gap-1.5 bg-slate-950 border border-slate-700 rounded-xl px-3 py-2"
                title="Maximum number of eligible pages the crawler will process (1 - 500)."
              >
                <span className="text-[11px] font-semibold text-slate-400 pl-1 hidden md:inline">Limit:</span>
                <select
                  value={isCustomLimit ? 'custom' : pageLimit}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === 'custom') {
                      setIsCustomLimit(true);
                      setCustomLimitInput(String(pageLimit));
                    } else {
                      setIsCustomLimit(false);
                      setPageLimit(Number(val));
                      setLimitError(null);
                    }
                  }}
                  disabled={isStarting}
                  className="bg-transparent text-slate-200 text-xs font-semibold focus:outline-none cursor-pointer py-1 pr-1"
                >
                  <option value={15} className="bg-slate-900 text-slate-200">15 Pages</option>
                  <option value={30} className="bg-slate-900 text-slate-200">30 Pages</option>
                  <option value={50} className="bg-slate-900 text-slate-200">50 Pages (Default)</option>
                  <option value={100} className="bg-slate-900 text-slate-200">100 Pages</option>
                  <option value={200} className="bg-slate-900 text-slate-200">200 Pages</option>
                  <option value="custom" className="bg-slate-900 text-slate-200">Custom (1-500)...</option>
                </select>

                {isCustomLimit && (
                  <div className="flex items-center gap-1 border-l border-slate-700 pl-2">
                    <input
                      type="number"
                      min={1}
                      max={500}
                      value={customLimitInput}
                      onChange={(e) => handleCustomLimitChange(e.target.value)}
                      placeholder="1-500"
                      disabled={isStarting}
                      className="w-16 bg-slate-900 border border-slate-600 focus:border-cyan-500 rounded px-2 py-1 text-xs text-white font-mono outline-none"
                    />
                    <span className="text-[11px] text-slate-400">pg</span>
                  </div>
                )}
              </div>

              <button
                type="submit"
                disabled={isStarting || Boolean(limitError)}
                className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold px-6 py-3.5 rounded-xl text-sm transition-all shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2 shrink-0 cursor-pointer disabled:opacity-50"
              >
                {isStarting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Initiating...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Scan Competitor</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Scan Options Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-1 text-xs text-slate-400">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={isDeepScan}
                onChange={(e) => setIsDeepScan(e.target.checked)}
                className="rounded border-slate-700 text-cyan-500 focus:ring-cyan-500 bg-slate-950"
              />
              <span className="text-slate-300 font-medium">
                Deep Stealth Mode (Headless browser rendering for SPAs & Cloudflare bypass)
              </span>
            </label>

            <div className="flex items-center gap-4 text-[11px] font-mono text-slate-400">
              <span>Adaptive Jitter: 0.5s - 2.5s</span>
              <span>•</span>
              <span>Strict Relationship Attribution</span>
              <span>•</span>
              <span>Zero Mock Leaks</span>
            </div>
          </div>
        </form>

        {error && (
          <div className="mt-4 p-3.5 bg-red-950/60 border border-red-800 rounded-xl flex items-center gap-3 text-red-200 text-xs">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </section>

      {/* 2. PROGRESS STEPPER (Active when job is loaded) */}
      {job && (
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-4 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <Activity className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                Execution Pipeline
              </span>
              <span className="font-mono text-xs text-slate-400">ID: {job.id.slice(-8)}</span>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 rounded text-[11px] font-mono uppercase font-bold ${
                  job.status === 'completed' || job.status === 'completed_with_warnings'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    : job.status === 'running'
                    ? 'bg-cyan-950 text-cyan-400 border border-cyan-800 animate-pulse'
                    : job.status === 'failed'
                    ? 'bg-red-950 text-red-400 border border-red-800'
                    : 'bg-slate-800 text-slate-300'
                }`}
              >
                {job.status.replace(/_/g, ' ')}
              </span>

              {['pending', 'running'].includes(job.status) && (
                <button
                  onClick={() => setIsCancelModalOpen(true)}
                  className="px-2.5 py-1 text-xs font-semibold text-red-400 hover:text-red-300 hover:bg-red-950/40 border border-red-900/40 rounded-lg transition-colors"
                >
                  Cancel Scan
                </button>
              )}
            </div>
          </div>

          {/* Stepper Steps */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            {[
              {
                step: 1,
                title: 'Rate Limit Profiler',
                desc: 'Domain pacing & burst probing',
              },
              {
                step: 2,
                title: 'Waterfall Discovery',
                desc: 'Sitemaps, RSS & Internal Crawl',
              },
              {
                step: 3,
                title: 'Client Extraction',
                desc: 'Evidence quotes & case studies',
              },
              {
                step: 4,
                title: 'Contact Enrichment',
                desc: 'Domain emails & decision makers',
              },
            ].map(({ step, title, desc }) => {
              const activeStep = getActiveStep();
              const isPast = activeStep > step || job.status === 'completed';
              const isCurrent = activeStep === step && job.status === 'running';

              return (
                <div
                  key={step}
                  className={`p-3 rounded-lg border transition-all ${
                    isCurrent
                      ? 'bg-cyan-950/40 border-cyan-500/80 shadow-md shadow-cyan-500/10'
                      : isPast
                      ? 'bg-slate-950 border-slate-800 text-slate-300'
                      : 'bg-slate-950/40 border-slate-900 text-slate-400 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center font-mono text-[10px] font-bold ${
                        isCurrent
                          ? 'bg-cyan-500 text-slate-950'
                          : isPast
                          ? 'bg-emerald-600 text-white'
                          : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {isPast ? '✓' : step}
                    </span>
                    <span className="font-bold text-slate-200 truncate">{title}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-tight">{desc}</p>
                </div>
              );
            })}
          </div>

          {/* Crawler Pipeline Breakdown & Live Progress */}
          <div className="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2 text-center">
            <div className="p-2 rounded-lg bg-slate-950/80 border border-slate-800">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Target Limit</span>
              <span className="text-xs font-mono font-bold text-cyan-400">{job.max_pages ?? 50}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-950/80 border border-slate-800">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Discovered</span>
              <span className="text-xs font-mono font-bold text-slate-200">{job.pages_discovered ?? 0}</span>
            </div>
            <div className="p-2 rounded-lg bg-slate-950/80 border border-slate-800">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Attempted</span>
              <span className="text-xs font-mono font-bold text-slate-200">{job.pages_attempted ?? 0}</span>
            </div>
            <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-900/40">
              <span className="text-[10px] uppercase font-bold text-emerald-400 block">Crawled</span>
              <span className="text-xs font-mono font-bold text-emerald-300">{job.pages_crawled ?? 0}</span>
            </div>
            <div className="p-2 rounded-lg bg-amber-950/40 border border-amber-900/40">
              <span className="text-[10px] uppercase font-bold text-amber-400 block">Skipped</span>
              <span className="text-xs font-mono font-bold text-amber-300">{job.pages_skipped ?? 0}</span>
            </div>
            <div className="p-2 rounded-lg bg-rose-950/40 border border-rose-900/40">
              <span className="text-[10px] uppercase font-bold text-rose-400 block">Failed</span>
              <span className="text-xs font-mono font-bold text-rose-300">{job.pages_failed ?? 0}</span>
            </div>
            <div className="p-2 rounded-lg bg-indigo-950/40 border border-indigo-900/40 col-span-2 sm:col-span-1">
              <span className="text-[10px] uppercase font-bold text-indigo-400 block">Analysed</span>
              <span className="text-xs font-mono font-bold text-indigo-300">{job.pages_analysed ?? job.pages_crawled ?? 0}</span>
            </div>
          </div>
        </section>
      )}

      {/* 3. COLLAPSIBLE TERMINAL LOG STREAM */}
      {job && (
        <section className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
          <div className="bg-slate-900 px-4 py-2.5 flex items-center justify-between border-b border-slate-800">
            <div className="flex items-center gap-3">
              <Terminal className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-mono font-bold text-slate-200">
                Live Execution Logs & Activity Stream
              </span>
              <span className="text-[11px] font-mono text-slate-400">({events.length} events)</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleCopyLogs}
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded text-xs flex items-center gap-1 transition-colors"
                title="Copy all logs"
              >
                {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline text-[11px]">Copy</span>
              </button>

              <button
                onClick={() => setIsTerminalExpanded(!isTerminalExpanded)}
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded text-xs flex items-center gap-1 transition-colors"
                title={isTerminalExpanded ? 'Collapse Terminal' : 'Expand Terminal'}
              >
                {isTerminalExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {isTerminalExpanded && (
            <div className="relative">
              <div
                ref={logContainerRef}
                onScroll={handleScroll}
                className="h-64 sm:h-72 overflow-y-auto p-4 font-mono text-xs leading-relaxed space-y-1.5 bg-slate-950 text-slate-300"
              >
                {events.length === 0 ? (
                  <div className="h-full flex items-center justify-center text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Waiting for background crawler stream events...
                  </div>
                ) : (
                  events.map((ev, idx) => {
                    const isError = ev.severity === 'error';
                    const isWarn = ev.severity === 'warning';
                    const isSuccess = ev.severity === 'success';

                    return (
                      <div
                        key={ev.id || idx}
                        className={`flex items-start gap-2 text-[11px] ${
                          isError
                            ? 'text-red-400 bg-red-950/20'
                            : isWarn
                            ? 'text-amber-400 bg-amber-950/20'
                            : isSuccess
                            ? 'text-emerald-400'
                            : 'text-slate-300'
                        }`}
                      >
                        <span className="text-slate-400 shrink-0 select-none">
                          {ev.event_timestamp ? new Date(ev.event_timestamp).toLocaleTimeString() : '00:00:00'}
                        </span>
                        <span
                          className={`font-bold px-1 rounded text-[10px] shrink-0 uppercase ${
                            isError
                              ? 'bg-red-950 text-red-400 border border-red-800'
                              : isWarn
                              ? 'bg-amber-950 text-amber-400 border border-amber-800'
                              : isSuccess
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          {ev.stage || 'EXEC'}
                        </span>
                        <span className="break-all">{ev.message}</span>
                      </div>
                    );
                  })
                )}
              </div>

              {hasNewLogs && !isAtBottom && (
                <button
                  onClick={scrollToBottom}
                  className="absolute bottom-3 right-4 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-lg flex items-center gap-1.5 animate-bounce transition-all"
                >
                  <ArrowDown className="w-3.5 h-3.5" />
                  <span>{unseenCount} new logs</span>
                </button>
              )}
            </div>
          )}
        </section>
      )}

      {/* 4. INSTANT RESULTS TABLE DIRECTLY BELOW SCANNER */}
      <section className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-cyan-400" />
              <h2 className="text-lg font-bold text-white">
                Discovered Clients & Verified Contacts
              </h2>
              <span className="px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 text-xs font-mono font-bold">
                {results.length} Found
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Authentic customer relationships extracted from published case studies, testimonials, and portfolios.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Filter results..."
                value={tableFilter}
                onChange={(e) => setTableFilter(e.target.value)}
                className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg pl-8 pr-3 py-1.5 focus:border-cyan-500 outline-none w-44 sm:w-56"
              />
            </div>

            <button
              onClick={handleExportCSV}
              disabled={filteredResults.length === 0}
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-700 flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-40"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export CSV</span>
            </button>
          </div>
        </div>

        {/* Results Table */}
        <div className="overflow-x-auto">
          {isResultsLoading ? (
            <div className="py-12 flex justify-center">
              <LoadingSpinner message="Loading discovered intelligence records..." />
            </div>
          ) : filteredResults.length === 0 ? (
            <div className="py-12 text-center text-slate-400 space-y-2">
              <Building2 className="w-10 h-10 mx-auto text-slate-700" />
              {job && ['running', 'pending'].includes(job.status) ? (
                <>
                  <p className="text-sm font-semibold text-cyan-400 animate-pulse">Scan in progress...</p>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    Currently scanning pages and extracting customer references. Results will appear here once extracted.
                  </p>
                </>
              ) : job && ['completed', 'completed_with_warnings'].includes(job.status) ? (
                <>
                  <p className="text-sm font-semibold text-slate-300">No client records discovered</p>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    The scan finished, but no explicit customer case studies or client references were identified on this domain. Try running a scan with Deep Stealth enabled or scanning another URL.
                  </p>
                </>
              ) : job && job.status === 'failed' ? (
                <>
                  <p className="text-sm font-semibold text-red-400">Scan failed</p>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    The scan encountered errors. Inspect the execution logs above or retry the job.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-semibold text-slate-300">No client records discovered yet</p>
                  <p className="text-xs text-slate-400 max-w-sm mx-auto">
                    Trigger a scan above using a valid agency or service provider URL to discover their client portfolio.
                  </p>
                </>
              )}
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-mono text-[11px] uppercase bg-slate-950/60">
                  <th className="py-3 px-4">Client Company</th>
                  <th className="py-3 px-4">Relationship & Evidence</th>
                  <th className="py-3 px-4">Key Decision Maker</th>
                  <th className="py-3 px-4">Verified Channels</th>
                  <th className="py-3 px-4 text-right">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredResults.map((item) => (
                  <React.Fragment key={item.id}>
                    <tr className="hover:bg-slate-800/40 transition-colors">
                      {/* Client Company */}
                    <td className="py-3 px-4 align-top">
                      <div className="font-bold text-white text-sm">
                        {item.company_name || 'Individual / Private Client'}
                      </div>
                      {item.website || item.company_website ? (
                        <a
                          href={item.website || item.company_website!}
                          target="_blank"
                          rel="noreferrer"
                          className="text-cyan-400 hover:underline flex items-center gap-1 text-[11px] mt-0.5"
                        >
                          <span className="truncate max-w-[170px]">
                            {(item.website || item.company_website)?.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                          </span>
                          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                        </a>
                      ) : (
                        <span className="text-slate-400 text-[11px]">Domain not published</span>
                      )}
                      {item.industry && (
                        <div className="text-[10px] text-slate-400 mt-1 uppercase tracking-wider font-mono">
                          {item.industry}
                        </div>
                      )}
                    </td>

                    {/* Relationship & Evidence */}
                    <td className="py-3 px-4 align-top max-w-xs">
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700 mb-1.5">
                        {item.relationship_type.replace(/_/g, ' ')}
                      </span>
                      {item.evidence_quote ? (
                        <p className="text-slate-300 text-xs italic line-clamp-2">
                          "{item.evidence_quote}"
                        </p>
                      ) : (
                        <span className="text-slate-400 text-xs">Direct reference quote</span>
                      )}
                      {item.source_url && (
                        <a
                          href={item.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-cyan-500 hover:text-cyan-400 text-[10px] flex items-center gap-1 mt-1 font-mono truncate max-w-xs"
                        >
                          <span>Source URL</span>
                          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                        </a>
                      )}
                    </td>

                    {/* Decision Maker */}
                    <td className="py-3 px-4 align-top">
                      {item.person_name ? (
                        <>
                          <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                            <User className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                            <span>{item.person_name}</span>
                          </div>
                          <div className="text-slate-400 text-[11px] mt-0.5">
                            {item.designation || 'Key Decision Maker'}
                          </div>
                        </>
                      ) : (
                        <div>
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700/60 inline-flex items-center gap-1">
                            <Building2 className="w-3 h-3 text-cyan-400" />
                            Company Target
                          </span>
                          <div className="text-slate-500 text-[10px] mt-0.5 italic">
                            Verified business channels
                          </div>
                        </div>
                      )}
                    </td>

                    {/* Verified Channels */}
                    <td className="py-3 px-4 align-top">
                      <div className="space-y-1.5">
                        {/* Email display with copy button and +N badge */}
                        {item.contacts?.email || (item.emails && item.emails.length > 0) || (item.contacts?.emails && item.contacts.emails.length > 0) ? (
                          (() => {
                            const allEmails = item.emails || item.contacts?.emails || (item.contacts?.email ? [item.contacts.email] : []);
                            const primaryEmail = allEmails[0] || item.contacts?.email;
                            return (
                              <div className="flex items-center gap-1.5 group flex-wrap">
                                <div className="flex items-center gap-1 text-emerald-400 font-mono text-[11px]">
                                  <Mail className="w-3 h-3 shrink-0" />
                                  <span className="truncate max-w-[160px]">{primaryEmail}</span>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handleCopyChannel(`email-${item.id}`, primaryEmail!)}
                                  className="text-slate-500 hover:text-slate-200 transition-colors p-0.5 rounded cursor-pointer"
                                  title="Copy email"
                                >
                                  {copiedId === `email-${item.id}` ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                </button>
                                {allEmails.length > 1 && (
                                  <span
                                    className="px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-mono font-bold"
                                    title={allEmails.join(', ')}
                                  >
                                    +{allEmails.length - 1}
                                  </span>
                                )}
                              </div>
                            );
                          })()
                        ) : null}

                        {/* Phone display with copy button and +N badge */}
                        {item.contacts?.phone || (item.phones && item.phones.length > 0) || (item.contacts?.phones && item.contacts.phones.length > 0) ? (
                          (() => {
                            const allPhones = item.phones || item.contacts?.phones || (item.contacts?.phone ? [item.contacts.phone] : []);
                            const primaryPhone = allPhones[0] || item.contacts?.phone;
                            return (
                              <div className="flex items-center gap-1.5 group flex-wrap">
                                <div className="flex items-center gap-1 text-slate-300 font-mono text-[11px]">
                                  <Phone className="w-3 h-3 shrink-0" />
                                  <span>{primaryPhone}</span>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => handleCopyChannel(`phone-${item.id}`, primaryPhone!)}
                                  className="text-slate-500 hover:text-slate-200 transition-colors p-0.5 rounded cursor-pointer"
                                  title="Copy phone"
                                >
                                  {copiedId === `phone-${item.id}` ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                </button>
                                {allPhones.length > 1 && (
                                  <span
                                    className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-mono font-bold"
                                    title={allPhones.join(', ')}
                                  >
                                    +{allPhones.length - 1}
                                  </span>
                                )}
                              </div>
                            );
                          })()
                        ) : null}

                        {/* Social Media Icon Pills */}
                        {(() => {
                          const soc = item.socials || item.contacts?.socials || {};
                          const linkedinUrl = soc.linkedin || item.contacts?.linkedin;
                          const instagramUrl = soc.instagram;
                          const facebookUrl = soc.facebook;
                          const twitterUrl = soc.twitter;
                          const youtubeUrl = soc.youtube;
                          const hasSocials = linkedinUrl || instagramUrl || facebookUrl || twitterUrl || youtubeUrl;

                          if (!hasSocials) return null;

                          return (
                            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                              {linkedinUrl && (
                                <a
                                  href={linkedinUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="p-1 rounded bg-slate-900 border border-slate-800 text-cyan-400 hover:text-cyan-300 hover:border-cyan-700 transition-colors"
                                  title="LinkedIn"
                                >
                                  <LinkedinIcon className="w-3 h-3" />
                                </a>
                              )}
                              {instagramUrl && (
                                <a
                                  href={instagramUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="p-1 rounded bg-slate-900 border border-slate-800 text-pink-400 hover:text-pink-300 hover:border-pink-700 transition-colors"
                                  title="Instagram"
                                >
                                  <InstagramIcon className="w-3 h-3" />
                                </a>
                              )}
                              {facebookUrl && (
                                <a
                                  href={facebookUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="p-1 rounded bg-slate-900 border border-slate-800 text-blue-500 hover:text-blue-400 hover:border-blue-700 transition-colors"
                                  title="Facebook"
                                >
                                  <FacebookIcon className="w-3 h-3" />
                                </a>
                              )}
                              {twitterUrl && (
                                <a
                                  href={twitterUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="p-1 rounded bg-slate-900 border border-slate-800 text-sky-400 hover:text-sky-300 hover:border-sky-700 transition-colors"
                                  title="Twitter / X"
                                >
                                  <TwitterIcon className="w-3 h-3" />
                                </a>
                              )}
                              {youtubeUrl && (
                                <a
                                  href={youtubeUrl}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="p-1 rounded bg-slate-900 border border-slate-800 text-red-500 hover:text-red-400 hover:border-red-700 transition-colors"
                                  title="YouTube"
                                >
                                  <YoutubeIcon className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          );
                        })()}

                        {/* Contact Form Links */}
                        {item.contacts?.channels?.filter((c: any) => c.type === 'contact_form').slice(0, 1).map((cf: any, idx: number) => (
                          <a
                            key={idx}
                            href={cf.value}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1.5 text-cyan-400 hover:underline font-mono text-[11px]"
                          >
                            <ExternalLink className="w-3 h-3 shrink-0" />
                            <span>Contact Form</span>
                          </a>
                        ))}

                        {!item.contacts?.email && !item.contacts?.phone && !item.contacts?.linkedin &&
                         (!item.emails || item.emails.length === 0) && (!item.phones || item.phones.length === 0) &&
                         (!item.contacts?.channels || item.contacts.channels.length === 0) && (
                          <span className="text-slate-500 text-[11px] italic">No direct channels published</span>
                        )}

                        {item.contacts?.channels && item.contacts.channels.length > 2 && (
                          <button
                            type="button"
                            onClick={() => setExpandedRowId(expandedRowId === item.id ? null : item.id)}
                            className="text-[10px] text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-mono mt-0.5 cursor-pointer"
                          >
                            <span>{expandedRowId === item.id ? 'Hide details' : `+${item.contacts.channels.length - 2} more channels`}</span>
                            {expandedRowId === item.id ? <ChevronUp className="w-2.5 h-2.5" /> : <ChevronDown className="w-2.5 h-2.5" />}
                          </button>
                        )}
                      </div>
                    </td>

                    {/* Confidence */}
                    <td className="py-3 px-4 align-top text-right">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono font-bold ${
                          item.confidence >= 0.8
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : item.confidence >= 0.6
                            ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                            : 'bg-amber-950 text-amber-400 border border-amber-800'
                        }`}
                      >
                        {Math.round(item.confidence * 100)}%
                      </span>
                    </td>
                  </tr>

                  {/* Expandable channels drawer row */}
                  {expandedRowId === item.id && (
                    <tr className="bg-slate-950/80 border-b border-slate-800">
                      <td colSpan={5} className="p-4 space-y-3">
                        <div className="flex items-center justify-between text-xs font-mono text-slate-400 border-b border-slate-800 pb-2">
                          <span className="font-bold text-slate-200">Enriched Intelligence Dossier: {item.company_name}</span>
                          <span className="text-[10px] text-cyan-400">All Discovered Channels ({item.contacts?.channels?.length || 0})</span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {item.contacts?.channels?.map((ch: any, cidx: number) => (
                            <div key={cidx} className="bg-slate-900 border border-slate-800 rounded-lg p-2.5 space-y-1">
                              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                                <span className="uppercase font-bold text-cyan-400">{ch.type}</span>
                                <span className="text-slate-500">{ch.scope?.replace(/_/g, ' ') || 'public'}</span>
                              </div>
                              <div className="text-xs font-mono text-slate-200 truncate flex items-center justify-between">
                                <span className="truncate">{ch.value}</span>
                                <button
                                  type="button"
                                  onClick={() => handleCopyChannel(`ch-${item.id}-${cidx}`, ch.value)}
                                  className="text-slate-500 hover:text-slate-200 ml-2"
                                  title="Copy"
                                >
                                  {copiedId === `ch-${item.id}-${cidx}` ? (
                                    <Check className="w-3 h-3 text-emerald-400" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                </button>
                              </div>
                              {ch.evidence_quote && (
                                <p className="text-[10px] text-slate-500 italic truncate">
                                  {ch.evidence_quote}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {/* 5. RECENT SCAN HISTORY */}
      <section className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Recent Competitor Scans
            </h3>
          </div>
          <button
            onClick={fetchRecentJobs}
            className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {recentJobs.slice(0, 4).map((j) => (
            <div
              key={j.id}
              onClick={() => {
                setActiveJobId(j.id);
                setJob(j);
              }}
              className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                activeJobId === j.id
                  ? 'bg-slate-800 border-cyan-500 shadow-sm'
                  : 'bg-slate-950 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono uppercase font-bold ${
                    j.status === 'completed'
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                      : j.status === 'running'
                      ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                      : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {j.status}
                </span>
                <span className="text-[10px] font-mono text-slate-400">
                  {j.started_at ? new Date(j.started_at).toLocaleTimeString() : ''}
                </span>
              </div>
              <div className="text-xs font-bold text-white truncate">{j.starting_url}</div>
              <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 font-mono">
                <span>{j.pages_crawled || 0} / {j.max_pages || 50} pages</span>
                <span>{j.references_found || 0} clients</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Cancellation Confirmation Modal */}
      <ConfirmModal
        isOpen={isCancelModalOpen}
        onClose={() => setIsCancelModalOpen(false)}
        onConfirm={handleCancelConfirm}
        title="Cancel Active Scan?"
        message="Are you sure you want to stop this scan? All pages and client references discovered so far will be safely preserved."
        confirmText={isCancelling ? 'Stopping...' : 'Yes, Stop Scan'}
        variant="danger"
      />
    </div>
  );
};
