import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  Search,
  Mail,
  Phone,
  Globe,
  ShieldCheck,
  ShieldAlert,
  Download,
  Trash2,
  Sparkles,
  ExternalLink,
  Plus,
  CheckCircle2,
  XCircle,
  Eye,
  RefreshCw,
  X,
} from 'lucide-react';
import { LinkedinIcon, TwitterIcon, InstagramIcon } from '../../components/ui/SocialIcons';
import {
  getContacts,
  suppressContact,
  deleteContact,
  enrichContact,
  enrichBatch,
  verifyContactChannel,
  rejectContactChannel,
  addContactChannel,
} from '../../services/contacts';
import { exportContacts } from '../../services/reports';
import { Contact, ContactChannel, EnrichmentStatus } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Badge } from '../../components/ui/Badge';
import { Pagination } from '../../components/ui/Pagination';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatDate } from '../../utils/format';

export const Contacts: React.FC = () => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [verificationFilter, setVerificationFilter] = useState('');
  const [enrichmentFilter, setEnrichmentFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  // Bulk selection & enrichment state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [enrichingIds, setEnrichingIds] = useState<Set<string>>(new Set());
  const [isBulkEnriching, setIsBulkEnriching] = useState(false);

  // Detail / Review Modal State
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);
  const [isAddChannelOpen, setIsAddChannelOpen] = useState(false);

  // New Channel Form State
  const [newChannelType, setNewChannelType] = useState<'email' | 'phone' | 'contact_form' | 'social'>('email');
  const [newChannelScope, setNewChannelScope] = useState<'person_direct_work' | 'company_generic' | 'company_switchboard'>('person_direct_work');
  const [newChannelValue, setNewChannelValue] = useState('');
  const [newChannelSourceUrl, setNewChannelSourceUrl] = useState('');
  const [newChannelEvidence, setNewChannelEvidence] = useState('');

  const fetchContacts = async () => {
    setIsLoading(true);
    try {
      const res = await getContacts({
        page,
        page_size: 20,
        search: search || undefined,
        verification_status: verificationFilter || undefined,
        enrichment_status: enrichmentFilter || undefined,
      });
      setContacts(res.items);
      setTotal(res.total);
    } catch {
      setContacts([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchContacts();
  }, [page, search, verificationFilter, enrichmentFilter]);

  const toggleSelectAll = () => {
    if (selectedIds.size === contacts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(contacts.map((c) => c.id)));
    }
  };

  const toggleSelectContact = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleEnrichSingle = async (id: string) => {
    setEnrichingIds((prev) => new Set([...prev, id]));
    try {
      const res = await enrichContact(id);
      if (selectedContact && selectedContact.id === id) {
        setSelectedContact(res.contact);
      }
      await fetchContacts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Enrichment failed');
    } finally {
      setEnrichingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleEnrichSelected = async () => {
    if (selectedIds.size === 0) return;
    setIsBulkEnriching(true);
    try {
      await enrichBatch(Array.from(selectedIds));
      setSelectedIds(new Set());
      await fetchContacts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Batch enrichment failed');
    } finally {
      setIsBulkEnriching(false);
    }
  };

  const handleSuppress = async (id: string) => {
    if (confirm('Mark this contact as Do-Not-Contact and add to suppression list?')) {
      await suppressContact(id, 'User requested suppression');
      fetchContacts();
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Delete this contact?')) {
      await deleteContact(id);
      fetchContacts();
    }
  };

  const handleVerifyChannel = async (channelIdx: number) => {
    if (!selectedContact) return;
    try {
      const updated = await verifyContactChannel(selectedContact.id, channelIdx);
      setSelectedContact(updated);
      fetchContacts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Channel verification failed');
    }
  };

  const handleRejectChannel = async (channelIdx: number) => {
    if (!selectedContact) return;
    const reason = prompt('Reason for rejection:', 'Not a valid direct contact');
    if (!reason) return;
    try {
      const updated = await rejectContactChannel(selectedContact.id, channelIdx, reason);
      setSelectedContact(updated);
      fetchContacts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Channel rejection failed');
    }
  };

  const handleAddChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedContact || !newChannelValue) return;
    try {
      const updated = await addContactChannel(selectedContact.id, {
        type: newChannelType,
        scope: newChannelScope,
        value: newChannelValue,
        source_url: newChannelSourceUrl,
        evidence_quote: newChannelEvidence,
        source_type: 'manual',
        verification_status: 'source_verified',
      });
      setSelectedContact(updated);
      setIsAddChannelOpen(false);
      setNewChannelValue('');
      setNewChannelSourceUrl('');
      setNewChannelEvidence('');
      fetchContacts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add contact channel');
    }
  };

  // Channel helper extractors
  const getDirectEmail = (c: Contact): ContactChannel | undefined => {
    return c.contact_channels?.find(
      (ch) => ch.type === 'email' && ch.scope === 'person_direct_work' && ch.verification_status !== 'rejected'
    );
  };

  const getDirectPhone = (c: Contact): ContactChannel | undefined => {
    return c.contact_channels?.find(
      (ch) => ch.type === 'phone' && ch.scope === 'person_direct_work' && ch.verification_status !== 'rejected'
    );
  };

  const getCompanyContact = (c: Contact): ContactChannel | undefined => {
    return c.contact_channels?.find(
      (ch) =>
        (ch.scope === 'company_generic' || ch.scope === 'company_switchboard' || ch.type === 'contact_form') &&
        ch.verification_status !== 'rejected'
    );
  };

  const renderEnrichmentBadge = (status?: EnrichmentStatus) => {
    switch (status) {
      case 'enriched':
        return <Badge variant="success">Enriched</Badge>;
      case 'partially_enriched':
        return <Badge variant="purple">Company Found</Badge>;
      case 'in_progress':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
            <RefreshCw className="w-3 h-3 animate-spin" /> In Progress
          </span>
        );
      case 'no_public_contacts_found':
        return <Badge variant="default">No Public Contacts</Badge>;
      case 'failed':
        return <Badge variant="danger">Failed</Badge>;
      default:
        return <Badge variant="default">Not Started</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Professional Contacts & Enrichment</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Verified client contacts with public business email, phone numbers, and official company channels.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selectedIds.size > 0 && (
            <Button
              variant="primary"
              size="md"
              onClick={handleEnrichSelected}
              disabled={isBulkEnriching}
              leftIcon={<Sparkles className="w-4 h-4" />}
            >
              {isBulkEnriching ? 'Enriching...' : `Enrich Selected (${selectedIds.size})`}
            </Button>
          )}
          <Button
            variant="outline"
            size="md"
            onClick={() => exportContacts(verificationFilter)}
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export Contacts
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="sm:col-span-2">
            <Input
              placeholder="Search by contact name, company, email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>
          <div>
            <Select
              value={enrichmentFilter}
              onChange={(e) => setEnrichmentFilter(e.target.value)}
              options={[
                { label: 'All Enrichment Statuses', value: '' },
                { label: 'Enriched (Direct Contact)', value: 'enriched' },
                { label: 'Partially Enriched', value: 'partially_enriched' },
                { label: 'In Progress', value: 'in_progress' },
                { label: 'No Public Contacts', value: 'no_public_contacts_found' },
                { label: 'Not Started', value: 'not_started' },
              ]}
            />
          </div>
          <div>
            <Select
              value={verificationFilter}
              onChange={(e) => setVerificationFilter(e.target.value)}
              options={[
                { label: 'All Verifications', value: '' },
                { label: 'Human Approved', value: 'human_approved' },
                { label: 'Source Verified', value: 'contact_source_verified' },
                { label: 'Company Verified', value: 'company_verified' },
                { label: 'Discovered', value: 'discovered' },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Contacts Table */}
      {isLoading ? (
        <LoadingSpinner message="Loading enriched contacts..." />
      ) : contacts.length === 0 ? (
        <EmptyState
          icon={UserCheck}
          title="No contacts found"
          description="Contacts will automatically appear as you research service providers."
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-3 px-3 w-8">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === contacts.length && contacts.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                  </th>
                  <th className="py-3 px-3">Contact Name</th>
                  <th className="py-3 px-3">Designation & Company</th>
                  <th className="py-3 px-3">Direct Business Email</th>
                  <th className="py-3 px-3">Direct Phone</th>
                  <th className="py-3 px-3">Company Contact</th>
                  <th className="py-3 px-3">LinkedIn</th>
                  <th className="py-3 px-3">Enrichment</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {contacts.map((c) => {
                  const directEmail = getDirectEmail(c);
                  const directPhone = getDirectPhone(c);
                  const companyContact = getCompanyContact(c);
                  const isEnriching = enrichingIds.has(c.id);

                  return (
                    <tr key={c.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-3">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(c.id)}
                          onChange={() => toggleSelectContact(c.id)}
                          className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        />
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-900">
                        <button
                          onClick={() => {
                            setSelectedContact(c);
                            setIsDetailModalOpen(true);
                          }}
                          className="hover:text-blue-600 text-left font-semibold"
                        >
                          {c.full_name}
                        </button>
                        {c.do_not_contact && (
                          <span className="block text-[10px] text-rose-600 font-semibold mt-0.5">
                            Do Not Contact
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        <div className="text-slate-800 font-medium">{c.designation || 'Executive'}</div>
                        <div className="text-[11px] text-slate-500">{c.company_name || 'Independent'}</div>
                      </td>
                      <td className="py-3 px-3">
                        {directEmail ? (
                          <div>
                            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-emerald-800 font-medium bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                              <Mail className="w-3 h-3 text-emerald-600" /> {directEmail.value}
                            </span>
                            <span className="block text-[10px] text-emerald-700 capitalize mt-0.5">
                              {directEmail.verification_status.replace(/_/g, ' ')}
                            </span>
                          </div>
                        ) : c.business_contacts?.email ? (
                          <span className="font-mono text-[11px] text-slate-700">
                            {c.business_contacts.email}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Not publicly found</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {directPhone ? (
                          <div>
                            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-blue-800 font-medium bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                              <Phone className="w-3 h-3 text-blue-600" /> {directPhone.value}
                            </span>
                            <span className="block text-[10px] text-blue-700 capitalize mt-0.5">
                              {directPhone.verification_status.replace(/_/g, ' ')}
                            </span>
                          </div>
                        ) : c.business_contacts?.phone ? (
                          <span className="font-mono text-[11px] text-slate-700">
                            {c.business_contacts.phone}
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Not found</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {companyContact ? (
                          <div className="text-[11px]">
                            <span className="font-medium text-slate-700 capitalize">{companyContact.type.replace('_', ' ')}:</span>
                            <div className="font-mono text-[10px] text-slate-600 truncate max-w-[140px]" title={companyContact.value}>
                              {companyContact.value}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">None</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {(c.professional_urls?.linkedin || c.linkedin_url) ? (
                          <a
                            href={c.professional_urls?.linkedin || c.linkedin_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 hover:underline font-medium text-[11px]"
                          >
                            <LinkedinIcon className="w-3.5 h-3.5" /> Profile
                          </a>
                        ) : (
                          <span className="text-slate-400 italic">—</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {renderEnrichmentBadge(c.enrichment_status)}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEnrichSingle(c.id)}
                            disabled={isEnriching}
                            className="text-blue-600 hover:bg-blue-50"
                            title="Run Public Contact Discovery"
                          >
                            {isEnriching ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Sparkles className="w-3.5 h-3.5" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedContact(c);
                              setIsDetailModalOpen(true);
                            }}
                            className="text-slate-500 hover:text-slate-900"
                            title="View Contact Dossier & Verification"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </Button>
                          {!c.do_not_contact && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleSuppress(c.id)}
                              className="text-slate-400 hover:text-rose-600"
                              title="Suppress contact"
                            >
                              <ShieldAlert className="w-3.5 h-3.5" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(c.id)}
                            className="text-slate-400 hover:text-rose-600"
                            title="Delete contact"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="p-3 border-t border-slate-200">
            <Pagination
              currentPage={page}
              totalPages={Math.ceil(total / 20)}
              totalItems={total}
              pageSize={20}
              onPageChange={(p) => setPage(p)}
            />
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* Contact Dossier / Detail Modal with Human Review Controls */}
      {/* ===================================================================== */}
      {isDetailModalOpen && selectedContact && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto border border-slate-200">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between z-10">
              <div>
                <h2 className="text-lg font-bold text-slate-900 tracking-tight flex items-center gap-2">
                  {selectedContact.full_name}
                  {renderEnrichmentBadge(selectedContact.enrichment_status)}
                </h2>
                <p className="text-xs text-slate-500">
                  {selectedContact.designation || 'Executive'} • {selectedContact.company_name || 'Independent'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleEnrichSingle(selectedContact.id)}
                  disabled={enrichingIds.has(selectedContact.id)}
                  leftIcon={<Sparkles className="w-3.5 h-3.5 text-blue-600" />}
                >
                  {enrichingIds.has(selectedContact.id) ? 'Enriching...' : 'Re-Run Discovery'}
                </Button>
                <button
                  onClick={() => setIsDetailModalOpen(false)}
                  className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6">
              {/* Professional & Company Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div>
                  <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Professional Identity</h4>
                  <div className="space-y-1 text-xs">
                    <div><span className="text-slate-500">Full Name:</span> <span className="font-semibold text-slate-800">{selectedContact.full_name}</span></div>
                    <div><span className="text-slate-500">Designation:</span> <span className="font-semibold text-slate-800">{selectedContact.designation || '—'}</span></div>
                    <div><span className="text-slate-500">Verification:</span> <span className="font-semibold capitalize text-indigo-700">{selectedContact.contact_verification_status.replace(/_/g, ' ')}</span></div>
                  </div>
                </div>
                <div>
                  <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Company Association</h4>
                  <div className="space-y-1 text-xs">
                    <div><span className="text-slate-500">Company:</span> <span className="font-semibold text-slate-800">{selectedContact.company_name || '—'}</span></div>
                    <div><span className="text-slate-500">Discovered At:</span> <span className="text-slate-700">{formatDate(selectedContact.created_at)}</span></div>
                    {selectedContact.last_enriched_at && (
                      <div><span className="text-slate-500">Last Enriched:</span> <span className="text-slate-700">{formatDate(selectedContact.last_enriched_at)}</span></div>
                    )}
                  </div>
                </div>
              </div>

              {/* Direct & Company Contact Channels */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    Public Contact Channels ({selectedContact.contact_channels?.length || 0})
                  </h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsAddChannelOpen(true)}
                    leftIcon={<Plus className="w-3.5 h-3.5" />}
                    className="text-blue-600 hover:bg-blue-50 text-xs"
                  >
                    Add Channel Manually
                  </Button>
                </div>

                {(!selectedContact.contact_channels || selectedContact.contact_channels.length === 0) ? (
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-500 text-center">
                    No public contact channels discovered yet. Click "Re-Run Discovery" to crawl company & directory sources.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedContact.contact_channels.map((ch, idx) => (
                      <div
                        key={idx}
                        className={`p-3.5 rounded-xl border text-xs transition-all ${
                          ch.verification_status === 'rejected'
                            ? 'bg-rose-50/40 border-rose-200 opacity-60'
                            : ch.scope === 'person_direct_work'
                            ? 'bg-emerald-50/40 border-emerald-200'
                            : 'bg-slate-50/70 border-slate-200'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-[10px] uppercase px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-600">
                                {ch.type}
                              </span>
                              <span className="font-semibold text-slate-800 font-mono text-xs">{ch.value}</span>
                              <Badge
                                variant={
                                  ch.verification_status === 'source_verified' || ch.verification_status === 'human_reviewed'
                                    ? 'success'
                                    : ch.verification_status === 'format_checked'
                                    ? 'purple'
                                    : ch.verification_status === 'rejected'
                                    ? 'danger'
                                    : 'default'
                                }
                              >
                                {ch.verification_status.replace(/_/g, ' ')}
                              </Badge>
                              <span className="text-[10px] text-slate-500 font-medium">({ch.scope.replace(/_/g, ' ')})</span>
                            </div>

                            {/* Validation indicators */}
                            <div className="flex items-center gap-3 text-[11px] text-slate-500 pt-0.5">
                              {ch.type === 'email' && (
                                <>
                                  <span className={ch.syntax_valid ? 'text-emerald-700' : 'text-rose-600'}>
                                    Syntax: {ch.syntax_valid ? 'Valid ✓' : 'Invalid ✗'}
                                  </span>
                                  {ch.mx_record_found !== undefined && (
                                    <span className={ch.mx_record_found ? 'text-emerald-700' : 'text-slate-500'}>
                                      DNS MX: {ch.mx_record_found ? 'Found ✓' : 'None'}
                                    </span>
                                  )}
                                </>
                              )}
                              {ch.source_url && (
                                <a
                                  href={ch.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-blue-600 hover:underline inline-flex items-center gap-0.5"
                                >
                                  Source Link <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              )}
                            </div>

                            {/* Evidence quote */}
                            {ch.evidence_quote && (
                              <div className="text-[11px] italic text-slate-600 bg-white/80 p-2 rounded border border-slate-200/60 mt-1">
                                "{ch.evidence_quote}"
                              </div>
                            )}
                          </div>

                          {/* Review Actions */}
                          <div className="flex items-center gap-1.5 shrink-0">
                            {ch.verification_status !== 'human_reviewed' && ch.verification_status !== 'rejected' && (
                              <button
                                onClick={() => handleVerifyChannel(idx)}
                                className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-medium flex items-center gap-1"
                                title="Confirm this contact detail is correct"
                              >
                                <CheckCircle2 className="w-3 h-3" /> Verify
                              </button>
                            )}
                            {ch.verification_status !== 'rejected' && (
                              <button
                                onClick={() => handleRejectChannel(idx)}
                                className="px-2 py-1 bg-white hover:bg-rose-50 text-rose-600 border border-rose-200 rounded text-[11px] font-medium flex items-center gap-1"
                                title="Reject incorrect or bounced contact detail"
                              >
                                <XCircle className="w-3 h-3" /> Reject
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Add Channel Modal */}
              {isAddChannelOpen && (
                <form onSubmit={handleAddChannel} className="p-4 bg-blue-50/60 rounded-xl border border-blue-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <h5 className="text-xs font-bold text-blue-900">Add Missing Contact Detail Manually</h5>
                    <button
                      type="button"
                      onClick={() => setIsAddChannelOpen(false)}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Channel Type</label>
                      <select
                        value={newChannelType}
                        onChange={(e: any) => setNewChannelType(e.target.value)}
                        className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
                      >
                        <option value="email">Email</option>
                        <option value="phone">Phone</option>
                        <option value="contact_form">Contact Form</option>
                        <option value="social">Social Profile</option>
                      </select>
                    </div>
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Scope</label>
                      <select
                        value={newChannelScope}
                        onChange={(e: any) => setNewChannelScope(e.target.value)}
                        className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg bg-white"
                      >
                        <option value="person_direct_work">Direct Personal Work</option>
                        <option value="company_generic">Company Generic</option>
                        <option value="company_switchboard">Company Switchboard</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Contact Value (Email / Phone / URL)</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. name@company.com or +91..."
                      value={newChannelValue}
                      onChange={(e) => setNewChannelValue(e.target.value)}
                      className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Source URL</label>
                      <input
                        type="url"
                        placeholder="https://company.com/team"
                        value={newChannelSourceUrl}
                        onChange={(e) => setNewChannelSourceUrl(e.target.value)}
                        className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                    <div>
                      <label className="block font-medium text-slate-700 mb-1">Evidence Quotation</label>
                      <input
                        type="text"
                        placeholder="e.g. Published on official leadership page"
                        value={newChannelEvidence}
                        onChange={(e) => setNewChannelEvidence(e.target.value)}
                        className="w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <Button variant="ghost" size="sm" type="button" onClick={() => setIsAddChannelOpen(false)}>
                      Cancel
                    </Button>
                    <Button variant="primary" size="sm" type="submit">
                      Save & Verify Channel
                    </Button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
