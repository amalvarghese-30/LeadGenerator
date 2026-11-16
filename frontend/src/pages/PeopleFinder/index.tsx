import React, { useState } from 'react';
import {
  UserSearch,
  Search,
  ExternalLink,
  ShieldCheck,
  Building2,
  MapPin,
  Briefcase,
  CheckCircle2,
  BookmarkPlus,
  UserCheck,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { searchIndividual, saveSearchResultToCrm } from '../../services/leadGenerator';
import { SearchResultCandidate } from '../../types';

export const PeopleFinder: React.FC = () => {
  const [fullName, setFullName] = useState('');
  const [company, setCompany] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [location, setLocation] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<SearchResultCandidate[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [savedUrls, setSavedUrls] = useState<Set<string>>(new Set());

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) return;

    setIsLoading(true);
    setHasSearched(true);
    try {
      const res = await searchIndividual({
        full_name: fullName,
        company: company || undefined,
        job_title: jobTitle || undefined,
        location: location || undefined,
      });
      setResults(res.results);
    } catch (err) {
      console.error('People search failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveContact = async (candidate: SearchResultCandidate) => {
    try {
      await saveSearchResultToCrm({
        entity_type: 'individual',
        name: fullName,
        company_name: company || undefined,
        title: jobTitle || undefined,
        url: candidate.url,
        social_platform: candidate.social_platform,
        snippet: candidate.snippet,
        create_lead: true,
      });
      setSavedUrls((prev) => new Set(prev).add(candidate.url));
    } catch (err) {
      console.error('Failed to save contact:', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">People Finder</h1>
        <p className="text-xs text-slate-500 mt-1">
          Locate verified professionals, executives, and founders with cross-network profile corroboration.
        </p>
      </div>

      {/* Filter Card */}
      <Card className="p-5">
        <form onSubmit={handleSearch} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 items-end">
          <Input
            label="Person Name *"
            placeholder="e.g. Satya Nadella"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
          <Input
            label="Current Company"
            placeholder="e.g. Microsoft"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
          <Input
            label="Designation / Role"
            placeholder="e.g. Chief Executive Officer"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
          />
          <Input
            label="Location"
            placeholder="e.g. Redmond, WA"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
          <div className="sm:col-span-2 lg:col-span-4 flex justify-end">
            <Button type="submit" variant="primary" size="md" isLoading={isLoading}>
              <UserSearch className="w-4 h-4 mr-1.5" />
              Find Professionals
            </Button>
          </div>
        </form>
      </Card>

      {/* Results Section */}
      {isLoading ? (
        <Card className="p-12 flex justify-center">
          <LoadingSpinner message="Searching verified profiles and calculating identity match confidence..." />
        </Card>
      ) : hasSearched ? (
        results.length === 0 ? (
          <Card className="p-8">
            <EmptyState
              title="No Profiles Found"
              description="No public profiles matched the specified identity criteria. Try broadening company or location terms."
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {results.map((r, idx) => {
              const isSaved = savedUrls.has(r.url);
              return (
                <Card key={idx} className="p-5 flex flex-col justify-between hover:shadow-md transition-shadow">
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={r.confidence >= 0.8 ? 'success' : r.confidence >= 0.6 ? 'info' : 'warning'}>
                            {Math.round(r.confidence * 100)}% Match
                          </Badge>
                          {r.social_platform && (
                            <Badge variant="default" className="capitalize">
                              {r.social_platform}
                            </Badge>
                          )}
                        </div>
                        <h3 className="text-sm font-bold text-slate-900 line-clamp-1">{r.title}</h3>
                      </div>
                    </div>

                    <a
                      href={r.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline flex items-center gap-1 font-mono truncate"
                    >
                      <span className="truncate">{r.url}</span>
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>

                    {r.snippet && (
                      <p className="text-xs text-slate-600 line-clamp-3 leading-relaxed">
                        {r.snippet}
                      </p>
                    )}

                    {r.evidence_points && r.evidence_points.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-slate-100">
                        {r.evidence_points.map((pt, pIdx) => (
                          <span key={pIdx} className="text-[10px] bg-slate-50 text-slate-600 px-2 py-0.5 rounded-full border border-slate-100">
                            {pt}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 font-medium">Domain: {r.domain}</span>
                    {isSaved ? (
                      <div className="flex items-center gap-1 text-emerald-600 text-xs font-semibold">
                        <CheckCircle2 className="w-4 h-4" />
                        Saved to CRM
                      </div>
                    ) : (
                      <Button variant="secondary" size="sm" onClick={() => handleSaveContact(r)}>
                        <BookmarkPlus className="w-3.5 h-3.5 mr-1 text-blue-600" />
                        Save Contact
                      </Button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )
      ) : (
        <Card className="p-12">
          <EmptyState
            title="People Finder Ready"
            description="Enter a name and optional company to discover public executive profiles with identity verification."
          />
        </Card>
      )}
    </div>
  );
};
