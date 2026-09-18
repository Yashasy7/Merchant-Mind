import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  postGrowthAnalyze,
  postGrowthRecommend,
  getCustomerSegments,
} from '../api';
import type {
  GrowthAnalysis,
  GrowthRecommendation,
  CustomerSegmentsData,
} from '../types';
import DiagnosisCard from '../components/growth/DiagnosisCard';
import RecommendationCard from '../components/copilot/RecommendationCard';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import ErrorMessage from '../components/shared/ErrorMessage';
import SyntheticLabel from '../components/shared/SyntheticLabel';
import Badge from '../components/shared/Badge';
import { IconArrowRight, IconLineChart } from '../components/shared/Icons';

export default function Growth() {
  const navigate = useNavigate();

  const [analysis, setAnalysis] = useState<GrowthAnalysis | null>(null);
  const [recommendation, setRecommendation] = useState<GrowthRecommendation | null>(null);
  const [customers, setCustomers] = useState<CustomerSegmentsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [analysisRes, recRes, custRes] = await Promise.all([
        postGrowthAnalyze(),
        postGrowthRecommend(),
        getCustomerSegments(),
      ]);
      setAnalysis(analysisRes.data);
      setRecommendation(recRes.data);
      setCustomers(custRes.data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load growth analysis');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner label="AI Growth Engine analyzing transaction signals and formulating strategy…" size="lg" />
      </div>
    );
  }

  if (error || !analysis || !recommendation) {
    return (
      <div className="py-12 max-w-xl mx-auto">
        <ErrorMessage
          message={error || 'Unable to retrieve growth recommendation'}
          onRetry={fetchData}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Workflow Step Tracker */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-4 sm:p-5 flex flex-wrap items-center justify-between gap-3 text-xs shadow-card">
        <div className="flex items-center gap-2.5">
          <Badge variant="core">Hero Workflow • Steps 4–8</Badge>
          <span className="text-slate-600 font-medium">
            Decline Detection → Diagnosis → Recommendation
          </span>
        </div>
        <div className="flex items-center gap-2">
          <SyntheticLabel variant="data" size="xs" />
        </div>
      </div>

      {/* Diagnosis Section (Step 4 & 5) */}
      <DiagnosisCard
        decline={analysis.decline_data}
        customers={customers ?? undefined}
      />

      {/* AI Recommendation Section (Step 7 & 8) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Targeted Campaign Recommendation
          </h3>
          <span className="text-[11px] text-slate-400">
            Deterministic heuristics + LLM rationale
          </span>
        </div>

        <RecommendationCard
          recommendation={recommendation}
          onSimulate={() => navigate('/simulator')}
        />
      </div>

      {/* Direct Link to Simulator (Step 10) */}
      <div className="bg-gradient-to-r from-sky-50 via-white to-sky-50/50 p-5 rounded-2xl border border-sky-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-sm">
        <div>
          <h4 className="text-sm font-bold text-slate-900">
            Ready to test projected revenue outcomes?
          </h4>
          <p className="text-xs text-slate-500 mt-0.5">
            Use the What-If Simulator to compare 4 cashback strategies side-by-side before committing any store budget.
          </p>
        </div>
        <button
          onClick={() => navigate('/simulator')}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-paytmNavy hover:bg-[#001c4d] text-white text-xs font-semibold transition-all shadow-sm flex-shrink-0 active:scale-[0.98]"
        >
          <IconLineChart size={15} className="text-paytm" />
          <span>Launch What-if Simulator</span>
          <IconArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}
