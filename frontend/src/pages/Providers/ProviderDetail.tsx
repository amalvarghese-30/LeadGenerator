import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Building2,
  Globe,
  MapPin,
  Calendar,
  Sparkles,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Clock,
  ShieldCheck,
  UserCheck,
  AlertCircle,
  RotateCcw,
  FileText,
} from 'lucide-react';
import { LinkedinIcon, TwitterIcon, InstagramIcon, YoutubeIcon } from '../../components/ui/SocialIcons';
import {
  getProvider,
  getProviderReferences,
  getProviderJobs,
  startProviderResearch,
} from '../../services/providers';
import { retryCrawlJob } from '../../services/discovery';
import { Provider, Reference, CrawlJob } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { useToast } from '../../context/ToastContext';
import { formatDate, formatDateTime } from '../../utils/format';

export const ProviderDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const [provider, setProvider] = useState<Provider | null>(null);
  const [references, setReferences] = useState<Reference[]>([]);
  const [jobs, setJobs] = useState<CrawlJob[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'references' | 'jobs'>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [isResearching, setIsResearching] = useState(false);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);

  const fetchData = async () => {
    if (!id) return;
    setIsLoading(true);
    try {
      const [pRes, refRes, jobRes] = await Promise.all([
        getProvider(id).catch(() => null),
        getProviderReferences(id).catch(() => ({ items: [] } as any)),
        getProviderJobs(id).catch(() => ({ items: [] } as any)),
      ]);
      if (pRes) setProvider(pRes);
      if (refRes) setReferences(refRes.items);
      if (jobRes) setJobs(jobRes.items);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  // Auto-refresh while a job is running
  useEffect(() => {
    const hasActive = jobs.some((j) => j.status === 'pending' || j.status === 'running');
    if (!hasActive) return;
    const t = window.setInterval(() => {
      fetchData();
    }, 4000);
    return () => window.clearInterval(t);
  }, [jobs]);

  const handleStartResearch = async () => {
    if (!id) return;
    setIsResearching(true);
    try {
      await startProviderResearch(id, 50);
      toast.success('Research job dispatched to background crawler');
      await fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to dispatch research job');
    } finally {
      setIsResearching(false);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    setRetryingJobId(jobId);
    try {
      await retryCrawlJob(jobId);
      toast.success('Crawl job retry initiated');
      await fetchData();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to retry job');
    } finally {
      setRetryingJobId(null);
    }
  };

  if (isLoading && !provider) {
    return <LoadingSpinner message="Loading provider intelligence profile..." />;
  }

  if (!provider) {
    return (
      <div className="text-center py-12">
        <h3 className="text-sm font-semibold text-slate-800">Provider not found</h3>
        <Link to="/providers" className="text-xs text-blue-600 mt-2 inline-block">
          Return to providers list
        </Link>
      </div>
    );
  }

  const statusVariant = (status: string): 'success' | 'warning' | 'info' | 'danger' | 'default' => {
    if (status === 'completed') return 'success';
    if (status === 'completed_with_warnings') return 'warning';
    if (status === 'running') return 'info';
    if (status === 'failed') return 'danger';
    return 'default';
  };

  return (
    <div className="space-y-6">
      {/* Back button & Action Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            to="/providers"
            className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">{provider.name}</h1>
              <Badge variant={provider.category === 'direct_competitor' ? 'info' : 'default'}>
                {provider.category ? provider.category.replace(/_/g, ' ') : '—'}
              </Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
              {provider.website && (
                <a
                  href={provider.website}
                  target="_blank"
                  rel="noreferrer"
                  className="hover:text-blue-600 flex items-center gap-1"
                >
                  <Globe className="w-3.5 h-3.5 text-slate-400" /> {provider.domain || provider.website}
                </a>
              )}
              {provider.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" /> {provider.location}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="md"
            onClick={handleStartResearch}
            isLoading={isResearching}
            leftIcon={<Sparkles className="w-4 h-4" />}
          >
            Start Website Research
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-3 px-1 border-b-2 font-medium text-xs transition-colors ${activeTab === 'overview'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
          >
            Overview & Services
          </button>
          <button
            onClick={() => setActiveTab('references')}
            className={`py-3 px-1 border-b-2 font-medium text-xs transition-colors flex items-center gap-1.5 ${activeTab === 'references'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
          >
            Disclosed Clients ({references.length})
          </button>
          <button
            onClick={() => setActiveTab('jobs')}
            className={`py-3 px-1 border-b-2 font-medium text-xs transition-colors flex items-center gap-1.5 ${activeTab === 'jobs'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
          >
            Crawl History ({jobs.length})
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="md:col-span-2 space-y-5">
            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">About Agency</h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                {provider.description ||
                  `${provider.name} is a service provider identified in the digital identity, personal branding, and Google search visibility space. They provide profile creation, Knowledge Panel, and authority building services.`}
              </p>
            </div>

            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Disclosed Services</h3>
              <div className="flex flex-wrap gap-2">
                {provider.services && provider.services.length > 0 ? (
                  provider.services.map((s) => (
                    <span
                      key={s}
                      className="bg-slate-100 text-slate-800 px-2.5 py-1 rounded-lg text-xs font-medium border border-slate-200"
                    >
                      {s}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-slate-400">No services cataloged yet.</span>
                )}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Social Presence</h3>
              <div className="flex items-center gap-3 flex-wrap">
                {provider.social_profiles?.linkedin && (
                  <a
                    href={provider.social_profiles.linkedin}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-700 hover:border-blue-500 hover:text-blue-600 transition-colors"
                  >
                    <LinkedinIcon className="w-3.5 h-3.5 text-blue-600" /> LinkedIn
                  </a>
                )}
                {provider.social_profiles?.twitter && (
                  <a
                    href={provider.social_profiles.twitter}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-700 hover:border-sky-500 hover:text-sky-500 transition-colors"
                  >
                    <TwitterIcon className="w-3.5 h-3.5 text-sky-500" /> X / Twitter
                  </a>
                )}
                {provider.social_profiles?.instagram && (
                  <a
                    href={provider.social_profiles.instagram}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-700 hover:border-pink-500 hover:text-pink-600 transition-colors"
                  >
                    <InstagramIcon className="w-3.5 h-3.5 text-pink-600" /> Instagram
                  </a>
                )}
                {provider.social_profiles?.youtube && (
                  <a
                    href={provider.social_profiles.youtube}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-700 hover:border-red-500 hover:text-red-600 transition-colors"
                  >
                    <YoutubeIcon className="w-3.5 h-3.5 text-red-600" /> YouTube
                  </a>
                )}
              </div>
            </div>
          </Card>

          <Card className="space-y-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Research Metadata</h3>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Discovery Status</span>
                <span className="font-semibold text-slate-900 capitalize">{provider.discovery_status}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Verification</span>
                <span className="font-semibold text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> {provider.verification_status}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Similarity Score</span>
                <span className="font-bold text-blue-600">{provider.similarity_score} / 100</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Last Crawled</span>
                <span className="text-slate-700">{formatDateTime(provider.last_crawled_at)}</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-slate-500">Discovery Source</span>
                <span className="text-slate-700 uppercase tracking-wider text-[11px] font-semibold">
                  {provider.source || 'Manual'}
                </span>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Tab: References */}
      {activeTab === 'references' && (
        <Card className="p-0 overflow-hidden">
          {references.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No client references extracted yet. Click "Start Website Research" above to crawl and extract public
              client references.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {references.map((ref) => (
                <div
                  key={ref.id}
                  className="p-4 hover:bg-slate-50 transition-colors flex flex-col sm:flex-row sm:items-start justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-slate-900">
                        {ref.person_name || 'Individual Reference'}
                      </span>
                      {ref.designation && <span className="text-xs text-slate-500">({ref.designation})</span>}
                      {ref.company_name && <Badge variant="default">{ref.company_name}</Badge>}
                      <Badge variant="purple">{ref.relationship_type.replace(/_/g, ' ')}</Badge>
                    </div>

                    {ref.evidence_quote && (
                      <blockquote className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border-l-2 border-blue-500 italic mt-2">
                        "{ref.evidence_quote}"
                      </blockquote>
                    )}

                    <div className="text-[11px] text-slate-400 flex items-center gap-3 pt-1">
                      <span>Source:</span>
                      <a
                        href={ref.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 hover:underline flex items-center gap-0.5 truncate max-w-sm"
                      >
                        {ref.source_url} <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    </div>
                  </div>

                  <div className="shrink-0 text-right">
                    <Badge variant={ref.verification_status === 'verified' ? 'success' : 'warning'}>
                      {ref.verification_status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Tab: Jobs — full detail cards with errors, counters, retry, and report link */}
      {activeTab === 'jobs' && (
        <Card className="p-0 overflow-hidden">
          {jobs.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No crawl jobs dispatched for this provider yet.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {jobs.map((job) => {
                const isActive = job.status === 'pending' || job.status === 'running';
                const hasErrors = job.errors && job.errors.length > 0;
                const hasWarnings = job.warnings && job.warnings.length > 0;

                return (
                  <div key={job.id} className="p-4 space-y-3">
                    {/* Header row */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-800">Job #{job.id.slice(-6)}</span>
                        <Badge variant={statusVariant(job.status)}>
                          {job.status.replace(/_/g, ' ')}
                        </Badge>
                        {job.current_stage && (
                          <span className="text-[11px] text-slate-500 capitalize">
                            {job.current_stage.replace(/_/g, ' ')}
                          </span>
                        )}
                        {isActive && (
                          <span className="text-[11px] font-semibold text-blue-600">{job.progress_pct}%</span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <Link to={`/reports/${job.id}`}>
                          <Button
                            variant="outline"
                            size="sm"
                            leftIcon={<FileText className="w-3.5 h-3.5" />}
                          >
                            View Report
                          </Button>
                        </Link>
                        {job.status === 'failed' && (
                          <Button
                            variant="outline"
                            size="sm"
                            isLoading={retryingJobId === job.id}
                            onClick={() => handleRetryJob(job.id)}
                            leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                          >
                            Retry
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Progress bar */}
                    {isActive && (
                      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-600 rounded-full transition-all duration-300"
                          style={{ width: `${job.progress_pct}%` }}
                        />
                      </div>
                    )}

                    {/* Counters grid */}
                    <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-[11px]">
                      <div>
                        <span className="text-slate-400 block">Discovered</span>
                        <span className="font-bold text-slate-800">{job.pages_discovered ?? 0}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Attempted</span>
                        <span className="font-bold text-slate-800">{job.pages_attempted ?? 0}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Crawled</span>
                        <span className="font-bold text-emerald-700">{job.pages_crawled ?? 0}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Failed</span>
                        <span className="font-bold text-rose-700">{job.pages_failed ?? 0}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">References</span>
                        <span className="font-bold text-indigo-700">{job.references_found ?? 0}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Leads</span>
                        <span className="font-bold text-slate-800">{job.leads_created ?? 0}</span>
                      </div>
                    </div>

                    {/* Timestamps */}
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400">
                      <span>Started: {formatDateTime(job.started_at || job.created_at)}</span>
                      {job.completed_at && <span>Completed: {formatDateTime(job.completed_at)}</span>}
                    </div>

                    {/* Errors */}
                    {hasErrors && (
                      <div className="mt-1">
                        <p className="text-[11px] font-semibold text-rose-700 flex items-center gap-1 mb-1">
                          <AlertCircle className="w-3 h-3" /> {job.errors.length} error(s)
                        </p>
                        <div className="max-h-32 overflow-y-auto text-[11px] font-mono bg-rose-50 border border-rose-100 p-2 rounded space-y-1">
                          {job.errors.slice(0, 5).map((e, idx) => (
                            <div key={idx} className="truncate">
                              <span className="font-bold text-rose-800">[{e.stage}]</span>{' '}
                              <span className="text-rose-600">{e.message}</span>
                              {e.url && (
                                <span className="text-rose-400 block text-[10px] truncate">{e.url}</span>
                              )}
                            </div>
                          ))}
                          {job.errors.length > 5 && (
                            <div className="text-rose-500 text-[10px]">+ {job.errors.length - 5} more…</div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Warnings */}
                    {hasWarnings && !hasErrors && (
                      <div className="mt-1">
                        <p className="text-[11px] font-semibold text-amber-700 flex items-center gap-1 mb-1">
                          <ShieldCheck className="w-3 h-3" /> {job.warnings.length} warning(s)
                        </p>
                        <div className="max-h-24 overflow-y-auto text-[11px] font-mono bg-amber-50 border border-amber-100 p-2 rounded">
                          {job.warnings.slice(0, 3).map((e, idx) => (
                            <div key={idx} className="truncate text-amber-800">
                              [{e.stage}] {e.message}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      )}
    </div>
  );
};