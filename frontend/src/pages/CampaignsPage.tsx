import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { getCampaignResult } from '../api';
import type { CampaignResult } from '../types';
import CampaignResultView from '../components/growth/CampaignResultView';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import ErrorMessage from '../components/shared/ErrorMessage';
import Badge from '../components/shared/Badge';

export default function CampaignsPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const wasJustApproved = searchParams.get('approved') === 'true';

  const [result, setResult] = useState<CampaignResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCampaign = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getCampaignResult('camp-hero-001');
      setResult(res.data);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch campaign performance');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaign();
  }, []);

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner label="Fetching campaign execution metrics and performance telemetry…" size="lg" />
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="py-12 max-w-xl mx-auto">
        <ErrorMessage
          message={error || 'No campaign record found'}
          onRetry={fetchCampaign}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Workflow Step Tracker */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-4 sm:p-5 flex flex-wrap items-center justify-between gap-3 text-xs shadow-card">
        <div className="flex items-center gap-2.5">
          <Badge variant="core">Hero Workflow • Steps 12–14</Badge>
          <span className="text-slate-600 font-medium">
            Execution → Performance Telemetry → Feedback Loop
          </span>
        </div>
        {wasJustApproved && (
          <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 flex items-center gap-1">
            ✓ Successfully Authorized by Merchant
          </span>
        )}
      </div>

      {/* Campaign Result View */}
      <CampaignResultView
        result={result}
        onResetToHero={() => navigate('/growth')}
      />
    </div>
  );
}
