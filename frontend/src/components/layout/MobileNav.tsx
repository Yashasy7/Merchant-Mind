import { NavLink } from 'react-router-dom';
import {
  IconDashboard,
  IconBot,
  IconTrendingUp,
  IconCalculator,
  IconUsers,
} from '../shared/Icons';

export default function MobileNav() {
  const navItems = [
    { to: '/', label: 'Home', icon: <IconDashboard size={20} /> },
    { to: '/copilot', label: 'AI Copilot', icon: <IconBot size={20} /> },
    { to: '/growth', label: 'Growth', icon: <IconTrendingUp size={20} /> },
    { to: '/accountant', label: 'Finance', icon: <IconCalculator size={20} /> },
    { to: '/customers', label: 'Customers', icon: <IconUsers size={20} /> },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200 px-2 py-1.5 flex items-center justify-around shadow-lg">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            `flex flex-col items-center justify-center py-1 px-3 rounded-lg text-[11px] font-medium transition-all ${
              isActive
                ? 'text-paytmNavy font-bold'
                : 'text-slate-500 hover:text-slate-800'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <div
                className={`p-1 rounded-full transition-colors ${
                  isActive ? 'bg-sky-50 text-paytmNavy' : 'text-slate-500'
                }`}
              >
                {item.icon}
              </div>
              <span className="mt-0.5">{item.label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
