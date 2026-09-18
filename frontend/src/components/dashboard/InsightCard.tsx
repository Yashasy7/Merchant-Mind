import { useNavigate } from 'react-router-dom';
import type { AiInsightCard } from '../../types';
import Badge from '../shared/Badge';
import { IconArrowRight } from '../shared/Icons';

interface InsightCardProps {
  insight: AiInsightCard;
}

export default function InsightCard({ insight }: InsightCardProps) {
  const navigate = useNavigate();

  const borderVariant = {
    high: 'border-l-rose-500 bg-rose-50/20 hover:border-rose-300',
    medium: 'border-l-amber-500 bg-amber-50/20 hover:border-amber-300',
    low: 'border-l-emerald-500 bg-emerald-50/20 hover:border-emerald-300',
  }[insight.severity];

  const handleAction = () => {
    if (insight.type === 'alert') {
      navigate('/growth');
    } else {
      navigate('/copilot');
    }
  };

  return (
    <div
      className={`p-5 rounded-2xl bg-white border border-slate-200/90 border-l-4 ${borderVariant} shadow-card hover:shadow-card-hover transition-all duration-200 flex flex-col justify-between`}
    >
      <div>
        <div className="flex items-center justify-between gap-2 mb-2.5">
          <div className="flex items-center gap-2">
            <span className="text-lg">{insight.icon}</span>
            <Badge
              variant={insight.severity === 'high' ? 'high' : insight.severity === 'medium' ? 'medium' : 'low'}
            >
              {insight.severity === 'high' ? 'High Impact' : insight.severity === 'medium' ? 'Opportunity' : 'Notice'}
            </Badge>
          </div>
          <span className="text-[11px] font-medium text-slate-400">
            MerchantMind AI
          </span>
        </div>

        <h4 className="text-sm font-bold text-slate-900 mb-1">
          {insight.title}
        </h4>
        <p className="text-xs text-slate-600 leading-relaxed">
          {insight.body}
        </p>
      </div>

      <div className="mt-4 pt-3 border-t border-slate-100 flex justify-end">
        <button
          onClick={handleAction}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-paytmNavy hover:text-paytm transition-colors"
        >
          <span>Take Action</span>
          <IconArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}
