import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
    ArrowLeft, Globe, ExternalLink, AlertCircle, CheckCircle2, Building2, Users, Mail, FileText,
} from 'lucide-react';
import api from '../../services/api';
import { getCrawlJob, getJobReport } from '../../services/discovery';
import { CrawlJob } from '../../types';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { formatDateTime } from '../../utils/format';

export const ResearchReport: React.FC = () => {
    const { jobId } = useParams<{ jobId: string }>();
    const [job, setJob] = useState<CrawlJob | null>(null);
    const [report, setReport] = useState<any>(null);
    const [references, setReferences] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!jobId) return;
        (async () => {
            try {
                const [j, r, refsRes] = await Promise.all([
                    getCrawlJob(jobId),
                    getJobReport(jobId).catch(() => null),
                    api.get('/references', { params: { provider_id: '', page_size: 200 } }).catch(() => ({ data: { items: [] } })),
                ]);
                setJob(j);
                setReport(r);
                // Fetch references by provider of this job
                if (j?.provider_id) {
                    const refs = await api.get('/references', { params: { provider_id: j.provider_id, page_size: 200 } });
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

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <Link to="/discovery" className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100">
                    <ArrowLeft className="w-5 h-5" />
                </Link>
                <div>
                    <h1 className="text-xl font-bold text-slate-900 tracking-tight">Provider Research Report</h1>
                    <p className="text-xs text-slate-500 mt-0.5">{job.starting_url}</p>
                </div>
            </div>

            {/* Overview metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card className="p-4"><div className="text-xs text-slate-500">URLs Discovered</div><div className="text-2xl font-bold text-slate-900">{job.pages_discovered}</div></Card>
                <Card className="p-4"><div className="text-xs text-slate-500">Pages Crawled</div><div className="text-2xl font-bold text-emerald-700">{job.pages_crawled}</div></Card>
                <Card className="p-4"><div className="text-xs text-slate-500">Client References</div><div className="text-2xl font-bold text-indigo-700">{job.references_found}</div></Card>
                <Card className="p-4"><div className="text-xs text-slate-500">CRM Leads Created</div><div className="text-2xl font-bold text-slate-900">{job.leads_created}</div></Card>
            </div>

            {/* Status banner */}
            <Card className="p-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs">
                        <Badge variant={job.status.startsWith('completed') ? 'success' : 'danger'}>
                            {job.status.replace(/_/g, ' ')}
                        </Badge>
                        <span className="text-slate-500">Stage: <span className="font-semibold">{job.current_stage}</span></span>
                        <span className="text-slate-500">Started: {formatDateTime(job.started_at)}</span>
                        {job.completed_at && <span className="text-slate-500">Completed: {formatDateTime(job.completed_at)}</span>}
                    </div>
                </div>
            </Card>

            {/* Client references table */}
            <Card className="p-0 overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2"><Users className="w-4 h-4" /> Client References</h3>
                    <span className="text-xs text-slate-500">{references.length} records</span>
                </div>
                {references.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-500">
                        No client references were extracted from this crawl. This may mean the website does not publicly disclose client case studies, or that pages were blocked.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-xs text-left">
                            <thead className="bg-slate-50 border-b border-slate-200">
                                <tr className="text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                                    <th className="py-3 px-4">Name</th>
                                    <th className="py-3 px-4">Designation</th>
                                    <th className="py-3 px-4">Company</th>
                                    <th className="py-3 px-4">Relationship</th>
                                    <th className="py-3 px-4">Evidence</th>
                                    <th className="py-3 px-4">Source</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {references.map((ref) => (
                                    <tr key={ref.id} className="hover:bg-slate-50">
                                        <td className="py-3 px-4 font-semibold text-slate-900">{ref.person_name || '—'}</td>
                                        <td className="py-3 px-4 text-slate-700">{ref.designation || '—'}</td>
                                        <td className="py-3 px-4 text-slate-700">{ref.company_name || '—'}</td>
                                        <td className="py-3 px-4"><Badge variant="purple">{ref.relationship_type?.replace(/_/g, ' ')}</Badge></td>
                                        <td className="py-3 px-4 text-slate-600 max-w-md">
                                            {ref.evidence_quote ? <span className="italic">"{ref.evidence_quote.slice(0, 180)}..."</span> : '—'}
                                        </td>
                                        <td className="py-3 px-4">
                                            {ref.source_url && (
                                                <a href={ref.source_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-[11px] flex items-center gap-1">
                                                    <Globe className="w-3 h-3" /> open <ExternalLink className="w-2.5 h-2.5" />
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

            {/* Report metadata */}
            {report && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card className="p-4">
                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                            <Mail className="w-3.5 h-3.5" /> Public Emails Discovered
                        </h4>
                        {report.public_emails_discovered && report.public_emails_discovered.length > 0 ? (
                            <ul className="text-xs space-y-1 font-mono">
                                {report.public_emails_discovered.map((e: string) => <li key={e} className="text-slate-700">{e}</li>)}
                            </ul>
                        ) : <p className="text-xs text-slate-400">None published</p>}
                    </Card>
                    <Card className="p-4">
                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                            <Building2 className="w-3.5 h-3.5" /> Social Media Profiles
                        </h4>
                        {report.social_media_profiles && Object.keys(report.social_media_profiles).length > 0 ? (
                            <ul className="text-xs space-y-1">
                                {Object.entries(report.social_media_profiles).map(([platform, urls]: [string, any]) => (
                                    <li key={platform} className="flex gap-2">
                                        <span className="font-semibold capitalize text-slate-700">{platform}:</span>
                                        <span className="text-slate-600 truncate">{Array.isArray(urls) ? urls[0] : String(urls)}</span>
                                    </li>
                                ))}
                            </ul>
                        ) : <p className="text-xs text-slate-400">None discovered</p>}
                    </Card>
                </div>
            )}

            {/* Errors */}
            {job.errors && job.errors.length > 0 && (
                <Card className="p-4">
                    <h4 className="text-xs font-bold text-rose-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" /> Failed URLs & Errors ({job.errors.length})
                    </h4>
                    <div className="max-h-60 overflow-y-auto space-y-1 text-[11px] font-mono">
                        {job.errors.map((e, i) => (
                            <div key={i} className="p-2 bg-rose-50 border border-rose-100 rounded">
                                <div className="text-rose-800 font-bold">[{e.stage}] {e.error_type}</div>
                                <div className="text-rose-700">{e.url || '(n/a)'}</div>
                                <div className="text-rose-600">{e.message}</div>
                            </div>
                        ))}
                    </div>
                </Card>
            )}
        </div>
    );
};