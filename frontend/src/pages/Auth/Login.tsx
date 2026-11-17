import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { login } from '../../services/auth';
import { ShieldCheck, ArrowRight, Lock, Mail } from 'lucide-react';
import { Input } from '../../components/ui/Input';
import { Button } from '../../components/ui/Button';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { loginUser } = useAuth();
  const [email, setEmail] = useState('admin@leadintel.local');
  const [password, setPassword] = useState('Admin@123456');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const res = await login(email, password);
      // Temporarily store token for getMe request
      localStorage.setItem('token', res.access_token);
      let userData;
      try {
        const { getMe } = await import('../../services/auth');
        userData = await getMe();
      } catch {
        userData = {
          id: 'user_active',
          email,
          username: email.split('@')[0],
          full_name: 'LeadIntel User',
          role: 'admin' as const,
          is_active: true,
        };
      }
      loginUser(res.access_token, res.refresh_token, userData);
      navigate('/dashboard');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Invalid email or password. Please check your credentials and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 items-center justify-center text-white shadow-xl shadow-blue-500/20 mb-4">
          <ShieldCheck className="w-8 h-8 stroke-[2.2]" />
        </div>
        <h2 className="text-2xl font-bold tracking-tight text-white font-sans">
          LeadIntel CRM
        </h2>
        <p className="mt-1 text-xs text-slate-400">
          Provider Intelligence & CRM Lead Discovery Platform
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white py-8 px-6 shadow-2xl rounded-2xl sm:px-10 border border-slate-100">
          <form className="space-y-4" onSubmit={handleSubmit}>
            {error && (
              <div className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg">
                {error}
              </div>
            )}

            <Input
              label="Email Address"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@leadintel.io"
              leftIcon={<Mail className="w-4 h-4 text-slate-400" />}
            />

            <Input
              label="Password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              leftIcon={<Lock className="w-4 h-4 text-slate-400" />}
            />

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="lg"
                isLoading={isLoading}
                className="w-full"
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Sign In to Platform
              </Button>
            </div>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-100 text-center">
            <span className="text-[11px] text-slate-400">
              Targeted research against personal branding, Google Knowledge Panel, and Entity SEO providers
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
