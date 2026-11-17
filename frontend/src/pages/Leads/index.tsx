import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  Search,
  Filter,
  Download,
  LayoutGrid,
  List,
  Sparkles,
  ArrowUpDown,
  Mail,
  Building,
  Award,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';
import { LinkedinIcon, TwitterIcon, InstagramIcon } from '../../components/ui/SocialIcons';
import { getLeads, updateLeadStage, deleteLead } from '../../services/leads';
import { exportLeads } from '../../services/reports';
import { Lead, CRMStage } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Badge } from '../../components/ui/Badge';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Pagination } from '../../components/ui/Pagination';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmModal } from '../../components/ui/ConfirmModal';
import { useToast } from '../../context/ToastContext';
import { formatScore, formatDateTime } from '../../utils/format';

const STAGES: CRMStage[] = [
  'discovered',
  'pending_verification',
  'verified',
  'qualified',
  'ready_for_outreach_review',
  'contacted',
  'replied',
  'interested',
  'converted',
  'closed',
  'disqualified',
  'do_not_contact',
];

export const Leads: React.FC = () => {
  const { toast } = useToast();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stageFilter, setStageFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [viewMode, setViewMode] = useState<'table' | 'kanban'>('table');
  const [isLoading, setIsLoading] = useState(true);
  const [leadToDelete, setLeadToDelete] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchLeads = async () => {
    setIsLoading(true);
    try {
      const pageSize = viewMode === 'kanban' ? 100 : 20;
      const res = await getLeads({
        page: viewMode === 'kanban' ? 1 : page,
        page_size: pageSize,
        crm_stage: stageFilter || undefined,
        lead_priority: priorityFilter || undefined,
      });
      setLeads(res.items);
      setTotal(res.total);
    } catch (err: any) {
      setLeads([]);
      setTotal(0);
      toast.error(err.response?.data?.detail || 'Failed to load leads from CRM');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [page, stageFilter, priorityFilter, viewMode]);

  const handleStageChange = async (leadId: string, newStage: CRMStage) => {
    try {
      await updateLeadStage(leadId, newStage);
      toast.success(`Lead moved to ${newStage.replace(/_/g, ' ')}`);
      fetchLeads();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update lead stage');
    }
  };

  const handleDeleteLead = async () => {
    if (!leadToDelete) return;
    setIsDeleting(true);
    try {
      await deleteLead(leadToDelete);
      toast.success('Lead deleted successfully');
      setLeadToDelete(null);
      fetchLeads();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete lead');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">CRM Prospect Pipeline</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Verified professionals and founders discovered through provider case studies, testimonials & portfolios.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === 'table' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
              title="Table View"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('kanban')}
              className={`p-1.5 rounded-md transition-colors ${
                viewMode === 'kanban' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
              title="Kanban View"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>

          <Button
            variant="outline"
            size="md"
            onClick={() => exportLeads('csv', stageFilter)}
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export CSV
          </Button>
          <Button
            variant="outline"
            size="md"
            onClick={() => exportLeads('excel', stageFilter)}
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export Excel
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <Select
              label="CRM Stage"
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              options={[
                { label: 'All Stages', value: '' },
                { label: 'Discovered', value: 'discovered' },
                { label: 'Pending Verification', value: 'pending_verification' },
                { label: 'Verified', value: 'verified' },
                { label: 'Qualified', value: 'qualified' },
                { label: 'Ready for Outreach Review', value: 'ready_for_outreach_review' },
                { label: 'Contacted', value: 'contacted' },
                { label: 'Replied', value: 'replied' },
                { label: 'Interested', value: 'interested' },
                { label: 'Converted', value: 'converted' },
                { label: 'Disqualified', value: 'disqualified' },
                { label: 'Do Not Contact', value: 'do_not_contact' },
              ]}
            />
          </div>
          <div>
            <Select
              label="Lead Priority"
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              options={[
                { label: 'All Priorities', value: '' },
                { label: 'High Priority (Score ≥ 80)', value: 'high' },
                { label: 'Medium Priority (Score 60-79)', value: 'medium' },
                { label: 'Low Priority (Score < 60)', value: 'low' },
              ]}
            />
          </div>
          <div className="flex items-end">
            <Button
              variant="ghost"
              size="md"
              className="w-full text-slate-500"
              onClick={() => {
                setStageFilter('');
                setPriorityFilter('');
              }}
            >
              Reset Filters
            </Button>
          </div>
        </div>
      </Card>

      {/* Content View: Table or Kanban */}
      {isLoading ? (
        <LoadingSpinner message="Loading CRM prospect records..." />
      ) : leads.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No leads match your criteria"
          description="Try resetting your filters or run a provider research crawl to discover new client references."
        />
      ) : viewMode === 'table' ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-3 px-4">Prospect Name</th>
                  <th className="py-3 px-4">Designation & Company</th>
                  <th className="py-3 px-4">Industry</th>
                  <th className="py-3 px-4">Score</th>
                  <th className="py-3 px-4">CRM Stage</th>
                  <th className="py-3 px-4">Contact Route</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {leads.map((l) => {
                  const scoreInfo = formatScore(l.lead_score);
                  const contact = l.contact;
                  const company = l.company;

                  return (
                    <tr key={l.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3.5 px-4">
                        <Link to={`/leads/${l.id}`} className="font-semibold text-slate-900 hover:text-blue-600 block">
                          {contact?.full_name || 'Prospect ' + l.id.slice(-6)}
                        </Link>
                        {contact?.do_not_contact && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-rose-600 font-semibold mt-0.5">
                            <ShieldAlert className="w-3 h-3" /> Do Not Contact
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="text-slate-800 font-medium">{contact?.designation || 'Executive'}</div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
                          <Building className="w-3 h-3 text-slate-400" />
                          {company?.name || contact?.company_name || 'Independent'}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">
                        {company?.industry || 'Professional Services'}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="inline-flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded font-bold border text-xs ${scoreInfo.bgClass} ${scoreInfo.colorClass}`}
                          >
                            {l.lead_score}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <StatusBadge stage={l.crm_stage} />
                      </td>
                      <td className="py-3.5 px-4 text-slate-500">
                        {contact?.business_contacts?.email && (
                          <div className="flex items-center gap-1 text-emerald-700 font-mono text-[11px] mb-1">
                            <Mail className="w-3 h-3 text-emerald-600" /> {contact.business_contacts.email}
                          </div>
                        )}
                        <div className="flex items-center gap-2">
                          {(contact?.professional_urls?.linkedin || contact?.linkedin_url) && (
                            <a
                              href={contact.professional_urls?.linkedin || contact.linkedin_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 hover:underline font-sans text-[11px] font-medium"
                              title="LinkedIn Profile"
                            >
                              <LinkedinIcon className="w-3 h-3" /> LinkedIn
                            </a>
                          )}
                          {contact?.professional_urls?.twitter && (
                            <a
                              href={contact.professional_urls.twitter}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-sky-500 hover:text-sky-700"
                              title="Twitter / X"
                            >
                              <TwitterIcon className="w-3 h-3" />
                            </a>
                          )}
                          {contact?.professional_urls?.instagram && (
                            <a
                              href={contact.professional_urls.instagram}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-pink-600 hover:text-pink-800"
                              title="Instagram"
                            >
                              <InstagramIcon className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                        {!contact?.business_contacts?.email && !contact?.professional_urls?.linkedin && !contact?.linkedin_url && (
                          <span className="text-slate-400">Website enquiry only</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link to={`/leads/${l.id}`}>
                          <Button variant="ghost" size="sm" rightIcon={<ChevronRight className="w-3.5 h-3.5" />}>
                            Review
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination
            currentPage={page}
            totalPages={Math.ceil(total / 20) || 1}
            totalItems={total}
            pageSize={20}
            onPageChange={setPage}
          />
        </div>
      ) : (
        /* Kanban View - All 12 Canonical CRM Stages */
        <div className="flex gap-4 overflow-x-auto pb-6 pt-1">
          {STAGES.map((stage) => {
            const stageLeads = leads.filter((l) => l.crm_stage === stage);
            return (
              <div key={stage} className="w-80 shrink-0 bg-slate-50/80 rounded-2xl p-3.5 border border-slate-200/80 flex flex-col max-h-[calc(100vh-280px)]">
                <div className="flex items-center justify-between mb-3 px-1.5 pb-2.5 border-b border-slate-200/60">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-800 capitalize">
                      {stage.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <span className="text-[11px] bg-white text-slate-700 px-2.5 py-0.5 rounded-full font-bold border border-slate-200 shadow-2xs">
                    {stageLeads.length}
                  </span>
                </div>
                <div className="space-y-3 overflow-y-auto pr-1 flex-1">
                  {stageLeads.map((l) => (
                    <Card key={l.id} className="p-3.5 bg-white shadow-xs hover:shadow-md transition-all border border-slate-200/80 group">
                      <div className="flex items-start justify-between gap-2">
                        <Link to={`/leads/${l.id}`} className="font-bold text-xs text-slate-900 hover:text-blue-600 block line-clamp-1">
                          {l.contact?.full_name || 'Prospect'}
                        </Link>
                        <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
                          {l.lead_score}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 truncate mt-1">
                        {l.contact?.designation ? `${l.contact.designation} • ` : ''}{l.company?.name || 'Company'}
                      </div>
                      <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between gap-2">
                        <select
                          value={l.crm_stage}
                          onChange={(e) => handleStageChange(l.id, e.target.value as CRMStage)}
                          className="text-[10px] font-medium bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 text-slate-700 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
                          title="Move stage"
                        >
                          {STAGES.map((s) => (
                            <option key={s} value={s}>
                              Move: {s.replace(/_/g, ' ')}
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={() => setLeadToDelete(l.id)}
                          className="opacity-0 group-hover:opacity-100 text-[10px] text-rose-500 hover:text-rose-700 hover:underline transition-opacity"
                        >
                          Delete
                        </button>
                      </div>
                    </Card>
                  ))}
                  {stageLeads.length === 0 && (
                    <div className="text-center py-8 text-slate-400 text-xs border border-dashed border-slate-200 rounded-xl bg-white/50">
                      No leads in {stage.replace(/_/g, ' ')}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Confirmation Modal for Lead Deletion */}
      <ConfirmModal
        isOpen={!!leadToDelete}
        title="Delete CRM Lead"
        message="Are you sure you want to delete this lead? This action will remove the lead record and log an audit event. Discovered contacts and companies will not be deleted."
        confirmText="Delete Lead"
        confirmVariant="danger"
        isLoading={isDeleting}
        onConfirm={handleDeleteLead}
        onCancel={() => setLeadToDelete(null)}
      />
    </div>
  );
};
