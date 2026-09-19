/**
 * Centralized API client — Paytm MerchantMind
 *
 * Architecture (blueprint §15 §17):
 *   - All API calls go through this module.
 *   - Uses the standard Fetch API (no Axios dependency).
 *   - When VITE_API_URL is set and backend is live, live calls are made.
 *   - When backend is unavailable (empty / dev phase), MOCK_MODE=true falls back
 *     to typed mock fixtures that match blueprint §14 response shapes exactly.
 *   - Mock data is isolated here — replacing with live calls requires only
 *     setting VITE_API_URL and removing the mock guard.
 *
 * IMPORTANT: Frontend never calculates financial metrics.
 *   All revenue, profit, ROI, margins come from mock fixtures or the live API.
 *   React only formats and displays these values.
 *
 * Blueprint §14 — Standard response format:
 * { success: true, data: T, meta: { merchant_id, data_type: "SYNTHETIC_DEMO", generated_at } }
 */

import type {
  ApiResponse,
  DashboardData,
  SalesSummary,
  SalesTrendsData,
  DeclineAnalysis,
  CustomerSegmentsData,
  AtRiskData,
  CopilotChatRequest,
  CopilotChatResponse,
  GrowthAnalysis,
  GrowthRecommendation,
  SimulateRequest,
  SimulationResult,
  CampaignApproveRequest,
  CampaignApprovalData,
  CampaignResult,
  ProfitLossData,
  ExpenseData,
  RevenueForecast,
} from '../types';

// ── Config ────────────────────────────────────────────────────────────────

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const DEMO_MERCHANT_ID = 'demo-merchant-001';

/**
 * MOCK_MODE: true while backend is not yet available.
 * Set to false (or remove guard) when Yashas's backend is running.
 */
const MOCK_MODE = true;

// ── Mock meta helper ──────────────────────────────────────────────────────

function mockMeta() {
  return {
    merchant_id: DEMO_MERCHANT_ID,
    data_type: 'SYNTHETIC_DEMO' as const,
    generated_at: new Date().toISOString(),
  };
}

// ── Simulated network delay for realistic UX testing ─────────────────────

function delay(ms = 600): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Core Fetch wrapper ────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }

  return res.json() as Promise<ApiResponse<T>>;
}

// ═══════════════════════════════════════════════════════════════════════════
// MOCK FIXTURES
// All values are SYNTHETIC DEMO DATA sourced from blueprint §8 (hero workflow
// demo numbers) and §13 (synthetic data strategy).
// React displays these values — it does NOT calculate them.
// ═══════════════════════════════════════════════════════════════════════════

const MOCK_DASHBOARD: ApiResponse<DashboardData> = {
  success: true,
  data: {
    kpis: {
      revenue_today: 17500,
      revenue_this_week: 87500,
      revenue_this_month: 500000,
      transaction_count_today: 80,
      transaction_count_week: 520,
      avg_transaction_value: 375,
      repeat_customer_rate: 68,
      estimated_profit: 115000,   // backend-calculated: revenue − expenses
      estimated_margin: 23,       // backend-calculated
      growth_score: 62,
    },
    insights: [
      {
        id: 'ins-001',
        type: 'alert',
        severity: 'high',
        icon: '📉',
        title: 'Sales declining 16% vs last 2 weeks',
        body: 'Evening hours (6–9 PM) show the steepest drop. 126 inactive customers not seen in 45+ days.',
      },
      {
        id: 'ins-002',
        type: 'recommendation',
        severity: 'medium',
        icon: '💡',
        title: 'Growth opportunity identified',
        body: 'Reactivating at-risk + inactive customers with a targeted evening offer could uplift revenue.',
      },
      {
        id: 'ins-003',
        type: 'forecast',
        severity: 'low',
        icon: '📈',
        title: 'Weekend mornings remain strong',
        body: 'Saturday and Sunday mornings continue to perform above baseline. 67 loyal customers are active.',
      },
    ],
    quick_actions: [
      { label: 'Ask MerchantMind', route: '/copilot' },
      { label: 'View Growth Plan', route: '/growth' },
      { label: 'Check Finances', route: '/accountant' },
    ],
  },
  meta: mockMeta(),
};

const MOCK_SALES_SUMMARY: ApiResponse<SalesSummary> = {
  success: true,
  data: {
    period_days: 14,
    total_revenue: 175000,
    total_transactions: 980,
    avg_transaction_value: 178.6,
    revenue_change_pct: -16,
    transaction_change_pct: -13,
    peak_hour: 12,
    peak_day: 'Saturday',
  },
  meta: mockMeta(),
};

// 14 days of daily revenue — blueprint §13 decay pattern (weeks 11–12 decline)
const MOCK_SALES_TRENDS: ApiResponse<SalesTrendsData> = {
  success: true,
  data: {
    daily: [
      { date: '2024-01-01', revenue: 18200, transaction_count: 82 },
      { date: '2024-01-02', revenue: 17800, transaction_count: 79 },
      { date: '2024-01-03', revenue: 21000, transaction_count: 95 }, // weekend
      { date: '2024-01-04', revenue: 19500, transaction_count: 88 }, // weekend
      { date: '2024-01-05', revenue: 16800, transaction_count: 74 },
      { date: '2024-01-06', revenue: 15200, transaction_count: 67 }, // decline begins
      { date: '2024-01-07', revenue: 14900, transaction_count: 65 },
      { date: '2024-01-08', revenue: 14200, transaction_count: 62 },
      { date: '2024-01-09', revenue: 13800, transaction_count: 60 },
      { date: '2024-01-10', revenue: 20100, transaction_count: 91 }, // weekend
      { date: '2024-01-11', revenue: 18900, transaction_count: 85 }, // weekend
      { date: '2024-01-12', revenue: 12500, transaction_count: 55 }, // steeper
      { date: '2024-01-13', revenue: 11800, transaction_count: 52 },
      { date: '2024-01-14', revenue: 17500, transaction_count: 80 }, // today
    ],
    hourly: [
      { hour: 8,  transaction_count: 45, revenue: 16875 },
      { hour: 9,  transaction_count: 62, revenue: 23250 },
      { hour: 10, transaction_count: 78, revenue: 29250 },
      { hour: 11, transaction_count: 95, revenue: 35625 },
      { hour: 12, transaction_count: 112, revenue: 42000 }, // peak
      { hour: 13, transaction_count: 88,  revenue: 33000 },
      { hour: 14, transaction_count: 72,  revenue: 27000 },
      { hour: 15, transaction_count: 65,  revenue: 24375 },
      { hour: 16, transaction_count: 58,  revenue: 21750 },
      { hour: 17, transaction_count: 55,  revenue: 20625 },
      { hour: 18, transaction_count: 38,  revenue: 14250 }, // decline zone
      { hour: 19, transaction_count: 29,  revenue: 10875 }, // worst
      { hour: 20, transaction_count: 25,  revenue: 9375  }, // worst
      { hour: 21, transaction_count: 18,  revenue: 6750  },
    ],
  },
  meta: mockMeta(),
};

const MOCK_DECLINE_ANALYSIS: ApiResponse<DeclineAnalysis> = {
  success: true,
  data: {
    has_decline: true,
    overall_decline_pct: 16,
    worst_period_label: '6 PM – 9 PM weekdays',
    worst_period_decline_pct: 31,
    affected_days: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
    diagnosis:
      'Sales have declined 16% compared to the prior 2-week period. The steepest drop (31%) is in weekday evenings between 6–9 PM, suggesting a specific time-window problem rather than an overall business issue.',
  },
  meta: mockMeta(),
};

const MOCK_CUSTOMER_SEGMENTS: ApiResponse<CustomerSegmentsData> = {
  success: true,
  data: {
    total_customers: 299,
    segments: [
      { segment: 'VIP',      count: 18,  total_revenue: 95400, avg_spend: 5300, pct_of_total: 6  },
      { segment: 'Loyal',    count: 67,  total_revenue: 134000, avg_spend: 2000, pct_of_total: 22 },
      { segment: 'New',      count: 45,  total_revenue: 22500, avg_spend: 500,  pct_of_total: 15 },
      { segment: 'At-Risk',  count: 43,  total_revenue: 43000, avg_spend: 1000, pct_of_total: 14 },
      { segment: 'Inactive', count: 126, total_revenue: 63000, avg_spend: 500,  pct_of_total: 42 },
    ],
  },
  meta: mockMeta(),
};

const MOCK_AT_RISK: ApiResponse<AtRiskData> = {
  success: true,
  data: {
    at_risk_count: 43,
    inactive_count: 126,
    customers: [
      { customer_id: 'cust-001', segment: 'Inactive', days_since_last_transaction: 62, transaction_count: 8,  total_spend: 6200,  avg_transaction: 775 },
      { customer_id: 'cust-002', segment: 'Inactive', days_since_last_transaction: 55, transaction_count: 5,  total_spend: 3500,  avg_transaction: 700 },
      { customer_id: 'cust-003', segment: 'At-Risk',  days_since_last_transaction: 38, transaction_count: 12, total_spend: 9600,  avg_transaction: 800 },
      { customer_id: 'cust-004', segment: 'Inactive', days_since_last_transaction: 71, transaction_count: 3,  total_spend: 1800,  avg_transaction: 600 },
      { customer_id: 'cust-005', segment: 'At-Risk',  days_since_last_transaction: 25, transaction_count: 7,  total_spend: 4900,  avg_transaction: 700 },
      { customer_id: 'cust-006', segment: 'Inactive', days_since_last_transaction: 48, transaction_count: 4,  total_spend: 2400,  avg_transaction: 600 },
      { customer_id: 'cust-007', segment: 'At-Risk',  days_since_last_transaction: 30, transaction_count: 9,  total_spend: 7200,  avg_transaction: 800 },
      { customer_id: 'cust-008', segment: 'Inactive', days_since_last_transaction: 90, transaction_count: 6,  total_spend: 3600,  avg_transaction: 600 },
    ],
  },
  meta: mockMeta(),
};

const MOCK_GROWTH_ANALYSIS: ApiResponse<GrowthAnalysis> = {
  success: true,
  data: {
    diagnosis: 'A 16% revenue decline is concentrated in weekday evenings (6–9 PM). This is not a general business downturn — it is a time-specific drop.',
    opportunity: 'Reactivating 126 inactive + 43 at-risk customers with a targeted evening incentive can recover this lost revenue window.',
    decline_data: MOCK_DECLINE_ANALYSIS.data,
    customer_data: MOCK_CUSTOMER_SEGMENTS.data,
  },
  meta: mockMeta(),
};

const MOCK_RECOMMENDATION: ApiResponse<GrowthRecommendation> = {
  success: true,
  data: {
    id: 'rec-001',
    diagnosis: 'Sales declined 16% overall; evenings 6–9 PM show 31% drop. 126 inactive customers absent 45+ days.',
    opportunity: 'Evening reactivation campaign targeting inactive + at-risk segment.',
    target_segment: 'Inactive',
    target_count: 169, // 126 inactive + 43 at-risk
    offer_type: 'cashback',
    offer_label: '₹50 cashback on ₹300+ transactions',
    offer_value: 50,
    min_transaction: 300,
    timing: '6 PM – 9 PM, weekdays',
    reasoning:
      'Evening hours (6–9 PM) show the steepest 31% decline vs prior period. Your 126 inactive customers last transacted 45+ days ago — this is the optimal reactivation window. A ₹50 cashback on ₹300+ spend provides strong incentive while maintaining margin.',
    expected_impact: '+18–24% evening revenue uplift (illustrative projection)',
    expected_revenue_uplift_pct: 21,
    created_at: new Date().toISOString(),
  },
  meta: mockMeta(),
};

// Blueprint §6 Module 06 — What-if simulation table (exact demo numbers)
const MOCK_SIMULATION: ApiResponse<SimulationResult> = {
  success: true,
  data: {
    recommended_strategy_id: 'strat-cashback-50',
    strategies: [
      {
        strategy_id: 'strat-baseline',
        label: 'No Offer (Baseline)',
        is_recommended: false,
        offer_type: 'none',
        offer_value: 0,
        expected_transactions: 45,
        expected_revenue: 18000,
        incentive_cost: 0,
        incremental_revenue: 0,
        estimated_roi: 0,
      },
      {
        strategy_id: 'strat-discount-5',
        label: '5% Discount',
        is_recommended: false,
        offer_type: 'discount',
        offer_value: 5,
        expected_transactions: 58,
        expected_revenue: 22040,
        incentive_cost: 1102,
        incremental_revenue: 2938,
        estimated_roi: 2.7,
      },
      {
        strategy_id: 'strat-discount-10',
        label: '10% Discount',
        is_recommended: false,
        offer_type: 'discount',
        offer_value: 10,
        expected_transactions: 65,
        expected_revenue: 23400,
        incentive_cost: 2600,
        incremental_revenue: 2800,
        estimated_roi: 2.1,
      },
      {
        strategy_id: 'strat-cashback-50',
        label: '₹50 Cashback (Recommended)',
        is_recommended: true,
        offer_type: 'cashback',
        offer_value: 50,
        expected_transactions: 72,
        expected_revenue: 28800,
        incentive_cost: 3600,
        incremental_revenue: 7200,
        estimated_roi: 3.0,
      },
    ],
  },
  meta: mockMeta(),
};

const MOCK_CAMPAIGN_APPROVAL: ApiResponse<CampaignApprovalData> = {
  success: true,
  data: {
    campaign_id: 'camp-001',
    status: 'active',
    target_segment: 'Inactive + At-Risk',
    offer_label: '₹50 cashback on ₹300+ transactions',
    timing: '6 PM – 9 PM, weekdays',
    estimated_cost: 3600,
    expected_impact: 'Projected +21% evening revenue uplift (illustrative)',
  },
  meta: mockMeta(),
};

const MOCK_CAMPAIGN_RESULT: ApiResponse<CampaignResult> = {
  success: true,
  data: {
    campaign_id: 'camp-001',
    status: 'active',
    offer_label: '₹50 cashback on ₹300+ transactions',
    target_segment: 'Inactive + At-Risk',
    timing: '6 PM – 9 PM, weekdays',
    actual_transactions: 72,
    actual_revenue: 28800,
    incentive_cost: 3600,
    incremental_revenue: 7200,
    actual_roi: 3.0,
    projected_transactions: 72,
    projected_revenue: 28800,
    created_at: new Date().toISOString(),
    performance_vs_projection_pct: 0,
  },
  meta: mockMeta(),
};

// Blueprint §6 Module 09 — Demo P&L (Synthetic)
const MOCK_PROFIT_LOSS: ApiResponse<ProfitLossData> = {
  success: true,
  data: {
    month: '2024-01',
    total_revenue: 500000,
    total_expenses: 385000,
    operating_profit: 115000,
    operating_margin_pct: 23,
    ai_explanation:
      'This month your estimated operating profit is ₹1,15,000 on ₹5,00,000 revenue — a 23% margin. Your largest expense is inventory at ₹1,20,000. I also noticed your electricity bill is 15% higher than last month, which may be worth investigating. Note: these are estimates based on your transaction and expense records.',
  },
  meta: mockMeta(),
};

const MOCK_EXPENSES: ApiResponse<ExpenseData> = {
  success: true,
  data: {
    month: '2024-01',
    total_expenses: 385000,
    largest_category: 'Inventory',
    anomaly_summary: 'Electricity costs are 15% higher than the prior month average.',
    categories: [
      { category: 'Inventory',    amount: 120000, pct_of_total: 31.2, vs_prior_month_pct: 2,   is_anomaly: false },
      { category: 'Salaries',     amount: 95000,  pct_of_total: 24.7, vs_prior_month_pct: 0,   is_anomaly: false },
      { category: 'Rent',         amount: 45000,  pct_of_total: 11.7, vs_prior_month_pct: 0,   is_anomaly: false },
      { category: 'Electricity',  amount: 28750,  pct_of_total: 7.5,  vs_prior_month_pct: 15,  is_anomaly: true,  anomaly_note: '+15% vs prior month average. Consider reviewing usage.' },
      { category: 'Marketing',    amount: 22000,  pct_of_total: 5.7,  vs_prior_month_pct: -5,  is_anomaly: false },
      { category: 'Packaging',    amount: 18500,  pct_of_total: 4.8,  vs_prior_month_pct: 3,   is_anomaly: false },
      { category: 'Maintenance',  amount: 15000,  pct_of_total: 3.9,  vs_prior_month_pct: 0,   is_anomaly: false },
      { category: 'Other',        amount: 40750,  pct_of_total: 10.6, vs_prior_month_pct: 1,   is_anomaly: false },
    ],
  },
  meta: mockMeta(),
};

const MOCK_FORECAST: ApiResponse<RevenueForecast> = {
  success: true,
  data: {
    horizon_months: 1,
    lower_bound: 210000,
    central_estimate: 220000,
    upper_bound: 230000,
    trend_direction: 'flat',
    forecast_basis: '4-week rolling average with trend factor',
    ai_explanation:
      'Based on your last 4 weeks of sales data, I project next month\'s revenue in the range of ₹2.1L – ₹2.3L. The recent evening decline is factored in. If the recommended campaign succeeds, the upper end of this range is more likely.',
  },
  meta: mockMeta(),
};

// Copilot mock — returns a canned hero-query response
const MOCK_COPILOT_RESPONSE: ApiResponse<CopilotChatResponse> = {
  success: true,
  data: {
    message:
      'I\'ve analyzed Sharma General Store\'s last 14 days of transaction data. Here\'s what I found:\n\n**Sales Decline Detected:** Your revenue is down **16%** compared to the prior 2-week period. The biggest drop is in weekday evenings — between 6 PM and 9 PM, you\'re seeing a **31% decline**.\n\n**Customer Insight:** You have **126 inactive customers** who haven\'t visited in over 45 days, and **43 at-risk customers** who are close to becoming inactive.\n\n**My Recommendation:** A targeted ₹50 cashback offer on ₹300+ transactions, running 6–9 PM on weekdays, could reactivate these customers during your weakest window. Projected uplift: +18–24% evening revenue.\n\nWould you like to see the What-if Simulator to compare strategies?',
    conversation_id: 'conv-001',
    intent_detected: 'growth_recommendation',
    structured_data: {
      type: 'recommendation',
      payload: MOCK_RECOMMENDATION.data,
    },
  },
  meta: mockMeta(),
};

// ═══════════════════════════════════════════════════════════════════════════
// API FUNCTIONS — each returns ApiResponse<T>
// In MOCK_MODE: returns mock fixtures after a simulated delay.
// In live mode: hits the real FastAPI backend.
// ═══════════════════════════════════════════════════════════════════════════

export async function getDashboard(): Promise<ApiResponse<DashboardData>> {
  if (MOCK_MODE) { await delay(500); return MOCK_DASHBOARD; }
  return apiFetch('/api/dashboard');
}

export async function getSalesSummary(days = 14): Promise<ApiResponse<SalesSummary>> {
  if (MOCK_MODE) { await delay(400); return MOCK_SALES_SUMMARY; }
  return apiFetch(`/api/sales/summary?days=${days}`);
}

export async function getSalesTrends(days = 14): Promise<ApiResponse<SalesTrendsData>> {
  if (MOCK_MODE) { await delay(400); return MOCK_SALES_TRENDS; }
  return apiFetch(`/api/sales/trends?days=${days}`);
}

export async function getDeclineAnalysis(): Promise<ApiResponse<DeclineAnalysis>> {
  if (MOCK_MODE) { await delay(600); return MOCK_DECLINE_ANALYSIS; }
  return apiFetch('/api/sales/decline-analysis');
}

export async function getCustomerSegments(): Promise<ApiResponse<CustomerSegmentsData>> {
  if (MOCK_MODE) { await delay(400); return MOCK_CUSTOMER_SEGMENTS; }
  return apiFetch('/api/customers/segments');
}

export async function getAtRiskCustomers(): Promise<ApiResponse<AtRiskData>> {
  if (MOCK_MODE) { await delay(500); return MOCK_AT_RISK; }
  return apiFetch('/api/customers/at-risk');
}

export async function postCopilotChat(
  req: CopilotChatRequest
): Promise<ApiResponse<CopilotChatResponse>> {
  if (MOCK_MODE) {
    await delay(1800); // simulate LLM latency
    return {
      ...MOCK_COPILOT_RESPONSE,
      data: { ...MOCK_COPILOT_RESPONSE.data, conversation_id: req.conversation_id ?? 'conv-001' },
    };
  }
  return apiFetch('/api/copilot/chat', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function postGrowthAnalyze(): Promise<ApiResponse<GrowthAnalysis>> {
  if (MOCK_MODE) { await delay(700); return MOCK_GROWTH_ANALYSIS; }
  return apiFetch('/api/growth/analyze', { method: 'POST', body: JSON.stringify({}) });
}

export async function postGrowthRecommend(): Promise<ApiResponse<GrowthRecommendation>> {
  if (MOCK_MODE) { await delay(900); return MOCK_RECOMMENDATION; }
  return apiFetch('/api/growth/recommend', { method: 'POST', body: JSON.stringify({}) });
}

export async function postCampaignSimulate(
  req: SimulateRequest
): Promise<ApiResponse<SimulationResult>> {
  if (MOCK_MODE) { await delay(600); return MOCK_SIMULATION; }
  return apiFetch('/api/campaign/simulate', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function postCampaignApprove(
  req: CampaignApproveRequest
): Promise<ApiResponse<CampaignApprovalData>> {
  if (MOCK_MODE) { await delay(800); return MOCK_CAMPAIGN_APPROVAL; }
  return apiFetch('/api/campaign/approve', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function getCampaignResult(
  campaignId: string
): Promise<ApiResponse<CampaignResult>> {
  if (MOCK_MODE) { await delay(500); return MOCK_CAMPAIGN_RESULT; }
  return apiFetch(`/api/campaigns/${campaignId}`);
}

export async function getProfitLoss(month?: string): Promise<ApiResponse<ProfitLossData>> {
  if (MOCK_MODE) { await delay(500); return MOCK_PROFIT_LOSS; }
  const q = month ? `?month=${month}` : '';
  return apiFetch(`/api/accounting/profit-loss${q}`);
}

export async function getExpenses(month?: string): Promise<ApiResponse<ExpenseData>> {
  if (MOCK_MODE) { await delay(500); return MOCK_EXPENSES; }
  const q = month ? `?month=${month}` : '';
  return apiFetch(`/api/accounting/expenses${q}`);
}

export async function getRevenueForecast(): Promise<ApiResponse<RevenueForecast>> {
  if (MOCK_MODE) { await delay(600); return MOCK_FORECAST; }
  return apiFetch('/api/forecast/revenue');
}

// ── Formatting helpers (display only, no business logic) ─────────────────

/** Format a number as Indian Rupees: ₹1,23,456 */
export function formatRupees(amount: number): string {
  return '₹' + amount.toLocaleString('en-IN');
}

/** Format a number as a compact value: ₹5L, ₹1.2K */
export function formatRupeesCompact(amount: number): string {
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`;
  if (amount >= 1000)   return `₹${(amount / 1000).toFixed(1)}K`;
  return `₹${amount}`;
}

/** Format a percentage with sign: +16%, -5% */
export function formatPct(value: number, showSign = true): string {
  const sign = showSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}
