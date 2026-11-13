import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles, Search, Globe, ExternalLink, Plus, Loader2, Check, AlertCircle,
  ArrowRight, ChevronRight,
} from 'lucide-react';
import { searchProviders } from '../../services/discovery';
import { createProvider, startProviderResearch } from '../../services/providers';
import { getCrawlJob } from '../../services/discovery';
import { CrawlJob } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';

export const Discovery: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'search' | 'website'>('search');

  const [searchQuery, setSearchQuery] = useState('Google Knowledge Panel services India');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [addedDomains, setAddedDomains] = useState<Set<string>>(new Set());

  const [targetUrl, setTargetUrl] = useState('https://theperson.in/');
  const [isStarting, setIsStarting] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [job, setJob] = useState<CrawlJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);

  // Poll active job
  useEffect(() => {
    if (!activeJobId) return;

    const tick = async () => {
      try {
        const j = await getCrawlJob(activeJobId);
        setJob(j);
        const terminal = ['completed', 'completed_with_warnings', 'failed', 'cancelled'].includes(j.status);
        if (terminal) {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
          setActiveJobId(null);
          if (j.status.startsWith('completed')) {
            // Auto-navigate to the report page
            setTimeout(() => navigate(`/reports/${j.id}`), 900);
          }
        }
      } catch {
        // transient error — keep polling
      }
    };

    pollRef.current = window.setInterval(tick, 2500);
    tick();

    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [activeJobId, navigate]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSearching(true);
    try {
      const res = await searchProviders(searchQuery);
      setSearchResults(res.results);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Search failed');
    } finally {
      setIsSearching(false);
    }
  };

  const handleAddAsProvider = async (result: any) => {
    try {
      await createProvider({
        name: result.title.split('–')[0].split('-')[0].trim(),
        website: result.url,
        category: 'direct_competitor',
        description: result.snippet,
      });
      setAddedDomains(new Set([...addedDomains, result.domain || result.url]));
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to save provider');
    }
  };

  const handleStartResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsStarting(true);
    try {
      // Reuse or create provider
      const provider = await createProvider({
        name: targetUrl.replace(/https?:\/\//, '').split('/')[0],
        website: targetUrl,
        category: 'direct_competitor',
      });
      const providerId = (provider as any).id || (provider as any)._id;

      const createdJob = await startProviderResearch(providerId);
      setActiveJobId(createdJob.id || (createdJob as any)._id);
      setJob(createdJob);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to start research');
    } finally {
      setIsStarting(false);
    }
  };

  const stageLabel = (s?: string) => {
    switch (s) {
      case 'queued': return 'Queued';
      case 'discovering': return 'Discovering URLs...';
      case 'crawling': return 'Crawling pages...';
      case 'extracting': return 'Extracting client references...';
      case 'generating_report': return 'Generating report...';
      case 'completed': return 'Completed';
      case 'failed': return 'Failed';
      default: return s || '';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">Provider Discovery Engine</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Zero-paid-API discovery. Automatically crawls, extracts client references, and builds CRM records.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div
          onClick={() => setActiveTab('search')}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${activeTab === 'search'
            ? 'bg-blue-50/60 border-blue-400/80 shadow-md'
            : 'bg-white border-slate-200 hover:border-slate-300'
            }`}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center">
              <Search className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Option A: Find Similar Providers</h3>
              <p className="text-xs text-slate-500">Keyword search using DDGS</p>
            </div>
          </div>
        </div>

        <div
          onClick={() => setActiveTab('website')}
          className={`cursor-pointer p-5 rounded-2xl border transition-all ${activeTab === 'website'
            ? 'bg-blue-50/60 border-blue-400/80 shadow-md'
            : 'bg-white border-slate-200 hover:border-slate-300'
            }`}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Option B: Research a Provider Website</h3>
              <p className="text-xs text-slate-500">Deep crawl and extract client references</p>
            </div>
          </div>
        </div>
      </div>

      {activeTab === 'search' && (
        <div className="space-y-4">
          <Card className="p-5">
            <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2">
              <div className="flex-1">
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g. Personal branding agency India"
                  leftIcon={<Search className="w-4 h-4 text-slate-400" />}
                />
              </div>
              <Button type="submit" variant="primary" isLoading={isSearching} leftIcon={<Sparkles className="w-4 h-4" />}>
                Run Discovery
              </Button>
            </form>
          </Card>

          {isSearching && <div className="py-8 text-center text-slate-400"><Loader2 className="w-6 h-6 mx-auto animate-spin" /></div>}

          {searchResults.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Discovered Companies ({searchResults.length})
              </h3>
              {searchResults.map((r, i) => {
                const isAdded = addedDomains.has(r.domain || r.url);
                return (
                  <Card key={i} className="p-4 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-semibold text-slate-900">{r.title}</h4>
                        <Badge variant="info">DDGS</Badge>
                      </div>
                      <p className="text-xs text-slate-600">{r.snippet}</p>
                      <a href={r.url} target="_blank" rel="noreferrer" className="text-[11px] text-blue-600 font-mono hover:underline">
                        <Globe className="w-3 h-3 inline mr-1" />{r.url}
                      </a>
                    </div>
                    <div>
                      {isAdded ? (
                        <Badge variant="success"><Check className="w-3 h-3 mr-1" /> Added</Badge>
                      ) : (
                        <Button variant="outline" size="sm" onClick={() => handleAddAsProvider(r)} leftIcon={<Plus className="w-3.5 h-3.5" />}>
                          Add to CRM
                        </Button>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === 'website' && (
        <div className="space-y-4">
          <Card className="p-5 space-y-4">
            <form onSubmit={handleStartResearch} className="space-y-3">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
                Target Website URL
              </label>
              <div className="flex flex-col sm:flex-row gap-2">
                <div className="flex-1">
                  <Input
                    type="url"
                    required
                    value={targetUrl}
                    onChange={(e) => setTargetUrl(e.target.value)}
                    placeholder="https://theperson.in/"
                    leftIcon={<Globe className="w-4 h-4 text-slate-400" />}
                    disabled={!!activeJobId}
                  />
                </div>
                <Button
                  type="submit"
                  variant="primary"
                  isLoading={isStarting || !!activeJobId}
                  disabled={!!activeJobId}
                  leftIcon={<Sparkles className="w-4 h-4" />}
                >
                  Start Research
                </Button>
              </div>
              {error && <p className="text-xs text-rose-600">{error}</p>}
            </form>

            {job && (
              <div className="pt-3 border-t border-slate-100 space-y-3">
                <div className="flex justify-between text-xs font-medium text-slate-700">
                  <span className="flex items-center gap-2">
                    <Loader2 className={`w-3.5 h-3.5 ${activeJobId ? 'animate-spin' : ''}`} />
                    {stageLabel(job.current_stage)} — <span className="capitalize">{job.status.replace(/_/g, ' ')}</span>
                  </span>
                  <span className="font-bold text-blue-600">{job.progress_pct}%</span>
                </div>
                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${job.status === 'failed' ? 'bg-rose-500' : 'bg-blue-600'
                      }`}
                    style={{ width: `${job.progress_pct}%` }}
                  />
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 text-xs">
                  <div><span className="text-slate-400 block">Discovered</span><span className="font-bold text-slate-800">{job.pages_discovered}</span></div>
                  <div><span className="text-slate-400 block">Attempted</span><span className="font-bold text-slate-800">{job.pages_attempted}</span></div>
                  <div><span className="text-slate-400 block">Crawled</span><span className="font-bold text-emerald-700">{job.pages_crawled}</span></div>
                  <div><span className="text-slate-400 block">Failed</span><span className="font-bold text-rose-700">{job.pages_failed}</span></div>
                  <div><span className="text-slate-400 block">References</span><span className="font-bold text-indigo-700">{job.references_found}</span></div>
                  <div><span className="text-slate-400 block">Contacts</span><span className="font-bold text-slate-800">{job.contacts_created}</span></div>
                  <div><span className="text-slate-400 block">Companies</span><span className="font-bold text-slate-800">{job.companies_created}</span></div>
                  <div><span className="text-slate-400 block">Leads</span><span className="font-bold text-slate-800">{job.leads_created}</span></div>
                </div>

                {job.errors && job.errors.length > 0 && (
                  <div className="pt-2">
                    <p className="text-xs font-semibold text-rose-700 flex items-center gap-1 mb-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {job.errors.length} error(s)
                    </p>
                    <div className="max-h-32 overflow-y-auto text-[11px] font-mono bg-rose-50 p-2 rounded border border-rose-100 text-rose-800">
                      {job.errors.slice(0, 5).map((e, i) => (
                        <div key={i} className="truncate">[{e.stage}] {e.message}</div>
                      ))}
                    </div>
                  </div>
                )}

                {job.status.startsWith('completed') && (
                  <Button
                    variant="success"
                    size="sm"
                    onClick={() => navigate(`/reports/${job.id}`)}
                    rightIcon={<ChevronRight className="w-4 h-4" />}
                  >
                    View Full Research Report
                  </Button>
                )}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
};