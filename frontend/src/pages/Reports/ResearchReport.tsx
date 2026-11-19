import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
    ArrowLeft, Globe, ExternalLink, AlertCircle, CheckCircle2, Building2, Users, Mail,
    ShieldAlert, ChevronDown, ChevronUp, Activity, BarChart2, CheckCheck, UserCheck, Layers,
    User, MapPin, Briefcase, Share2, Sparkles, Phone, ShieldCheck, Check, Info, FileText
} from 'lucide-react';
import api from '../../services/api';
import { getCrawlJob, getJobReport } from '../../services/discovery';
import { CrawlJob, PersonProfile } from '../../types';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { formatDateTime } from '../../utils/format';
import { CompanyDetailModal } from '../Companies/CompanyDetailModal';

const PLATFORM_COLORS: Record<string, { bg: string; text: string; border: string; badge: string }> = {
    linkedin: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', badge: 'bg-blue-600 text-white' },
    twitter: { bg: 'bg-slate-50', text: 'text-slate-800', border: 'border-slate-300', badge: 'bg-slate-900 text-white' },
    x: { bg: 'bg-slate-50', text: 'text-slate-800', border: 'border-slate-300', badge: 'bg-slate-900 text-white' },
    instagram: { bg: 'bg-pink-50', text: 'text-pink-700', border: 'border-pink-200', badge: 'bg-gradient-to-r from-purple-500 to-pink-500 text-white' },
    youtube: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', badge: 'bg-red-600 text-white' },
    github: { bg: 'bg-slate-50', text: 'text-slate-800', border: 'border-slate-300', badge: 'bg-slate-800 text-white' },
    threads: { bg: 'bg-zinc-50', text: 'text-zinc-800', border: 'border-zinc-300', badge: 'bg-zinc-900 text-white' },
    pinterest: { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200', badge: 'bg-rose-600 text-white' },
    telegram: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200', badge: 'bg-sky-500 text-white' },
    medium: { bg: 'bg-emerald-50', text: 'text-emerald-800', border: 'border-emerald-200', badge: 'bg-emerald-700 text-white' },
    substack: { bg: 'bg-amber-50', text: 'text-amber-800', border: 'border-amber-200', badge: 'bg-amber-600 text-white' },
};

export const ResearchReport: React.FC = () => {
    const { jobId } = useParams<{ jobId: string }>();
    const [job, setJob] = useState<CrawlJob | null>(null);
    const [report, setReport] = useState<any>(null);
    const [references, setReferences] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showRejected, setShowRejected] = useState(false);
    const [activeTab, setActiveTab] = useState<'person' | 'provider'>('provider');
    const [selectedCompany, setSelectedCompany] = useState<any | null>(null);

    useEffect(() => {
        if (!jobId) return;
        (async () => {
            try {
                const [j, r] = await Promise.all([
                    getCrawlJob(jobId),
                    getJobReport(jobId).catch(() => null),
                ]);
                setJob(j);
                setReport(r);

                // Auto-select tab based on report_mode or person_profile presence
                const mode = r?.report_mode || (j as any)?.report_mode;
                if (mode === 'person' || r?.person_profile) {
                    setActiveTab('person');
                } else {
                    setActiveTab('provider');
                }

                // Fetch references by provider of this job
                if (j?.provider_id) {
                    const refs = await api.get('/references', {
                        params: { provider_id: j.provider_id, page_size: 200 }
                    });
                    setReferences(refs.data.items || []);
                }
            } catch (e: any) {
                setError(e?.response?.data?.detail || 'Failed to load report');
            } finally {
                setLoading(false);
            }
        })();
    }, [jobId]);

    if (loading) return <LoadingSpinner message="Loading research report..." />;
    if (error) return (
        <Card className="p-6 text-center">
            <AlertCircle className="w-8 h-8 text-rose-500 mx-auto mb-2" />
            <p className="text-sm text-rose-700">{error}</p>
            <Link to="/discovery" className="text-xs text-blue-600 mt-3 inline-block">← Back to Discovery</Link>
        </Card>
    );
    if (!job) return <div className="text-center py-8 text-slate-500">Job not found</div>;

    const metrics = report?.data_quality_metrics || (job as any)?.data_quality_metrics || {};
    const rejectedCandidates = report?.rejected_candidates || [];
    const personProfile: PersonProfile | undefined = report?.person_profile || (job as any)?.person_profile;
    const pageDiagnostics = report?.page_diagnostics || [];

    const rawCandidates = metrics.candidates_detected ?? (job.references_found + (metrics.rejected_false_matches || 0));
    const validRefs = metrics.valid_client_references ?? job.references_found;
    const contactsCount = metrics.contacts_created ?? job.contacts_created;
    const leadsCount = metrics.leads_created ?? job.leads_created;

    const isPersonReport = !!personProfile;
    const isHybrid = isPersonReport && validRefs > 0;

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-12">
            {/* Header & Breadcrumb */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    <Link to="/discovery" className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors">
                        <ArrowLeft className="w-5 h-5" />
                    </Link>
                    <div>
                        <div className="flex items-center gap-2">
                            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                                {isPersonReport && activeTab === 'person' ? 'Person Intelligence Profile Report' : 'Provider Intelligence Research Report'}
                            </h1>
                            <Badge variant={job.status.startsWith('completed') ? 'success' : 'warning'}>
                                {job.status.replace(/_/g, ' ')}
                            </Badge>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5 truncate max-w-xl">
                            <Globe className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <a href={job.starting_url} target="_blank" rel="noreferrer" className="hover:underline hover:text-blue-600">
                                {job.starting_url}
                            </a>
                        </p>
                    </div>
                </div>

                {/* Workflow Mode Tabs (When Person Profile is detected) */}
                {isPersonReport && (
                    <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
                        <button
                            onClick={() => setActiveTab('person')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                                activeTab === 'person'
                                    ? 'bg-white text-indigo-700 shadow-sm'
                                    : 'text-slate-600 hover:text-slate-900'
                            }`}
                        >
                            <User className="w-3.5 h-3.5" /> Person Intelligence
                            <span className="ml-1 px-1.5 py-0.2 bg-indigo-50 text-indigo-600 rounded text-[10px]">Verified</span>
                        </button>
                        <button
                            onClick={() => setActiveTab('provider')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                                activeTab === 'provider'
                                    ? 'bg-white text-slate-900 shadow-sm'
                                    : 'text-slate-600 hover:text-slate-900'
                            }`}
                        >
                            <Building2 className="w-3.5 h-3.5" /> Pipeline & Reference Audit ({validRefs})
                        </button>
                    </div>
                )}
            </div>

            {/* TAB 1: PERSON INTELLIGENCE REPORT (Workflow B) */}
            {isPersonReport && activeTab === 'person' && personProfile && (
                <div className="space-y-6">
                    {/* Hero Profile Banner */}
                    <Card className="p-6 bg-gradient-to-br from-indigo-900 via-indigo-950 to-slate-900 text-white rounded-2xl shadow-md border-0 relative overflow-hidden">
                        <div className="absolute right-0 top-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
                            <div className="flex items-start gap-4">
                                <div className="w-16 h-16 rounded-2xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-2xl font-black text-indigo-300 shadow-inner shrink-0">
                                    {personProfile.person_name.charAt(0)}
                                </div>
                                <div className="space-y-1.5">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h2 className="text-2xl font-black tracking-tight text-white">
                                            {personProfile.person_name}
                                        </h2>
                                        {personProfile.confidence_score && (
                                            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 border border-emerald-400/30 text-emerald-300 flex items-center gap-1">
                                                <Sparkles className="w-3 h-3" />
                                                {Math.round(personProfile.confidence_score * 100)}% Confidence
                                            </span>
                                        )}
                                        {personProfile.name_source && (
                                            <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-white/10 text-slate-300">
                                                via {personProfile.name_source.replace(/_/g, ' ')}
                                            </span>
                                        )}
                                    </div>

                                    <div className="flex flex-wrap items-center gap-3 text-xs text-indigo-200">
                                        {personProfile.designation && (
                                            <div className="flex items-center gap-1">
                                                <Briefcase className="w-3.5 h-3.5 text-indigo-400" />
                                                <span>{personProfile.designation}</span>
                                            </div>
                                        )}
                                        {personProfile.company_name && (
                                            <div className="flex items-center gap-1 font-semibold text-white">
                                                <Building2 className="w-3.5 h-3.5 text-indigo-400" />
                                                <span>{personProfile.company_name}</span>
                                            </div>
                                        )}
                                        {personProfile.location && (
                                            <div className="flex items-center gap-1">
                                                <MapPin className="w-3.5 h-3.5 text-indigo-400" />
                                                <span>{personProfile.location}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                                <Link
                                    to="/contacts"
                                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow transition-colors flex items-center gap-1.5"
                                >
                                    <UserCheck className="w-3.5 h-3.5" /> View in CRM Contacts
                                </Link>
                                <Link
                                    to="/leads"
                                    className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold rounded-xl transition-colors flex items-center gap-1.5"
                                >
                                    <BarChart2 className="w-3.5 h-3.5" /> View Leads ({leadsCount})
                                </Link>
                            </div>
                        </div>
                    </Card>

                    {/* Bio & Career Overview */}
                    {personProfile.bio_summary && (
                        <Card className="p-5 bg-white border border-slate-200 shadow-sm">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                                <FileText className="w-3.5 h-3.5 text-indigo-600" /> Executive Bio & Background
                            </h3>
                            <p className="text-sm text-slate-800 leading-relaxed font-sans bg-slate-50/70 p-4 rounded-xl border border-slate-100">
                                {personProfile.bio_summary}
                            </p>
                        </Card>
                    )}

                    {/* Social Media Profiles Matrix */}
                    <Card className="p-5 bg-white border border-slate-200 shadow-sm">
                        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                                    <Share2 className="w-4 h-4 text-indigo-600" />
                                    Discovered Social Media Profiles & Channels
                                </h3>
                                <p className="text-[11px] text-slate-500 mt-0.5">
                                    Verified public social profiles extracted from DOM, JSON-LD, and targeted public discovery.
                                </p>
                            </div>
                            <span className="text-xs font-bold px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-lg">
                                {personProfile.social_profiles?.length || 0} Profiles Detected
                            </span>
                        </div>

                        {!personProfile.social_profiles || personProfile.social_profiles.length === 0 ? (
                            <div className="text-center py-6 text-xs text-slate-400">
                                No social media profiles discovered for this individual.
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                {personProfile.social_profiles.map((sp, idx) => {
                                    const plat = sp.platform.toLowerCase();
                                    const style = PLATFORM_COLORS[plat] || {
                                        bg: 'bg-slate-50', text: 'text-slate-800', border: 'border-slate-200', badge: 'bg-slate-700 text-white'
                                    };
                                    return (
                                        <div
                                            key={idx}
                                            className={`p-3.5 rounded-xl border ${style.border} ${style.bg} flex flex-col justify-between transition-all hover:shadow-sm`}
                                        >
                                            <div className="space-y-1">
                                                <div className="flex items-center justify-between">
                                                    <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded ${style.badge}`}>
                                                        {sp.platform}
                                                    </span>
                                                    <Badge variant={sp.verification_status === 'likely_official' ? 'success' : 'default'}>
                                                        {sp.verification_status?.replace(/_/g, ' ') || 'discovered'}
                                                    </Badge>
                                                </div>
                                                <div className="pt-1.5 font-bold text-sm text-slate-900 truncate">
                                                    {sp.handle ? `@${sp.handle}` : sp.url.split('/').pop()}
                                                </div>
                                                <div className="text-[10px] text-slate-500 truncate">
                                                    Source: {sp.extraction_method?.replace(/_/g, ' ') || 'webpage'}
                                                </div>
                                            </div>

                                            <div className="mt-3 pt-2 border-t border-slate-200/60 flex items-center justify-between">
                                                <span className="text-[10px] text-slate-400">
                                                    {sp.confidence ? `${Math.round(sp.confidence * 100)}% match` : 'High confidence'}
                                                </span>
                                                <a
                                                    href={sp.url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                                                >
                                                    Open Profile <ExternalLink className="w-3 h-3" />
                                                </a>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </Card>

                    {/* Direct Contact Channels & Associated Websites */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Contact Channels */}
                        <Card className="p-5 bg-white border border-slate-200 shadow-sm">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                                <Mail className="w-3.5 h-3.5 text-emerald-600" /> Direct & Business Contact Channels
                            </h3>
                            <div className="space-y-3">
                                <div>
                                    <span className="text-[11px] font-semibold text-slate-500 block mb-1">Public Emails</span>
                                    {personProfile.public_emails && personProfile.public_emails.length > 0 ? (
                                        <div className="space-y-1">
                                            {personProfile.public_emails.map((e, idx) => (
                                                <div key={idx} className="flex items-center gap-2 p-2 bg-emerald-50/70 border border-emerald-200 rounded-lg text-xs font-mono text-emerald-900">
                                                    <Mail className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                                                    <span className="truncate">{e}</span>
                                                    <span className="ml-auto text-[10px] bg-emerald-200/70 px-1.5 py-0.5 rounded text-emerald-800 font-sans">Published</span>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="text-xs text-slate-400 italic bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                                            No direct personal email published in public source.
                                        </div>
                                    )}
                                </div>

                                <div>
                                    <span className="text-[11px] font-semibold text-slate-500 block mb-1">Direct Phone Numbers</span>
                                    {personProfile.public_phones && personProfile.public_phones.length > 0 ? (
                                        <div className="space-y-1">
                                            {personProfile.public_phones.map((p, idx) => (
                                                <div key={idx} className="flex items-center gap-2 p-2 bg-blue-50/70 border border-blue-200 rounded-lg text-xs font-mono text-blue-900">
                                                    <Phone className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                                                    <span className="truncate">{p}</span>
                                                    <span className="ml-auto text-[10px] bg-blue-200/70 px-1.5 py-0.5 rounded text-blue-800 font-sans">E.164</span>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="text-xs text-slate-400 italic bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                                            No personal phone number publicly published.
                                        </div>
                                    )}
                                </div>
                            </div>
                        </Card>

                        {/* Associated Websites & Portfolios */}
                        <Card className="p-5 bg-white border border-slate-200 shadow-sm">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-1.5">
                                <Globe className="w-3.5 h-3.5 text-blue-600" /> Associated Websites & External Links
                            </h3>
                            {personProfile.associated_websites && personProfile.associated_websites.length > 0 ? (
                                <div className="space-y-2">
                                    {personProfile.associated_websites.map((wb, idx) => (
                                        <div key={idx} className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
                                            <div className="truncate max-w-[240px]">
                                                <span className="font-semibold text-slate-800 block truncate">{wb.label}</span>
                                                <span className="text-[10px] text-slate-500 truncate block">{wb.url}</span>
                                            </div>
                                            <a
                                                href={wb.url}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1 text-[11px] shrink-0"
                                            >
                                                Visit <ExternalLink className="w-2.5 h-2.5" />
                                            </a>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-xs text-slate-400 italic bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                                    No independent personal domain or portfolio detected on page.
                                </div>
                            )}

                            {/* Confidence Rationale List */}
                            {personProfile.confidence_reasons && personProfile.confidence_reasons.length > 0 && (
                                <div className="mt-4 pt-3 border-t border-slate-100">
                                    <span className="text-[11px] font-semibold text-slate-500 block mb-1.5">Confidence Evidence Audit</span>
                                    <ul className="text-xs space-y-1">
                                        {personProfile.confidence_reasons.map((r, idx) => (
                                            <li key={idx} className="flex items-center gap-1.5 text-slate-700">
                                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                                                <span>{r}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </Card>
                    </div>

                    {/* Page Diagnostics Table */}
                    {pageDiagnostics.length > 0 && (
                        <Card className="p-0 overflow-hidden shadow-sm">
                            <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
                                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                                    <Activity className="w-3.5 h-3.5 text-indigo-600" /> Page-Level Intelligence Diagnostics
                                </h3>
                                <span className="text-[11px] text-slate-500">{pageDiagnostics.length} pages audited</span>
                            </div>
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs text-left">
                                    <thead className="bg-slate-50 border-b border-slate-200 text-[11px] text-slate-500 font-semibold uppercase">
                                        <tr>
                                            <th className="py-2.5 px-4">Page URL</th>
                                            <th className="py-2.5 px-4">Person Profile?</th>
                                            <th className="py-2.5 px-4">Confidence</th>
                                            <th className="py-2.5 px-4">Detection Signals</th>
                                            <th className="py-2.5 px-4">Signals Found</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100">
                                        {pageDiagnostics.map((pd: any, idx: number) => (
                                            <tr key={idx} className="hover:bg-slate-50/60">
                                                <td className="py-2.5 px-4 max-w-sm truncate text-slate-800 font-mono text-[11px]">
                                                    {pd.url}
                                                </td>
                                                <td className="py-2.5 px-4">
                                                    <Badge variant={pd.is_person_profile ? 'success' : 'default'}>
                                                        {pd.is_person_profile ? 'Profile Page' : 'General Page'}
                                                    </Badge>
                                                </td>
                                                <td className="py-2.5 px-4 font-semibold text-slate-700">
                                                    {Math.round(pd.person_confidence * 100)}%
                                                </td>
                                                <td className="py-2.5 px-4 text-slate-600 max-w-xs truncate">
                                                    {pd.detection_reason}
                                                </td>
                                                <td className="py-2.5 px-4 text-slate-500">
                                                    {pd.socials_found} socials, {pd.emails_found} emails
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    )}
                </div>
            )}

            {/* TAB 2: PROVIDER INTELLIGENCE & PIPELINE AUDIT (Workflow A) */}
            {(!isPersonReport || activeTab === 'provider') && (
                <div className="space-y-6">
                    {/* 4-Tier Pipeline Distinction (Task 10) */}
                    <div>
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                            Four-Tier Pipeline Funnel (Strictly Verified)
                        </h3>
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                            <Card className="p-4 border-l-4 border-l-slate-400">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-slate-500">1. Raw Candidates</span>
                                    <Layers className="w-4 h-4 text-slate-400" />
                                </div>
                                <div className="text-2xl font-bold text-slate-900 mt-1">{rawCandidates}</div>
                                <div className="text-[11px] text-slate-400 mt-1">Total phrases & entities detected</div>
                            </Card>

                            <Card className="p-4 border-l-4 border-l-indigo-500">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-indigo-700">2. Validated References</span>
                                    <CheckCheck className="w-4 h-4 text-indigo-500" />
                                </div>
                                <div className="text-2xl font-bold text-indigo-900 mt-1">{validRefs}</div>
                                <div className="text-[11px] text-slate-400 mt-1">Source-backed client evidence</div>
                            </Card>

                            <Card className="p-4 border-l-4 border-l-emerald-500">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-emerald-700">3. Verified Contacts</span>
                                    <UserCheck className="w-4 h-4 text-emerald-500" />
                                </div>
                                <div className="text-2xl font-bold text-emerald-900 mt-1">{contactsCount}</div>
                                <div className="text-[11px] text-slate-400 mt-1">Deduplicated professional persons</div>
                            </Card>

                            <Card className="p-4 border-l-4 border-l-blue-600">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-blue-700">4. CRM Leads Created</span>
                                    <BarChart2 className="w-4 h-4 text-blue-600" />
                                </div>
                                <div className="text-2xl font-bold text-blue-900 mt-1">{leadsCount}</div>
                                <div className="text-[11px] text-slate-400 mt-1">Pipeline-ready qualified records</div>
                            </Card>
                        </div>
                    </div>

                    {/* Data-Quality & Verification Breakdown */}
                    <Card className="p-5 bg-gradient-to-br from-slate-50 to-white">
                        <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
                            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                                <Activity className="w-4 h-4 text-indigo-600" />
                                Data Quality & False-Positive Elimination Audit
                            </h3>
                            <Badge variant={metrics.rejected_false_matches ? 'warning' : 'success'}>
                                {metrics.rejected_false_matches || 0} False Positives Rejected
                            </Badge>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                            <div>
                                <span className="text-slate-500 block">Research Crawl Limit</span>
                                <span className="text-sm font-bold text-slate-800">
                                    {job.max_pages ?? 50} pages
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Pages Crawled / Analysed</span>
                                <span className="text-sm font-bold text-slate-800">
                                    {job.pages_crawled ?? 0} / {job.pages_analysed ?? metrics.pages_analysed ?? job.pages_crawled ?? 0}
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Discovered / Attempted</span>
                                <span className="text-sm font-bold text-slate-800">
                                    {job.pages_discovered ?? 0} / {job.pages_attempted ?? 0}
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Failed / Skipped</span>
                                <span className="text-sm font-bold text-slate-800">
                                    {job.pages_failed ?? 0} / {job.pages_skipped ?? 0}
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Company-Only References</span>
                                <span className="text-sm font-bold text-slate-800">
                                    {metrics.company_only_references ?? 0}
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Companies Created</span>
                                <span className="text-sm font-bold text-slate-800">
                                    {metrics.companies_created ?? job.companies_created}
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Pending Verification</span>
                                <span className="text-sm font-bold text-amber-700">
                                    {validRefs} (AI never self-verifies)
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Featured Personalities</span>
                                <span className="text-sm font-semibold text-slate-700">
                                    {metrics.featured_personalities ?? 0} (Not clients)
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Collaborators / Partners</span>
                                <span className="text-sm font-semibold text-slate-700">
                                    {metrics.collaborators ?? 0} (Not clients)
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Ordinary Mentions</span>
                                <span className="text-sm font-semibold text-slate-700">
                                    {metrics.ordinary_mentions ?? 0} (Excluded)
                                </span>
                            </div>

                            <div>
                                <span className="text-slate-500 block">Confidence Distribution</span>
                                <span className="text-xs font-semibold text-slate-700">
                                    High: {metrics.confidence_distribution?.high ?? 0} | Med: {metrics.confidence_distribution?.medium ?? 0} | Low: {metrics.confidence_distribution?.low ?? 0}
                                </span>
                            </div>
                        </div>
                    </Card>

                    {/* Enriched Client Companies & Decision-Makers Dossiers */}
                    {report?.companies && report.companies.length > 0 && (
                        <Card className="p-0 overflow-hidden shadow-sm">
                            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                                <div>
                                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                                        <Building2 className="w-4 h-4 text-indigo-600" /> Discovered Client Companies & Official Contact Dossiers
                                    </h3>
                                    <p className="text-[11px] text-slate-500 mt-0.5">
                                        Official websites crawled, public contact channels extracted, and leadership identified.
                                    </p>
                                </div>
                                <span className="text-xs font-medium text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                                    {report.companies.length} enriched client organizations
                                </span>
                            </div>

                            <div className="divide-y divide-slate-100">
                                {report.companies.map((comp: any, idx: number) => {
                                    const emails = (comp.public_contact_channels || []).filter((c: any) => c.type === 'email');
                                    const phones = (comp.public_contact_channels || []).filter((c: any) => c.type === 'phone');
                                    const forms = (comp.public_contact_channels || []).filter((c: any) => c.type === 'contact_form');
                                    const people = comp.associated_people || [];

                                    return (
                                        <div key={comp.id || idx} className="p-4 hover:bg-slate-50/60 transition-colors">
                                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                                                <div>
                                                    <div className="flex items-center gap-2 flex-wrap">
                                                        <h4 className="font-bold text-slate-900 text-sm">{comp.name}</h4>
                                                        <Badge variant={comp.enrichment_status === 'enriched' ? 'success' : 'default'}>
                                                            {comp.enrichment_status === 'enriched' ? 'Enriched' : 'Discovered'}
                                                        </Badge>
                                                        {comp.industry && (
                                                            <span className="text-slate-500 text-xs font-medium">• {comp.industry}</span>
                                                        )}
                                                    </div>

                                                    <div className="flex items-center gap-3 text-xs text-slate-500 mt-1 flex-wrap">
                                                        {comp.website && (
                                                            <a
                                                                href={comp.website}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="text-blue-600 hover:underline flex items-center gap-1 font-mono text-[11px]"
                                                            >
                                                                <Globe className="w-3 h-3 text-slate-400" />
                                                                {comp.domain || comp.website}
                                                                <ExternalLink className="w-2.5 h-2.5" />
                                                            </a>
                                                        )}
                                                        {comp.address && (
                                                            <span className="flex items-center gap-1 text-slate-600">
                                                                <MapPin className="w-3 h-3 text-slate-400" />
                                                                {comp.address}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-2 flex-wrap">
                                                    {emails.length > 0 && (
                                                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 text-xs font-medium">
                                                            <Mail className="w-3 h-3" /> {emails.length} email{emails.length > 1 ? 's' : ''}
                                                        </span>
                                                    )}
                                                    {phones.length > 0 && (
                                                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium">
                                                            <Phone className="w-3 h-3" /> {phones.length} phone{phones.length > 1 ? 's' : ''}
                                                        </span>
                                                    )}
                                                    {forms.length > 0 && (
                                                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-purple-50 text-purple-700 text-xs font-medium">
                                                            <FileText className="w-3 h-3" /> Form
                                                        </span>
                                                    )}
                                                    {people.length > 0 && (
                                                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-medium">
                                                            <UserCheck className="w-3 h-3" /> {people.length} leader{people.length > 1 ? 's' : ''}
                                                        </span>
                                                    )}
                                                    <button
                                                        onClick={() => setSelectedCompany(comp)}
                                                        className="px-3 py-1 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-indigo-600 text-xs font-semibold shadow-2xs transition-colors"
                                                    >
                                                        View Full Dossier
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Discovered Leaders preview */}
                                            {people.length > 0 && (
                                                <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center gap-3 flex-wrap">
                                                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Identified Leadership:</span>
                                                    {people.map((p: any, pIdx: number) => (
                                                        <div key={pIdx} className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-100 text-slate-800 text-xs">
                                                            <span className="font-semibold">{p.full_name}</span>
                                                            <span className="text-slate-500 text-[11px]">({p.designation || 'Leader'})</span>
                                                            {p.linkedin_url && (
                                                                <a href={p.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                                                                    <ExternalLink className="w-2.5 h-2.5" />
                                                                </a>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </Card>
                    )}

                    {/* Validated Client References Table */}
                    <Card className="p-0 overflow-hidden shadow-sm">
                        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                                    <Users className="w-4 h-4 text-indigo-600" /> Validated Client References
                                </h3>
                                <p className="text-[11px] text-slate-500 mt-0.5">
                                    Genuinely accurate, source-backed client references with exact quotations.
                                </p>
                            </div>
                            <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
                                {references.length} verified records
                            </span>
                        </div>

                        {references.length === 0 ? (
                            <div className="p-8 text-center text-xs text-slate-500">
                                No verified B2B client references were extracted on this domain.
                                {isPersonReport && (
                                    <div className="mt-2 text-indigo-600 font-semibold">
                                        Note: This target was identified as an Individual Person Profile. Switch to the "Person Intelligence" tab to inspect the profile, contacts, and social handles!
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="w-full text-xs text-left">
                                    <thead className="bg-slate-50 border-b border-slate-200">
                                        <tr className="text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                                            <th className="py-3 px-4">Person Name</th>
                                            <th className="py-3 px-4">Designation</th>
                                            <th className="py-3 px-4">Company</th>
                                            <th className="py-3 px-4">Relationship Type</th>
                                            <th className="py-3 px-4">Status</th>
                                            <th className="py-3 px-4">Evidence Quote</th>
                                            <th className="py-3 px-4">Source Page</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100">
                                        {references.map((ref) => (
                                            <tr key={ref.id} className="hover:bg-slate-50 transition-colors">
                                                <td className="py-3 px-4 font-semibold text-slate-900">
                                                    {ref.person_name || <span className="text-slate-400 italic">Company-only</span>}
                                                </td>
                                                <td className="py-3 px-4 text-slate-700">{ref.designation || '—'}</td>
                                                <td className="py-3 px-4 text-slate-700 font-medium">{ref.company_name || '—'}</td>
                                                <td className="py-3 px-4">
                                                    <Badge variant="purple">
                                                        {ref.relationship_type?.replace(/_/g, ' ')}
                                                    </Badge>
                                                </td>
                                                <td className="py-3 px-4">
                                                    <Badge variant="warning">
                                                        {ref.verification_status || 'pending'}
                                                    </Badge>
                                                </td>
                                                <td className="py-3 px-4 text-slate-600 max-w-md">
                                                    {ref.evidence_quote ? (
                                                        <span className="italic text-[11px] block bg-slate-50 p-1.5 rounded border border-slate-100">
                                                            "{ref.evidence_quote.slice(0, 220)}..."
                                                        </span>
                                                    ) : '—'}
                                                </td>
                                                <td className="py-3 px-4 whitespace-nowrap">
                                                    {ref.source_url && (
                                                        <a
                                                            href={ref.source_url}
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="text-blue-600 hover:underline text-[11px] inline-flex items-center gap-1"
                                                        >
                                                            <Globe className="w-3 h-3" /> Source <ExternalLink className="w-2.5 h-2.5" />
                                                        </a>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </Card>

                    {/* Internal Data-Quality Review & Rejection Audit */}
                    {rejectedCandidates.length > 0 && (
                        <Card className="p-4 border border-rose-200 bg-rose-50/30">
                            <button
                                onClick={() => setShowRejected(!showRejected)}
                                className="w-full flex items-center justify-between text-left text-xs font-bold text-rose-800"
                            >
                                <div className="flex items-center gap-2">
                                    <ShieldAlert className="w-4 h-4 text-rose-600" />
                                    Internal Data-Quality Review: Rejected False Candidates ({rejectedCandidates.length})
                                </div>
                                <div className="flex items-center gap-1 text-[11px] text-rose-600">
                                    {showRejected ? 'Hide Rejections' : 'Inspect Rejection Reasons'}
                                    {showRejected ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </div>
                            </button>

                            {showRejected && (
                                <div className="mt-3 overflow-x-auto">
                                    <table className="w-full text-xs text-left bg-white rounded border border-rose-100">
                                        <thead className="bg-rose-50/50 border-b border-rose-100 text-[11px] text-rose-900 font-semibold">
                                            <tr>
                                                <th className="py-2.5 px-3">Rejected Candidate</th>
                                                <th className="py-2.5 px-3">Rejection Reasons</th>
                                                <th className="py-2.5 px-3">Sample Context</th>
                                                <th className="py-2.5 px-3">Source URL</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-rose-50 text-[11px]">
                                            {rejectedCandidates.map((rej: any, idx: number) => (
                                                <tr key={idx} className="hover:bg-rose-50/20">
                                                    <td className="py-2 px-3 font-semibold text-rose-900">
                                                        {rej.candidate_name || rej.person_name || rej.company_name}
                                                    </td>
                                                    <td className="py-2 px-3 text-rose-700">
                                                        <ul className="list-disc list-inside space-y-0.5">
                                                            {(rej.rejection_reasons || []).map((r: string, ri: number) => (
                                                                <li key={ri}>{r}</li>
                                                            ))}
                                                        </ul>
                                                    </td>
                                                    <td className="py-2 px-3 text-slate-500 max-w-xs truncate italic">
                                                        "{rej.evidence_quote}"
                                                    </td>
                                                    <td className="py-2 px-3 text-blue-600 truncate max-w-xs">
                                                        <a href={rej.source_url} target="_blank" rel="noreferrer" className="hover:underline">
                                                            {rej.source_url}
                                                        </a>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </Card>
                    )}
                </div>
            )}

            {selectedCompany && (
                <CompanyDetailModal
                    isOpen={!!selectedCompany}
                    onClose={() => setSelectedCompany(null)}
                    company={selectedCompany}
                />
            )}
        </div>
    );
};
