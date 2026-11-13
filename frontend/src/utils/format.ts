export function formatDate(dateString?: string): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString?: string): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return dateString;
  }
}

export function formatCRMStage(stage: string): string {
  return stage
    .split('_')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function formatScore(score: number): { label: string; colorClass: string; bgClass: string } {
  if (score >= 80) {
    return { label: 'High Priority', colorClass: 'text-emerald-700', bgClass: 'bg-emerald-50 border-emerald-200' };
  }
  if (score >= 60) {
    return { label: 'Medium Priority', colorClass: 'text-amber-700', bgClass: 'bg-amber-50 border-amber-200' };
  }
  return { label: 'Low Priority', colorClass: 'text-slate-600', bgClass: 'bg-slate-50 border-slate-200' };
}
