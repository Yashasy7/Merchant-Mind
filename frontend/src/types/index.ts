/**
 * TypeScript types for Paytm MerchantMind frontend.
 *
 * All interfaces are derived from the blueprint.html API design (Section 14)
 * and backend Pydantic schemas (Section 16). These types must stay in sync
 * with what Yashas's FastAPI backend returns.
 *
 * Standard response envelope (Section 14):
 * { success: boolean; data: T; meta: ResponseMeta }
 *
 * IMPORTANT: Do NOT add calculated financial fields here.
 * All business metrics come from the backend.
 */

// ── Standard API envelope ──────────────────────────────────────────────────

export interface ResponseMeta {
  merchant_id: string;
  /** MANDATORY: always "SYNTHETIC_DEMO" for demo builds */
  data_type: 'SYNTHETIC_DEMO';
  generated_at: string; // ISO timestamp
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta: ResponseMeta;
}

// ── Dashboard (GET /api/dashboard) ─────────────────────────────────────────

export interface KpiSummary {
  revenue_today: number;       // INR
  revenue_this_week: number;   // INR
  revenue_this_month: number;  // INR
  transaction_count_today: number;
  transaction_count_week: number;
  avg_transaction_value: number; // INR
  repeat_customer_rate: number;  // 0–100 percent
  estimated_profit: number;      // INR — backend-calculated
  estimated_margin: number;      // 0–100 percent — backend-calculated
  growth_score: number;          // 0–100
}

export interface AiInsightCard {
  id: string;
  type: 'alert' | 'recommendation' | 'forecast';
  title: string;
  body: string;
  severity: 'high' | 'medium' | 'low';
  icon: string; // emoji or icon key
}

export interface QuickAction {
  label: string;
  route: string;
}

export interface DashboardData {
  kpis: KpiSummary;
  insights: AiInsightCard[];
  quick_actions: QuickAction[];
}

// ── Sales (GET /api/sales/summary + /api/sales/trends) ────────────────────

export interface SalesSummary {
  period_days: number;
  total_revenue: number;       // INR
  total_transactions: number;
  avg_transaction_value: number; // INR
  revenue_change_pct: number;    // vs prior period, e.g. -16.0
  transaction_change_pct: number;
  peak_hour: number;             // 0–23
  peak_day: string;              // e.g. "Saturday"
}

export interface DailyRevenueTrend {
  date: string; // ISO date string YYYY-MM-DD
  revenue: number;
  transaction_count: number;
}

export interface HourlyBucket {
  hour: number;        // 0–23
  transaction_count: number;
  revenue: number;
}

export interface SalesTrendsData {
  daily: DailyRevenueTrend[];
  hourly: HourlyBucket[];
}

// ── Sales Decline Analysis (GET /api/sales/decline-analysis) ──────────────

export interface DeclineAnalysis {
  has_decline: boolean;
  overall_decline_pct: number;    // e.g. 16.0
  worst_period_label: string;     // e.g. "6 PM – 9 PM weekdays"
  worst_period_decline_pct: number; // e.g. 31.0
  affected_days: string[];         // e.g. ["Monday", "Tuesday"]
  diagnosis: string;               // human-readable summary
}

// ── Customer Segments (GET /api/customers/segments) ───────────────────────

export interface CustomerSegmentCount {
  segment: 'VIP' | 'Loyal' | 'New' | 'At-Risk' | 'Inactive';
  count: number;
  total_revenue: number;  // INR — backend-calculated
  avg_spend: number;      // INR — backend-calculated
  pct_of_total: number;   // 0–100
}

export interface CustomerSegmentsData {
  total_customers: number;
  segments: CustomerSegmentCount[];
}

// ── At-Risk Customers (GET /api/customers/at-risk) ────────────────────────

export interface AtRiskCustomer {
  customer_id: string;
  segment: 'At-Risk' | 'Inactive';
  days_since_last_transaction: number;
  transaction_count: number;
  total_spend: number;     // INR
  avg_transaction: number; // INR
}

export interface AtRiskData {
  at_risk_count: number;
  inactive_count: number;
  customers: AtRiskCustomer[];
}

// ── Copilot (POST /api/copilot/chat) ──────────────────────────────────────

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string; // ISO
  structured_data?: CopilotStructuredData;
}

export interface CopilotChatRequest {
  message: string;
  conversation_id?: string;
}

export type CopilotStructuredData =
  | { type: 'sales_analysis'; payload: DeclineAnalysis }
  | { type: 'recommendation'; payload: GrowthRecommendation }
  | { type: 'profit_loss'; payload: ProfitLossData }
  | { type: 'customer_segments'; payload: CustomerSegmentsData };

export interface CopilotChatResponse {
  message: string;       // LLM narrative
  conversation_id: string;
  structured_data?: CopilotStructuredData;
  intent_detected?: string;
}

// ── Growth (POST /api/growth/analyze + /api/growth/recommend) ─────────────

export interface GrowthAnalysis {
  diagnosis: string;
  opportunity: string;
  decline_data: DeclineAnalysis;
  customer_data: CustomerSegmentsData;
}

export interface GrowthRecommendation {
  id: string;
  diagnosis: string;
  opportunity: string;
  target_segment: 'At-Risk' | 'Inactive' | 'VIP' | 'Loyal' | 'New';
  target_count: number;
  offer_type: 'cashback' | 'discount' | 'free_item';
  offer_label: string;   // e.g. "₹50 cashback on ₹300+ transactions"
  offer_value: number;   // INR
  min_transaction: number; // INR
  timing: string;          // e.g. "6 PM – 9 PM, weekdays"
  reasoning: string;       // LLM explanation — does NOT contain invented numbers
  expected_impact: string; // e.g. "+18–24% evening revenue uplift"
  /** All expected_* are illustrative backend estimates, not guarantees */
  expected_revenue_uplift_pct: number;
  created_at: string;
}

// ── Campaign Simulation (POST /api/campaign/simulate) ─────────────────────

export interface SimulationStrategy {
  strategy_id: string;
  label: string;          // e.g. "₹50 Cashback (Recommended)"
  is_recommended: boolean;
  offer_type: string;
  offer_value: number;
  expected_transactions: number;
  expected_revenue: number;     // INR
  incentive_cost: number;       // INR
  incremental_revenue: number;  // INR — backend-calculated
  estimated_roi: number;        // multiplier, e.g. 3.0 — backend-calculated
}

export interface SimulateRequest {
  recommendation_id: string;
}

export interface SimulationResult {
  strategies: SimulationStrategy[];
  recommended_strategy_id: string;
}

// ── Campaign Approval (POST /api/campaign/approve) ─────────────────────────

export interface CampaignApproveRequest {
  recommendation_id: string;
  strategy_id: string;
}

export interface CampaignApprovalData {
  campaign_id: string;
  status: 'active' | 'pending' | 'completed' | 'rejected';
  target_segment: string;
  offer_label: string;
  timing: string;
  estimated_cost: number;      // INR — backend-calculated
  expected_impact: string;
}

// ── Campaign Result (GET /api/campaigns/{id}) ─────────────────────────────

export interface CampaignResult {
  campaign_id: string;
  status: 'active' | 'completed' | 'pending';
  offer_label: string;
  target_segment: string;
  timing: string;
  actual_transactions: number;
  actual_revenue: number;       // INR
  incentive_cost: number;       // INR
  incremental_revenue: number;  // INR — backend-calculated
  actual_roi: number;           // backend-calculated
  projected_transactions: number;
  projected_revenue: number;
  created_at: string;
  completed_at?: string;
  /** Feedback loop: comparison vs projection */
  performance_vs_projection_pct: number; // backend-calculated, e.g. +5.2
}

// ── AI Accountant (GET /api/accounting/profit-loss + /accounting/expenses) ─

export interface ProfitLossData {
  month: string; // e.g. "2024-01"
  total_revenue: number;         // INR — backend-calculated
  total_expenses: number;        // INR — backend-calculated
  operating_profit: number;      // INR — backend-calculated
  operating_margin_pct: number;  // 0–100 — backend-calculated
  ai_explanation: string;        // LLM narrative
}

export interface ExpenseCategory {
  category: string;   // e.g. "Inventory", "Rent", "Electricity"
  amount: number;     // INR
  pct_of_total: number; // 0–100
  vs_prior_month_pct: number; // e.g. +15 means 15% increase
  is_anomaly: boolean;
  anomaly_note?: string;
}

export interface ExpenseData {
  month: string;
  categories: ExpenseCategory[];
  total_expenses: number; // INR — backend-calculated
  largest_category: string;
  anomaly_summary?: string;
}

// ── Revenue Forecast (GET /api/forecast/revenue) ── P3 / simplified ───────

export interface RevenueForecast {
  horizon_months: number;
  lower_bound: number;  // INR
  central_estimate: number; // INR
  upper_bound: number;  // INR
  trend_direction: 'up' | 'flat' | 'down';
  ai_explanation: string;
  forecast_basis: string; // e.g. "4-week rolling average"
}

// ── UI State helpers ───────────────────────────────────────────────────────

export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

export interface ApiError {
  message: string;
  code?: number;
}
