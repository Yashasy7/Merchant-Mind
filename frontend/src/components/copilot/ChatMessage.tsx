import type { ChatMessage as ChatMessageType } from '../../types';
import RecommendationCard from './RecommendationCard';
import { formatRupees } from '../../api';
import { IconBot } from '../shared/Icons';

interface ChatMessageProps {
  message: ChatMessageType;
  onSimulateRecommendation?: () => void;
}

export default function ChatMessage({
  message,
  onSimulateRecommendation,
}: ChatMessageProps) {
  const isUser = message.role === 'user';

  const formattedTime = new Date(message.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div
      className={`flex gap-3 my-4 ${
        isUser ? 'flex-row-reverse' : 'flex-row'
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-xl flex-shrink-0 flex items-center justify-center text-xs font-bold shadow-sm ${
          isUser
            ? 'bg-paytmNavy text-paytm'
            : 'bg-sky-50 border border-sky-200 text-paytmNavy'
        }`}
      >
        {isUser ? 'SS' : <IconBot size={16} className="text-paytm" />}
      </div>

      {/* Bubble Container */}
      <div
        className={`flex flex-col max-w-2xl space-y-1.5 ${
          isUser ? 'items-end' : 'items-start'
        }`}
      >
        <div className="flex items-center gap-2 px-1">
          <span className="text-[11px] font-semibold text-slate-600">
            {isUser ? 'Sharma Sweets' : 'MerchantMind AI Copilot'}
          </span>
          <span className="text-[10px] text-slate-400">
            {formattedTime}
          </span>
        </div>

        {/* Message Body */}
        <div
          className={`rounded-2xl p-4 text-xs sm:text-sm leading-relaxed ${
            isUser
              ? 'bg-paytmNavy text-white font-normal rounded-tr-sm shadow-sm'
              : 'bg-white border border-slate-200/90 text-slate-800 rounded-tl-sm shadow-card'
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>

        {/* Inline Structured Cards */}
        {!isUser && message.structured_data && (
          <div className="w-full mt-2">
            {message.structured_data.type === 'recommendation' && (
              <RecommendationCard
                recommendation={message.structured_data.payload}
                onSimulate={onSimulateRecommendation}
              />
            )}

            {message.structured_data.type === 'sales_analysis' && (
              <div className="bg-white border border-amber-200 p-4 rounded-2xl text-xs space-y-2.5 shadow-card">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-amber-800 uppercase text-[11px]">
                    Decline Analysis Signal
                  </span>
                  <span className="text-rose-700 font-bold bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                    -{message.structured_data.payload.overall_decline_pct}% overall drop
                  </span>
                </div>
                <p className="text-slate-600 leading-relaxed">
                  {message.structured_data.payload.diagnosis}
                </p>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70 flex justify-between text-xs">
                  <span className="text-slate-600">Worst Window: {message.structured_data.payload.worst_period_label}</span>
                  <span className="text-rose-600 font-bold">
                    -{message.structured_data.payload.worst_period_decline_pct}% decline
                  </span>
                </div>
              </div>
            )}

            {message.structured_data.type === 'profit_loss' && (
              <div className="bg-white border border-slate-200/90 p-4 rounded-2xl text-xs space-y-3 shadow-card">
                <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                  <span className="font-bold text-slate-900 uppercase text-[11px]">
                    Financial P&L Summary
                  </span>
                  <span className="text-slate-500 font-medium">
                    {message.structured_data.payload.month}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/70">
                    <span className="text-[10px] text-slate-400 block font-semibold uppercase">Revenue</span>
                    <span className="font-bold text-slate-900 text-xs sm:text-sm">
                      {formatRupees(message.structured_data.payload.total_revenue)}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/70">
                    <span className="text-[10px] text-slate-400 block font-semibold uppercase">Expenses</span>
                    <span className="font-bold text-slate-900 text-xs sm:text-sm">
                      {formatRupees(message.structured_data.payload.total_expenses)}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-200/70">
                    <span className="text-[10px] text-slate-400 block font-semibold uppercase">Profit</span>
                    <span className="font-bold text-emerald-600 text-xs sm:text-sm">
                      {formatRupees(message.structured_data.payload.operating_profit)}
                    </span>
                  </div>
                </div>
                <p className="text-slate-600 text-xs leading-relaxed">
                  {message.structured_data.payload.ai_explanation}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
