import React from 'react';
import { Badge } from './Badge';
import { CRMStage } from '../../types';
import { formatCRMStage } from '../../utils/format';

interface StatusBadgeProps {
  stage: CRMStage | string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ stage, className }) => {
  const getVariant = (s: string): 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple' => {
    switch (s) {
      case 'discovered':
        return 'default';
      case 'pending_verification':
        return 'warning';
      case 'verified':
      case 'qualified':
        return 'info';
      case 'ready_for_outreach_review':
        return 'purple';
      case 'contacted':
      case 'replied':
        return 'info';
      case 'interested':
      case 'converted':
        return 'success';
      case 'closed':
      case 'disqualified':
      case 'do_not_contact':
        return 'danger';
      default:
        return 'default';
    }
  };

  return (
    <Badge variant={getVariant(stage)} className={className}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      {formatCRMStage(stage)}
    </Badge>
  );
};
