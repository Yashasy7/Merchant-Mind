import React from 'react';

/** Reusable Badge / status chip — modern fintech design */

export type BadgeVariant =
  | 'core'      // green — live/confirmed
  | 'mvp'       // blue — primary
  | 'warning'   // yellow / amber
  | 'stretch'   // orange
  | 'future'    // indigo / purple
  | 'paytm'     // cyan — paytm brand
  | 'vishal'    // navy
  | 'high'      // red — high priority
  | 'medium'    // amber — medium priority
  | 'low'       // green — low priority
  | 'active'    // emerald — campaign active
  | 'pending'   // amber — pending
  | 'completed' // blue — completed
  | 'simulated' // soft indigo — simulated badge
  | 'ghost';    // neutral slate

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  size?: 'sm' | 'md';
}

const variantClasses: Record<BadgeVariant, string> = {
  core:      'bg-emerald-50 text-emerald-700 border border-emerald-200/80',
  mvp:       'bg-blue-50 text-blue-700 border border-blue-200/80',
  warning:   'bg-amber-50 text-amber-700 border border-amber-200/80',
  stretch:   'bg-orange-50 text-orange-700 border border-orange-200/80',
  future:    'bg-indigo-50 text-indigo-700 border border-indigo-200/80',
  paytm:     'bg-sky-50 text-sky-700 border border-sky-200/80',
  vishal:    'bg-slate-100 text-slate-800 border border-slate-200',
  high:      'bg-rose-50 text-rose-700 border border-rose-200/80',
  medium:    'bg-amber-50 text-amber-700 border border-amber-200/80',
  low:       'bg-emerald-50 text-emerald-700 border border-emerald-200/80',
  active:    'bg-emerald-50 text-emerald-700 border border-emerald-300 font-semibold',
  pending:   'bg-amber-50 text-amber-700 border border-amber-200/80',
  completed: 'bg-blue-50 text-blue-700 border border-blue-200/80',
  simulated: 'bg-indigo-50 text-indigo-700 border border-indigo-200/80',
  ghost:     'bg-slate-100 text-slate-600 border border-slate-200',
};

export default function Badge({
  children,
  variant = 'ghost',
  className = '',
  size = 'md',
}: BadgeProps) {
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-0.5 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${sizeClass} ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
