import React, { useEffect, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  PlayCircle,
  Clock,
  ExternalLink,
  Copy,
  Check,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  RefreshCw,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Layers,
  Database,
  Building,
  Users,
  Search,
} from 'lucide-react';
import { getCrawlJobs, getJobEvents } from '../../services/discovery';
import { CrawlJob, JobEvent } from '../../types';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

export const STAGE_DISPLAY_MAP: Record<string, string> = {
  queued: 'Queued',
  discovering: 'Discovering pages',
  crawling: 'Crawling website',
  extracting: 'Extracting intelligence',
  verifying: 'Verifying information',
  creating_crm_records: 'Saving CRM records',
  enriching_contacts: 'Enriching contacts',
  enriching_companies: 'Enriching companies',
  generating_report: 'Generating report',
  completed: 'Completed',
  completed_with_warnings: 'Completed with warnings',
  failed: 'Failed',
  cancelled: 'Cancelled',
  paused: 'Paused',
};

export function formatStageLabel(stage?: string): string {
  if (!stage) return 'Unknown Stage';
  const clean = stage.toLowerCase().trim();
  if (STAGE_DISPLAY_MAP[clean]) {
    return STAGE_DISPLAY_MAP[clean];
  }
  return clean
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function getCompetitorDisplayName(job: CrawlJob): string {
  if (job.provider_name && job.provider_name.trim()) {
    return job.provider_name.trim();
  }
  try {
    const url = new URL(job.starting_url);
    const host = url.hostname.replace(/^www\./, '');
    const firstPart = host.split('.')[0];
    if (firstPart) {
      return firstPart.charAt(0).toUpperCase() + firstPart.slice(1);
    }
    return host;
  } catch {
    return job.starting_url || 'Competitor Scan';
  }
}

export function getScanFreshness(job: CrawlJob, latestEvent?: JobEvent): { text: string; isStale: boolean } {
  const timestampStr = latestEvent?.event_timestamp || job.updated_at || job.started_at || job.created_at;
  if (!timestampStr) {
    return { text: 'No recent activity recorded', isStale: true };
  }
  const date = new Date(timestampStr);
  const now = new Date();
  const diffSec = Math.max(0, Math.floor((now.getTime() - date.getTime()) / 1000));

  if (diffSec > 90) {
    return { text: 'No recent activity recorded', isStale: true };
  }
  if (diffSec < 5) return { text: 'Active just now', isStale: false };
  if (diffSec < 60) return { text: `Last activity: ${diffSec}s ago`, isStale: false };
  const diffMin = Math.floor(diffSec / 60);
  return { text: `Last activity: ${diffMin}m ago`, isStale: false };
}

export const CurrentScanMonitor: React.FC = () => {
  const [runningJobs, setRunningJobs] = useState<CrawlJob[]>([]);
  const [pendingJobs, setPendingJobs] = useState<CrawlJob[]>([]);
  const [pendingTotal, setPendingTotal] = useState<number>(0);
  const [eventsMap, setEventsMap] = useState<Record<string, JobEvent[]>>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const isMountedRef = useRef<boolean>(true);
  const isFetchingRef = useRef<boolean>(false);

  const pollScanActivity = useCallback(async (isManual: boolean = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    if (isManual) setIsRefreshing(true);

    try {
      // 1. Fetch running jobs (up to 100)
      const runningRes = await getCrawlJobs({
        page: 1,
        page_size: 100,
        status: 'running',
      });

      // 2. Fetch pending jobs for queue info
      const pendingRes = await getCrawlJobs({
        page: 1,
        page_size: 5,
        status: 'pending',
      });

      if (!isMountedRef.current) return;

      const activeJobs = runningRes.items || [];
      const queuedJobs = pendingRes.items || [];
      const queuedTotal = pendingRes.total ?? queuedJobs.length;

      setRunningJobs(activeJobs);
      setPendingJobs(queuedJobs);
      setPendingTotal(queuedTotal);
      setError(null);

      // 3. For each running job, fetch its latest 8 persistent events in parallel
      if (activeJobs.length > 0) {
        const eventPromises = activeJobs.map(async (j) => {
          const jid = j.id || (j as any)._id;
          if (!jid) return { jid: '', events: [] };
          try {
            const evts = await getJobEvents(jid, { limit: 8, latest: true });
            return { jid, events: evts || [] };
          } catch {
            return { jid, events: [] };
          }
        });

        const results = await Promise.all(eventPromises);
        if (!isMountedRef.current) return;

        const nextEventsMap: Record<string, JobEvent[]> = {};
        for (const { jid, events } of results) {
          if (jid) nextEventsMap[jid] = events;
        }
        setEventsMap(nextEventsMap);
      } else {
        setEventsMap({});
      }
    } catch (err: any) {
      if (!isMountedRef.current) return;
      setError(err?.message || 'Failed to update live scan activity telemetry.');
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
        setIsRefreshing(false);
      }
      isFetchingRef.current = false;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    pollScanActivity(false);

    // Refresh every 4.5 seconds
    const intervalId = setInterval(() => {
      pollScanActivity(false);
    }, 4500);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [pollScanActivity]);

  const handleCopyId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-1 border-b border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 flex items-center justify-center">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-bold text-white tracking-tight">Current Scan Activity</h2>
              {runningJobs.length > 0 ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  {runningJobs.length} {runningJobs.length === 1 ? 'Scan Active' : 'Scans Active'}
                </span>
              ) : pendingTotal > 0 ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-950/80 text-amber-400 border border-amber-800">
                  <Clock className="w-3 h-3" />
                  {pendingTotal} Queued
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
                  Idle
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">
              Live monitoring of competitor research and background discovery jobs.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <button
            onClick={() => pollScanActivity(true)}
            disabled={isRefreshing}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-md shadow-xs transition-colors disabled:opacity-50"
            title="Refresh scan monitor"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
            <span>{isRefreshing ? 'Updating...' : 'Live (4s)'}</span>
          </button>
        </div>
      </div>

      {/* Non-blocking error notification */}
      {error && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-amber-950/40 border border-amber-800/60 text-amber-300 text-xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => pollScanActivity(true)}
            className="font-semibold underline hover:text-amber-200"
          >
            Retry
          </button>
        </div>
      )}

      {/* STATE 1: At least one scan is actively running */}
      {runningJobs.length > 0 && (
        <div className="space-y-4">
          {runningJobs.map((job) => {
            const jid = job.id || (job as any)._id || '';
            const competitorName = getCompetitorDisplayName(job);
            const events = eventsMap[jid] || [];
            // Order newest on top for display
            const displayedEvents = [...events].reverse();
            const latestEvent = events.length > 0 ? events[events.length - 1] : undefined;
            const freshness = getScanFreshness(job, latestEvent);

            const isPostCrawlEnrichment =
              ['extracting', 'verifying', 'creating_crm_records', 'enriching_contacts', 'enriching_companies', 'generating_report'].includes(
                job.current_stage
              ) ||
              (job.pages_crawled > 0 &&
                job.pages_crawled >= (job.max_pages || 50) &&
                job.status === 'running');

            return (
              <Card
                key={jid}
                className="overflow-hidden border border-slate-800 bg-slate-900 shadow-md transition-all"
              >
                {/* Accent Progress Line */}
                <div className="h-1 w-full bg-slate-800">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-blue-600 transition-all duration-500 ease-out"
                    style={{ width: `${Math.min(100, Math.max(2, job.progress_pct || 0))}%` }}
                  />
                </div>

                <div className="p-4 sm:p-5 space-y-4">
                  {/* Top Bar: Competitor Info, Stage, and Freshness */}
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm sm:text-base font-bold text-white truncate">
                          {competitorName}
                        </span>
                        <a
                          href={job.starting_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 hover:underline max-w-[280px] sm:max-w-md truncate"
                        >
                          <span className="truncate">{job.starting_url}</span>
                          <ExternalLink className="w-3 h-3 shrink-0" />
                        </a>
                      </div>

                      <div className="flex flex-wrap items-center gap-2.5 mt-1 text-[11px] text-slate-400">
                        <div className="inline-flex items-center gap-1 font-mono">
                          <span>Job ID: {jid.slice(-8)}</span>
                          <button
                            onClick={() => handleCopyId(jid)}
                            className="p-0.5 text-slate-400 hover:text-slate-200 transition-colors"
                            title="Copy Job ID"
                          >
                            {copiedId === jid ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3" />
                            )}
                          </button>
                        </div>
                        {job.started_at && (
                          <span>
                            Started: {new Date(job.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                        <span className="text-slate-600">•</span>
                        <span
                          className={`inline-flex items-center gap-1 ${
                            freshness.isStale ? 'text-amber-400 font-medium' : 'text-slate-400'
                          }`}
                        >
                          <Clock className="w-3 h-3" />
                          {freshness.text}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-start md:self-center">
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-cyan-950/80 text-cyan-300 border border-cyan-800/80 shadow-xs">
                        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                        {formatStageLabel(job.current_stage)}
                      </span>
                      <span className="px-2.5 py-1 rounded-md text-xs font-bold bg-slate-950 text-cyan-400 border border-slate-800 font-mono">
                        {job.progress_pct || 0}%
                      </span>
                    </div>
                  </div>

                  {/* Visual Progress Bar */}
                  <div className="space-y-1">
                    <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${Math.min(100, Math.max(3, job.progress_pct || 0))}%` }}
                      />
                    </div>
                  </div>

                  {/* Post-crawl ongoing enrichment indicator */}
                  {isPostCrawlEnrichment && (
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-950/40 border border-indigo-800/60 text-indigo-200 text-xs font-medium">
                      <Sparkles className="w-4 h-4 text-indigo-400 shrink-0 animate-pulse" />
                      <span>
                        <strong>Crawling finished</strong> — Deep intelligence extraction, entity classification, and CRM enrichment are actively in progress.
                      </span>
                    </div>
                  )}

                  {/* Core Crawl & Discovery Metrics Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                    <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
                        Pages Attempted
                      </span>
                      <div className="flex items-baseline gap-1 mt-0.5">
                        <span className="text-base font-bold text-white">
                          {job.pages_attempted || 0}
                        </span>
                        <span className="text-[11px] text-slate-400">
                          / {job.max_pages || 50} limit
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 block mt-0.5">
                        {job.pages_discovered || 0} discovered
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-emerald-950/30 border border-emerald-900/60">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400 block">
                        Crawled Successfully
                      </span>
                      <div className="text-base font-bold text-emerald-300 mt-0.5">
                        {job.pages_crawled || 0}
                      </div>
                      <span className="text-[10px] text-emerald-400/80 block mt-0.5">
                        {job.pages_analysed || job.pages_crawled || 0} analysed
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
                        Failed / Skipped
                      </span>
                      <div className="flex items-baseline gap-1.5 mt-0.5">
                        <span className="text-base font-bold text-rose-400">
                          {job.pages_failed || 0}
                        </span>
                        <span className="text-[11px] text-slate-400">failed</span>
                        <span className="text-slate-600">•</span>
                        <span className="text-[11px] text-slate-400">
                          {job.pages_skipped || 0} skipped
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 block mt-0.5">Rate & safety bounded</span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-indigo-950/30 border border-indigo-900/60">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-400 block">
                        Discovered Yield
                      </span>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5 text-xs font-bold text-indigo-200">
                        <span>{job.contacts_created || 0} contacts</span>
                        <span className="text-indigo-400/60">•</span>
                        <span>{job.companies_created || 0} co.</span>
                      </div>
                      <span className="text-[10px] text-indigo-300/80 block mt-0.5">
                        {job.references_found || 0} references • {job.leads_created || 0} leads
                      </span>
                    </div>
                  </div>

                  {/* Live Activity Timeline (Latest 5–8 Real Persistent Events) */}
                  <div className="pt-2 border-t border-slate-800/80">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                        <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                          Live Activity Log
                        </h4>
                      </div>
                      <span className="text-[10px] text-slate-400">Newest events first</span>
                    </div>

                    {displayedEvents.length === 0 ? (
                      <div className="p-3 text-center rounded-lg bg-slate-950/50 border border-slate-800/60 text-[11px] text-slate-400 italic">
                        Connecting to persistent event telemetry...
                      </div>
                    ) : (
                      <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                        {displayedEvents.map((event, idx) => {
                          const isNewest = idx === 0;
                          const sev = event.severity || 'info';

                          let badgeColor = 'bg-slate-800 text-slate-300 border-slate-700';
                          let dotColor = 'bg-slate-400';
                          if (sev === 'success') {
                            badgeColor = 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60';
                            dotColor = 'bg-emerald-400';
                          } else if (sev === 'warning') {
                            badgeColor = 'bg-amber-950/60 text-amber-300 border-amber-800/60';
                            dotColor = 'bg-amber-400';
                          } else if (sev === 'error') {
                            badgeColor = 'bg-rose-950/60 text-rose-300 border-rose-800/60';
                            dotColor = 'bg-rose-400';
                          } else if (sev === 'info') {
                            badgeColor = 'bg-cyan-950/60 text-cyan-300 border-cyan-800/60';
                            dotColor = 'bg-cyan-400';
                          }

                          const formattedTime = event.event_timestamp
                            ? new Date(event.event_timestamp).toLocaleTimeString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                              })
                            : '—';

                          return (
                            <div
                              key={event.id || `${event.event_timestamp}-${idx}`}
                              className={`flex items-start gap-2.5 p-2 rounded-md text-xs transition-colors ${
                                isNewest
                                  ? 'bg-slate-950/90 border border-slate-800 text-slate-200 shadow-xs'
                                  : 'hover:bg-slate-800/50 text-slate-300'
                              }`}
                            >
                              <div className="pt-0.5 shrink-0">
                                <span className={`inline-block w-2 h-2 rounded-full ${dotColor}`} />
                              </div>

                              <span className="text-[10px] font-mono text-slate-400 shrink-0 pt-0.5">
                                {formattedTime}
                              </span>

                              <span
                                className={`px-1.5 py-0.2 rounded text-[10px] font-medium border uppercase tracking-wider shrink-0 ${badgeColor}`}
                              >
                                {formatStageLabel(event.stage)}
                              </span>

                              <p className="text-slate-200 leading-snug flex-1 break-words">
                                {event.message}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* STATE 2: No scan running, but pending jobs exist in queue */}
      {runningJobs.length === 0 && pendingJobs.length > 0 && (
        <Card className="p-5 border border-slate-800 bg-slate-900 shadow-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <Clock className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white">No scan is currently running.</h3>
                <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-950/80 text-amber-400 border border-amber-800">
                  {pendingTotal} in queue
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Active crawler workers are currently idle or between domain rate limits.
              </p>
            </div>

            <Link to="/scanner" className="shrink-0">
              <Button variant="secondary" size="sm" className="w-full sm:w-auto">
                View Queue in Scanner
                <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </Link>
          </div>

          {/* Next Queued Competitor Preview */}
          {pendingJobs[0] && (
            <div className="mt-4 pt-3 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-semibold text-slate-400 shrink-0">Next Up:</span>
                <span className="font-bold text-white truncate">
                  {getCompetitorDisplayName(pendingJobs[0])}
                </span>
                <a
                  href={pendingJobs[0].starting_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300 hover:underline truncate max-w-xs inline-flex items-center gap-1"
                >
                  <span className="truncate">{pendingJobs[0].starting_url}</span>
                  <ExternalLink className="w-3 h-3 shrink-0" />
                </a>
              </div>
              <Badge variant="warning">Queued</Badge>
            </div>
          )}
        </Card>
      )}

      {/* STATE 3: No scan running and no jobs pending (Idle) */}
      {runningJobs.length === 0 && pendingJobs.length === 0 && !isLoading && (
        <Card className="p-6 border border-slate-800 bg-slate-900 text-center shadow-md">
          <div className="max-w-md mx-auto space-y-3">
            <div className="w-10 h-10 rounded-full bg-slate-800 text-slate-400 mx-auto flex items-center justify-center border border-slate-700">
              <PlayCircle className="w-5 h-5 text-slate-300" />
            </div>
            <h3 className="text-sm font-bold text-white">All research jobs are currently idle.</h3>
            <p className="text-xs text-slate-400">
              No competitor scans are currently active or queued. Launch a scan on any agency or competitor website to discover clients and contacts.
            </p>
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-2.5">
              <Link to="/scanner" className="w-full sm:w-auto">
                <Button variant="primary" size="sm" className="w-full sm:w-auto">
                  <Sparkles className="w-3.5 h-3.5 mr-1" />
                  Start Competitor Scan
                </Button>
              </Link>
              <Link to="/lead-generator" className="w-full sm:w-auto">
                <Button variant="secondary" size="sm" className="w-full sm:w-auto">
                  Launch Lead Generator
                </Button>
              </Link>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};
