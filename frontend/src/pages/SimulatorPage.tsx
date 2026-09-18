import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  postCampaignSimulate,
  postCampaignApprove,
} from '../api';
import type { SimulationStrategy, SimulationResult } from '../types';
import WhatIfSimulator from '../components/growth/WhatIfSimulator';
import ApprovalModal from '../components/growth/ApprovalModal';
import LoadingSpinner from '../components/shared/LoadingSpinner';
import ErrorMessage from '../components/shared/ErrorMessage';
import Badge from '../components/shared/Badge';

export default function SimulatorPage() {
  const navigate = useNavigate();

  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [strategyToApprove, setStrategyToApprove] = useState<SimulationStrategy | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSimulation = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await postCampaignSimulate({ recommendation_id: 'rec-001' });
      setSimulation(res.data);
      setSelectedStrategyId(res.data.recommended_strategy_id);
    } catch (err: any) {
      setError(err?.message || 'Failed to simulate strategies');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSimulation();
  }, []);

  const handleProceedToApproval = (strategy: SimulationStrategy) => {
    setStrategyToApprove(strategy);
    setIsModalOpen(true);
  };

  const handleApprove = async () => {
    if (!strategyToApprove) return;
    setIsSubmitting(true);
    try {
      await postCampaignApprove({
        recommendation_id: 'rec-001',
        strategy_id: strategyToApprove.strategy_id,
      });
      setIsModalOpen(false);
      // Navigate to campaign result screen
      navigate('/campaigns?approved=true');
    } catch (err: any) {
      alert('Error approving campaign: ' + (err?.message || 'Network error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24">
        <LoadingSpinner label="Running what-if simulations across 4 strategy options…" size="lg" />
      </div>
    );
  }

  if (error || !simulation) {
    return (
      <div className="py-12 max-w-xl mx-auto">
        <ErrorMessage
          message={error || 'No simulation results returned'}
          onRetry={fetchSimulation}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Step Header */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-4 sm:p-5 flex flex-wrap items-center justify-between gap-3 text-xs shadow-card">
        <div className="flex items-center gap-2.5">
          <Badge variant="core">Hero Workflow • Steps 10 & 11</Badge>
          <span className="text-slate-600 font-medium">
            Comparative Scenario Modeling → Merchant Governance Review
          </span>
        </div>
        <span className="text-slate-400 font-medium">
          Deterministic Simulation Engine
        </span>
      </div>

      {/* Simulator Component */}
      <WhatIfSimulator
        strategies={simulation.strategies}
        selectedStrategyId={selectedStrategyId}
        onSelectStrategy={(id) => setSelectedStrategyId(id)}
        onProceedToApproval={handleProceedToApproval}
      />

      {/* Campaign Approval Modal */}
      {strategyToApprove && (
        <ApprovalModal
          isOpen={isModalOpen}
          strategy={strategyToApprove}
          onApprove={handleApprove}
          onReject={() => setIsModalOpen(false)}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
}
