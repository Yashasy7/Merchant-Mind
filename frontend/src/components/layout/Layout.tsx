import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import MobileNav from './MobileNav';

const pageTitles: Record<string, string> = {
  '/': 'Merchant Dashboard',
  '/copilot': 'MerchantMind Copilot',
  '/growth': 'Sales & Growth Opportunities',
  '/simulator': 'What-if Campaign Simulator',
  '/campaigns': 'Campaigns & Performance',
  '/accountant': 'AI Accountant Copilot',
  '/customers': 'Customer Intelligence',
  '/forecast': 'Revenue Forecast',
};

export default function Layout() {
  const location = useLocation();
  const currentTitle = pageTitles[location.pathname] ?? 'MerchantMind';

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900 antialiased selection:bg-sky-100 selection:text-paytmNavy">
      {/* Desktop Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 pb-16 md:pb-0">
        <Topbar title={currentTitle} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>

      {/* Mobile Bottom Navigation */}
      <MobileNav />
    </div>
  );
}
