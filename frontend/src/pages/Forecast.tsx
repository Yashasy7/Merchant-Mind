import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { getRevenueForecast, formatRupees, formatRupeesCompact } from '../api';
import type { RevenueForecast } from '../types';
import KPICard from '../components/dashboard/KPICard';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import ErrorMessage from '../components/shared/ErrorMessage';
import SyntheticLabel from '../components/shared/SyntheticLabel';
import Badge from '../components/shared/Badge';
import { IconTrendingUp, IconBot } from '../components/shared/Icons';

export default function Forecast() {
  const [forecast, setForecast] = useState<RevenueForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getRevenueForecast();
      setForecast(res.data);
    } catch (err: any) {
      setError(err?.message || 'Failed to calculate forecast');
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
        <LoadingSpinner label="AI Forecasting Engine calculating rolling revenue bounds…" size="lg" />
      </div>
    );
  }

  if (error || !forecast) {
    return (
      <div className="py-12 max-w-xl mx-auto">
        <ErrorMessage
          message={error || 'No forecast data available'}
          onRetry={fetchData}
        />
      </div>
    );
  }

  // Projection trend points (Historical + 3-month outlook)
  const projectionPoints = [
    { month: 'Oct 2023', actual: 480000, central: null, lower: null, upper: null },
    { month: 'Nov 2023', actual: 495000, central: null, lower: null, upper: null },
    { month: 'Dec 2023', actual: 520000, central: null, lower: null, upper: null },
    { month: 'Jan 2024 (Now)', actual: 500000, central: 500000, lower: 500000, upper: 500000 },
    { month: 'Feb 2024 (P)', actual: null, central: 512000, lower: 475000, upper: 540000 },
    { month: 'Mar 2024 (P)', actual: null, central: 525000, lower: 470000, upper: 565000 },
    { month: 'Apr 2024 (P)', actual: null, central: 535000, lower: 460000, upper: 580000 },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-5 rounded-2xl border border-slate-200/90 shadow-card">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
              Revenue Forecast & Horizon Projection
            </h2>
            <Badge variant="mvp" size="sm">Statistical Model</Badge>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Statistical projection model based on {forecast.forecast_basis}
          </p>
        </div>
        <SyntheticLabel variant="projection" size="xs" />
      </div>

      {/* Projection Bounds Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KPICard
          label="Conservative Floor (Lower)"
          value={formatRupees(forecast.lower_bound)}
          subValue="90% statistical floor"
          accent="yellow"
        />
        <KPICard
          label="Central Estimate (Expected)"
          value={formatRupees(forecast.central_estimate)}
          subValue="Baseline run-rate trajectory"
          accent="blue"
          icon={<IconTrendingUp size={18} />}
        />
        <KPICard
          label="Optimistic Ceiling (Upper)"
          value={formatRupees(forecast.upper_bound)}
          subValue="With active growth campaigns"
          accent="green"
        />
      </div>

      {/* Historical + Projected Trajectory Chart */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 space-y-4 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Revenue Horizon Trajectory (INR)
            </h3>
            <p className="text-xs text-slate-400">
              Historical performance transitioning into 3-month forecast cone
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-slate-600">
              <span className="w-2.5 h-2.5 rounded-full bg-paytmNavy inline-block" />
              Historical Actual
            </span>
            <span className="flex items-center gap-1.5 font-semibold text-emerald-700">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
              Projected Central
            </span>
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-2.5 h-0.5 bg-slate-400 inline-block" />
              Confidence Cone
            </span>
          </div>
        </div>

        <div className="w-full h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={projectionPoints} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis
                dataKey="month"
                stroke="#94a3b8"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: '#f1f5f9' }}
              />
              <YAxis
                stroke="#94a3b8"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: '#f1f5f9' }}
                tickFormatter={(v) => formatRupeesCompact(v)}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="bg-white border border-slate-200 p-3 rounded-xl shadow-lg text-xs space-y-1">
                        <p className="text-slate-800 font-bold mb-1">{label}</p>
                        {payload.map((p, idx) => (
                          <p key={`item-${idx}`} style={{ color: p.color }} className="font-semibold">
                            {p.name}: {p.value ? formatRupees(p.value as number) : '—'}
                          </p>
                        ))}
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <ReferenceLine x="Jan 2024 (Now)" stroke="#00baf2" strokeDasharray="3 3" label={{ value: 'Current', fill: '#0052cc', fontSize: 10, position: 'top' }} />
              <Line
                type="monotone"
                dataKey="actual"
                name="Historical Actual"
                stroke="#002970"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#002970' }}
              />
              <Line
                type="monotone"
                dataKey="central"
                name="Projected Central"
                stroke="#16a34a"
                strokeWidth={2.5}
                strokeDasharray="4 4"
                dot={{ r: 4, fill: '#16a34a' }}
              />
              <Line
                type="monotone"
                dataKey="upper"
                name="Upper Bound"
                stroke="#6366f1"
                strokeWidth={1.5}
                strokeDasharray="2 2"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="lower"
                name="Lower Bound"
                stroke="#f59e0b"
                strokeWidth={1.5}
                strokeDasharray="2 2"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* AI Narrative */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 space-y-2 shadow-card">
        <div className="flex items-center gap-2 text-paytmNavy font-bold text-xs">
          <IconBot size={16} className="text-paytm" />
          <span>AI Macro Narrative & Projections</span>
        </div>
        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
          {forecast.ai_explanation}
        </p>
      </div>
    </div>
  );
}
