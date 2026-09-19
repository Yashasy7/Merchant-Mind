import { useNavigate } from 'react-router-dom';
import type { CampaignResult } from '../../types';
import { formatRupees } from '../../api';
import Badge from '../shared/Badge';
import SyntheticLabel from '../shared/SyntheticLabel';
import {
  IconCheckCircle,
  IconSparkles,
  IconArrowRight,
  IconRefresh,
} from '../shared/Icons';

interface CampaignResultViewProps {
  result: CampaignResult;
  onResetToHero?: () => void;
}

export default function CampaignResultView({
  result,
  onResetToHero,
}: CampaignResultViewProps) {
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      {/* Campaign Success Banner */}
      <div className="bg-white border border-emerald-200 rounded-2xl p-6 sm:p-7 relative overflow-hidden shadow-card">
        <div className="absolute top-0 right-0 w-80 h-80 bg-emerald-50/50 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center">
                <IconCheckCircle size={22} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
                    Campaign Live & Generating Revenue
                  </h3>
                  <Badge variant="active">ACTIVE</Badge>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  ID: {result.campaign_id} • Offer: {result.offer_label}
                </p>
              </div>
            </div>

            <SyntheticLabel variant="data" size="xs" />
          </div>

          <p className="text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
            Targeting <strong>{result.target_segment}</strong> customers during <strong>{result.timing}</strong>.
            Authorized by merchant. Transaction telemetry is feeding directly into your sales intelligence model.
          </p>

          {/* Core Performance Numbers (Backend-calculated) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 pt-2">
            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/80">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Orders Completed
              </span>
              <span className="text-2xl font-bold text-slate-900 block mt-1">
                {result.actual_transactions}
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Projected: {result.projected_transactions}
              </span>
            </div>

            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/80">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Campaign Revenue
              </span>
              <span className="text-2xl font-bold text-slate-900 block mt-1">
                {formatRupees(result.actual_revenue)}
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Projected: {formatRupees(result.projected_revenue)}
              </span>
            </div>

            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/80">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Incentive Cost
              </span>
              <span className="text-2xl font-bold text-rose-600 block mt-1">
                {formatRupees(result.incentive_cost)}
              </span>
              <span className="text-[11px] text-slate-500 block mt-0.5">
                Cashback utilized
              </span>
            </div>

            <div className="p-4 bg-slate-50 rounded-2xl border border-slate-200/80">
              <span className="text-[10px] text-slate-400 uppercase font-bold block">
                Realized Return
              </span>
              <span className="text-2xl font-bold text-emerald-600 block mt-1">
                {result.actual_roi.toFixed(1)}x ROI
              </span>
              <span className="text-[11px] text-emerald-700 font-medium block mt-0.5">
                +{formatRupees(result.incremental_revenue)} incremental
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Step 14: Feedback Loop & Learning Representation */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 space-y-4 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-sky-50 text-paytmNavy flex items-center justify-center">
              <IconSparkles size={16} className="text-paytm" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                AI Continuous Learning & Model Feedback
              </h4>
              <p className="text-xs text-slate-500">
                Step 14 of Hero Workflow • Informs Future Merchant Recommendations
              </p>
            </div>
          </div>
          <Badge variant="core" size="sm">Model Updated</Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2.5">
            <div className="flex justify-between">
              <span className="text-slate-600 font-medium">Performance vs Projection:</span>
              <span className="font-bold text-emerald-600">
                +{result.performance_vs_projection_pct.toFixed(1)}% above forecast
              </span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
              <div className="bg-emerald-500 h-2.5 rounded-full" style={{ width: '100%' }} />
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              Actual customer response exceeded baseline by 5.2%. Inactive customer propensity for evening cashback has been weighted higher for future growth suggestions.
            </p>
          </div>

          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-2.5">
            <span className="text-[10px] text-paytmNavy uppercase font-bold block">
              Next Autonomous Suggestion
            </span>
            <p className="text-slate-800 font-medium leading-relaxed">
              Expand offer window to weekend afternoons for VIP customers to test basket size expansion (target ₹450+ average order).
            </p>
            <div className="pt-1 flex justify-end">
              <button
                onClick={() => navigate('/copilot?prompt=Tell%20me%20more%20about%20the%20VIP%20weekend%20expansion%20suggestion')}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-paytmNavy hover:text-paytm transition-colors"
              >
                <span>Ask Copilot to Elaborate</span>
                <IconArrowRight size={13} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation and Reset Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <button
          onClick={() => navigate('/')}
          className="px-5 py-2.5 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-100 text-xs font-semibold transition-colors shadow-sm"
        >
          ← Return to Dashboard
        </button>

        {onResetToHero && (
          <button
            onClick={onResetToHero}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold transition-colors"
          >
            <IconRefresh size={14} />
            <span>Test Hero Sequence Again</span>
          </button>
        )}
      </div>
    </div>
  );
}
