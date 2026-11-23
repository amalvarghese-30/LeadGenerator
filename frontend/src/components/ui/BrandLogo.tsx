import React from 'react';

interface BrandLogoProps {
  mode?: 'icon' | 'full';
  className?: string;
}

const CDIcon: React.FC<{ size?: number }> = ({ size = 36 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    xmlns="http://www.w3.org/2000/svg"
    aria-label="Candid Digital"
    className="shrink-0"
  >
    <rect width="32" height="32" rx="8" fill="#0EA5E9" />
    <text
      x="50%"
      y="55%"
      dominantBaseline="middle"
      textAnchor="middle"
      fontFamily="system-ui,sans-serif"
      fontWeight="700"
      fontSize="13"
      fill="white"
    >
      CD
    </text>
  </svg>
);

export const BrandLogo: React.FC<BrandLogoProps> = ({ mode = 'full', className = '' }) => {
  if (mode === 'icon') {
    return (
      <span className={className} aria-label="Candid Digital">
        <CDIcon size={36} />
      </span>
    );
  }

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <CDIcon size={36} />
      <div className="flex flex-col leading-none">
        <span className="text-sm font-bold tracking-tight text-slate-900">Candid Digital</span>
        <span className="text-[10px] font-semibold text-sky-500 tracking-wider uppercase">CRM Platform</span>
      </div>
    </div>
  );
};
