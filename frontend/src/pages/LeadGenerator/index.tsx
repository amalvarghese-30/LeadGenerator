import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Building,
  User,
  Search,
  ExternalLink,
  ShieldCheck,
  AlertCircle,
  BookmarkPlus,
  History,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import {
  searchCompany,
  searchIndividual,
  getSearchHistory,
  saveSearchResultToCrm,
  SearchResponse,
} from '../../services/leadGenerator';
import { SearchResultCandidate } from '../../types';

export const LeadGenerator: React.FC = () => {
  const [mode, setMode] = useState<'company' | 'individual'>('company');
  const [activeTab, setActiveTab] = useState<'search' | 'history'>('search');

  // Company Form
  const [companyName, setCompanyName] = useState('');
  const [companyWebsite, setCompanyWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [country, setCountry] = useState('');
  const [additionalTerms, setAdditionalTerms] = useState('');

  // Individual Form
  const [fullName, setFullName] = useState('');
  const [indivCompany, setIndivCompany] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [location, setLocation] = useState('');

  // Search execution state
  const [isLoading, setIsLoading] = useState(false);
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedUrls, setSavedUrls] = useState<Set<string>>(new Set());

  // History state
  const [historyItems, setHistoryItems] = useState<any[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setSearchResponse(null);

    try {
      if (mode === 'company') {
        if (!companyName.trim()) {
          setError('Please provide a company name.');
          setIsLoading(false);
          return;
        }
        const res = await searchCompany({
          company_name: companyName,
          website: companyWebsite || undefined,
          industry: industry || undefined,
          country: country || undefined,
          additional_terms: additionalTerms || undefined,
        });
        setSearchResponse(res);
      } else {
        if (!fullName.trim()) {
          setError('Please provide an individual name.');
          setIsLoading(false);
          return;
        }
        const res = await searchIndividual({
          full_name: fullName,
          company: indivCompany || undefined,
          job_title: jobTitle || undefined,
          location: location || undefined,
        });
        setSearchResponse(res);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Search failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const loadHistory = async () => {
    setIsHistoryLoading(true);
    try {
      const items = await getSearchHistory(20);
      setHistoryItems(items);
    } catch (err) {
      console.error('History load failed:', err);
    } finally {
      setIsHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory();
    }
  }, [activeTab]);

  const handleSaveToCrm = async (item: SearchResultCandidate) => {
    try {
      await saveSearchResultToCrm({
        entity_type: item.entity_type,
        name: mode === 'individual' ? fullName : (item.domain || item.title),
        website: item.url,
        domain: item.domain,
        title: item.corroborated_title ? jobTitle : undefined,
        company_name: mode === 'company' ? companyName : indivCompany,
        snippet: item.snippet,
        social_platform: item.social_platform,
        url: item.url,
        create_lead: true,
      });
      setSavedUrls((prev) => new Set(prev).add(item.url));
    } catch (err) {
      console.error('Save to CRM failed:', err);
    }
  };

  const getEntityBadge = (type: string) => {
    switch (type) {
      case 'individual':
        return <Badge variant="info">Individual</Badge>;
      case 'company':
        return <Badge variant="success">Company</Badge>;
      case 'organisation':
        return <Badge variant="warning">Organisation</Badge>;
      default:
        return <Badge variant="default">Review Required</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">Lead Generator</h1>
          <p className="text-xs text-slate-500 mt-1">
            Discover verified companies, executive contacts, and corroborated intelligence across public sources.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant={activeTab === 'search' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setActiveTab('search')}
          >
            <Search className="w-3.5 h-3.5 mr-1.5" />
            Active Search
          </Button>
          <Button
            variant={activeTab === 'history' ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setActiveTab('history')}
          >
            <History className="w-3.5 h-3.5 mr-1.5" />
            Search History
          </Button>
        </div>
      </div>

      {activeTab === 'search' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Search Controls Panel */}
          <div className="lg:col-span-4 space-y-4">
            <Card className="p-5">
              {/* Mode Toggle */}
              <div className="flex p-1 bg-slate-100 rounded-xl mb-4">
                <button
                  type="button"
                  onClick={() => setMode('company')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all ${
                    mode === 'company'
                      ? 'bg-white text-blue-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Building className="w-3.5 h-3.5" />
                  Company Search
                </button>
                <button
                  type="button"
                  onClick={() => setMode('individual')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all ${
                    mode === 'individual'
                      ? 'bg-white text-blue-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <User className="w-3.5 h-3.5" />
                  Individual Search
                </button>
              </div>

              <form onSubmit={handleSearch} className="space-y-3.5">
                {mode === 'company' ? (
                  <>
                    <Input
                      label="Company Name *"
                      placeholder="e.g. Acme Corporation"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      required
                    />
                    <Input
                      label="Website / Domain (Optional)"
                      placeholder="e.g. acme.com"
                      value={companyWebsite}
                      onChange={(e) => setCompanyWebsite(e.target.value)}
                    />
                    <Input
                      label="Industry"
                      placeholder="e.g. Software, Fintech, Healthcare"
                      value={industry}
                      onChange={(e) => setIndustry(e.target.value)}
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        label="Country / Region"
                        placeholder="e.g. US, IN, UK"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                      />
                      <Input
                        label="Extra Terms"
                        placeholder="e.g. Agency, PR"
                        value={additionalTerms}
                        onChange={(e) => setAdditionalTerms(e.target.value)}
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <Input
                      label="Full Name *"
                      placeholder="e.g. Sarah Connor"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                    <Input
                      label="Current Company"
                      placeholder="e.g. Cyberdyne Systems"
                      value={indivCompany}
                      onChange={(e) => setIndivCompany(e.target.value)}
                    />
                    <Input
                      label="Job Title / Role"
                      placeholder="e.g. Chief Technology Officer"
                      value={jobTitle}
                      onChange={(e) => setJobTitle(e.target.value)}
                    />
                    <Input
                      label="Location"
                      placeholder="e.g. San Francisco, CA"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                    />
                  </>
                )}

                {error && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-100 flex items-start gap-2 text-rose-700 text-xs">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>{error}</span>
                  </div>
                )}

                <Button type="submit" variant="primary" className="w-full mt-2" isLoading={isLoading}>
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  {mode === 'company' ? 'Search Companies & Providers' : 'Discover Individual Profiles'}
                </Button>
              </form>
            </Card>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-8 space-y-4">
            {isLoading ? (
              <Card className="p-12 flex flex-col items-center justify-center">
                <LoadingSpinner message="Orchestrating search across public sources and extracting entity signals..." />
              </Card>
            ) : searchResponse ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between px-1">
                  <div>
                    <h2 className="text-sm font-bold text-slate-800">
                      Discovered Results ({searchResponse.total_results})
                    </h2>
                    <p className="text-[11px] text-slate-500">
                      Query: <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">{searchResponse.query}</code>
                    </p>
                  </div>
                  <Badge variant="success">Sources Active: DDGS</Badge>
                </div>

                {searchResponse.results.length === 0 ? (
                  <Card className="p-8">
                    <EmptyState
                      title="No Results Found"
                      description="No public profiles or company records matched your search terms. Try broadening your keywords."
                    />
                  </Card>
                ) : (
                  <div className="space-y-3">
                    {searchResponse.results.map((res, idx) => {
                      const isSaved = savedUrls.has(res.url);
                      return (
                        <Card key={idx} className="p-4.5 hover:shadow-md transition-shadow">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap mb-1">
                                {getEntityBadge(res.entity_type)}
                                {res.social_platform && (
                                  <Badge variant="info" className="capitalize">
                                    {res.social_platform}
                                  </Badge>
                                )}
                                {res.is_official_website && (
                                  <Badge variant="success">Official Site</Badge>
                                )}
                                <span className="text-[10px] font-semibold text-slate-400">
                                  Confidence: {Math.round(res.confidence * 100)}%
                                </span>
                              </div>

                              <a
                                href={res.url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-sm font-bold text-blue-700 hover:underline flex items-center gap-1.5 group"
                              >
                                <span className="truncate">{res.title}</span>
                                <ExternalLink className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 shrink-0" />
                              </a>
                              <p className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                                {res.url}
                              </p>

                              {res.snippet && (
                                <p className="text-xs text-slate-600 mt-2 line-clamp-2 leading-relaxed">
                                  {res.snippet}
                                </p>
                              )}

                              {res.evidence_points && res.evidence_points.length > 0 && (
                                <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center gap-1.5 flex-wrap">
                                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                                  <span className="text-[10px] text-slate-500 font-medium">Evidence:</span>
                                  {res.evidence_points.map((pt, pIdx) => (
                                    <span
                                      key={pIdx}
                                      className="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full"
                                    >
                                      {pt}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div className="shrink-0">
                              {isSaved ? (
                                <div className="flex items-center gap-1 text-emerald-600 text-xs font-semibold px-3 py-1.5 rounded-xl bg-emerald-50">
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  Saved
                                </div>
                              ) : (
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => handleSaveToCrm(res)}
                                >
                                  <BookmarkPlus className="w-3.5 h-3.5 mr-1 text-blue-600" />
                                  Save to CRM
                                </Button>
                              )}
                            </div>
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <Card className="p-12">
                <EmptyState
                  title="Search Orchestrator Ready"
                  description="Choose Company or Individual Search on the left to begin discoverings leads with verified entity classification."
                />
              </Card>
            )}
          </div>
        </div>
      ) : (
        /* History Tab */
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">Recent Search Inquiries</h2>
            <Button variant="secondary" size="sm" onClick={loadHistory} isLoading={isHistoryLoading}>
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Refresh History
            </Button>
          </div>

          {isHistoryLoading ? (
            <div className="py-8 flex justify-center">
              <LoadingSpinner message="Loading historical searches..." />
            </div>
          ) : historyItems.length === 0 ? (
            <EmptyState
              title="No Search History"
              description="Searches performed in the Lead Generator will be logged here with duplicate detection."
            />
          ) : (
            <div className="divide-y divide-slate-100">
              {historyItems.map((item) => (
                <div key={item.id} className="py-3.5 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant={item.search_type === 'company' ? 'info' : 'success'}>
                        {item.search_type}
                      </Badge>
                      <span className="text-xs font-bold text-slate-900 truncate">
                        {item.search_type === 'company'
                          ? item.query_params?.company_name
                          : item.query_params?.full_name}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      {item.results_count} results found • Sources: {(item.sources_used || []).join(', ')} •{' '}
                      {new Date(item.created_at).toLocaleString()}
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
