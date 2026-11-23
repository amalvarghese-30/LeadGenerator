import React, { useState, useEffect } from 'react';
import {
  Users,
  Search,
  Filter,
  Download,
  Mail,
  Phone,
  ExternalLink,
  Sparkles,
  ShieldCheck,
  Building2,
  Trash2,
  RefreshCw,
  Check,
  Copy,
  ChevronRight,
  Eye,
  Sliders,
} from 'lucide-react';
import { getContacts, enrichContact, suppressContact, deleteContact } from '../../services/contacts';
import { getProviders } from '../../services/providers';
import { Contact, ContactChannel, Provider } from '../../types';
import {
  LinkedinIcon,
  InstagramIcon,
  TwitterIcon,
  FacebookIcon,
  YoutubeIcon,
} from '../../components/ui/SocialIcons';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { useToast } from '../../context/ToastContext';

export const Directory: React.FC = () => {
  const { toast } = useToast();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Search & Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<string>('');
  const [filterHasEmail, setFilterHasEmail] = useState(false);
  const [filterHasPhone, setFilterHasPhone] = useState(false);
  const [filterHasLinkedIn, setFilterHasLinkedIn] = useState(false);
  const [filterVerifiedOnly, setFilterVerifiedOnly] = useState(false);

  // Selected contact for detail drawer
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [enrichingId, setEnrichingId] = useState<string | null>(null);

  const fetchContactsList = async () => {
    setIsLoading(true);
    try {
      const res = await getContacts({
        page,
        page_size: 50,
        search: searchQuery || undefined,
        provider_id: selectedProviderId || undefined,
        is_suppressed: false,
      });
      setContacts(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error('Failed to fetch directory contacts:', err);
      toast.error('Failed to load contacts directory');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchContactsList();
  }, [page, searchQuery, selectedProviderId]);

  useEffect(() => {
    const loadProviders = async () => {
      try {
        const pRes = await getProviders({ page_size: 100 });
        setProviders(pRes.items || []);
      } catch (e) {
        // ignore
      }
    };
    loadProviders();
  }, []);

  const handleCopy = async (text: string, fieldId: string) => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(fieldId);
      setTimeout(() => setCopiedField(null), 1500);
    } catch {
      // ignore
    }
  };

  const handleEnrich = async (contactId: string) => {
    setEnrichingId(contactId);
    try {
      const res = await enrichContact(contactId);
      toast.success(`Enriched contact: ${res.summary?.channels_added || 0} channels updated`);
      fetchContactsList();
      if (selectedContact?.id === contactId) {
        setSelectedContact(res.contact);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Enrichment failed');
    } finally {
      setEnrichingId(null);
    }
  };

  // Client-side filtering on top of server search
  const filteredContacts = contacts.filter((c) => {
    if (filterHasEmail && !c.email) return false;
    if (filterHasPhone && !c.phone) return false;
    if (filterHasLinkedIn && !c.linkedin_url && !c.professional_urls?.linkedin) return false;
    if (filterVerifiedOnly && c.contact_verification_status !== 'verified') return false;
    return true;
  });

  // Export CSV
  const handleExportCSV = () => {
    if (filteredContacts.length === 0) return;
    const headers = [
      'Full Name',
      'Designation',
      'Company Name',
      'Email',
      'Phone',
      'LinkedIn',
      'Discovered Via (Competitor)',
      'Competitor URL',
      'Verification Status',
      'Enrichment Status',
      'Created At',
    ];
    const rows = filteredContacts.map((c) => [
      `"${(c.full_name || '').replace(/"/g, '""')}"`,
      `"${(c.designation || '').replace(/"/g, '""')}"`,
      `"${(c.company_name || '').replace(/"/g, '""')}"`,
      `"${(c.email || '').replace(/"/g, '""')}"`,
      `"${(c.phone || '').replace(/"/g, '""')}"`,
      `"${(c.linkedin_url || c.professional_urls?.linkedin || '').replace(/"/g, '""')}"`,
      `"${(c.primary_provider_name || '').replace(/"/g, '""')}"`,
      `"${(c.primary_provider_website || c.source_url || '').replace(/"/g, '""')}"`,
      `"${c.contact_verification_status || 'discovered'}"`,
      `"${c.enrichment_status || 'pending'}"`,
      `"${c.created_at || ''}"`,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `candiddigital_directory_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan-400" />
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Client & Contact Directory
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800 text-xs font-mono font-bold">
              {total} Total Contacts
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Browse, search, and export discovered decision makers, corporate emails, and validated social links.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchContactsList}
            className="p-2 bg-slate-950 border border-slate-700 hover:border-slate-600 rounded-xl text-slate-300 text-xs flex items-center gap-1.5 transition-colors"
            title="Refresh Directory"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <button
            onClick={handleExportCSV}
            disabled={filteredContacts.length === 0}
            className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all shadow-md shadow-cyan-500/20 disabled:opacity-40"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name, company, email, or designation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-white placeholder-slate-500 text-xs rounded-xl pl-9 pr-4 py-2.5 focus:border-cyan-500 outline-none"
            />
          </div>

          {/* Quick Filter Toggles & Provider Selector */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* Competitor / Provider Filter Dropdown */}
            <div className="flex items-center gap-1.5 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1">
              <Building2 className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-[11px] font-semibold text-slate-400 hidden sm:inline">Competitor:</span>
              <select
                value={selectedProviderId}
                onChange={(e) => {
                  setSelectedProviderId(e.target.value);
                  setPage(1);
                }}
                className="bg-transparent text-slate-200 text-xs font-semibold focus:outline-none cursor-pointer py-1 max-w-[160px] truncate"
              >
                <option value="" className="bg-slate-900 text-slate-200">All Competitor Sources</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id} className="bg-slate-900 text-slate-200">
                    {p.name || p.domain || 'Competitor'}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => setFilterHasEmail(!filterHasEmail)}
              className={`px-3 py-1.5 rounded-lg border font-medium flex items-center gap-1.5 transition-colors ${
                filterHasEmail
                  ? 'bg-emerald-950 border-emerald-700 text-emerald-300 font-bold'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              <Mail className="w-3 h-3" />
              <span>Has Email</span>
            </button>

            <button
              onClick={() => setFilterHasPhone(!filterHasPhone)}
              className={`px-3 py-1.5 rounded-lg border font-medium flex items-center gap-1.5 transition-colors ${
                filterHasPhone
                  ? 'bg-cyan-950 border-cyan-700 text-cyan-300 font-bold'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              <Phone className="w-3 h-3" />
              <span>Has Phone</span>
            </button>

            <button
              onClick={() => setFilterHasLinkedIn(!filterHasLinkedIn)}
              className={`px-3 py-1.5 rounded-lg border font-medium flex items-center gap-1.5 transition-colors ${
                filterHasLinkedIn
                  ? 'bg-blue-950 border-blue-700 text-blue-300 font-bold'
                  : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              <LinkedinIcon className="w-3 h-3" />
              <span>Has LinkedIn</span>
            </button>
          </div>
        </div>
      </div>

      {/* Directory Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="py-20 flex justify-center">
              <LoadingSpinner message="Querying verified directory..." />
            </div>
          ) : filteredContacts.length === 0 ? (
            <div className="py-20 text-center text-slate-400 space-y-2">
              <Users className="w-12 h-12 mx-auto text-slate-700" />
              <p className="text-sm font-semibold text-slate-300">No matching contacts found</p>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                Try broadening your search query or run a new scan from the Scanner workspace.
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-mono text-[11px] uppercase bg-slate-950/80">
                  <th className="py-3 px-4">Contact & Title</th>
                  <th className="py-3 px-4">Company</th>
                  <th className="py-3 px-4">Discovered Via</th>
                  <th className="py-3 px-4">Corporate Email</th>
                  <th className="py-3 px-4">Phone / WhatsApp</th>
                  <th className="py-3 px-4">Social & LinkedIn</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredContacts.map((contact) => (
                  <tr
                    key={contact.id}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                    onClick={() => setSelectedContact(contact)}
                  >
                    {/* Contact & Title */}
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-white text-sm">{contact.full_name}</div>
                      <div className="text-slate-400 text-[11px] mt-0.5">
                        {contact.designation || 'Client Executive'}
                      </div>
                    </td>

                    {/* Company */}
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-200">
                        {contact.company_name || 'Individual Profile'}
                      </div>
                      {(contact.website || contact.company_website) && (
                        <a
                          href={contact.website || contact.company_website}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-cyan-400 hover:underline flex items-center gap-1 text-[11px] mt-0.5"
                        >
                          <span className="truncate max-w-[150px]">
                            {(contact.website || contact.company_website)?.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                          </span>
                          <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                        </a>
                      )}
                      <span className="text-[10px] font-mono text-slate-400 uppercase block mt-0.5">
                        {contact.contact_verification_status || 'discovered'}
                      </span>
                    </td>

                    {/* Discovered Via Competitor */}
                    <td className="py-3.5 px-4" onClick={(e) => e.stopPropagation()}>
                      {contact.primary_provider_name ? (
                        <div>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-800 text-cyan-300 text-[11px] font-medium">
                            <Building2 className="w-2.5 h-2.5 text-cyan-400" />
                            {contact.primary_provider_name}
                          </span>
                          {(contact.primary_provider_website || contact.source_url) && (
                            <a
                              href={contact.primary_provider_website || contact.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-slate-400 hover:text-cyan-400 flex items-center gap-1 text-[10px] mt-1 hover:underline truncate max-w-[130px]"
                              title={contact.primary_provider_website || contact.source_url}
                            >
                              <span>{(contact.primary_provider_website || contact.source_url)?.replace(/^https?:\/\//, '').split('/')[0]}</span>
                              <ExternalLink className="w-2.5 h-2.5 shrink-0" />
                            </a>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-500 text-xs">—</span>
                      )}
                    </td>

                    {/* Email */}
                    <td className="py-3.5 px-4">
                      {contact.email || (contact.emails && contact.emails.length > 0) ? (
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCopy(contact.emails?.[0] || contact.email!, `email-${contact.id}`);
                            }}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-950 border border-slate-800 text-emerald-400 font-mono text-[11px] hover:border-emerald-600 transition-colors"
                            title="Click to copy email"
                          >
                            <Mail className="w-3 h-3 shrink-0" />
                            <span className="truncate max-w-[140px]">{contact.emails?.[0] || contact.email}</span>
                            {copiedField === `email-${contact.id}` ? (
                              <Check className="w-3 h-3 text-emerald-300 ml-1" />
                            ) : (
                              <Copy className="w-3 h-3 text-slate-400 ml-1" />
                            )}
                          </div>
                          {contact.emails && contact.emails.length > 1 && (
                            <span
                              className="px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-mono font-bold"
                              title={contact.emails.join(', ')}
                            >
                              +{contact.emails.length - 1}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400 text-[11px] italic">Not discovered</span>
                      )}
                    </td>

                    {/* Phone */}
                    <td className="py-3.5 px-4">
                      {contact.phone || (contact.phones && contact.phones.length > 0) ? (
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCopy(contact.phones?.[0] || contact.phone!, `phone-${contact.id}`);
                            }}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-950 border border-slate-800 text-slate-200 font-mono text-[11px] hover:border-cyan-600 transition-colors"
                            title="Click to copy phone"
                          >
                            <Phone className="w-3 h-3 shrink-0" />
                            <span>{contact.phones?.[0] || contact.phone}</span>
                            {copiedField === `phone-${contact.id}` ? (
                              <Check className="w-3 h-3 text-emerald-300 ml-1" />
                            ) : (
                              <Copy className="w-3 h-3 text-slate-400 ml-1" />
                            )}
                          </div>
                          {contact.phones && contact.phones.length > 1 && (
                            <span
                              className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-mono font-bold"
                              title={contact.phones.join(', ')}
                            >
                              +{contact.phones.length - 1}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400 text-[11px] italic">—</span>
                      )}
                    </td>

                    {/* Socials / LinkedIn / Channels */}
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {/* LinkedIn */}
                        {(contact.socials?.linkedin || contact.linkedin_url || contact.professional_urls?.linkedin) && (
                          <a
                            href={contact.socials?.linkedin || contact.linkedin_url || contact.professional_urls?.linkedin}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 rounded bg-slate-950 border border-slate-800 text-cyan-400 hover:text-cyan-300 hover:border-cyan-700 transition-colors"
                            title="LinkedIn Profile"
                          >
                            <LinkedinIcon className="w-3.5 h-3.5" />
                          </a>
                        )}

                        {/* Instagram */}
                        {contact.socials?.instagram && (
                          <a
                            href={contact.socials.instagram}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 rounded bg-slate-950 border border-slate-800 text-pink-400 hover:text-pink-300 hover:border-pink-700 transition-colors"
                            title="Instagram Profile"
                          >
                            <InstagramIcon className="w-3.5 h-3.5" />
                          </a>
                        )}

                        {/* Facebook */}
                        {contact.socials?.facebook && (
                          <a
                            href={contact.socials.facebook}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 rounded bg-slate-950 border border-slate-800 text-blue-500 hover:text-blue-400 hover:border-blue-700 transition-colors"
                            title="Facebook Profile"
                          >
                            <FacebookIcon className="w-3.5 h-3.5" />
                          </a>
                        )}

                        {/* Twitter/X */}
                        {contact.socials?.twitter && (
                          <a
                            href={contact.socials.twitter}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 rounded bg-slate-950 border border-slate-800 text-sky-400 hover:text-sky-300 hover:border-sky-700 transition-colors"
                            title="Twitter / X"
                          >
                            <TwitterIcon className="w-3.5 h-3.5" />
                          </a>
                        )}

                        {/* YouTube */}
                        {contact.socials?.youtube && (
                          <a
                            href={contact.socials.youtube}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 rounded bg-slate-950 border border-slate-800 text-red-500 hover:text-red-400 hover:border-red-700 transition-colors"
                            title="YouTube Channel"
                          >
                            <YoutubeIcon className="w-3.5 h-3.5" />
                          </a>
                        )}

                        {!contact.socials?.linkedin && !contact.linkedin_url && !contact.professional_urls?.linkedin &&
                         !contact.socials?.instagram && !contact.socials?.facebook && !contact.socials?.twitter && !contact.socials?.youtube && (
                          <span className="text-slate-400 text-[11px]">—</span>
                        )}
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEnrich(contact.id);
                        }}
                        disabled={enrichingId === contact.id}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-slate-800 transition-colors"
                        title="Enrich Contact Channels"
                      >
                        <Sparkles
                          className={`w-4 h-4 ${enrichingId === contact.id ? 'animate-spin text-cyan-400' : ''}`}
                        />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Contact Details Slide-over Modal / Drawer */}
      {selectedContact && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end">
          <div className="bg-slate-900 border-l border-slate-800 w-full max-w-md h-full p-6 overflow-y-auto space-y-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-white">{selectedContact.full_name}</h3>
                <p className="text-xs text-slate-400">{selectedContact.designation}</p>
              </div>
              <button
                onClick={() => setSelectedContact(null)}
                className="text-slate-400 hover:text-white text-lg font-bold px-2 py-1 rounded"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">
                  Company
                </span>
                <span className="text-sm font-semibold text-white">
                  {selectedContact.company_name || 'Individual Profile'}
                </span>
              </div>

              {/* Competitor / Source Attribution Card */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-cyan-900/50 space-y-2">
                <div className="flex items-center gap-1.5 text-cyan-400 font-semibold text-xs">
                  <Building2 className="w-3.5 h-3.5" />
                  <span>Competitor Source & Origin</span>
                </div>
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Discovered On Competitor:</span>
                    <span className="font-bold text-white">
                      {selectedContact.primary_provider_name || 'Direct / Scan'}
                    </span>
                  </div>
                  {(selectedContact.primary_provider_website || selectedContact.source_url) && (
                    <div className="flex items-center justify-between gap-2 pt-1.5 border-t border-slate-900">
                      <span className="text-slate-400">Scanned URL:</span>
                      <a
                        href={selectedContact.primary_provider_website || selectedContact.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-cyan-400 hover:underline flex items-center gap-1 truncate max-w-[210px]"
                      >
                        <span className="truncate">{selectedContact.primary_provider_website || selectedContact.source_url}</span>
                        <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                    </div>
                  )}
                  {selectedContact.source_providers && selectedContact.source_providers.length > 0 && (
                    <div className="pt-1 text-[11px] text-slate-500">
                      Cited across {selectedContact.source_providers.length} provider portfolio reference(s).
                    </div>
                  )}
                </div>
              </div>

              <div>
                <span className="text-[11px] font-mono uppercase text-slate-400 block mb-1">
                  Discovered Contact Channels
                </span>
                <div className="space-y-2">
                  {selectedContact.contact_channels && selectedContact.contact_channels.length > 0 ? (
                    selectedContact.contact_channels.map((ch, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] font-bold text-cyan-400 uppercase">
                            {ch.type} ({ch.scope || 'direct'})
                          </span>
                          <span className="text-[10px] text-emerald-400 font-mono">
                            {ch.verification_status}
                          </span>
                        </div>
                        <div className="font-mono text-xs text-white break-all">{ch.value}</div>
                        {ch.evidence_quote && (
                          <div className="text-[11px] text-slate-400 italic">
                            "{ch.evidence_quote}"
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-400 italic">No channel history recorded yet</div>
                  )}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end gap-2">
                <button
                  onClick={() => handleEnrich(selectedContact.id)}
                  disabled={enrichingId === selectedContact.id}
                  className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 transition-all"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{enrichingId === selectedContact.id ? 'Enriching...' : 'Run Enrichment'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
