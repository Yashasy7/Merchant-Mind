import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  IconDashboard,
  IconBot,
  IconTrendingUp,
  IconLineChart,
  IconUsers,
  IconCalculator,
  IconSparkles,
  IconCheckCircle,
  IconStore,
  IconSliders,
} from '../shared/Icons';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  badge?: string;
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: <IconDashboard size={18} /> },
  { to: '/copilot', label: 'AI Copilot', icon: <IconBot size={18} />, badge: 'AI' },
  { to: '/growth', label: 'Sales & Growth', icon: <IconTrendingUp size={18} /> },
  { to: '/simulator', label: 'What-if Simulator', icon: <IconLineChart size={18} /> },
  { to: '/campaigns', label: 'Campaigns & Results', icon: <IconCheckCircle size={18} /> },
  { to: '/accountant', label: 'AI Accountant', icon: <IconCalculator size={18} /> },
  { to: '/customers', label: 'Customers', icon: <IconUsers size={18} /> },
  { to: '/forecast', label: 'Revenue Forecast', icon: <IconSparkles size={18} /> },
];

export default function Sidebar() {
  return (
    <aside className="hidden md:flex w-[260px] flex-shrink-0 bg-white border-r border-slate-200 min-h-screen flex-col justify-between select-none">
      <div>
        {/* Brand Header */}
        <div className="p-5 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#002970] flex items-center justify-center font-black text-white shadow-sm">
              <span className="text-[#00baf2] text-base">₹</span>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-sm tracking-tight text-[#002970]">Paytm</span>
                <span className="font-bold text-sm text-[#00baf2]">MerchantMind</span>
              </div>
              <p className="text-[10px] font-semibold text-slate-400 tracking-wider uppercase mt-0.5">
                AI Business Copilot
              </p>
            </div>
          </div>
        </div>

        {/* Merchant Store Profile Card */}
        <div className="p-3 mx-3 my-3 bg-slate-50 border border-slate-200/80 rounded-xl text-xs">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-100 text-[#002970] flex items-center justify-center flex-shrink-0">
              <IconStore size={16} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-slate-800 truncate text-xs">Sharma Sweets & Bakers</p>
              <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                <span>Jaipur Outlet</span>
                <span>•</span>
                <span className="text-emerald-600 font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="px-3 py-1 space-y-1">
          <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Menu
          </div>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs transition-all duration-150 ${
                  isActive
                    ? 'bg-sky-50 border border-sky-200 shadow-sm'
                    : 'hover:bg-slate-100/80 border border-transparent'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className="flex items-center gap-3">
                    <span className={isActive ? 'text-[#002970]' : 'text-slate-400'}>
                      {item.icon}
                    </span>
                    <span className={isActive ? 'text-[#002970] font-bold' : 'text-slate-600 font-medium'}>
                      {item.label}
                    </span>
                  </div>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${
                        isActive
                          ? 'bg-sky-100 text-[#002970] border border-sky-200'
                          : 'bg-indigo-50 text-indigo-600 border border-indigo-200/60'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      {/* Footer Info & Settings */}
      <div className="p-4 border-t border-slate-100 bg-slate-50/60 text-xs space-y-3">
        <div className="flex items-center justify-between text-slate-500 text-[11px]">
          <div className="flex items-center gap-1.5">
            <IconSliders size={14} className="text-slate-400" />
            <span>Store Settings</span>
          </div>
          <span className="font-mono text-[10px] text-slate-400">v1.2</span>
        </div>
        <div className="flex items-center gap-2 pt-2 border-t border-slate-200/60 text-[10px] text-slate-400">
          <span className="w-2 h-2 rounded-full bg-[#00baf2]" />
          <span>Paytm AI Partner • Build for India</span>
        </div>
      </div>
    </aside>
  );
}
