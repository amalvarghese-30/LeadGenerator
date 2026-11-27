import React from 'react';
import { cn } from '../../utils/cn';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className,
  hover = false,
  ...props
}) => {
  return (
    <div
      className={cn(
        'bg-slate-900 rounded-xl border border-slate-800 text-slate-100 shadow-sm p-5 transition-all',
        hover && 'hover:shadow-md hover:border-slate-700',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
