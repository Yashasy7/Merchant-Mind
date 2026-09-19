import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { HourlyBucket } from '../../types';
import { formatRupees } from '../../api';

interface HoursBarChartProps {
  data: HourlyBucket[];
}

export default function HoursBarChart({ data }: HoursBarChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-xs text-slate-400">
        No hourly transaction data available
      </div>
    );
  }

  // Format hour for display: 9 -> "9 AM", 18 -> "6 PM"
  const chartData = data.map((item) => {
    const h = item.hour;
    const label =
      h === 0 ? '12 AM' : h < 12 ? `${h} AM` : h === 12 ? '12 PM' : `${h - 12} PM`;
    return {
      ...item,
      label,
      isDeclineZone: h >= 18 && h <= 21,
    };
  });

  return (
    <div className="space-y-4">
      {/* Chart Sub-header and Legend */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3 text-xs">
        <span className="text-slate-500 font-medium">Customer Footfall by Hour</span>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-slate-500">
            <span className="w-2.5 h-2.5 rounded-sm bg-sky-400 inline-block" />
            Standard traffic
          </span>
          <span className="flex items-center gap-1 font-medium text-amber-700">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-400 inline-block" />
            6–9 PM drop window
          </span>
        </div>
      </div>

      <div className="w-full h-64 sm:h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="#94a3b8"
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: '#f1f5f9' }}
              interval={2}
            />
            <YAxis
              stroke="#94a3b8"
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: '#f1f5f9' }}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const item = payload[0].payload;
                  return (
                    <div className="bg-white border border-slate-200 p-3 rounded-xl shadow-lg text-xs">
                      <p className="text-slate-800 font-bold">{item.label}</p>
                      <p className="text-paytmNavy font-bold mt-1">
                        {item.transaction_count} orders ({formatRupees(item.revenue)})
                      </p>
                      {item.isDeclineZone && (
                        <p className="text-amber-700 text-[11px] font-medium mt-1 bg-amber-50 px-2 py-0.5 rounded border border-amber-200/60">
                          Decline window: -31% drop vs prior 2 weeks
                        </p>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar dataKey="transaction_count" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.isDeclineZone ? '#f59e0b' : '#38bdf8'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
