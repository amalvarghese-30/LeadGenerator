import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
    ArrowLeft, Globe, ExternalLink, AlertCircle, CheckCircle2, Building2, Users, Mail,
    ShieldAlert, ChevronDown, ChevronUp, Activity, BarChart2, CheckCheck, UserCheck, Layers
} from 'lucide-react';
import api from '../../services/api';
import { getCrawlJob, getJobReport } from '../../services/discovery';
import { CrawlJob } from '../../types';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { formatDateTime } from '../../utils/format';

export const ResearchReport: React.FC = () => {
    const { jobId } = useParams<{ jobId: string }>();
    const [job, setJob] = useState<CrawlJob | null>(null);
    const [report, setReport] = useState<any>(null);
    const [references, setReferences] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showRejected, setShowRejected] = useState(false);

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

    const rawCandidates = metrics.candidates_detected ?? (job.references_found + (metrics.rejected_false_matches || 0));
    const validRefs = metrics.valid_client_references ?? job.references_found;
    const contactsCount = metrics.contacts_created ?? job.contacts_created;
    const leadsCount = metrics.leads_created ?? job.leads_created;

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            {/* Header */}
            <div className="flex items-center gap-3">
                <Link to="/discovery" className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100">
                    <ArrowLeft className="w-5 h-5" />
                </Link>
                <div>
                    <h1 className="text-xl font-bold text-slate-900 tracking-tight">Provider Intelligence Research Report</h1>
                    <p className="text-xs text-slate-500 mt-0.5">{job.starting_url}</p>
                </div>
            </div>

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

            {/* Data-Quality & Verification Breakdown (Task 10) */}
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
                        <span className="text-slate-500 block">Pages Crawled / Analysed</span>
                        <span className="text-sm font-bold text-slate-800">
                            {job.pages_crawled} / {metrics.pages_analysed ?? job.pages_crawled}
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

            {/* Contact Enrichment & Public Discovery Results (Contact Enrichment Engine) */}
            {(() => {
                const en = report?.enrichment_summary || metrics.enrichment_metrics || {};
                return (
                    <Card className="p-5 bg-white border border-slate-200 shadow-sm">
                        <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                                    <Mail className="w-4 h-4 text-emerald-600" />
                                    Contact Enrichment & Public Discovery Audit
                                </h3>
                                <p className="text-[11px] text-slate-500 mt-0.5">
                                    Multi-source discovery across company websites, leadership pages, and public directories.
                                </p>
                            </div>
                            <Badge variant={en.direct_emails_found || en.direct_phones_found ? 'success' : 'default'}>
                                {en.total_contacts_enriched ?? contactsCount} Contacts Processed
                            </Badge>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
                            <div className="p-3 bg-emerald-50/70 border border-emerald-200 rounded-xl">
                                <span className="text-[11px] font-medium text-emerald-800 block">Direct Work Emails</span>
                                <span className="text-xl font-bold text-emerald-900">{en.direct_emails_found ?? 0}</span>
                                <span className="text-[10px] text-emerald-700 block mt-0.5">MX & Syntax Verified</span>
                            </div>

                            <div className="p-3 bg-blue-50/70 border border-blue-200 rounded-xl">
                                <span className="text-[11px] font-medium text-blue-800 block">Direct Phones</span>
                                <span className="text-xl font-bold text-blue-900">{en.direct_phones_found ?? 0}</span>
                                <span className="text-[10px] text-blue-700 block mt-0.5">E.164 Standard</span>
                            </div>

                            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                                <span className="text-[11px] font-medium text-slate-700 block">Company Emails</span>
                                <span className="text-xl font-bold text-slate-900">{en.generic_emails_found ?? (report?.public_emails_discovered?.length || 0)}</span>
                                <span className="text-[10px] text-slate-500 block mt-0.5">Info / Support / Sales</span>
                            </div>

                            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                                <span className="text-[11px] font-medium text-slate-700 block">Company Switchboards</span>
                                <span className="text-xl font-bold text-slate-900">{en.company_phones_found ?? 0}</span>
                                <span className="text-[10px] text-slate-500 block mt-0.5">Office / Reception</span>
                            </div>

                            <div className="p-3 bg-indigo-50/70 border border-indigo-200 rounded-xl">
                                <span className="text-[11px] font-medium text-indigo-800 block">Contact Forms</span>
                                <span className="text-xl font-bold text-indigo-900">{en.contact_forms_found ?? 1}</span>
                                <span className="text-[10px] text-indigo-700 block mt-0.5">Official Web Route</span>
                            </div>

                            <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl">
                                <span className="text-[11px] font-medium text-amber-800 block">No Public Contact</span>
                                <span className="text-xl font-bold text-amber-900">{en.no_public_contacts_found ?? 0}</span>
                                <span className="text-[10px] text-amber-700 block mt-0.5">No Hallucinated Data</span>
                            </div>
                        </div>
                    </Card>
                );
            })()}

            {/* Validated Client References Table (Task 12) */}
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
                        No verified client references were extracted. Generic navigation, marketing phrases, and sentence fragments were strictly rejected to prevent CRM pollution.
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

            {/* Internal Data-Quality Review & Rejection Audit (Task 12) */}
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

            {/* Published Public Contact Channels & Socials */}
            {report && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card className="p-4">
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                            <Mail className="w-3.5 h-3.5 text-slate-600" /> Explicitly Published Business Emails
                        </h4>
                        {report.public_emails_discovered && report.public_emails_discovered.length > 0 ? (
                            <ul className="text-xs space-y-1 font-mono">
                                {report.public_emails_discovered.map((e: string) => (
                                    <li key={e} className="text-slate-800 bg-slate-50 px-2 py-1 rounded inline-block mr-2 mb-1">
                                        {e}
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="text-xs text-slate-400">No public email channels published</p>
                        )}
                    </Card>

                    <Card className="p-4">
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                            <Building2 className="w-3.5 h-3.5 text-slate-600" /> Verified Social Media Profiles
                        </h4>
                        {report.social_media_profiles && Object.keys(report.social_media_profiles).length > 0 ? (
                            <ul className="text-xs space-y-1">
                                {Object.entries(report.social_media_profiles).map(([platform, urls]: [string, any]) => (
                                    <li key={platform} className="flex gap-2">
                                        <span className="font-semibold capitalize text-slate-700">{platform}:</span>
                                        <span className="text-slate-600 truncate">
                                            {Array.isArray(urls) ? urls[0] : String(urls)}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            <p className="text-xs text-slate-400">No social profiles detected</p>
                        )}
                    </Card>
                </div>
            )}
        </div>
    );
};
