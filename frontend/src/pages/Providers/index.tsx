import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Building2,
  Plus,
  Search,
  ExternalLink,
  Sparkles,
  CheckCircle2,
  Globe,
  MapPin,
  Trash2,
} from 'lucide-react';
import { LinkedinIcon, TwitterIcon, InstagramIcon, YoutubeIcon } from '../../components/ui/SocialIcons';
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
import { formatDate } from '../../utils/format';

export const Providers: React.FC = () => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [isLoading, setIsLoading] = useState(true);

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
        page_size: 15,
        search: search || undefined,
        category: category || undefined,
      });
      setProviders(res.items);
      setTotal(res.total);
    } catch {
      // Demo fallback if fresh database
      setProviders([
        {
          id: 'sample_theperson',
          name: 'The Person',
          website: 'https://theperson.in/',
          domain: 'theperson.in',
          category: 'direct_competitor',
          similarity_score: 100,
          location: 'Bangalore / Mumbai',
          country: 'India',
          services: ['Google Knowledge Panel', 'Personal Branding', 'Entity SEO', 'Authority PR'],
          social_profiles: { linkedin: 'https://linkedin.com/company/thepersonin' },
          discovery_status: 'researched',
          verification_status: 'verified',
          last_crawled_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
      setTotal(1);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, [page, search, category]);

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
      fetchProviders();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create provider');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartResearch = async (id: string) => {
    setResearchingId(id);
    try {
      await startProviderResearch(id);
      fetchProviders();
      alert('Research and crawl job dispatched to background processor.');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Could not start research job');
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

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Service Providers</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Target providers offering Google Knowledge Panel, Entity SEO, and Personal Branding services.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/discovery">
            <Button variant="secondary" size="md" leftIcon={<Sparkles className="w-4 h-4 text-blue-600" />}>
              Discover via DDGS
            </Button>
          </Link>
          <Button variant="primary" size="md" onClick={() => setIsModalOpen(true)} leftIcon={<Plus className="w-4 h-4" />}>
            Add Provider
          </Button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2">
            <Input
              placeholder="Search providers by name, domain, service..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>
          <div>
            <Select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              options={[
                { label: 'All Categories', value: '' },
                { label: 'Direct Competitors', value: 'direct_competitor' },
                { label: 'Close Competitors', value: 'close_competitor' },
                { label: 'Adjacent Providers', value: 'adjacent_provider' },
                { label: 'Pending Review', value: 'pending_review' },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Providers Table / Cards */}
      {isLoading ? (
        <LoadingSpinner message="Fetching providers..." />
      ) : providers.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No service providers found"
          description="Add a provider manually or use the multi-source discovery engine to search for similar agencies."
          actionText="Add New Provider"
          onAction={() => setIsModalOpen(true)}
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-3 px-4">Provider</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Location</th>
                  <th className="py-3 px-4">Services Disclosed</th>
                  <th className="py-3 px-4">Social</th>
                  <th className="py-3 px-4">Last Crawled</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {providers.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3.5 px-4">
                      <Link to={`/providers/${p.id}`} className="font-semibold text-slate-900 hover:text-blue-600 block">
                        {p.name}
                      </Link>
                      {p.website && (
                        <a
                          href={p.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[11px] text-slate-400 hover:text-slate-600 flex items-center gap-1 mt-0.5"
                        >
                          <Globe className="w-3 h-3" /> {p.domain || p.website}
                        </a>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge
                        variant={
                          p.category === 'direct_competitor'
                            ? 'info'
                            : p.category === 'close_competitor'
                            ? 'purple'
                            : 'default'
                        }
                      >
                        {p.category.replace(/_/g, ' ')}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {p.location ? (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-slate-400" /> {p.location}
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-3.5 px-4 max-w-xs">
                      <div className="flex flex-wrap gap-1">
                        {p.services.slice(0, 3).map((s) => (
                          <span
                            key={s}
                            className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded text-[10px] truncate"
                          >
                            {s}
                          </span>
                        ))}
                        {p.services.length > 3 && (
                          <span className="text-[10px] text-slate-400">+{p.services.length - 3}</span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-1.5 text-slate-400">
                        {p.social_profiles?.linkedin && <LinkedinIcon className="w-3.5 h-3.5 hover:text-blue-600" />}
                        {p.social_profiles?.twitter && <TwitterIcon className="w-3.5 h-3.5 hover:text-sky-500" />}
                        {p.social_profiles?.instagram && <InstagramIcon className="w-3.5 h-3.5 hover:text-pink-600" />}
                        {p.social_profiles?.youtube && <YoutubeIcon className="w-3.5 h-3.5 hover:text-red-600" />}
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 text-[11px]">
                      {p.last_crawled_at ? (
                        <span className="flex items-center gap-1 text-emerald-600 font-medium">
                          <CheckCircle2 className="w-3 h-3" /> {formatDate(p.last_crawled_at)}
                        </span>
                      ) : (
                        <span className="text-slate-400">Not Crawled</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          isLoading={researchingId === p.id}
                          onClick={() => handleStartResearch(p.id)}
                          leftIcon={<Sparkles className="w-3.5 h-3.5 text-blue-600" />}
                          title="Crawl & Extract Clients"
                        >
                          Research
                        </Button>
                        <Link to={`/providers/${p.id}`}>
                          <Button variant="ghost" size="sm">
                            <ExternalLink className="w-3.5 h-3.5" />
                          </Button>
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(p.id)}
                          className="text-slate-400 hover:text-rose-600"
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
          <Pagination
            currentPage={page}
            totalPages={Math.ceil(total / 15) || 1}
            totalItems={total}
            pageSize={15}
            onPageChange={setPage}
          />
        </div>
      )}

      {/* Add Provider Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Add Service Provider"
        description="Add a competitor or related service provider for intelligence analysis."
        maxWidth="lg"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <Input
            label="Company Name *"
            required
            placeholder="e.g. The Person, Authority Brand"
            value={newProvider.name}
            onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
          />

          <Input
            label="Official Website URL *"
            type="url"
            required
            placeholder="https://example.com"
            value={newProvider.website}
            onChange={(e) => setNewProvider({ ...newProvider, website: e.target.value })}
          />

          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Provider Category"
              value={newProvider.category}
              onChange={(e) => setNewProvider({ ...newProvider, category: e.target.value as any })}
              options={[
                { label: 'Direct Competitor (Knowledge Panel / Entity SEO)', value: 'direct_competitor' },
                { label: 'Close Competitor (Personal Branding)', value: 'close_competitor' },
                { label: 'Adjacent Provider (Executive PR / Wikipedia)', value: 'adjacent_provider' },
                { label: 'Pending Review', value: 'pending_review' },
              ]}
            />
            <Input
              label="Country / Region"
              placeholder="e.g. India, United States"
              value={newProvider.country}
              onChange={(e) => setNewProvider({ ...newProvider, country: e.target.value })}
            />
          </div>

          <Input
            label="Location / Headquarter"
            placeholder="e.g. Bangalore, Mumbai"
            value={newProvider.location}
            onChange={(e) => setNewProvider({ ...newProvider, location: e.target.value })}
          />

          <Input
            label="Services (Comma separated)"
            placeholder="Knowledge Panel, Entity SEO, Personal Branding"
            value={newProvider.services}
            onChange={(e) => setNewProvider({ ...newProvider, services: e.target.value })}
          />

          <div className="pt-3 flex justify-end gap-2 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              Save Provider
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
