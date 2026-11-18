import React, { useState, useEffect } from 'react';
import {
  Building2,
  Globe,
  Mail,
  Phone,
  MapPin,
  ExternalLink,
  Copy,
  Check,
  UserCheck,
  Users,
  ShieldCheck,
  FileText,
  Share2,
} from 'lucide-react';
import { Company, ContactChannel } from '../../types';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { getCompanyPeople } from '../../services/companies';
import { SocialIcon } from '../../components/ui/SocialIcons';

interface CompanyDetailModalProps {
  company: Company | null;
  isOpen: boolean;
  onClose: () => void;
}

export const CompanyDetailModal: React.FC<CompanyDetailModalProps> = ({
  company,
  isOpen,
  onClose,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [people, setPeople] = useState<any[]>([]);
  const [isLoadingPeople, setIsLoadingPeople] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'contacts' | 'people' | 'sources'>('overview');

  useEffect(() => {
    if (company?.id && isOpen) {
      setIsLoadingPeople(true);
      getCompanyPeople(company.id)
        .then((res) => setPeople(res.people || []))
        .catch(() => setPeople(company.associated_people || []))
        .finally(() => setIsLoadingPeople(false));
    } else {
      setPeople([]);
    }
  }, [company?.id, isOpen]);

  if (!company) return null;

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const channels: ContactChannel[] = company.public_contact_channels || [];
  const emails = channels.filter((c) => c.type === 'email');
  const phones = channels.filter((c) => c.type === 'phone');
  const forms = channels.filter((c) => c.type === 'contact_form');
  const socials = Array.isArray(company.social_profiles)
    ? company.social_profiles
    : Object.entries(company.social_profiles || {}).map(([platform, url]) => ({ platform, url: String(url) }));

  // Fallback email/phone from public_contact if channels empty
  const fallbackEmail = company.public_contact?.email;
  const fallbackPhone = company.public_contact?.phone;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      maxWidth="2xl"
      title=""
    >
      <div className="space-y-5">
        {/* Header Header */}
        <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/10 to-blue-500/10 border border-indigo-200/50 flex items-center justify-center text-indigo-600 shadow-sm flex-shrink-0">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-bold text-slate-900 tracking-tight">{company.name}</h2>
                <Badge variant={company.verification_status === 'verified' ? 'success' : 'default'}>
                  {company.verification_status || 'Identified Client'}
                </Badge>
                {company.enrichment_status && (
                  <Badge variant={company.enrichment_status === 'enriched' ? 'info' : 'warning'}>
                    {company.enrichment_status === 'enriched' ? 'Enriched' : company.enrichment_status}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                {company.industry && <span className="font-medium text-slate-700">{company.industry}</span>}
                {company.website && (
                  <a
                    href={company.website}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline flex items-center gap-1 font-mono text-[11px]"
                  >
                    <Globe className="w-3 h-3 text-slate-400" />
                    {company.domain || company.website}
                    <ExternalLink className="w-2.5 h-2.5 text-slate-400" />
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-200 text-xs font-medium">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-2 px-1 border-b-2 transition-colors ${
              activeTab === 'overview'
                ? 'border-indigo-600 text-indigo-600 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('contacts')}
            className={`pb-2 px-1 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'contacts'
                ? 'border-indigo-600 text-indigo-600 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Business Channels
            {(emails.length > 0 || phones.length > 0) && (
              <span className="px-1.5 py-0.2 bg-indigo-100 text-indigo-700 rounded-full text-[10px]">
                {emails.length + phones.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('people')}
            className={`pb-2 px-1 border-b-2 transition-colors flex items-center gap-1.5 ${
              activeTab === 'people'
                ? 'border-indigo-600 text-indigo-600 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Leadership & People
            {people.length > 0 && (
              <span className="px-1.5 py-0.2 bg-emerald-100 text-emerald-700 rounded-full text-[10px]">
                {people.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('sources')}
            className={`pb-2 px-1 border-b-2 transition-colors ${
              activeTab === 'sources'
                ? 'border-indigo-600 text-indigo-600 font-semibold'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            Provenance & Sources
          </button>
        </div>

        {/* Tab 1: Overview */}
        {activeTab === 'overview' && (
          <div className="space-y-4 text-xs">
            {company.description && (
              <div className="bg-slate-50/80 p-3.5 rounded-xl border border-slate-100">
                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Company Overview
                </div>
                <p className="text-slate-700 leading-relaxed">{company.description}</p>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="bg-white p-3 rounded-lg border border-slate-200">
                <div className="text-slate-500 text-[11px] font-medium flex items-center gap-1.5 mb-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" /> Address & Headquarters
                </div>
                <div className="text-slate-800 font-medium">
                  {company.address || (company.city || company.country ? `${company.city || ''}, ${company.country || ''}` : 'Not published')}
                </div>
              </div>

              <div className="bg-white p-3 rounded-lg border border-slate-200">
                <div className="text-slate-500 text-[11px] font-medium flex items-center gap-1.5 mb-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" /> Intelligence Status
                </div>
                <div className="text-slate-800 font-medium">
                  {company.enrichment_status ? `Status: ${company.enrichment_status}` : 'Discovered via Client Portfolio'}
                </div>
              </div>
            </div>

            {socials.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Share2 className="w-3.5 h-3.5" /> Official Social Profiles
                </div>
                <div className="flex flex-wrap gap-2">
                  {socials.map((s: any, idx: number) => (
                    <a
                      key={idx}
                      href={s.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 hover:bg-slate-100 hover:border-slate-300 text-slate-700 transition-colors"
                    >
                      <SocialIcon platform={s.platform || 'globe'} className="w-4 h-4 text-slate-600" />
                      <span className="font-medium capitalize">{s.platform}</span>
                      {s.handle && <span className="text-slate-400 text-[11px]">@{s.handle}</span>}
                      <ExternalLink className="w-2.5 h-2.5 text-slate-400" />
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Contacts */}
        {activeTab === 'contacts' && (
          <div className="space-y-4 text-xs">
            {/* Emails */}
            <div>
              <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-blue-500" /> Published Business Emails
              </div>
              {emails.length === 0 && !fallbackEmail ? (
                <p className="text-slate-400 italic">No business email published on official website.</p>
              ) : (
                <div className="space-y-2">
                  {emails.map((em, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200"
                    >
                      <div>
                        <div className="font-mono text-slate-900 font-medium">{em.value}</div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                          <span className="capitalize">{em.scope?.replace('_', ' ') || 'generic'}</span>
                          {em.source_url && (
                            <span className="text-slate-400 truncate max-w-[200px]">via {em.source_url}</span>
                          )}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleCopy(em.value, `em-${idx}`)}
                        leftIcon={copiedKey === `em-${idx}` ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      >
                        {copiedKey === `em-${idx}` ? 'Copied' : 'Copy'}
                      </Button>
                    </div>
                  ))}
                  {emails.length === 0 && fallbackEmail && (
                    <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                      <div className="font-mono text-slate-900 font-medium">{fallbackEmail}</div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleCopy(fallbackEmail, 'fallback-em')}
                        leftIcon={copiedKey === 'fallback-em' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      >
                        {copiedKey === 'fallback-em' ? 'Copied' : 'Copy'}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Phones */}
            <div>
              <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-emerald-500" /> Official Business Phone Numbers
              </div>
              {phones.length === 0 && !fallbackPhone ? (
                <p className="text-slate-400 italic">No business phone published on official website.</p>
              ) : (
                <div className="space-y-2">
                  {phones.map((ph, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200"
                    >
                      <div>
                        <div className="font-mono text-slate-900 font-medium">{ph.value}</div>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          {ph.evidence_quote || 'Published phone channel'}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleCopy(ph.value, `ph-${idx}`)}
                        leftIcon={copiedKey === `ph-${idx}` ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      >
                        {copiedKey === `ph-${idx}` ? 'Copied' : 'Copy'}
                      </Button>
                    </div>
                  ))}
                  {phones.length === 0 && fallbackPhone && (
                    <div className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                      <div className="font-mono text-slate-900 font-medium">{fallbackPhone}</div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleCopy(fallbackPhone, 'fallback-ph')}
                        leftIcon={copiedKey === 'fallback-ph' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      >
                        {copiedKey === 'fallback-ph' ? 'Copied' : 'Copy'}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Forms */}
            {forms.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-indigo-500" /> Contact & Enquiry Forms
                </div>
                <div className="space-y-2">
                  {forms.map((fm, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                      <div className="truncate text-slate-700 font-mono max-w-[400px]">
                        {fm.value}
                      </div>
                      <a
                        href={fm.value}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 hover:underline flex items-center gap-1 text-[11px]"
                      >
                        Open Form <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: People */}
        {activeTab === 'people' && (
          <div className="space-y-3 text-xs">
            <div className="text-slate-500 text-xs">
              Publicly identified decision-makers, founders, and directors corroborated for this company.
            </div>

            {isLoadingPeople ? (
              <div className="py-8 text-center text-slate-400">Loading affiliated leaders...</div>
            ) : people.length === 0 ? (
              <div className="text-center py-8 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                <Users className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-slate-600 font-medium">No individual executive identified yet</p>
                <p className="text-slate-400 text-[11px] mt-0.5">
                  Company intelligence & direct contact channels are preserved independently.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {people.map((p, idx) => (
                  <div
                    key={p.id || idx}
                    className="p-3 bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-semibold text-slate-900 text-sm flex items-center gap-1.5">
                          <UserCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                          {p.full_name}
                        </div>
                        <Badge variant="success">
                          {p.verification_status || 'Verified'}
                        </Badge>
                      </div>
                      <div className="text-slate-600 text-xs mt-1 font-medium">
                        {p.designation || 'Corporate Executive'}
                      </div>
                      {p.evidence_quote && (
                        <div className="text-[11px] text-slate-400 italic mt-1 line-clamp-2">
                          "{p.evidence_quote}"
                        </div>
                      )}
                    </div>

                    <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between">
                      {p.linkedin_url ? (
                        <a
                          href={p.linkedin_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-blue-600 hover:underline text-[11px]"
                        >
                          <SocialIcon platform="linkedin" className="w-3.5 h-3.5" />
                          LinkedIn Profile
                          <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      ) : (
                        <span className="text-slate-400 text-[11px]">No LinkedIn link</span>
                      )}
                      {p.email && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleCopy(p.email, `p-em-${idx}`)}
                          className="text-[11px] h-6 px-2"
                        >
                          {copiedKey === `p-em-${idx}` ? 'Copied' : 'Copy Email'}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Provenance */}
        {activeTab === 'sources' && (
          <div className="space-y-3 text-xs">
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-700 mb-1">Company Website Crawled</div>
              <div className="font-mono text-slate-600 break-all">{company.website || 'No website URL'}</div>
            </div>

            {channels.length > 0 && (
              <div>
                <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Discovered Channel Evidence Quotes
                </div>
                <div className="space-y-2 max-h-56 overflow-y-auto">
                  {channels.map((ch, idx) => (
                    <div key={idx} className="p-2.5 bg-slate-50 rounded-lg border border-slate-200">
                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                        <span className="font-semibold uppercase">{ch.type} ({ch.scope})</span>
                        <span>{ch.source_url}</span>
                      </div>
                      <div className="text-slate-700 italic font-mono text-[11px]">
                        "{ch.evidence_quote || ch.value}"
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-end pt-3 border-t border-slate-100">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close Dossier
          </Button>
        </div>
      </div>
    </Modal>
  );
};
