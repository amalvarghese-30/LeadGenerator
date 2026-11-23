import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Building2,
  Plus,
  Search,
  ExternalLink,
  Sparkles,
  CheckCircle2,
  Globe,
  Trash2,
  RotateCcw,
  Activity,
  Layers,
  FileSearch,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';
import { getProviders, createProvider, startProviderResearch, deleteProvider } from '../../services/providers';
import { Provider } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { Pagination } from '../../components/ui/Pagination';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { useToast } from '../../context/ToastContext';
import { formatDateTime } from '../../utils/format';

type ScanFilterTab = 'scanned' | 'researching' | 'completed' | 'failed' | 'all';

export const Providers: React.FC = () => {
  const { toast } = useToast();
  const navigate = useNavigate();

  const [providers, setProviders] = useState<Provider[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [activeTab, setActiveTab] = useState<ScanFilterTab>('scanned');
  const [isLoading, setIsLoading] = useState(true);

  // Top KPI Metrics
  const [metrics, setMetrics] = useState({
    totalScanned: 0,
    activeScans: 0,
    totalPagesCrawled: 0,
    totalReferences: 0,
  });

  // Add Provider Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newProvider, setNewProvider] = useState({
    name: '',
    website: '',
    category: 'direct_competitor' as Provider['category'],
    location: '',
    country: '',
    description: '',
    services: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [researchingId, setResearchingId] = useState<string | null>(null);

  const fetchProviders = async () => {
    setIsLoading(true);
    try {
      const res = await getProviders({
        page,
        page_size: pageSize,
        search: search || undefined,
        category: category || undefined,
        scan_status: activeTab,
        sort_by: 'last_crawled_at',
        order: 'desc',
      });
      setProviders(res.items);
      setTotal(res.total);

      // Derive KPI summary
      let active = 0;
      let pages = 0;
      let refs = 0;
      res.items.forEach((p) => {
        if (p.latest_job_status === 'running') active += 1;
        pages += p.pages_crawled || 0;
        refs += p.references_found || 0;
      });
      setMetrics((prev) => ({
        ...prev,
        activeScans: active,
        totalPagesCrawled: pages > prev.totalPagesCrawled ? pages : prev.totalPagesCrawled,
        totalReferences: refs > prev.totalReferences ? refs : prev.totalReferences,
      }));
    } catch (err: any) {
      setProviders([]);
      setTotal(0);
      toast.error(err.response?.data?.detail || 'Failed to load providers');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, [page, pageSize, search, category, activeTab]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const servicesArray = newProvider.services
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      await createProvider({
        name: newProvider.name,
        website: newProvider.website,
        category: newProvider.category,
        location: newProvider.location,
        country: newProvider.country,
        description: newProvider.description,
        services: servicesArray,
      });
      setIsModalOpen(false);
      setNewProvider({
        name: '',
        website: '',
        category: 'direct_competitor',
        location: '',
        country: '',
        description: '',
        services: '',
      });
      toast.success('Provider created successfully');
      fetchProviders();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create provider');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartResearch = async (id: string) => {
    setResearchingId(id);
    try {
      await startProviderResearch(id, 50);
      toast.success('Website research job queued');
      fetchProviders();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not start research job');
    } finally {
      setResearchingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Delete this provider record?')) {
      await deleteProvider(id);
      fetchProviders();
    }
  };

  const renderStatusBadge = (provider: Provider) => {
    const status = provider.latest_job_status;
    if (status === 'running') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-cyan-950 text-cyan-400 border border-cyan-800 animate-pulse">
          <Activity className="w-3.5 h-3.5 animate-spin" />
          Scanning ({provider.latest_job_progress_pct || 0}%)
        </span>
      );
    }
    if (status === 'completed') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Completed
        </span>
      );
    }
    if (status === 'completed_with_warnings') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-950 text-amber-400 border border-amber-800">
          <AlertTriangle className="w-3.5 h-3.5" />
          Warnings
        </span>
      );
    }
    if (status === 'failed') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-950 text-rose-400 border border-rose-800">
          Failed
        </span>
      );
    }
    if (provider.last_crawled_at) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-950 text-blue-400 border border-blue-800">
          Scanned
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
        Never Scanned
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Building2 className="w-6 h-6 text-cyan-400" />
            Scanned Competitors &amp; Providers
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Complete intelligence archive of target agencies, scanned domains, and client extraction histories.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/">
            <Button variant="secondary" size="md" className="min-h-[44px]">
              <FileSearch className="w-4 h-4 mr-1.5 text-cyan-400" />
              Live Scanner
            </Button>
          </Link>
          <Button variant="primary" size="md" onClick={() => setIsModalOpen(true)} className="min-h-[44px]">
            <Plus className="w-4 h-4 mr-1.5" />
            Add Provider
          </Button>
        </div>
      </div>

      {/* Top KPI Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Scanned Targets</span>
            <Layers className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-extrabold text-white mt-2">{total}</div>
          <div className="text-[11px] text-slate-400 mt-1">In current filter view</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Active Crawls</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-extrabold text-emerald-400 mt-2">{metrics.activeScans}</div>
          <div className="text-[11px] text-slate-400 mt-1">Background worker jobs</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Pages Analyzed</span>
            <Globe className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-extrabold text-white mt-2">{metrics.totalPagesCrawled}</div>
          <div className="text-[11px] text-slate-400 mt-1">DOM pages crawled</div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Clients &amp; Leads Found</span>
            <Sparkles className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-extrabold text-amber-400 mt-2">{metrics.totalReferences}</div>
          <div className="text-[11px] text-slate-400 mt-1">Attributed client proofs</div>
        </div>
      </div>

      {/* Quick-Filter Tabs */}
      <div className="flex items-center gap-1 sm:gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
        {[
          { key: 'scanned', label: 'All Scanned Providers' },
          { key: 'researching', label: 'Currently Scanning' },
          { key: 'completed', label: 'Completed' },
          { key: 'failed', label: 'Failed / Warnings' },
          { key: 'all', label: 'All Providers' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key as ScanFilterTab);
              setPage(1);
            }}
            className={`px-3.5 py-2 text-xs font-semibold rounded-lg transition-all min-h-[44px] sm:min-h-0 whitespace-nowrap ${
              activeTab === tab.key
                ? 'bg-slate-800 text-cyan-400 border border-slate-700 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Filter / Search Bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2">
            <Input
              placeholder="Filter providers by name, domain, or service keyword..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              leftIcon={<Search className="w-4 h-4 text-slate-400" />}
              className="bg-slate-950 border-slate-800 text-white min-h-[44px]"
            />
          </div>
          <div>
            <Select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setPage(1);
              }}
              options={[
                { label: 'All Categories', value: '' },
                { label: 'Direct Competitors', value: 'direct_competitor' },
                { label: 'Close Competitors', value: 'close_competitor' },
                { label: 'Adjacent Providers', value: 'adjacent_provider' },
                { label: 'Pending Review', value: 'pending_review' },
              ]}
              className="bg-slate-950 border-slate-800 text-white min-h-[44px]"
            />
          </div>
        </div>
      </div>

      {/* Providers Table */}
      {isLoading ? (
        <LoadingSpinner message="Loading scanned providers..." />
      ) : providers.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No providers found for this filter"
          description="Try selecting 'All Providers' or start a new scan from the Scanner page."
          actionText="Add New Provider"
          onAction={() => setIsModalOpen(true)}
        />
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-3 px-4">Provider / Domain</th>
                  <th className="py-3 px-4">Scan Status</th>
                  <th className="py-3 px-4">Last Scanned</th>
                  <th className="py-3 px-4 text-center">Pages Crawled</th>
                  <th className="py-3 px-4 text-center">Clients Found</th>
                  <th className="py-3 px-4 text-center">Total Scans</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {providers.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-800/40 transition-colors">
                    {/* Provider name & website */}
                    <td className="py-3.5 px-4">
                      <Link
                        to={`/providers/${p.id}`}
                        className="font-bold text-white hover:text-cyan-400 text-sm block"
                      >
                        {p.name}
                      </Link>
                      {p.website && (
                        <a
                          href={p.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[11px] text-slate-400 hover:text-cyan-300 flex items-center gap-1 mt-0.5"
                        >
                          <Globe className="w-3 h-3 text-slate-500" />
                          <span className="truncate max-w-xs">{p.website.replace(/^https?:\/\//, '')}</span>
                          <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                        </a>
                      )}
                    </td>

                    {/* Status badge */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {renderStatusBadge(p)}
                    </td>

                    {/* Last scanned */}
                    <td className="py-3.5 px-4 text-slate-400 whitespace-nowrap">
                      {p.last_crawled_at ? (
                        formatDateTime(p.last_crawled_at)
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>

                    {/* Pages crawled */}
                    <td className="py-3.5 px-4 text-center font-mono font-semibold text-slate-200">
                      {p.pages_crawled || 0}
                    </td>

                    {/* Clients found */}
                    <td className="py-3.5 px-4 text-center">
                      <span className="px-2 py-0.5 rounded font-mono font-bold text-xs bg-cyan-950 text-cyan-300 border border-cyan-800">
                        {p.references_found || 0}
                      </span>
                    </td>

                    {/* Total scans */}
                    <td className="py-3.5 px-4 text-center font-mono text-slate-400">
                      {p.total_scans_count || (p.last_crawled_at ? 1 : 0)}
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link to={`/providers/${p.id}`}>
                          <Button variant="ghost" size="sm" className="text-cyan-400 hover:bg-cyan-950">
                            Details
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          isLoading={researchingId === p.id}
                          onClick={() => handleStartResearch(p.id)}
                          className="text-slate-300 hover:text-cyan-400 hover:bg-slate-800"
                          title="Trigger re-scan"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(p.id)}
                          className="text-slate-400 hover:text-rose-400 hover:bg-rose-950/40"
                          title="Delete provider"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="p-4 border-t border-slate-800 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} providers
            </span>
            <Pagination
              currentPage={page}
              totalPages={Math.ceil(total / pageSize) || 1}
              totalItems={total}
              pageSize={pageSize}
              onPageChange={setPage}
            />
          </div>
        </div>
      )}

      {/* Add Provider Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Add Competitor / Service Provider">
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Provider Name"
            required
            value={newProvider.name}
            onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
            placeholder="e.g. Acme Agency"
          />

          <Input
            label="Website URL"
            type="url"
            required
            value={newProvider.website}
            onChange={(e) => setNewProvider({ ...newProvider, website: e.target.value })}
            placeholder="https://example.com"
          />

          <Select
            label="Category"
            value={newProvider.category}
            onChange={(e) =>
              setNewProvider({ ...newProvider, category: e.target.value as Provider['category'] })
            }
            options={[
              { label: 'Direct Competitor', value: 'direct_competitor' },
              { label: 'Close Competitor', value: 'close_competitor' },
              { label: 'Adjacent Provider', value: 'adjacent_provider' },
              { label: 'Pending Review', value: 'pending_review' },
            ]}
          />

          <Input
            label="Services (comma separated)"
            value={newProvider.services}
            onChange={(e) => setNewProvider({ ...newProvider, services: e.target.value })}
            placeholder="Personal Branding, Entity SEO, PR"
          />

          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              Create &amp; Save
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
