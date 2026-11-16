import React, { useState, useEffect } from 'react';
import {
  Radar,
  Plus,
  Search,
  ExternalLink,
  Edit2,
  Trash2,
  RefreshCw,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Globe,
  Tag,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { Modal } from '../../components/ui/Modal';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import {
  getCompetitors,
  createCompetitor,
  updateCompetitor,
  deleteCompetitor,
  discoverCompetitors,
  runCompetitorResearch,
} from '../../services/competitors';
import { Competitor } from '../../types';

export const CompetitorIntelligence: React.FC = () => {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isDiscoverModalOpen, setIsDiscoverModalOpen] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);

  // Form state for add/edit
  const [editTarget, setEditTarget] = useState<Competitor | null>(null);
  const [formName, setFormName] = useState('');
  const [formWebsite, setFormWebsite] = useState('');
  const [formCategory, setFormCategory] = useState('');
  const [formServices, setFormServices] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Discover modal state
  const [discoverSeed, setDiscoverSeed] = useState('');
  const [discoverCategory, setDiscoverCategory] = useState('');
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveredList, setDiscoveredList] = useState<any[]>([]);

  // Research execution state
  const [researchingId, setResearchingId] = useState<string | null>(null);

  const fetchCompetitors = async () => {
    setIsLoading(true);
    try {
      const res = await getCompetitors({ search: searchQuery || undefined });
      setCompetitors(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('Failed to fetch competitors:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCompetitors();
  }, [searchQuery]);

  const handleOpenAdd = (comp?: Competitor) => {
    if (comp) {
      setEditTarget(comp);
      setFormName(comp.name);
      setFormWebsite(comp.website || '');
      setFormCategory(comp.business_category || '');
      setFormServices((comp.services || []).join(', '));
    } else {
      setEditTarget(null);
      setFormName('');
      setFormWebsite('');
      setFormCategory('Agency / Marketing');
      setFormServices('');
    }
    setIsAddModalOpen(true);
  };

  const handleSaveCompetitor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) return;

    setIsSaving(true);
    try {
      const srvList = formServices.split(',').map((s) => s.trim()).filter(Boolean);
      if (editTarget) {
        await updateCompetitor(editTarget.id, {
          name: formName,
          website: formWebsite,
          business_category: formCategory,
          services: srvList,
        });
      } else {
        await createCompetitor({
          name: formName,
          website: formWebsite,
          business_category: formCategory,
          services: srvList,
        });
      }
      setIsAddModalOpen(false);
      fetchCompetitors();
    } catch (err) {
      console.error('Save competitor failed:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTargetId) return;
    try {
      await deleteCompetitor(deleteTargetId);
      setDeleteTargetId(null);
      fetchCompetitors();
    } catch (err) {
      console.error('Delete competitor failed:', err);
    }
  };

  const handleDiscover = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!discoverSeed.trim()) return;

    setIsDiscovering(true);
    try {
      const items = await discoverCompetitors({
        seed_terms: discoverSeed,
        category: discoverCategory || undefined,
      });
      setDiscoveredList(items);
    } catch (err) {
      console.error('Discover failed:', err);
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleAddDiscovered = async (item: any) => {
    try {
      await createCompetitor({
        name: item.name,
        website: item.website,
        business_category: item.suggested_category,
      });
      fetchCompetitors();
      setDiscoveredList((prev) =>
        prev.map((d) => (d.domain === item.domain ? { ...d, already_saved: true } : d))
      );
    } catch (err) {
      console.error('Add discovered failed:', err);
    }
  };

  const handleRunResearch = async (comp: Competitor) => {
    setResearchingId(comp.id);
    try {
      await runCompetitorResearch(comp.id);
      fetchCompetitors();
    } catch (err) {
      console.error('Run research failed:', err);
    } finally {
      setResearchingId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Competitor Intelligence</h1>
          <p className="text-xs text-slate-500 mt-1">
            Monitor providers, competitive digital offerings, client reference footprints, and advertising references.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setIsDiscoverModalOpen(true)}>
            <Sparkles className="w-3.5 h-3.5 mr-1.5" />
            Discover Competitors
          </Button>
          <Button variant="primary" size="sm" onClick={() => handleOpenAdd()}>
            <Plus className="w-3.5 h-3.5 mr-1.5" />
            Add Competitor
          </Button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <Card className="p-4 flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search tracked competitors by name, domain, or category..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-slate-200 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
        <Button variant="secondary" size="sm" onClick={fetchCompetitors}>
          <RefreshCw className="w-3.5 h-3.5" />
        </Button>
      </Card>

      {/* Competitors List */}
      {isLoading ? (
        <Card className="p-12 flex justify-center">
          <LoadingSpinner message="Loading competitor records..." />
        </Card>
      ) : competitors.length === 0 ? (
        <Card className="p-12">
          <EmptyState
            title="No Competitors Tracked"
            description="Add a competitor manually or use the Discovery tool to automatically find industry providers."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {competitors.map((comp) => (
            <Card key={comp.id} className="p-5 flex flex-col justify-between hover:shadow-md transition-shadow">
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 line-clamp-1">{comp.name}</h3>
                    <Badge variant="info" className="mt-1">
                      {comp.business_category || 'Provider'}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenAdd(comp)}
                      className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => setDeleteTargetId(comp.id)}
                      className="p-1 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {comp.website && (
                  <a
                    href={comp.website}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1 font-mono truncate"
                  >
                    <Globe className="w-3 h-3 text-slate-400 shrink-0" />
                    <span className="truncate">{comp.website}</span>
                    <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                  </a>
                )}

                {comp.services && comp.services.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {comp.services.slice(0, 3).map((srv, idx) => (
                      <span key={idx} className="text-[10px] bg-slate-50 text-slate-600 px-2 py-0.5 rounded-full border border-slate-100">
                        {srv}
                      </span>
                    ))}
                  </div>
                )}

                {comp.client_references && comp.client_references.length > 0 && (
                  <div className="p-2.5 rounded-xl bg-slate-50/80 border border-slate-100 text-[11px] text-slate-600">
                    <span className="font-bold text-slate-800">
                      Discovered Clients ({comp.client_references.length}):
                    </span>
                    <p className="mt-0.5 line-clamp-2 text-[10px] text-slate-500">
                      {comp.client_references[0]?.evidence || 'Evidence captured'}
                    </p>
                  </div>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[10px] text-slate-400">
                  {comp.last_research_date
                    ? `Scanned: ${new Date(comp.last_research_date).toLocaleDateString()}`
                    : 'Not scanned yet'}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleRunResearch(comp)}
                  isLoading={researchingId === comp.id}
                >
                  <Radar className="w-3 h-3 mr-1 text-indigo-600" />
                  Scan Intelligence
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Add / Edit Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title={editTarget ? 'Edit Competitor' : 'Add New Competitor'}
      >
        <form onSubmit={handleSaveCompetitor} className="space-y-4">
          <Input
            label="Competitor Name *"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            placeholder="e.g. Acme Agency"
            required
          />
          <Input
            label="Website URL"
            value={formWebsite}
            onChange={(e) => setFormWebsite(e.target.value)}
            placeholder="https://..."
          />
          <Input
            label="Business Category"
            value={formCategory}
            onChange={(e) => setFormCategory(e.target.value)}
            placeholder="e.g. SEO & Knowledge Panel Agency"
          />
          <Input
            label="Published Services (Comma-separated)"
            value={formServices}
            onChange={(e) => setFormServices(e.target.value)}
            placeholder="e.g. Executive PR, Wikipedia, Personal Branding"
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" size="sm" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isSaving}>
              Save Competitor
            </Button>
          </div>
        </form>
      </Modal>

      {/* Discover Competitors Modal */}
      <Modal
        isOpen={isDiscoverModalOpen}
        onClose={() => setIsDiscoverModalOpen(false)}
        title="Discover Competitors & Providers"
      >
        <div className="space-y-4">
          <form onSubmit={handleDiscover} className="space-y-3">
            <Input
              label="Seed Query / Category *"
              placeholder="e.g. Personal branding agency India"
              value={discoverSeed}
              onChange={(e) => setDiscoverSeed(e.target.value)}
              required
            />
            <div className="flex justify-end">
              <Button type="submit" variant="primary" size="sm" isLoading={isDiscovering}>
                <Search className="w-3.5 h-3.5 mr-1" />
                Find Competitors
              </Button>
            </div>
          </form>

          {isDiscovering ? (
            <div className="py-6 flex justify-center">
              <LoadingSpinner message="Searching provider directories..." />
            </div>
          ) : (
            discoveredList.length > 0 && (
              <div className="space-y-2 max-h-80 overflow-y-auto divide-y divide-slate-100 pr-1">
                {discoveredList.map((d, idx) => (
                  <div key={idx} className="pt-2.5 first:pt-0 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <h4 className="text-xs font-bold text-slate-900 truncate">{d.name}</h4>
                      <p className="text-[11px] text-slate-500 font-mono truncate">{d.website}</p>
                    </div>
                    {d.already_saved ? (
                      <span className="text-[11px] text-emerald-600 font-bold shrink-0">Saved</span>
                    ) : (
                      <Button variant="secondary" size="sm" onClick={() => handleAddDiscovered(d)}>
                        <Plus className="w-3 h-3 mr-1" />
                        Add
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={Boolean(deleteTargetId)}
        onClose={() => setDeleteTargetId(null)}
        onConfirm={handleDelete}
        title="Delete Competitor Record?"
        message="Are you sure you want to remove this competitor record? Existing leads and references in CRM will be preserved."
        confirmLabel="Delete Competitor"
      />
    </div>
  );
};
