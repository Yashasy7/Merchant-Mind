import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { getProfitLoss, getExpenses, formatRupees, formatPct } from '../api';
import type { ProfitLossData, ExpenseData } from '../types';
import KPICard from '../components/dashboard/KPICard';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import ErrorMessage from '../components/shared/ErrorMessage';
import SyntheticLabel from '../components/shared/SyntheticLabel';
import Badge from '../components/shared/Badge';
import {
  IconCalculator,
  IconAlertTriangle,
  IconTrendingUp,
  IconShieldCheck,
  IconBot,
} from '../components/shared/Icons';

const CATEGORY_COLORS = ['#0052cc', '#00baf2', '#10b981', '#f59e0b', '#8b5cf6'];

export default function Accountant() {
  const navigate = useNavigate();
  const [plData, setPlData] = useState<ProfitLossData | null>(null);
  const [expenseData, setExpenseData] = useState<ExpenseData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [plRes, expRes] = await Promise.all([
        getProfitLoss(),
        getExpenses(),
      ]);
      setPlData(plRes.data);
      setExpenseData(expRes.data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load financial records');
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
        <LoadingSpinner label="AI Accountant aggregating verified ledger items & analyzing expenses…" size="lg" />
      </div>
    );
  }

  if (error || !plData || !expenseData) {
    return (
      <div className="py-12 max-w-xl mx-auto">
        <ErrorMessage
          message={error || 'Unable to retrieve accounting data'}
          onRetry={fetchData}
        />
      </div>
    );
  }

  const pieData = expenseData.categories.map((c) => ({
    name: c.category,
    value: c.amount,
    pct: c.pct_of_total,
  }));

  const anomalyItem = expenseData.categories.find((c) => c.is_anomaly);

  return (
    <div className="space-y-6">
      {/* MANDATORY ACCOUNTING SAFETY DISCLAIMER (Blueprint & Instructions.md) */}
      <div className="p-4 bg-amber-50/80 border border-amber-200/80 rounded-2xl flex items-start gap-3 text-xs text-amber-900 shadow-subtle">
        <IconShieldCheck size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="space-y-0.5">
          <p className="font-bold text-amber-900">
            Chartered Accountant Regulatory Notice
          </p>
          <p className="text-amber-800 leading-relaxed">
            MerchantMind helps you understand and organize your financial data. For tax filings, compliance, or official financial statements, please consult a qualified CA.
          </p>
        </div>
      </div>

      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-5 rounded-2xl border border-slate-200/90 shadow-card">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
            Profit & Loss Statement ({plData.month})
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Deterministic calculation engine • Integrated POS & Store Ledger
          </p>
        </div>
        <SyntheticLabel variant="data" size="xs" />
      </div>

      {/* P&L Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KPICard
          label="Total Gross Revenue"
          value={formatRupees(plData.total_revenue)}
          subValue="Verified POS transactions"
          accent="blue"
          icon={<IconTrendingUp size={18} />}
        />
        <KPICard
          label="Operating Expenses"
          value={formatRupees(plData.total_expenses)}
          subValue={`Largest: ${expenseData.largest_category}`}
          accent="yellow"
          icon={<IconCalculator size={18} />}
        />
        <KPICard
          label="Operating Profit"
          value={formatRupees(plData.operating_profit)}
          subValue="Net merchant margin"
          accent="green"
          icon={<IconShieldCheck size={18} />}
        />
        <KPICard
          label="Operating Margin"
          value={`${plData.operating_margin_pct}%`}
          subValue="Backend verified"
          accent="purple"
          changePct={2.1}
          changeLabel="vs last month"
        />
      </div>

      {/* AI Financial Narrative & Donut Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Narrative Box */}
        <div className="lg:col-span-2 bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 space-y-4 shadow-card flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <IconBot size={18} className="text-paytm" />
                <h3 className="text-sm font-bold text-slate-900">
                  AI Financial Analyst Commentary
                </h3>
              </div>
              <Badge variant="core" size="sm">Verified Numbers</Badge>
            </div>

            <p className="text-xs sm:text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
              {plData.ai_explanation}
            </p>

            {/* Anomaly Callout */}
            {anomalyItem && (
              <div className="p-4 bg-amber-50/70 border border-amber-200/80 rounded-xl space-y-1.5 mt-3">
                <div className="flex items-center gap-2 text-amber-800 font-bold text-xs">
                  <IconAlertTriangle size={16} className="text-amber-600" />
                  <span>Expense Anomaly Flagged: {anomalyItem.category}</span>
                  <span className="text-[11px] font-semibold text-rose-600">
                    ({formatPct(anomalyItem.vs_prior_month_pct)} vs prior month)
                  </span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {anomalyItem.anomaly_note ||
                    expenseData.anomaly_summary ||
                    'Abnormal expense spike detected relative to historical monthly run rates.'}
                </p>
              </div>
            )}
          </div>

          {/* Interactive Financial Questions */}
          <div className="pt-4 border-t border-slate-100 space-y-2">
            <span className="text-xs font-bold text-slate-700 block">
              Ask AI Accountant to drill down:
            </span>
            <div className="flex flex-wrap gap-2">
              {[
                'How can I lower my raw material costs?',
                'Compare Jaipur store margin to benchmark',
                'What is my breakeven daily sales number?',
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => navigate(`/copilot?prompt=${encodeURIComponent(q)}`)}
                  className="text-xs bg-slate-100 hover:bg-sky-50 text-slate-700 hover:text-paytmNavy px-3 py-1.5 rounded-lg border border-slate-200/70 transition-colors"
                >
                  {q} →
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Donut Chart: Expense Breakdown */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 space-y-3 shadow-card flex flex-col justify-between">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900">Expense Breakdown</h3>
            <span className="text-xs font-bold text-slate-700">
              {formatRupees(expenseData.total_expenses)}
            </span>
          </div>

          <div className="w-full h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={46}
                  outerRadius={72}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={CATEGORY_COLORS[index % CATEGORY_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload;
                      return (
                        <div className="bg-white border border-slate-200 p-2.5 rounded-xl shadow-lg text-xs">
                          <p className="font-bold text-slate-900">{item.name}</p>
                          <p className="text-paytmNavy font-bold">{formatRupees(item.value)}</p>
                          <p className="text-slate-500 text-[10px]">{item.pct}% of total</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-slate-100 text-xs">
            {expenseData.categories.map((c, idx) => (
              <div
                key={c.category}
                className="flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: CATEGORY_COLORS[idx % CATEGORY_COLORS.length] }}
                  />
                  <span className="text-slate-600">{c.category}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-900 font-semibold">{formatRupees(c.amount)}</span>
                  <span className="text-slate-400 text-[10px]">({c.pct_of_total}%)</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
