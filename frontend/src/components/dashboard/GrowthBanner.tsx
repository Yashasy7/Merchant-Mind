import { useNavigate } from 'react-router-dom';
import { IconArrowRight, IconSparkles, IconBot } from '../shared/Icons';
import SyntheticLabel from '../shared/SyntheticLabel';

export default function GrowthBanner() {
  const navigate = useNavigate();

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-sky-50/70 via-white to-blue-50/50 border border-sky-200/80 p-5 sm:p-6 shadow-card hover:shadow-card-hover transition-all duration-200">
      {/* Soft decorative background circles */}
      <div className="absolute top-0 right-0 w-72 h-72 bg-sky-100/40 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-5">
        <div className="space-y-2.5">
          {/* AI Header Tag */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-100/80 text-paytmNavy border border-sky-200">
              <IconBot size={14} className="text-paytm" />
              <span>MerchantMind AI</span>
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200/80">
              AI Insight
            </span>
            <SyntheticLabel variant="data" size="xs" />
          </div>

          {/* Assistant Direct Statement */}
          <h3 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight leading-snug">
            “Your sales dropped 16% over the last two weeks.”
          </h3>

          <p className="text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
            I analyzed your transaction patterns and found that your evening sales between <strong className="text-slate-800">6–9 PM</strong> decreased significantly, led by 126 inactive regular customers. 
            <span className="block mt-1 font-medium text-slate-700">
              Recommended action: Launch a targeted evening cashback campaign to recover ₹7,200/wk.
            </span>
          </p>
        </div>

        {/* Action Button */}
        <div className="flex items-center gap-3 flex-shrink-0 pt-2 md:pt-0">
          <button
            onClick={() => navigate('/growth')}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-paytmNavy hover:bg-[#001c4d] text-white text-xs sm:text-sm font-semibold transition-all shadow-sm active:scale-[0.98]"
          >
            <IconSparkles size={15} className="text-paytm" />
            <span>Review Recommendation</span>
            <IconArrowRight size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
