import React from 'react';

interface KPICardProps {
  label: string;
  value: string | number;
  subValue?: string;
  changePct?: number;
  changeLabel?: string;
  accent?: 'blue' | 'green' | 'yellow' | 'purple' | 'cyan';
  icon?: React.ReactNode;
}

export default function KPICard({
  label,
  value,
  subValue,
  changePct,
  changeLabel = 'vs prior period',
  accent = 'blue',
  icon,
}: KPICardProps) {
  const isPositive = changePct !== undefined ? changePct >= 0 : undefined;

  const iconBgMap = {
    blue: 'bg-sky-50 text-paytmNavy',
    green: 'bg-emerald-50 text-emerald-600',
    yellow: 'bg-amber-50 text-amber-600',
    purple: 'bg-indigo-50 text-indigo-600',
    cyan: 'bg-cyan-50 text-cyan-600',
  };

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-card hover:shadow-card-hover transition-all duration-200 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="text-xs font-semibold text-slate-500 tracking-normal">
            {label}
          </span>
          {icon && (
            <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${iconBgMap[accent]}`}>
              {icon}
            </div>
          )}
        </div>

        <div className="my-1">
          <div className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
            {value}
          </div>
          {subValue && (
            <p className="text-xs text-slate-500 mt-1 font-normal">{subValue}</p>
          )}
        </div>
      </div>

      {changePct !== undefined && (
        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-2 text-xs">
          <span
            className={`font-semibold px-2 py-0.5 rounded-full text-[11px] ${
              isPositive
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/60'
                : 'bg-rose-50 text-rose-700 border border-rose-200/60'
            }`}
          >
            {isPositive ? '↑ +' : '↓ '}{Math.abs(changePct)}%
          </span>
          <span className="text-slate-400 text-[11px] truncate">{changeLabel}</span>
        </div>
      )}
    </div>
  );
}
