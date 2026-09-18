import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Copilot from './pages/Copilot';
import Growth from './pages/Growth';
import SimulatorPage from './pages/SimulatorPage';
import CampaignsPage from './pages/CampaignsPage';
import Accountant from './pages/Accountant';
import Customers from './pages/Customers';
import Forecast from './pages/Forecast';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Hero & Core Screens */}
          <Route index element={<Dashboard />} />
          <Route path="dashboard" element={<Navigate to="/" replace />} />
          <Route path="copilot" element={<Copilot />} />
          <Route path="growth" element={<Growth />} />
          <Route path="simulator" element={<SimulatorPage />} />
          <Route path="campaigns" element={<CampaignsPage />} />

          {/* Additional Business Modules */}
          <Route path="accountant" element={<Accountant />} />
          <Route path="customers" element={<Customers />} />
          <Route path="forecast" element={<Forecast />} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
