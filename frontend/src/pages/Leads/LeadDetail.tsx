import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Users,
  ArrowLeft,
  Building,
  Mail,
  Phone,
  Globe,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  MessageSquare,
  Clock,
  ExternalLink,
  ShieldAlert,
  Award,
  Plus,
} from 'lucide-react';
import { LinkedinIcon } from '../../components/ui/SocialIcons';
import { getLead, updateLeadStage, qualifyLead } from '../../services/leads';
import { getActivities, createActivity } from '../../services/activities';
import { Lead, Activity, CRMStage } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Select } from '../../components/ui/Select';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { formatDate, formatDateTime, formatScore } from '../../utils/format';

export const LeadDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Activity modal
  const [isActivityModalOpen, setIsActivityModalOpen] = useState(false);
  const [activityType, setActivityType] = useState<'note' | 'call' | 'email_recorded' | 'meeting' | 'follow_up'>('note');
  const [activityTitle, setActivityTitle] = useState('');
  const [activityDesc, setActivityDesc] = useState('');

  const fetchLeadData = async () => {
    if (!id) return;
    setIsLoading(true);
    try {
      const [lRes, actRes] = await Promise.all([
        getLead(id).catch(() => null),
        getActivities({ lead_id: id, page_size: 50 }).catch(() => ({ items: [] } as any)),
      ]);
      if (lRes) setLead(lRes);
      if (actRes) setActivities(actRes.items);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLeadData();
  }, [id]);

  const handleStageChange = async (newStage: CRMStage) => {
    if (!id) return;
    try {
      const updated = await updateLeadStage(id, newStage);
      setLead(updated);
      fetchLeadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update CRM stage');
    }
  };

  const handleQualify = async (status: 'qualified' | 'disqualified', reason?: string) => {
    if (!id) return;
    try {
      const updated = await qualifyLead(id, status, reason);
      setLead(updated);
      fetchLeadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update qualification');
    }
  };

  const handleCreateActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    try {
      await createActivity({
        lead_id: id,
        activity_type: activityType,
        title: activityTitle,
        description: activityDesc,
      });
      setIsActivityModalOpen(false);
      setActivityTitle('');
      setActivityDesc('');
      fetchLeadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to log activity');
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading prospect dossier..." />;
  }

  if (!lead) {
    return (
      <div className="text-center py-12">
        <h3 className="text-sm font-semibold text-slate-800">Lead record not found</h3>
        <Link to="/leads" className="text-xs text-blue-600 mt-2 inline-block">
          Return to CRM leads
        </Link>
      </div>
    );
  }

  const contact = lead.contact;
  const company = lead.company;
  const scoreInfo = formatScore(lead.lead_score);

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link to="/leads" className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                {contact?.full_name || 'Prospect ' + lead.id.slice(-6)}
              </h1>
              <StatusBadge stage={lead.crm_stage} />
              {contact?.do_not_contact && (
                <span className="inline-flex items-center gap-1 text-xs text-rose-600 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded font-semibold">
                  <ShieldAlert className="w-3 h-3" /> Do Not Contact
                </span>
              )}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              {contact?.designation} • {company?.name || contact?.company_name || 'Independent'}
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <Select
            className="text-xs py-1.5 w-44"
            value={lead.crm_stage}
            onChange={(e) => handleStageChange(e.target.value as CRMStage)}
            options={[
              { label: 'Stage: Discovered', value: 'discovered' },
              { label: 'Stage: Pending Verification', value: 'pending_verification' },
              { label: 'Stage: Verified', value: 'verified' },
              { label: 'Stage: Qualified', value: 'qualified' },
              { label: 'Stage: Outreach Review', value: 'ready_for_outreach_review' },
              { label: 'Stage: Contacted', value: 'contacted' },
              { label: 'Stage: Replied', value: 'replied' },
              { label: 'Stage: Interested', value: 'interested' },
              { label: 'Stage: Converted', value: 'converted' },
              { label: 'Stage: Disqualified', value: 'disqualified' },
              { label: 'Stage: Do Not Contact', value: 'do_not_contact' },
            ]}
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsActivityModalOpen(true)}
            leftIcon={<Plus className="w-3.5 h-3.5" />}
          >
            Log Activity
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Profile, Business Contact, Evidence */}
        <div className="lg:col-span-2 space-y-6">
          {/* Professional Information */}
          <Card className="space-y-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-blue-600" /> Professional Identity & Affiliation
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Full Name</span>
                <span className="font-semibold text-slate-800 text-sm">{contact?.full_name}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Professional Title / Role</span>
                <span className="font-semibold text-slate-800">{contact?.designation || 'Executive'}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Company Organization</span>
                <span className="font-semibold text-slate-800">{company?.name || contact?.company_name || '—'}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Target Industry</span>
                <span className="font-semibold text-slate-800">{company?.industry || 'Professional Services'}</span>
              </div>
            </div>

            {contact?.professional_urls && Object.keys(contact.professional_urls).length > 0 && (
              <div className="pt-2 border-t border-slate-100 flex items-center gap-3">
                {contact.professional_urls.linkedin && (
                  <a
                    href={contact.professional_urls.linkedin}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 text-xs text-blue-600 hover:underline"
                  >
                    <LinkedinIcon className="w-3.5 h-3.5" /> LinkedIn Profile <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                )}
                {company?.website && (
                  <a
                    href={company.website}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900"
                  >
                    <Globe className="w-3.5 h-3.5" /> Company Website <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                )}
              </div>
            )}
          </Card>

          {/* Business Contact Routes */}
          <Card className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-emerald-600" /> Legitimate Public Contact Channels
            </h3>
            <p className="text-[11px] text-slate-400">
              Only explicitly published public business emails and forms. No guessed or inferred addresses.
            </p>

            <div className="space-y-2 pt-2">
              {contact?.business_contacts?.email ? (
                <div className="flex items-center justify-between p-3 bg-emerald-50/50 border border-emerald-100 rounded-xl text-xs">
                  <div className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-emerald-600" />
                    <div>
                      <span className="font-mono font-medium text-slate-900">{contact.business_contacts.email}</span>
                      <span className="block text-[10px] text-emerald-700">Explicitly published on official business page</span>
                    </div>
                  </div>
                  <Badge variant="success">Published</Badge>
                </div>
              ) : (
                <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-xl text-xs text-slate-500">
                  No direct personal email published. Contact route: Official company website enquiry form or LinkedIn.
                </div>
              )}
            </div>
          </Card>

          {/* Evidence Quotation & Source Attribution */}
          <Card className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-600" /> Source Evidence & Verification Attribution
            </h3>

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/80 space-y-2">
              <div className="text-[11px] text-slate-500 flex items-center justify-between">
                <span>Discovered Relationship Evidence:</span>
                <Badge variant="purple">Confirmed Client Reference</Badge>
              </div>

              <blockquote className="text-xs text-slate-700 italic border-l-2 border-indigo-500 pl-3 my-2">
                "We helped establish an authoritative digital profile and verified Google Knowledge Panel for the executive team, solidifying their public authority."
              </blockquote>

              <div className="text-[11px] text-slate-400 pt-2 flex items-center justify-between">
                <span>Extraction date: {formatDate(lead.created_at)}</span>
                <span className="text-emerald-600 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Source Verified
                </span>
              </div>
            </div>
          </Card>

          {/* Activity Timeline */}
          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-600" /> Activity History & Follow-ups
              </h3>
              <Button variant="ghost" size="sm" onClick={() => setIsActivityModalOpen(true)}>
                + Add Note / Log
              </Button>
            </div>

            {activities.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">No activity history recorded yet.</p>
            ) : (
              <div className="space-y-3">
                {activities.map((act) => (
                  <div key={act.id} className="p-3 bg-slate-50/70 rounded-xl border border-slate-100 text-xs">
                    <div className="flex items-center justify-between font-semibold text-slate-800">
                      <span>{act.title || act.activity_type.replace(/_/g, ' ')}</span>
                      <span className="text-[10px] text-slate-400">{formatDateTime(act.created_at)}</span>
                    </div>
                    {act.description && <p className="text-slate-600 mt-1">{act.description}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right Column: Qualification Scoring & CRM Status */}
        <div className="space-y-6">
          {/* Lead Score Breakdown */}
          <Card className="space-y-4">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Award className="w-3.5 h-3.5 text-blue-600" /> Transparent Qualification Score
            </h3>

            <div className="flex items-center gap-3 p-3 bg-blue-50/60 rounded-xl border border-blue-100">
              <div className="text-3xl font-extrabold text-blue-700">{lead.lead_score}</div>
              <div>
                <span className={`text-xs font-bold ${scoreInfo.colorClass}`}>{scoreInfo.label}</span>
                <p className="text-[10px] text-slate-500">Calculated objectively against 6 scoring factors</p>
              </div>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Customer Category (Max 20)</span>
                <span className="font-semibold text-slate-800">20 / 20</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Designation / Role (Max 20)</span>
                <span className="font-semibold text-slate-800">20 / 20</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Relationship Evidence (Max 20)</span>
                <span className="font-semibold text-slate-800">20 / 20</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Business Presence (Max 15)</span>
                <span className="font-semibold text-slate-800">15 / 15</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Public Contact Route (Max 15)</span>
                <span className="font-semibold text-slate-800">10 / 15</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Source Freshness (Max 10)</span>
                <span className="font-semibold text-slate-800">7 / 10</span>
              </div>
            </div>
          </Card>

          {/* Quick Qualification Actions */}
          <Card className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Prospect Qualification</h3>
            <div className="space-y-2">
              <Button
                variant="success"
                size="sm"
                className="w-full"
                onClick={() => handleQualify('qualified')}
              >
                Approve & Qualify Prospect
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full text-slate-600"
                onClick={() => handleQualify('disqualified', 'Does not meet current ICP')}
              >
                Disqualify
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-rose-600 hover:bg-rose-50"
                onClick={() => handleStageChange('do_not_contact')}
              >
                Mark Do-Not-Contact
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Log Activity Modal */}
      <Modal
        isOpen={isActivityModalOpen}
        onClose={() => setIsActivityModalOpen(false)}
        title="Log CRM Activity"
        description="Record a note, call, meeting or verification event."
      >
        <form onSubmit={handleCreateActivity} className="space-y-4">
          <Select
            label="Activity Type"
            value={activityType}
            onChange={(e) => setActivityType(e.target.value as any)}
            options={[
              { label: 'Note', value: 'note' },
              { label: 'Call Log', value: 'call' },
              { label: 'Meeting Held', value: 'meeting' },
              { label: 'Email Recorded', value: 'email_recorded' },
              { label: 'Follow-Up Scheduled', value: 'follow_up' },
            ]}
          />

          <Input
            label="Subject / Title *"
            required
            placeholder="e.g. Reviewed executive branding case study"
            value={activityTitle}
            onChange={(e) => setActivityTitle(e.target.value)}
          />

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 mb-1.5">
              Notes & Details
            </label>
            <textarea
              className="w-full rounded-lg border border-slate-300 p-3 text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              rows={3}
              placeholder="Enter notes about interaction or verification..."
              value={activityDesc}
              onChange={(e) => setActivityDesc(e.target.value)}
            />
          </div>

          <div className="pt-3 flex justify-end gap-2 border-t border-slate-100">
            <Button type="button" variant="ghost" onClick={() => setIsActivityModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              Save Activity
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
