import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getDashboard,
  getSalesTrends,
  getProfitLoss,
  formatRupees,
} from '../api';
import type { DashboardData, SalesTrendsData, ProfitLossData } from '../types';
import KPICard from '../components/dashboard/KPICard';
import RevenueChart from '../components/dashboard/RevenueChart';
import HoursBarChart from '../components/dashboard/HoursBarChart';
import InsightCard from '../components/dashboard/InsightCard';
import GrowthBanner from '../components/dashboard/GrowthBanner';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import ErrorMessage from '../components/shared/ErrorMessage';
import SyntheticLabel from '../components/shared/SyntheticLabel';
import Badge from '../components/shared/Badge';
import {
  IconTrendingUp,
  IconCalculator,
  IconLineChart,
  IconUsers,
  IconSparkles,
  IconArrowRight,
  IconPackage,
} from '../components/shared/Icons';

export default function Dashboard() {
  const navigate = useNavigate();
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [trendsData, setTrendsData] = useState<SalesTrendsData | null>(null);
  const [plData, setPlData] = useState<ProfitLossData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [dashRes, trendsRes, plRes] = await Promise.all([
        getDashboard(),
        getSalesTrends(14),
        getProfitLoss(),
      ]);
      setDashboardData(dashRes.data);
      setTrendsData(trendsRes.data);
      setPlData(plRes.data);
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch dashboard metrics');
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
        <LoadingSpinner label="Fetching your daily merchant metrics and AI recommendations…" size="lg" />
      </div>
    );
  }

  if (error || !dashboardData) {
    return (
      <div className="py-12 max-w-xl mx-auto">
        <ErrorMessage
          message={error || 'No dashboard data returned by API'}
          onRetry={fetchData}
        />
      </div>
    );
  }

  const { kpis, insights } = dashboardData;

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* ── Top Greeting Section ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-5 sm:p-6 rounded-2xl border border-slate-200/80 shadow-card">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold uppercase tracking-wider text-paytmNavy">
              Paytm Business Partner
            </span>
            <span className="w-1 h-1 rounded-full bg-slate-300" />
            <span className="text-xs text-slate-500 font-medium">Jaipur Outlet</span>
          </div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            GOOD MORNING, SHARMA SWEETS 👋
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Here's how your business is doing today.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <SyntheticLabel variant="data" size="xs" />
        </div>
      </div>

      {/* ── Compact Daily Summary Cards ── */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KPICard
          label="Today's Revenue"
          value={formatRupees(kpis.revenue_today)}
          subValue="₹17,500 expected by EOD"
          accent="blue"
          icon={<IconTrendingUp size={18} />}
        />
        <KPICard
          label="Transactions"
          value={kpis.transaction_count_today}
          subValue="Avg ₹219 per order"
          accent="green"
          icon={<IconLineChart size={18} />}
        />
        <KPICard
          label="Estimated Profit"
          value={formatRupees(kpis.estimated_profit)}
          subValue={`${kpis.estimated_margin}% margin (P&L)`}
          accent="purple"
          icon={<IconCalculator size={18} />}
        />
        <KPICard
          label="Business Health"
          value={`${kpis.growth_score}/100`}
          subValue="Evening traffic needs attention"
          changePct={8.4}
          changeLabel="growth indicator"
          accent="yellow"
          icon={<IconSparkles size={18} />}
        />
      </section>

      {/* ── AI Insight as Hero ── */}
      <section>
        <GrowthBanner />
      </section>

      {/* ── Sales Analytics Section ── */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-5 sm:gap-6">
        {/* Daily Sales Trend */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-card hover:shadow-card-hover transition-all duration-200 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span>Sales Trend</span>
                <span className="text-xs font-normal text-slate-500">(Continuous Revenue)</span>
              </h3>
              <p className="text-xs text-slate-400">Track daily revenue trajectory against baseline</p>
            </div>
            <SyntheticLabel variant="data" size="xs" />
          </div>
          {trendsData && <RevenueChart data={trendsData.daily} />}
        </div>

        {/* Hourly Distribution & Drop Window */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-card hover:shadow-card-hover transition-all duration-200 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span>Transactions by Hour</span>
                <Badge variant="warning" size="sm">6–9 PM Drop</Badge>
              </h3>
              <p className="text-xs text-slate-400">Pinpoints busy store hours vs. traffic slowdowns</p>
            </div>
            <SyntheticLabel variant="data" size="xs" />
          </div>
          {trendsData && <HoursBarChart data={trendsData.hourly} />}
        </div>
      </section>

      {/* ── AI Accountant & Growth Opportunities Section ── */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-5 sm:gap-6">
        {/* AI Accountant Assistant Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-card hover:shadow-card-hover transition-all duration-200 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-700 flex items-center justify-center">
                  <IconCalculator size={18} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">AI ACCOUNTANT</h3>
                  <p className="text-xs text-slate-400">Your real-time financial summary</p>
                </div>
              </div>
              <Badge variant="core" size="sm">Cash Flow: Healthy</Badge>
            </div>

            {/* Financial Summary Grid */}
            <div className="grid grid-cols-3 gap-2.5 bg-slate-50 p-3.5 rounded-xl border border-slate-200/70 mb-4 text-center">
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">
                  Revenue
                </span>
                <span className="text-sm sm:text-base font-bold text-slate-900 block mt-0.5">
                  {formatRupees(plData?.total_revenue ?? kpis.revenue_this_month)}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">
                  Expenses
                </span>
                <span className="text-sm sm:text-base font-bold text-slate-900 block mt-0.5">
                  {formatRupees(plData?.total_expenses ?? 385000)}
                </span>
              </div>
              <div>
                <span className="text-[10px] uppercase font-bold text-slate-400 block">
                  Est. Profit
                </span>
                <span className="text-sm sm:text-base font-bold text-emerald-600 block mt-0.5">
                  {formatRupees(plData?.operating_profit ?? kpis.estimated_profit)}
                </span>
              </div>
            </div>

            {/* Suggested Questions */}
            <div className="space-y-2 mb-4">
              <span className="text-xs font-semibold text-slate-700 block">
                Ask your AI Accountant:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  'How much profit did I make this month?',
                  'Where am I spending the most?',
                  'Compare this month with last month',
                  'Show my biggest expenses',
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => navigate(`/copilot?prompt=${encodeURIComponent(q)}`)}
                    className="text-left text-xs bg-slate-100/80 hover:bg-sky-50 hover:text-paytmNavy text-slate-600 px-3 py-1.5 rounded-lg transition-colors border border-slate-200/60"
                  >
                    • {q}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex justify-between items-center">
            <span className="text-[11px] text-slate-400">Deterministic ledger aggregation</span>
            <button
              onClick={() => navigate('/accountant')}
              className="inline-flex items-center gap-1.5 text-xs font-bold text-paytmNavy hover:text-paytm transition-colors"
            >
              <span>Open AI Accountant</span>
              <IconArrowRight size={14} />
            </button>
          </div>
        </div>

        {/* Growth Opportunities Card */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-card hover:shadow-card-hover transition-all duration-200 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
                  <IconSparkles size={18} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">GROWTH OPPORTUNITIES</h3>
                  <p className="text-xs text-slate-400">Personalized AI recommendations for Jaipur outlet</p>
                </div>
              </div>
              <Badge variant="mvp" size="sm">3 Actions</Badge>
            </div>

            <div className="space-y-3">
              {/* Opportunity 1 */}
              <div className="p-3 bg-slate-50 hover:bg-sky-50/50 rounded-xl border border-slate-200/70 transition-colors flex items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-emerald-100/70 text-emerald-700 mt-0.5">
                    <IconTrendingUp size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">Increase Weekend Sales</h4>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Your weekend revenue is 22% higher than weekdays.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => navigate('/growth')}
                  className="text-xs font-bold text-paytmNavy hover:text-paytm px-3 py-1 rounded-lg bg-white border border-slate-200 shadow-sm flex-shrink-0"
                >
                  View
                </button>
              </div>

              {/* Opportunity 2 */}
              <div className="p-3 bg-slate-50 hover:bg-sky-50/50 rounded-xl border border-slate-200/70 transition-colors flex items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-blue-100/70 text-blue-700 mt-0.5">
                    <IconPackage size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">Restock Fast-Selling Products</h4>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Kaju Katli and Milk Cake may run low in 3 days.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => navigate('/copilot?prompt=Restock%20fast-selling%20products')}
                  className="text-xs font-bold text-paytmNavy hover:text-paytm px-3 py-1 rounded-lg bg-white border border-slate-200 shadow-sm flex-shrink-0"
                >
                  Check
                </button>
              </div>

              {/* Opportunity 3 */}
              <div className="p-3 bg-slate-50 hover:bg-sky-50/50 rounded-xl border border-slate-200/70 transition-colors flex items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-purple-100/70 text-purple-700 mt-0.5">
                    <IconUsers size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900">Improve Customer Retention</h4>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      126 inactive regular customers haven't visited in 45+ days.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => navigate('/customers')}
                  className="text-xs font-bold text-paytmNavy hover:text-paytm px-3 py-1 rounded-lg bg-white border border-slate-200 shadow-sm flex-shrink-0"
                >
                  Review
                </button>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-100 flex justify-between items-center mt-3">
            <span className="text-[11px] text-slate-400">Updated hourly from Paytm POS</span>
            <button
              onClick={() => navigate('/growth')}
              className="inline-flex items-center gap-1.5 text-xs font-bold text-paytmNavy hover:text-paytm transition-colors"
            >
              <span>Explore All Opportunities</span>
              <IconArrowRight size={14} />
            </button>
          </div>
        </div>
      </section>

      {/* ── Additional Autonomous AI Insights ── */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Autonomous Business Diagnostics
          </h2>
          <span className="text-[11px] text-slate-400">
            Generated by AI Orchestrator
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {insights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      </section>
    </div>
  );
}
