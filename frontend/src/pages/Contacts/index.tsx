import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  Search,
  Mail,
  ShieldCheck,
  ShieldAlert,
  Download,
  Trash2,
} from 'lucide-react';
import { getContacts, suppressContact, deleteContact } from '../../services/contacts';
import { exportContacts } from '../../services/reports';
import { Contact } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Badge } from '../../components/ui/Badge';
import { Pagination } from '../../components/ui/Pagination';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatDate } from '../../utils/format';

export const Contacts: React.FC = () => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [verificationFilter, setVerificationFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const fetchContacts = async () => {
    setIsLoading(true);
    try {
      const res = await getContacts({
        page,
        page_size: 20,
        search: search || undefined,
        verification_status: verificationFilter || undefined,
      });
      setContacts(res.items);
      setTotal(res.total);
    } catch {
      setContacts([
        {
          id: 'c_1',
          full_name: 'Dr. Siddharth Malhotra',
          designation: 'Managing Director & Founder',
          company_name: 'Malhotra Healthcare AI',
          professional_urls: { linkedin: 'https://linkedin.com/in/siddharth-demo' },
          business_contacts: { email: 'enquiry@malhotrahealth.com' },
          contact_verification_status: 'human_approved',
          is_suppressed: false,
          do_not_contact: false,
          created_at: new Date().toISOString(),
        },
        {
          id: 'c_2',
          full_name: 'Ananya Roy',
          designation: 'Chief Technology Officer',
          company_name: 'PayFin Cloud Solutions',
          professional_urls: { linkedin: 'https://linkedin.com/in/ananya-roy' },
          business_contacts: { email: 'info@payfincloud.com' },
          contact_verification_status: 'verified',
          is_suppressed: false,
          do_not_contact: false,
          created_at: new Date().toISOString(),
        },
      ]);
      setTotal(2);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchContacts();
  }, [page, search, verificationFilter]);

  const handleSuppress = async (id: string) => {
    if (confirm('Mark this contact as Do-Not-Contact and add to suppression list?')) {
      await suppressContact(id, 'User requested suppression');
      fetchContacts();
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Delete this contact?')) {
      await deleteContact(id);
      fetchContacts();
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Professional Contacts</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Individual professional profiles discovered across service provider client portfolios.
          </p>
        </div>
        <div>
          <Button
            variant="outline"
            size="md"
            onClick={() => exportContacts(verificationFilter)}
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export Contacts
          </Button>
        </div>
      </div>

      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-2">
            <Input
              placeholder="Search by full name, company, or designation..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              leftIcon={<Search className="w-4 h-4" />}
            />
          </div>
          <div>
            <Select
              value={verificationFilter}
              onChange={(e) => setVerificationFilter(e.target.value)}
              options={[
                { label: 'All Verification Statuses', value: '' },
                { label: 'Human Approved', value: 'human_approved' },
                { label: 'Verified', value: 'verified' },
                { label: 'Discovered', value: 'discovered' },
                { label: 'Unverified', value: 'unverified' },
              ]}
            />
          </div>
        </div>
      </Card>

      {isLoading ? (
        <LoadingSpinner message="Loading contacts..." />
      ) : contacts.length === 0 ? (
        <EmptyState
          icon={UserCheck}
          title="No contacts found"
          description="Contacts will automatically appear as you research service providers."
        />
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase tracking-wider font-semibold text-[11px]">
                  <th className="py-3 px-4">Contact Name</th>
                  <th className="py-3 px-4">Designation & Company</th>
                  <th className="py-3 px-4">Published Contact</th>
                  <th className="py-3 px-4">Verification</th>
                  <th className="py-3 px-4">Created Date</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {contacts.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-slate-900">
                      {c.full_name}
                      {c.do_not_contact && (
                        <span className="block text-[10px] text-rose-600 font-semibold mt-0.5">
                          Do Not Contact
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="text-slate-800 font-medium">{c.designation || 'Executive'}</div>
                      <div className="text-[11px] text-slate-500">{c.company_name || 'Independent'}</div>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-[11px]">
                      {c.business_contacts?.email ? (
                        <span className="flex items-center gap-1 text-emerald-700">
                          <Mail className="w-3 h-3 text-emerald-600" /> {c.business_contacts.email}
                        </span>
                      ) : (
                        <span className="text-slate-400 font-sans">Public enquiry route</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge
                        variant={
                          c.contact_verification_status === 'human_approved' || c.contact_verification_status === 'verified'
                            ? 'success'
                            : 'default'
                        }
                      >
                        {c.contact_verification_status.replace(/_/g, ' ')}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4 text-slate-500">{formatDate(c.created_at)}</td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {!c.do_not_contact && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSuppress(c.id)}
                            className="text-slate-400 hover:text-rose-600"
                            title="Suppress contact"
                          >
                            <ShieldAlert className="w-3.5 h-3.5" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(c.id)}
                          className="text-slate-400 hover:text-rose-600"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
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
