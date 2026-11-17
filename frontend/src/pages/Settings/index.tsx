import React, { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Cpu,
  Globe,
  Database,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Save,
} from 'lucide-react';
import { getAppSettings, getIntegrationsHealth } from '../../services/settings';
import { IntegrationStatus } from '../../types';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { useToast } from '../../context/ToastContext';

export const Settings: React.FC = () => {
  const { toast } = useToast();
  const [appConfig, setAppConfig] = useState<any>(null);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Editable fields
  const [delaySeconds, setDelaySeconds] = useState('1.5');
  const [maxPages, setMaxPages] = useState('50');

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const [confRes, intRes] = await Promise.all([
          getAppSettings().catch(() => null),
          getIntegrationsHealth().catch(() => ({ integrations: [] })),
        ]);
        if (confRes) {
          setAppConfig(confRes);
          if (confRes.crawler?.delay_seconds) {
            setDelaySeconds(String(confRes.crawler.delay_seconds));
          }
          if (confRes.crawler?.max_pages) {
            setMaxPages(String(confRes.crawler.max_pages));
          }
        }
        if (intRes?.integrations) setIntegrations(intRes.integrations);
      } finally {
        setIsLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      const delay = parseFloat(delaySeconds);
      const pages = parseInt(maxPages, 10);
      const { updateAppSettings } = await import('../../services/settings');
      await updateAppSettings({
        crawler: {
          delay_seconds: isNaN(delay) ? 1.5 : delay,
          max_pages: isNaN(pages) ? 50 : pages,
        },
      });
      toast.success('Crawler and system settings persisted successfully to database');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <LoadingSpinner message="Checking system & integration health..." />;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">System & Integration Settings</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Configure crawler parameters, AI extraction fallbacks, and inspect integration health.
        </p>
      </div>

      {/* Integration Registry Section */}
      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-600" /> Integration Registry & Health Checks
            </h3>
            <p className="text-xs text-slate-500">Live operational status of backing services (secrets masked)</p>
          </div>
        </div>

        <div className="divide-y divide-slate-100">
          {integrations.length === 0 ? (
            <div className="py-4 text-center text-xs text-slate-400">
              No active integration status reported by backend.
            </div>
          ) : (
            integrations.map((item) => (
              <div key={item.id} className="py-3 flex items-center justify-between text-xs">
                <div className="space-y-0.5">
                  <div className="font-semibold text-slate-800 flex items-center gap-2">
                    <span>{item.name}</span>
                    {item.is_optional && <span className="text-[10px] text-slate-400 font-normal">(Optional)</span>}
                  </div>
                  <div className="text-[11px] text-slate-500">{item.message}</div>
                  {item.model && <div className="text-[10px] font-mono text-slate-400">Model: {item.model}</div>}
                </div>

                <div>
                  {item.status === 'connected' || item.status === 'active' ? (
                    <Badge variant="success" className="py-1 px-2.5">
                      <CheckCircle2 className="w-3 h-3" /> Active
                    </Badge>
                  ) : item.status === 'not_configured' ? (
                    <Badge variant="default" className="py-1 px-2.5">
                      NLP Fallback Active
                    </Badge>
                  ) : (
                    <Badge variant="danger" className="py-1 px-2.5">
                      <AlertCircle className="w-3 h-3" /> Disconnected
                    </Badge>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Crawler Controls Form */}
      <Card className="p-5 space-y-4">
        <div className="border-b border-slate-100 pb-3">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Globe className="w-4 h-4 text-indigo-600" /> Crawler Rate Limiting & Safety Parameters
          </h3>
          <p className="text-xs text-slate-500">Polite request delays and SSRF security protection</p>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Request Delay (Seconds)"
              type="number"
              step="0.5"
              min="0.5"
              max="10"
              value={delaySeconds}
              onChange={(e) => setDelaySeconds(e.target.value)}
              helperText="Polite interval between consecutive requests to the same domain"
            />
            <Input
              label="Max Pages Crawled Per Provider"
              type="number"
              min="10"
              max="500"
              value={maxPages}
              onChange={(e) => setMaxPages(e.target.value)}
              helperText="Depth limit to prevent unbounded crawl jobs"
            />
          </div>

          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs text-slate-600 space-y-1">
            <span className="font-semibold text-slate-800 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-600" /> Active Security Boundary:
            </span>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              SSRF Guard enforces DNS pre-resolution and blocks all localhost (127.0.0.0/8), link-local cloud metadata (169.254.169.254), and private RFC1918 addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
            </p>
          </div>

          <div className="pt-2 flex items-center justify-end">
            <Button type="submit" variant="primary" size="md" isLoading={isSaving} leftIcon={<Save className="w-4 h-4" />}>
              Save Preferences
            </Button>
          </div>
        </form>
      </Card>

      {/* Security & Data Retention */}
      <Card className="p-5 space-y-3">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" /> Compliance & Privacy Safeguards
        </h3>
        <p className="text-xs text-slate-600 leading-relaxed">
          LeadIntel CRM operates under strict research compliance boundaries:
        </p>
        <ul className="list-disc list-inside text-xs text-slate-600 space-y-1">
          <li>Zero harvesting of private behind-login databases.</li>
          <li>No guessed personal email addresses generated by LLM models.</li>
          <li>Mandatory evidence attribution and verification links for all extracted records.</li>
          <li>Instant respect for Do-Not-Contact requests and suppression list checks.</li>
        </ul>
      </Card>
    </div>
  );
};
