import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Edit3,
  BookmarkPlus,
  History,
  Globe,
} from 'lucide-react';
import {
  LinkedinIcon,
  TwitterIcon,
  GithubIcon,
  InstagramIcon,
  FacebookIcon,
  YoutubeIcon,
} from '../../components/ui/SocialIcons';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import {
  discoverProfile,
  saveProfileToCrm,
  getRecentProfileCandidates,
} from '../../services/profileCreator';
import { ProfileCandidate } from '../../types';

export const AutoProfileCreator: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'create' | 'candidates'>('create');

  // Input fields
  const [fullName, setFullName] = useState('');
  const [company, setCompany] = useState('');
  const [designation, setDesignation] = useState('');
  const [location, setLocation] = useState('');

  // Execution state
  const [isLoading, setIsLoading] = useState(false);
  const [candidate, setCandidate] = useState<ProfileCandidate | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Editable candidate fields
  const [editBio, setEditBio] = useState('');
  const [editLinkedin, setEditLinkedin] = useState('');
  const [editTwitter, setEditTwitter] = useState('');
  const [editGithub, setEditGithub] = useState('');

  // Candidates list
  const [recentCandidates, setRecentCandidates] = useState<ProfileCandidate[]>([]);
  const [isCandidatesLoading, setIsCandidatesLoading] = useState(false);

  const handleDiscover = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) return;

    setIsLoading(true);
    setError(null);
    setCandidate(null);
    setSaveSuccess(false);

    try {
      const res = await discoverProfile({
        full_name: fullName,
        company: company || undefined,
        designation: designation || undefined,
        location: location || undefined,
      });
      setCandidate(res);
      setEditBio(res.professional_biography || '');
      setEditLinkedin(res.platform_profiles?.linkedin || '');
      setEditTwitter(res.platform_profiles?.twitter || '');
      setEditGithub(res.platform_profiles?.github || '');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Profile discovery failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveToCrm = async () => {
    if (!candidate) return;
    setIsSaving(true);
    try {
      const updatedCandidate: ProfileCandidate = {
        ...candidate,
        professional_biography: editBio,
        platform_profiles: {
          ...candidate.platform_profiles,
          ...(editLinkedin ? { linkedin: editLinkedin } : {}),
          ...(editTwitter ? { twitter: editTwitter } : {}),
          ...(editGithub ? { github: editGithub } : {}),
        },
      };

      await saveProfileToCrm(updatedCandidate, true);
      setSaveSuccess(true);
    } catch (err) {
      console.error('Save profile failed:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const loadCandidates = async () => {
    setIsCandidatesLoading(true);
    try {
      const items = await getRecentProfileCandidates(20);
      setRecentCandidates(items);
    } catch (err) {
      console.error('Failed to load candidates:', err);
    } finally {
      setIsCandidatesLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'candidates') {
      loadCandidates();
    }
  }, [activeTab]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Auto Profile Creator</h1>
          <p className="text-xs text-slate-500 mt-1">
            Synthesize corroborated executive profiles across professional networks and save verified records to Contacts CRM.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={activeTab === 'create' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setActiveTab('create')}
          >
            <Sparkles className="w-3.5 h-3.5 mr-1.5" />
            Profile Creator
          </Button>
          <Button
            variant={activeTab === 'candidates' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setActiveTab('candidates')}
          >
            <History className="w-3.5 h-3.5 mr-1.5" />
            Generated Profiles
          </Button>
        </div>
      </div>

      {activeTab === 'create' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Input Form */}
          <div className="lg:col-span-4 space-y-4">
            <Card className="p-5">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3.5">
                Target Executive
              </h2>
              <form onSubmit={handleDiscover} className="space-y-3.5">
                <Input
                  label="Full Name *"
                  placeholder="e.g. Satya Nadella"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
                <Input
                  label="Known Company"
                  placeholder="e.g. Microsoft"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
                <Input
                  label="Professional Title"
                  placeholder="e.g. Chairman and CEO"
                  value={designation}
                  onChange={(e) => setDesignation(e.target.value)}
                />
                <Input
                  label="Location"
                  placeholder="e.g. Greater Seattle Area"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />

                {error && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-100 flex items-start gap-2 text-rose-700 text-xs">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>{error}</span>
                  </div>
                )}

                <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isLoading}>
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  Synthesize Profile
                </Button>
              </form>
            </Card>
          </div>

          {/* Profile Review Section */}
          <div className="lg:col-span-8 space-y-4">
            {isLoading ? (
              <Card className="p-12 flex flex-col items-center justify-center">
                <LoadingSpinner message="Scanning LinkedIn, GitHub, Twitter, biographies, and verifying identity signals..." />
              </Card>
            ) : candidate ? (
              <Card className="p-6 space-y-5">
                {/* Profile Banner */}
                <div className="flex items-start justify-between gap-4 pb-5 border-b border-slate-100">
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Badge variant={candidate.confidence_level === 'high' ? 'success' : candidate.confidence_level === 'medium' ? 'info' : 'warning'}>
                        {Math.round(candidate.confidence_score * 100)}% Confidence ({candidate.confidence_level})
                      </Badge>
                      <Badge variant="default">Pending Confirmation</Badge>
                    </div>
                    <h2 className="text-lg font-bold text-slate-900">{candidate.full_name}</h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {candidate.designation || 'Executive'} {candidate.company_name ? `• ${candidate.company_name}` : ''} {candidate.location ? `• ${candidate.location}` : ''}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={() => setIsEditing(!isEditing)}>
                      <Edit3 className="w-3.5 h-3.5 mr-1" />
                      {isEditing ? 'Done Editing' : 'Edit Details'}
                    </Button>
                    {saveSuccess ? (
                      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 text-emerald-700 text-xs font-bold">
                        <CheckCircle2 className="w-4 h-4" />
                        Saved in CRM
                      </div>
                    ) : (
                      <Button variant="primary" size="sm" onClick={handleSaveToCrm} isLoading={isSaving}>
                        <BookmarkPlus className="w-3.5 h-3.5 mr-1.5" />
                        Save to Contacts CRM
                      </Button>
                    )}
                  </div>
                </div>

                {/* Discovered Platform Links */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2.5">
                    Discovered Professional Profiles
                  </h3>
                  {isEditing ? (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <Input
                        label="LinkedIn URL"
                        value={editLinkedin}
                        onChange={(e) => setEditLinkedin(e.target.value)}
                        placeholder="https://linkedin.com/in/..."
                      />
                      <Input
                        label="X / Twitter URL"
                        value={editTwitter}
                        onChange={(e) => setEditTwitter(e.target.value)}
                        placeholder="https://x.com/..."
                      />
                      <Input
                        label="GitHub URL"
                        value={editGithub}
                        onChange={(e) => setEditGithub(e.target.value)}
                        placeholder="https://github.com/..."
                      />
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2.5">
                      {Object.entries(candidate.platform_profiles || {}).map(([plat, url]) => (
                        <a
                          key={plat}
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-200/80 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors"
                        >
                          {plat === 'linkedin' && <LinkedinIcon className="w-3.5 h-3.5 text-blue-600" />}
                          {plat === 'twitter' && <TwitterIcon className="w-3.5 h-3.5 text-sky-500" />}
                          {plat === 'github' && <GithubIcon className="w-3.5 h-3.5 text-slate-800" />}
                          {plat === 'instagram' && <InstagramIcon className="w-3.5 h-3.5 text-rose-500" />}
                          {plat === 'facebook' && <FacebookIcon className="w-3.5 h-3.5 text-blue-700" />}
                          {plat === 'youtube' && <YoutubeIcon className="w-3.5 h-3.5 text-red-600" />}
                          {!['linkedin', 'twitter', 'github', 'instagram', 'facebook', 'youtube'].includes(plat) && (
                            <Globe className="w-3.5 h-3.5 text-slate-500" />
                          )}
                          <span className="capitalize">{plat}</span>
                          <ExternalLink className="w-3 h-3 text-slate-400" />
                        </a>
                      ))}
                      {Object.keys(candidate.platform_profiles || {}).length === 0 && (
                        <span className="text-xs text-slate-400 italic">No direct social profile links identified.</span>
                      )}
                    </div>
                  )}
                </div>

                {/* Professional Biography */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                    Professional Biography
                  </h3>
                  {isEditing ? (
                    <textarea
                      rows={3}
                      value={editBio}
                      onChange={(e) => setEditBio(e.target.value)}
                      className="w-full text-xs p-3 rounded-xl border border-slate-200 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20"
                    />
                  ) : (
                    <p className="text-xs text-slate-600 leading-relaxed bg-slate-50/80 p-3.5 rounded-xl border border-slate-100">
                      {candidate.professional_biography || 'No aggregated public biography available.'}
                    </p>
                  )}
                </div>

                {/* Supporting Source Evidence */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2.5">
                    Supporting Identity Evidence ({candidate.evidence_items?.length || 0})
                  </h3>
                  <div className="space-y-2">
                    {(candidate.evidence_items || []).map((ev, evIdx) => (
                      <div key={evIdx} className="p-3 rounded-xl bg-white border border-slate-100 text-xs">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-semibold text-slate-800">{ev.title || ev.type}</span>
                          {ev.confidence && (
                            <span className="text-[10px] text-slate-400">
                              Confidence: {Math.round(ev.confidence * 100)}%
                            </span>
                          )}
                        </div>
                        <p className="text-slate-500 line-clamp-2">{ev.evidence_quote}</p>
                        {ev.source_url && (
                          <a
                            href={ev.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[11px] text-blue-600 hover:underline flex items-center gap-1 mt-1 font-mono truncate"
                          >
                            <span className="truncate">{ev.source_url}</span>
                            <ExternalLink className="w-2.5 h-2.5" />
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            ) : (
              <Card className="p-12">
                <EmptyState
                  title="Auto Profile Creator Ready"
                  description="Provide an executive name and company to automatically synthesize verified profiles and social channels."
                />
              </Card>
            )}
          </div>
        </div>
      ) : (
        /* Candidates History */
        <Card className="p-6">
          <h2 className="text-sm font-bold text-slate-800 mb-4">Synthesized Profile History</h2>
          {isCandidatesLoading ? (
            <div className="py-8 flex justify-center">
              <LoadingSpinner message="Loading profiles..." />
            </div>
          ) : recentCandidates.length === 0 ? (
            <EmptyState
              title="No Profiles Generated Yet"
              description="Profiles generated with Auto Profile Creator will be listed here for historical reference."
            />
          ) : (
            <div className="divide-y divide-slate-100">
              {recentCandidates.map((c) => (
                <div key={c.id} className="py-3.5 flex items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900">{c.full_name}</span>
                      <Badge variant={c.verification_status === 'confirmed' ? 'success' : 'default'}>
                        {c.verification_status}
                      </Badge>
                      <Badge variant="info">
                        {Math.round(c.confidence_score * 100)}% Match
                      </Badge>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      {c.designation || 'Executive'} {c.company_name ? `at ${c.company_name}` : ''} •{' '}
                      {c.created_at ? new Date(c.created_at).toLocaleString() : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
};
