import { useNavigate } from 'react-router-dom';
import type { GrowthRecommendation } from '../../types';
import Badge from '../shared/Badge';
import SyntheticLabel from '../shared/SyntheticLabel';
import { IconSparkles, IconArrowRight } from '../shared/Icons';

interface RecommendationCardProps {
  recommendation: GrowthRecommendation;
  onSimulate?: () => void;
}

export default function RecommendationCard({
  recommendation,
  onSimulate,
}: RecommendationCardProps) {
  const navigate = useNavigate();

  const handleSimulate = () => {
    if (onSimulate) {
      onSimulate();
    } else {
      navigate('/simulator');
    }
  };

  return (
    <div className="bg-white border border-sky-200 rounded-2xl p-5 sm:p-6 space-y-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-sky-50 text-paytmNavy flex items-center justify-center">
            <IconSparkles size={16} className="text-paytm" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-900 tracking-tight">
              Recommended Growth Strategy
            </h4>
            <p className="text-[11px] text-slate-400">
              Formulated by MerchantMind Growth Agent
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="core" size="sm">Recommended</Badge>
          <SyntheticLabel variant="projection" size="xs" />
        </div>
      </div>

      {/* Diagnosis & Opportunity */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200/70">
          <span className="text-[10px] uppercase font-bold text-rose-600 block">
            Diagnosed Problem
          </span>
          <p className="text-slate-800 mt-1 font-medium leading-relaxed">
            {recommendation.diagnosis}
          </p>
        </div>
        <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200/70">
          <span className="text-[10px] uppercase font-bold text-emerald-600 block">
            Identified Opportunity
          </span>
          <p className="text-slate-800 mt-1 font-medium leading-relaxed">
            {recommendation.opportunity}
          </p>
        </div>
      </div>

      {/* Offer Parameters */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-3.5 bg-sky-50/50 rounded-xl border border-sky-100 text-xs">
        <div>
          <span className="text-[10px] text-slate-500 uppercase font-semibold block">Target Customers</span>
          <p className="font-bold text-slate-900 mt-0.5">
            {recommendation.target_count} {recommendation.target_segment}
          </p>
        </div>
        <div>
          <span className="text-[10px] text-slate-500 uppercase font-semibold block">Proposed Incentive</span>
          <p className="font-bold text-paytmNavy mt-0.5">{recommendation.offer_label}</p>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <span className="text-[10px] text-slate-500 uppercase font-semibold block">Campaign Window</span>
          <p className="font-bold text-slate-900 mt-0.5">{recommendation.timing}</p>
        </div>
      </div>

      {/* LLM Reasoning */}
      <div className="text-xs text-slate-600 bg-slate-50 p-3.5 rounded-xl border border-slate-200/70 leading-relaxed">
        <span className="text-[10px] font-bold text-paytmNavy block mb-1 uppercase">
          AI Rationale & Business Justification
        </span>
        <p>{recommendation.reasoning}</p>
      </div>

      {/* Expected Impact & CTA */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
        <div>
          <span className="text-[10px] uppercase font-bold text-slate-400 block">Expected Revenue Uplift</span>
          <p className="text-sm font-bold text-emerald-700 font-sans">
            {recommendation.expected_impact}
          </p>
        </div>
        <button
          onClick={handleSimulate}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-paytmNavy hover:bg-[#001c4d] text-white text-xs font-semibold transition-all shadow-sm active:scale-[0.98]"
        >
          <span>Simulate What-If Scenarios</span>
          <IconArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}
