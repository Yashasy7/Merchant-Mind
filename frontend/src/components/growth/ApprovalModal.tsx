import { useState } from 'react';
import type { SimulationStrategy } from '../../types';
import { formatRupees } from '../../api';
import SyntheticLabel from '../shared/SyntheticLabel';
import { IconShieldCheck, IconCheckCircle, IconX } from '../shared/Icons';

interface ApprovalModalProps {
  isOpen: boolean;
  strategy: SimulationStrategy;
  onApprove: () => Promise<void>;
  onReject: () => void;
  isSubmitting?: boolean;
}

export default function ApprovalModal({
  isOpen,
  strategy,
  onApprove,
  onReject,
  isSubmitting = false,
}: ApprovalModalProps) {
  const [confirmedConsent, setConfirmedConsent] = useState(false);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in-up">
      <div className="bg-white border border-slate-200 rounded-3xl max-w-lg w-full shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-100 bg-slate-50/70 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
              <IconShieldCheck size={20} />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                Merchant Authorization Required
              </h3>
              <p className="text-xs text-slate-500">
                Human-in-the-loop governance • Step 11 of Hero Workflow
              </p>
            </div>
          </div>
          <button
            onClick={onReject}
            disabled={isSubmitting}
            className="text-slate-400 hover:text-slate-700 transition-colors p-1.5 rounded-lg hover:bg-slate-100"
          >
            <IconX size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5">
          <div className="p-4 bg-sky-50/60 rounded-2xl border border-sky-100 text-xs space-y-1">
            <span className="text-[10px] uppercase font-bold text-paytmNavy block">
              Selected Campaign Package
            </span>
            <p className="text-sm font-bold text-slate-900">{strategy.label}</p>
            <p className="text-slate-500 text-xs mt-0.5">
              Audience: 126 Inactive + 43 At-Risk Customers • 6:00 PM – 9:00 PM Weekdays
            </p>
          </div>

          {/* Key Financial Parameters */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/80">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Authorized Incentive Cost
              </span>
              <span className="text-xl font-bold text-rose-600 block mt-1">
                {formatRupees(strategy.incentive_cost)}
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Maximum store budget
              </span>
            </div>

            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/80">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Projected Incremental Gain
              </span>
              <span className="text-xl font-bold text-emerald-600 block mt-1">
                +{formatRupees(strategy.incremental_revenue)}
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Estimated ~{strategy.estimated_roi.toFixed(1)}x return
              </span>
            </div>
          </div>

          {/* Synthetic Disclaimer */}
          <div className="flex justify-center">
            <SyntheticLabel variant="projection" size="xs" />
          </div>

          {/* Merchant Confirmation Checkbox */}
          <label className="flex items-start gap-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200/70 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={confirmedConsent}
              onChange={(e) => setConfirmedConsent(e.target.checked)}
              className="mt-0.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 w-4 h-4"
            />
            <span className="text-xs text-slate-600 leading-snug">
              I authorize MerchantMind to activate this targeted campaign for Sharma Sweets & Bakers and disburse customer cashback up to {formatRupees(strategy.incentive_cost)}.
            </span>
          </label>
        </div>

        {/* Footer Buttons */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex flex-col-reverse sm:flex-row items-center justify-end gap-3">
          <button
            type="button"
            onClick={onReject}
            disabled={isSubmitting}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-slate-200 bg-white text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Cancel / Reject
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={!confirmedConsent || isSubmitting}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold transition-all shadow-sm active:scale-[0.98]"
          >
            <IconCheckCircle size={16} />
            <span>{isSubmitting ? 'Authorizing…' : 'Approve & Launch Campaign'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
