import { useNavigate } from 'react-router-dom';
import SyntheticLabel from '../shared/SyntheticLabel';
import { IconBot, IconBell } from '../shared/Icons';

interface TopbarProps {
  title?: string;
}

export default function Topbar({ title = 'Merchant Dashboard' }: TopbarProps) {
  const navigate = useNavigate();

  return (
    <header className="h-16 bg-white/95 backdrop-blur-md border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-subtle">
      <div className="flex items-center gap-3">
        <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
          {title}
        </h1>
        <div className="hidden sm:block">
          <SyntheticLabel variant="data" size="xs" />
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-3">
        {/* Quick Launch Copilot */}
        <button
          onClick={() => navigate('/copilot')}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-50 border border-sky-200/80 text-paytmNavy hover:bg-sky-100 transition-colors text-xs font-semibold shadow-sm"
        >
          <IconBot size={15} className="text-paytm" />
          <span className="hidden sm:inline">Ask Copilot</span>
          <span className="hidden md:inline-block bg-white text-slate-500 border border-slate-200 text-[10px] px-1.5 py-0.2 rounded font-sans ml-0.5">
            AI
          </span>
        </button>

        {/* AI Status Indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-emerald-50 border border-emerald-200/80 text-[11px] font-medium text-emerald-700">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="hidden md:inline text-slate-600">MerchantMind AI:</span>
          <span className="font-semibold">Active</span>
        </div>

        {/* Notification Bell */}
        <button
          onClick={() => navigate('/growth')}
          className="relative p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
          title="1 active growth notification"
          aria-label="Notifications"
        >
          <IconBell size={18} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-white" />
        </button>

        {/* Merchant Avatar */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-200">
          <div className="w-8 h-8 rounded-full bg-paytmNavy text-paytm font-bold text-xs flex items-center justify-center shadow-sm">
            SS
          </div>
          <div className="hidden lg:block text-left">
            <p className="text-xs font-semibold text-slate-800 leading-none">Sharma Sweets</p>
            <p className="text-[10px] text-slate-400 mt-0.5 leading-none">Verified Merchant</p>
          </div>
        </div>
      </div>
    </header>
  );
}
