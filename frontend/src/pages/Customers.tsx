import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getCustomerSegments,
  getAtRiskCustomers,
  formatRupees,
} from '../api';
import type { CustomerSegmentsData, AtRiskData } from '../types';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import ErrorMessage from '../components/shared/ErrorMessage';
import SyntheticLabel from '../components/shared/SyntheticLabel';
import Badge from '../components/shared/Badge';
import { IconAlertTriangle, IconSparkles, IconArrowRight } from '../components/shared/Icons';

export default function Customers() {
  const navigate = useNavigate();

  const [segmentsData, setSegmentsData] = useState<CustomerSegmentsData | null>(null);
  const [atRiskData, setAtRiskData] = useState<AtRiskData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'at-risk' | 'inactive'>('all');

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [segRes, atRiskRes] = await Promise.all([
        getCustomerSegments(),
        getAtRiskCustomers(),
      ]);
      setSegmentsData(segRes.data);
      setAtRiskData(atRiskRes.data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load customer segments');
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
        <LoadingSpinner label="AI Customer Engine segmenting patrons into RFM behavioral cohorts…" size="lg" />
      </div>
    );
  }

  if (error || !segmentsData || !atRiskData) {
    return (
      <div className="py-12 max-w-xl mx-auto">
        <ErrorMessage
          message={error || 'Unable to retrieve customer data'}
          onRetry={fetchData}
        />
      </div>
    );
  }

  const filteredCustomers = atRiskData.customers.filter((c) => {
    if (activeTab === 'all') return true;
    if (activeTab === 'at-risk') return c.segment === 'At-Risk';
    if (activeTab === 'inactive') return c.segment === 'Inactive';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-5 rounded-2xl border border-slate-200/90 shadow-card">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
            Customer Intelligence & Behavioral Cohorts
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Cohort segmentation calculated deterministically from transaction frequency, recency, and spend
          </p>
        </div>
        <SyntheticLabel variant="data" size="xs" />
      </div>

      {/* 5-Tier Segment Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {segmentsData.segments.map((seg) => {
          const badgeVariant =
            seg.segment === 'VIP'
              ? 'core'
              : seg.segment === 'Loyal'
              ? 'mvp'
              : seg.segment === 'New'
              ? 'vishal'
              : seg.segment === 'At-Risk'
              ? 'warning'
              : 'high';

          return (
            <div
              key={seg.segment}
              className="bg-white border border-slate-200/90 rounded-2xl p-4 sm:p-5 space-y-2 shadow-card hover:shadow-card-hover transition-all"
            >
              <div className="flex items-center justify-between">
                <Badge variant={badgeVariant as any} size="sm">{seg.segment}</Badge>
                <span className="text-xs font-semibold text-slate-400">{seg.pct_of_total}%</span>
              </div>
              <p className="text-2xl font-bold text-slate-900 mt-1">
                {seg.count}
              </p>
              <div className="text-xs text-slate-500 space-y-1 pt-2 border-t border-slate-100">
                <div className="flex justify-between">
                  <span className="text-slate-400">Avg Ticket:</span>
                  <span className="font-semibold text-slate-700">{formatRupees(seg.avg_spend)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Rev:</span>
                  <span className="font-semibold text-slate-700">{formatRupees(seg.total_revenue)}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Hero Attrition Callout */}
      <div className="bg-gradient-to-r from-amber-50/70 via-white to-sky-50/50 border border-amber-200/80 rounded-2xl p-5 sm:p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shadow-card">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-amber-800 font-bold text-xs">
            <IconAlertTriangle size={16} className="text-amber-600" />
            <span>Customer Retention Alert: {atRiskData.inactive_count} Inactive + {atRiskData.at_risk_count} At-Risk</span>
          </div>
          <p className="text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
            These patrons haven't visited in 22+ days, causing an estimated ₹7,200/wk drop in evening revenue.
            MerchantMind has synthesized a tailored ₹50 cashback campaign to reactivate them.
          </p>
        </div>

        <button
          onClick={() => navigate('/growth')}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-paytmNavy hover:bg-[#001c4d] text-white text-xs font-semibold transition-all flex-shrink-0 shadow-sm active:scale-[0.98]"
        >
          <IconSparkles size={14} className="text-paytm" />
          <span>Launch Reactivation Campaign</span>
          <IconArrowRight size={14} />
        </button>
      </div>

      {/* Customer Directory Table */}
      <div className="bg-white border border-slate-200/90 rounded-2xl shadow-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-slate-50/50">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Customer Retention Priority Directory
            </h3>
            <p className="text-xs text-slate-500">
              Showing patrons who qualify for targeted reactivation incentives
            </p>
          </div>

          <div className="inline-flex rounded-xl bg-slate-100 p-1 text-xs font-medium">
            <button
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeTab === 'all'
                  ? 'bg-white text-slate-900 font-bold shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              All ({atRiskData.customers.length})
            </button>
            <button
              onClick={() => setActiveTab('at-risk')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeTab === 'at-risk'
                  ? 'bg-amber-100/80 text-amber-800 font-bold shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              At-Risk ({atRiskData.at_risk_count})
            </button>
            <button
              onClick={() => setActiveTab('inactive')}
              className={`px-3 py-1 rounded-lg transition-all ${
                activeTab === 'inactive'
                  ? 'bg-rose-100/80 text-rose-800 font-bold shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Inactive ({atRiskData.inactive_count})
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] font-bold tracking-wider border-b border-slate-100">
              <tr>
                <th className="py-3 px-4">Customer ID</th>
                <th className="py-3 px-4">Cohort</th>
                <th className="py-3 px-4">Days Since Visit</th>
                <th className="py-3 px-4">Total Orders</th>
                <th className="py-3 px-4">Lifetime Spend</th>
                <th className="py-3 px-4">Avg Order Value</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredCustomers.map((c) => (
                <tr key={c.customer_id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-3.5 px-4 font-bold text-slate-900">{c.customer_id}</td>
                  <td className="py-3.5 px-4">
                    <Badge variant={c.segment === 'At-Risk' ? 'warning' : 'high'} size="sm">
                      {c.segment}
                    </Badge>
                  </td>
                  <td className="py-3.5 px-4">
                    <span className="text-amber-700 font-semibold">{c.days_since_last_transaction} days</span>
                  </td>
                  <td className="py-3.5 px-4 font-medium">{c.transaction_count} orders</td>
                  <td className="py-3.5 px-4 font-semibold text-slate-900">{formatRupees(c.total_spend)}</td>
                  <td className="py-3.5 px-4">{formatRupees(c.avg_transaction)}</td>
                  <td className="py-3.5 px-4 text-right">
                    <button
                      onClick={() => navigate('/growth')}
                      className="text-paytmNavy hover:text-paytm font-semibold text-xs px-2.5 py-1 rounded-lg hover:bg-sky-50 transition-colors"
                    >
                      Target →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
