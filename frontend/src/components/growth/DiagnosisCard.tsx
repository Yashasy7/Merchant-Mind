import type { DeclineAnalysis, CustomerSegmentsData } from '../../types';
import Badge from '../shared/Badge';
import SyntheticLabel from '../shared/SyntheticLabel';
import { IconTrendingDown, IconUsers, IconAlertTriangle } from '../shared/Icons';

interface DiagnosisCardProps {
  decline: DeclineAnalysis;
  customers?: CustomerSegmentsData;
}

export default function DiagnosisCard({ decline, customers }: DiagnosisCardProps) {
  const atRiskCount =
    customers?.segments.find((s) => s.segment === 'At-Risk')?.count ?? 43;
  const inactiveCount =
    customers?.segments.find((s) => s.segment === 'Inactive')?.count ?? 126;

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 space-y-5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center">
            <IconAlertTriangle size={18} />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight">
              AI Sales & Customer Diagnostics
            </h3>
            <p className="text-xs text-slate-500">
              Deterministic transaction pattern analysis • Steps 4–6 of Growth Workflow
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="warning" size="sm">Attention Needed</Badge>
          <SyntheticLabel variant="data" size="xs" />
        </div>
      </div>

      {/* Main Diagnosis Text */}
      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/70 text-xs sm:text-sm text-slate-800 leading-relaxed font-sans">
        <p className="font-medium">{decline.diagnosis}</p>
      </div>

      {/* Key Metric Indicators */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        <div className="p-4 bg-rose-50/40 border border-rose-100 rounded-xl">
          <div className="flex items-center justify-between text-xs text-slate-600 mb-1 font-medium">
            <span>Overall Sales Drop</span>
            <IconTrendingDown size={16} className="text-rose-600" />
          </div>
          <p className="text-2xl font-bold text-rose-600">
            -{decline.overall_decline_pct}%
          </p>
          <span className="text-[11px] text-slate-400">vs prior 14 days</span>
        </div>

        <div className="p-4 bg-amber-50/40 border border-amber-100 rounded-xl">
          <div className="flex items-center justify-between text-xs text-slate-600 mb-1 font-medium">
            <span>Peak Decline Window</span>
            <span className="text-amber-700 text-[11px] font-semibold">Weekday Evenings</span>
          </div>
          <p className="text-2xl font-bold text-amber-700">
            -{decline.worst_period_decline_pct}%
          </p>
          <span className="text-[11px] text-slate-400">{decline.worst_period_label}</span>
        </div>

        <div className="p-4 bg-sky-50/40 border border-sky-100 rounded-xl">
          <div className="flex items-center justify-between text-xs text-slate-600 mb-1 font-medium">
            <span>Customers Inactive</span>
            <IconUsers size={16} className="text-paytmNavy" />
          </div>
          <p className="text-2xl font-bold text-slate-900">
            {inactiveCount + atRiskCount} <span className="text-xs font-normal text-slate-500">regular patrons</span>
          </p>
          <span className="text-[11px] text-slate-500">
            {inactiveCount} inactive + {atRiskCount} at-risk
          </span>
        </div>
      </div>
    </div>
  );
}
