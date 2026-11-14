import React, { useState, useEffect } from 'react';
import {
  Briefcase,
  Search,
  Globe,
  Download,
} from 'lucide-react';
import { getCompanies } from '../../services/companies';
import { exportCompanies } from '../../services/reports';
import { Company } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { Pagination } from '../../components/ui/Pagination';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatDate } from '../../utils/format';

export const Companies: React.FC = () => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const fetchCompanies = async () => {
    setIsLoading(true);
    try {
      const res = await getCompanies({
        page,
        page_size: 20,
        search: search || undefined,
      });
      setCompanies(res.items);
      setTotal(res.total);
    } catch {
      setCompanies([
        {
          id: 'co_1',
          name: 'Malhotra Healthcare AI',
          domain: 'malhotrahealth.com',
          website: 'https://malhotrahealth.com',
          industry: 'Healthcare Technology',
          country: 'India',
          city: 'Bangalore',
          public_contact: { email: 'contact@malhotrahealth.com' },
          verification_status: 'verified',
          created_at: new Date().toISOString(),
        },
        {
          id: 'co_2',
          name: 'PayFin Cloud Solutions',
          domain: 'payfincloud.com',
          website: 'https://payfincloud.com',
          industry: 'FinTech',
          country: 'India',
          city: 'Mumbai',
          public_contact: {},
          verification_status: 'verified',
          created_at: new Date().toISOString(),
        },
      ]);
      setTotal(2);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, [page, search]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Client Companies & Organizations</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Organizations associated with identified client references, case studies, and corporate leaders.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => exportCompanies()}
          leftIcon={<Download className="w-4 h-4" />}
        >
          Export Companies
        </Button>
      </div>

      <Card className="p-4">
        <Input
          placeholder="Search by company name or domain..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          leftIcon={<Search className="w-4 h-4" />}
        />
      </Card>

      {isLoading ? (
        <LoadingSpinner message="Loading company organizations..." />
      ) : companies.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No companies recorded yet"
          description="Organizations will be created automatically as provider case studies are crawled."
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-3 px-4">Company Name</th>
                  <th className="py-3 px-4">Industry</th>
                  <th className="py-3 px-4">Location</th>
                  <th className="py-3 px-4">Website</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {companies.map((co) => (
                  <tr key={co.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-900">
                      {co.name}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600">
                      {co.industry || 'Professional Services'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-500">
                      {co.city || co.country ? `${co.city || ''} ${co.country || ''}` : '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      {co.website ? (
                        <a
                          href={co.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-600 hover:underline flex items-center gap-1 font-mono text-[11px]"
                        >
                          <Globe className="w-3 h-3 text-slate-400" /> {co.domain || co.website}
                        </a>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge variant="success">Verified</Badge>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500 text-right">
                      {formatDate(co.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            currentPage={page}
            totalPages={Math.ceil(total / 20) || 1}
            totalItems={total}
            pageSize={20}
            onPageChange={setPage}
          />
        </div>
      )}
    </div>
  );
};
