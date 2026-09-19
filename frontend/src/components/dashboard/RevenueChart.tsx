import { useState } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { DailyRevenueTrend } from '../../types';
import { formatRupeesCompact, formatRupees } from '../../api';

interface RevenueChartProps {
  data: DailyRevenueTrend[];
}

export default function RevenueChart({ data }: RevenueChartProps) {
  const [activeTab, setActiveTab] = useState<'7d' | '30d' | '3m'>('7d');

  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-xs text-slate-400">
        No sales trend data available
      </div>
    );
  }

  // Filter based on tab if needed, or format dates
  const displayData = activeTab === '7d' ? data.slice(-7) : data;
  const formattedData = displayData.map((item) => ({
    ...item,
    formattedDate: item.date.slice(5), // MM-DD
  }));

  return (
    <div className="space-y-4">
      {/* Time-range filter tabs */}
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div className="text-xs text-slate-500 font-medium">Daily Revenue Performance</div>
        <div className="inline-flex rounded-lg bg-slate-100 p-0.5 text-xs font-medium">
          {(['7d', '30d', '3m'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1 rounded-md transition-all ${
                activeTab === tab
                  ? 'bg-white text-paytmNavy font-semibold shadow-sm'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              {tab === '7d' ? '7 Days' : tab === '30d' ? '30 Days' : '3 Months'}
            </button>
          ))}
        </div>
      </div>

      <div className="w-full h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={formattedData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <defs>
              <linearGradient id="fintechRevenueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#00baf2" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#00baf2" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="formattedDate"
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: '#f1f5f9' }}
            />
            <YAxis
              stroke="#94a3b8"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: '#f1f5f9' }}
              tickFormatter={(val) => formatRupeesCompact(val)}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const item = payload[0].payload as DailyRevenueTrend;
                  return (
                    <div className="bg-white border border-slate-200 p-3 rounded-xl shadow-lg text-xs">
                      <p className="text-slate-500 font-medium mb-1">Date: {item.date}</p>
                      <p className="text-paytmNavy font-bold text-sm">
                        Revenue: {formatRupees(item.revenue)}
                      </p>
                      <p className="text-slate-500 text-[11px] mt-0.5">
                        {item.transaction_count} transactions
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Area
              type="monotone"
              dataKey="revenue"
              stroke="#0052cc"
              strokeWidth={2.5}
              fillOpacity={1}
              fill="url(#fintechRevenueGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
