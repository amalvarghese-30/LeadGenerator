import React from 'react';
import { cn } from '../../utils/cn';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'purple';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  className,
  variant = 'default',
  size = 'md',
  ...props
}) => {
  const variants = {
    default: 'bg-slate-800 text-slate-300 border-slate-700',
    success: 'bg-emerald-950/70 text-emerald-300 border-emerald-800/80',
    warning: 'bg-amber-950/70 text-amber-300 border-amber-800/80',
    danger: 'bg-rose-950/70 text-rose-300 border-rose-800/80',
    info: 'bg-sky-950/70 text-sky-300 border-sky-800/80',
    purple: 'bg-purple-950/70 text-purple-300 border-purple-800/80',
  };

  const sizes = {
    sm: 'text-[11px] px-1.5 py-0.5 font-medium rounded',
    md: 'text-xs px-2.5 py-1 font-medium rounded-full',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 border border-solid transition-colors',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
};
