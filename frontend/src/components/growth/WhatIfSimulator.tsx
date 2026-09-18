import type { SimulationStrategy } from '../../types';
import { formatRupees } from '../../api';
import Badge from '../shared/Badge';
import SyntheticLabel from '../shared/SyntheticLabel';
import { IconCheckCircle, IconArrowRight } from '../shared/Icons';

interface WhatIfSimulatorProps {
  strategies: SimulationStrategy[];
  selectedStrategyId: string | null;
  onSelectStrategy: (strategyId: string) => void;
  onProceedToApproval: (strategy: SimulationStrategy) => void;
}

export default function WhatIfSimulator({
  strategies,
  selectedStrategyId,
  onSelectStrategy,
  onProceedToApproval,
}: WhatIfSimulatorProps) {
  const activeStrategy =
    strategies.find((s) => s.strategy_id === selectedStrategyId) ??
    strategies.find((s) => s.is_recommended) ??
    strategies[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
              What-if Campaign Simulator
            </h3>
            <Badge variant="core">Hero Step 10</Badge>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Compare expected return, incentive budget, and incremental revenue across 4 candidate campaign strategies.
          </p>
        </div>

        {/* Mandatory simulator disclaimer per blueprint §6 Module 06 */}
        <SyntheticLabel variant="projection" size="xs" />
      </div>

      {/* 4-Strategy Grid Comparison */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {strategies.map((strat) => {
          const isSelected = strat.strategy_id === (selectedStrategyId ?? activeStrategy?.strategy_id);
          const isRecommended = strat.is_recommended;

          return (
            <div
              key={strat.strategy_id}
              onClick={() => onSelectStrategy(strat.strategy_id)}
              className={`cursor-pointer rounded-2xl p-5 transition-all duration-200 border flex flex-col justify-between ${
                isSelected
                  ? 'bg-white border-paytmNavy ring-2 ring-paytmNavy/15 shadow-card-hover -translate-y-0.5'
                  : 'bg-white border-slate-200/90 hover:border-slate-300 shadow-card'
              }`}
            >
              <div>
                <div className="flex items-center justify-between gap-1 mb-2">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    Option {strat.strategy_id}
                  </span>
                  {isRecommended ? (
                    <Badge variant="core" size="sm">
                      Best ROI
                    </Badge>
                  ) : (
                    <span className="text-[10px] text-slate-400">Alternative</span>
                  )}
                </div>

                <h4 className="text-sm font-bold text-slate-900 mb-2 leading-tight">
                  {strat.label}
                </h4>

                <div className="space-y-2.5 py-3 my-2 border-y border-slate-100 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Expected Orders:</span>
                    <span className="font-bold text-slate-900">{strat.expected_transactions}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Gross Revenue:</span>
                    <span className="font-bold text-slate-900">{formatRupees(strat.expected_revenue)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Incentive Cost:</span>
                    <span className="font-bold text-rose-600">{formatRupees(strat.incentive_cost)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Incremental Rev:</span>
                    <span className="font-bold text-emerald-600">
                      +{formatRupees(strat.incremental_revenue)}
                    </span>
                  </div>
                  <div className="flex justify-between pt-1 border-t border-slate-100">
                    <span className="text-slate-500 font-medium">Estimated ROI:</span>
                    <span className="font-extrabold text-paytmNavy">
                      {strat.estimated_roi.toFixed(1)}x
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectStrategy(strat.strategy_id);
                  }}
                  className={`w-full py-2 rounded-xl text-xs font-semibold transition-all ${
                    isSelected
                      ? 'bg-paytmNavy text-white shadow-sm'
                      : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                  }`}
                >
                  {isSelected ? '✓ Selected Strategy' : 'Select Strategy'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Strategy Deep-Dive & Action Banner */}
      {activeStrategy && (
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-card flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-paytmNavy">
                Chosen Configuration:
              </span>
              <span className="text-sm font-bold text-slate-900">
                {activeStrategy.label}
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Projected to generate <strong>+{formatRupees(activeStrategy.incremental_revenue)}</strong> incremental sales at an authorized incentive cost of <strong>{formatRupees(activeStrategy.incentive_cost)}</strong> (~{activeStrategy.estimated_roi.toFixed(1)}x return).
            </p>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <button
              onClick={() => onProceedToApproval(activeStrategy)}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs sm:text-sm font-bold transition-all shadow-sm active:scale-[0.98]"
            >
              <IconCheckCircle size={16} />
              <span>Review & Approve Campaign</span>
              <IconArrowRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
