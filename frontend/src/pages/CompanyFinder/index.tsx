import React, { useState } from 'react';
import {
  Building,
  Search,
  ExternalLink,
  Globe,
  MapPin,
  Tag,
  CheckCircle2,
  BookmarkPlus,
  Briefcase,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { searchCompany, saveSearchResultToCrm } from '../../services/leadGenerator';
import { SearchResultCandidate } from '../../types';

export const CompanyFinder: React.FC = () => {
  const [companyName, setCompanyName] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [country, setCountry] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<SearchResultCandidate[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [savedDomains, setSavedDomains] = useState<Set<string>>(new Set());

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!companyName.trim()) return;

    setIsLoading(true);
    setHasSearched(true);
    try {
      const res = await searchCompany({
        company_name: companyName,
        website: website || undefined,
        industry: industry || undefined,
        country: country || undefined,
      });
      setResults(res.results);
    } catch (err) {
      console.error('Company search failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveCompany = async (candidate: SearchResultCandidate) => {
    try {
      await saveSearchResultToCrm({
        entity_type: 'company',
        name: candidate.title || companyName,
        company_name: companyName,
        website: candidate.url,
        domain: candidate.domain,
        snippet: candidate.snippet,
        create_lead: false,
      });
      if (candidate.domain) {
        setSavedDomains((prev) => new Set(prev).add(candidate.domain!));
      }
    } catch (err) {
      console.error('Failed to save company:', err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">Company Finder</h1>
        <p className="text-xs text-slate-500 mt-1">
          Explore organizations, digital agencies, enterprise service providers, and business footprints.
        </p>
      </div>

      {/* Filter Card */}
      <Card className="p-5">
        <form onSubmit={handleSearch} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 items-end">
          <Input
            label="Company Name *"
            placeholder="e.g. Ogilvy"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            required
          />
          <Input
            label="Website (Optional)"
            placeholder="e.g. ogilvy.com"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
          <Input
            label="Industry / Domain"
            placeholder="e.g. Advertising, Marketing, PR"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          />
          <Input
            label="Country Code"
            placeholder="e.g. US, IN, UK"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
          />
          <div className="sm:col-span-2 lg:col-span-4 flex justify-end">
            <Button type="submit" variant="primary" size="md" isLoading={isLoading}>
              <Search className="w-4 h-4 mr-1.5" />
              Find Companies
            </Button>
          </div>
        </form>
      </Card>

      {/* Results Section */}
      {isLoading ? (
        <Card className="p-12 flex justify-center">
          <LoadingSpinner message="Searching public registries, company indexes, and business profiles..." />
        </Card>
      ) : hasSearched ? (
        results.length === 0 ? (
          <Card className="p-8">
            <EmptyState
              title="No Companies Found"
              description="No public organization profiles or websites matched your search criteria."
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {results.map((r, idx) => {
              const isSaved = r.domain ? savedDomains.has(r.domain) : false;
              return (
                <Card key={idx} className="p-5 flex flex-col justify-between hover:shadow-md transition-shadow">
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          {r.is_official_website && (
                            <Badge variant="success">Official Website</Badge>
                          )}
                          <Badge variant="info">
                            {r.entity_type}
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
                      <Globe className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                      <span className="truncate">{r.url}</span>
                      <ExternalLink className="w-3 h-3 shrink-0" />
                    </a>

                    {r.snippet && (
                      <p className="text-xs text-slate-600 line-clamp-3 leading-relaxed">
                        {r.snippet}
                      </p>
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
                      <Button variant="secondary" size="sm" onClick={() => handleSaveCompany(r)}>
                        <BookmarkPlus className="w-3.5 h-3.5 mr-1 text-blue-600" />
                        Save Company
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
            title="Company Finder Ready"
            description="Enter a company name and industry parameters to discover official business domains and footprints."
          />
        </Card>
      )}
    </div>
  );
};
