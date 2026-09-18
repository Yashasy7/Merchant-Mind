# Paytm MerchantMind — Frontend API Contract

> **Target Audience:** Frontend Team (Vishal / UI Developers)  
> **Backend Service:** FastAPI on `http://127.0.0.1:8000`  
> **API Version:** v1 (`/api/v1/*` with backwards-compatible `/api/*` unversioned aliases)  
> **Synthetic Demo Mode:** Active (`is_demo_data: true`, synthetic disclosures on financial actions)  

---

## 1. General Architectural & Protocol Rules

### 1.1 Base URLs & CORS
* **Development Backend URL:** `http://127.0.0.1:8000`
* **CORS Policy:** Allowed origins include:
  * `http://localhost:5173`
  * `http://127.0.0.1:5173`
  * `http://localhost:3000`
  * `http://127.0.0.1:3000`
* **Headers:** `Content-Type: application/json` on all POST/PATCH/PUT requests.

### 1.2 Multi-Tenant Merchant Isolation
Every analytical and transactional request **requires** `merchant_id`.
* For **GET** requests: Pass as query parameter: `?merchant_id=demo-merchant-001`.
* For **POST/PATCH** requests: Pass inside request JSON body `{"merchant_id": "demo-merchant-001", ...}` (and/or query parameter where supported).
* **Default Demo Merchant ID:** `"demo-merchant-001"` (Pre-seeded with 90 days of transactions, customer segments, expenses, and invoices).
* **Unknown Merchant Behavior:**
  * Analytical aggregate queries (sales summary, forecast summary) return safe zero metrics (HTTP 200).
  * Specific resource lookups (customer by ID, campaign by ID) return `HTTP 404 Not Found`.

### 1.3 Standard Response & Error Formats
Successful responses return HTTP 200 (or HTTP 201 for resource creation).  
HTTP 4xx/5xx responses return standard FastAPI `{"detail": "string or object"}` envelopes:
* `400 Bad Request`: Invalid parameter value or business rule violation (e.g., negative expense amount, invalid date format).
* `404 Not Found`: Merchant, campaign, or customer resource does not exist.
* `409 Conflict`: Illegal campaign lifecycle transition (e.g., executing a campaign in `PENDING_APPROVAL` status without approval, or approving an already approved campaign).
* `422 Unprocessable Entity`: Pydantic schema validation error (e.g., missing required fields, horizon exceeding maximum bounds).

---

## 2. Screen-by-Screen API Mapping

### Screen 1: Dashboard Overview / Executive Summary
Combines top-level revenue, customer counts, business health, and active growth levers.

#### 1. Sales KPI Summary
* **Endpoint:** `GET /api/v1/sales/summary?merchant_id=demo-merchant-001`
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "total_revenue": 1690173.23,
  "total_transactions": 2934,
  "average_transaction_value": 576.06,
  "minimum_transaction_value": 15.0,
  "maximum_transaction_value": 4890.0,
  "successful_transactions": 2934,
  "failed_transactions": 0,
  "success_rate": 100.0,
  "start_date": "2026-06-20",
  "end_date": "2026-09-18"
}
```

#### 2. Composite Business Health Card
* **Endpoint:** `GET /api/v1/business-health?merchant_id=demo-merchant-001`
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "overall_score": 78.4,
  "overall_status": "stable",
  "dimensions": [
    {
      "dimension_name": "revenue_trend",
      "score": 75.0,
      "status": "good",
      "metric_summary": "Revenue trajectory is stable.",
      "details": { "revenue_change_percentage": 4.2 }
    },
    {
      "dimension_name": "customer_retention",
      "score": 71.4,
      "status": "good",
      "metric_summary": "Healthy repeat customer ratio.",
      "details": { "repeat_customer_rate": 65.0 }
    },
    {
      "dimension_name": "profitability",
      "score": 95.0,
      "status": "excellent",
      "metric_summary": "Net profit margin is 60.79%.",
      "details": { "operating_margin_pct": 60.79 }
    },
    {
      "dimension_name": "operational_risk",
      "score": 76.0,
      "status": "good",
      "metric_summary": "Stable overhead costs.",
      "details": { "overhead_ratio": 22.0 }
    },
    {
      "dimension_name": "growth_readiness",
      "score": 75.5,
      "status": "good",
      "metric_summary": "Strong upside potential from weekend campaigns.",
      "details": { "growth_levers_count": 3 }
    }
  ],
  "risks": [
    {
      "risk_id": "risk-001",
      "category": "operational",
      "severity": "high",
      "title": "Inventory Expense Surge",
      "description": "Inventory expense is 201% above 90-day baseline.",
      "metric_evidence": "INR 359,287.31 vs baseline",
      "suggested_action": "Audit vendor contracts."
    }
  ],
  "opportunities": [
    {
      "opportunity_id": "opp-001",
      "category": "weekend_lift",
      "potential_impact": "high",
      "title": "Weekend Sales Campaign",
      "description": "Incentivize weekend shopping to boost revenue.",
      "metric_evidence": "Weekend sales lag by 28%",
      "recommendation_id": "rec-demo-mer-weekend-boost"
    }
  ],
  "disclaimer": "Business health indicators and risk signals are derived deterministically from historical records."
}
```

#### 3. Top Growth Opportunities Carousel
* **Endpoint:** `GET /api/v1/growth/recommendations?merchant_id=demo-merchant-001`
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "recommendations": [
    {
      "recommendation_id": "rec-demo-mer-weekend-boost",
      "title": "Weekend Sales Surge Campaign",
      "description": "Weekend revenue drops 28% compared to peak weekdays. Incentivize weekend shopping.",
      "category": "sales_boost",
      "priority": "high",
      "confidence_score": 0.88,
      "estimated_impact_revenue": 45000.0,
      "suggested_action": {
        "scenario_type": "percentage_discount",
        "discount_percent": 10.0,
        "minimum_transaction_amount": 300.0,
        "target_segment": "All Customers"
      }
    }
  ]
}
```

---

### Screen 2: Sales Intelligence
Provides deep-dive charts into sales patterns, hourly peaks, weekday vs. weekend, and historical comparisons.

#### 1. Daily Sales Trends
* **Endpoint:** `GET /api/v1/sales/trends?merchant_id=demo-merchant-001&period_days=30`
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "trends": [
    {
      "date": "2026-09-10",
      "revenue": 18450.0,
      "transactions": 28,
      "average_ticket": 658.92
    }
  ]
}
```

#### 2. Hourly Footfall & Sales Heatmap
* **Endpoint:** `GET /api/v1/sales/hourly?merchant_id=demo-merchant-001`

#### 3. Weekend vs Weekday Performance
* **Endpoint:** `GET /api/v1/sales/weekend?merchant_id=demo-merchant-001`

#### 4. Day of Week Breakdown
* **Endpoint:** `GET /api/v1/sales/day-of-week?merchant_id=demo-merchant-001`

#### 5. Deterministic Sales Insights
* **Endpoint:** `GET /api/v1/sales/insights?merchant_id=demo-merchant-001`

---

### Screen 3: Customer Intelligence
Audience segmentation, RFM scoring, churn risk, and customer lists.

#### 1. Customer Segment Distribution
* **Endpoint:** `GET /api/v1/customers/segments?merchant_id=demo-merchant-001`
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "total_customers": 299,
  "segments": [
    { "segment": "VIP", "count": 22, "percentage": 7.36, "avg_spend": 2840.5 },
    { "segment": "Loyal", "count": 35, "percentage": 11.71, "avg_spend": 1420.0 },
    { "segment": "Regular", "count": 28, "percentage": 9.36, "avg_spend": 750.0 },
    { "segment": "At-Risk", "count": 43, "percentage": 14.38, "avg_spend": 510.0 },
    { "segment": "Inactive", "count": 126, "percentage": 42.14, "avg_spend": 320.0 }
  ]
}
```

#### 2. At-Risk Customers List
* **Endpoint:** `GET /api/v1/customers/at-risk?merchant_id=demo-merchant-001&limit=50`

#### 3. Inactive Customers List
* **Endpoint:** `GET /api/v1/customers/inactive?merchant_id=demo-merchant-001&limit=50`

#### 4. Top VIP Customers
* **Endpoint:** `GET /api/v1/customers/top?merchant_id=demo-merchant-001&limit=20`

---

### Screen 4: Growth Recommendations & What-If Simulator
Interactive predictive simulation before creating campaigns.

#### 1. Baseline Metrics
* **Endpoint:** `GET /api/v1/what-if/baseline?merchant_id=demo-merchant-001`

#### 2. Run What-If Simulation
* **Endpoint:** `POST /api/v1/what-if/simulate`
* **Request Body:**
```json
{
  "merchant_id": "demo-merchant-001",
  "recommendation_id": "rec-demo-mer-weekend-boost",
  "scenario_type": "percentage_discount",
  "discount_percent": 10.0,
  "minimum_transaction_amount": 250.0,
  "target_segment": "All Customers"
}
```
* **Response:**
```json
{
  "simulation_id": "sim-a9e1d84b",
  "merchant_id": "demo-merchant-001",
  "scenario_type": "percentage_discount",
  "projected_revenue": 1859264.0,
  "baseline_revenue": 1690240.0,
  "incremental_revenue": 169024.0,
  "projected_transactions": 2695,
  "baseline_transactions": 2450,
  "incremental_transactions": 245,
  "estimated_incentive_cost": 42256.0,
  "net_incremental_impact": 126768.0,
  "estimated_roi": 3.0,
  "confidence_interval_lower": 101414.4,
  "confidence_interval_upper": 152121.6,
  "is_viable": true
}
```

#### 3. Compare Scenarios
* **Endpoint:** `POST /api/v1/what-if/compare`

---

### Screen 5: Marketing Campaigns & Human-in-the-Loop Actions
Guaranteed safety boundary: Creation enters `PENDING_APPROVAL`. Cannot execute until explicit merchant approval.

#### 1. Create Campaign Draft
* **Endpoint:** `POST /api/v1/campaigns`
* **Request Body:**
```json
{
  "merchant_id": "demo-merchant-001",
  "name": "Weekend Sales Booster",
  "description": "10% off for weekend orders above ₹250",
  "target_segment": "All Customers",
  "offer_type": "percentage_discount",
  "discount_percent": 10.0,
  "minimum_transaction_amount": 250.0,
  "target_days": "weekend",
  "target_hours": "all",
  "source_recommendation_id": "rec-demo-mer-weekend-boost"
}
```
* **Response (HTTP 201):**
```json
{
  "campaign_id": "cmp-f7a28b9c1d3e",
  "merchant_id": "demo-merchant-001",
  "name": "Weekend Sales Booster",
  "status": "PENDING_APPROVAL",
  "projected_revenue": 1859264.0,
  "estimated_incentive_cost": 42256.0,
  "estimated_roi": 3.0,
  "created_at": "2026-09-18T20:30:00Z"
}
```

#### 2. List Campaigns
* **Endpoint:** `GET /api/v1/campaigns?merchant_id=demo-merchant-001&status=PENDING_APPROVAL`

#### 3. Get Campaign Detail
* **Endpoint:** `GET /api/v1/campaigns/{campaign_id}?merchant_id=demo-merchant-001`

#### 4. Approve Campaign (Human Merchant Decision)
* **Endpoint:** `POST /api/v1/campaigns/{campaign_id}/approve?merchant_id=demo-merchant-001`
* **Request Body (Optional):**
```json
{
  "notes": "Approved for this coming weekend launch."
}
```
* **Response (HTTP 200):** Status moves to `"APPROVED"`.

#### 5. Reject Campaign
* **Endpoint:** `POST /api/v1/campaigns/{campaign_id}/reject?merchant_id=demo-merchant-001`
* **Request Body:**
```json
{
  "reason": "Discount margin is too aggressive for this week."
}
```

#### 6. Safe Execute Campaign (Simulated Execution)
* **Endpoint:** `POST /api/v1/campaigns/{campaign_id}/execute?merchant_id=demo-merchant-001`
* **Response (HTTP 200):** Status moves to `"COMPLETED"` with simulated outcomes.
* **Error Behavior:** If called on `PENDING_APPROVAL`, returns `HTTP 409 Conflict`.

#### 7. Campaign Execution Result
* **Endpoint:** `GET /api/v1/campaigns/{campaign_id}/result?merchant_id=demo-merchant-001`

#### 8. Campaign Audit Trail
* **Endpoint:** `GET /api/v1/campaigns/{campaign_id}/audit?merchant_id=demo-merchant-001`

---

### Screen 6: AI Accountant & Bookkeeping
Automated P&L, expense tracking, invoice ledger, and anomaly detection.

#### 1. Unified Accountant Summary
* **Endpoint:** `GET /api/v1/accountant/summary?merchant_id=demo-merchant-001`

#### 2. Profit & Loss Summary
* **Endpoint:** `GET /api/v1/accountant/profit-loss?merchant_id=demo-merchant-001`
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "total_revenue": 1690173.23,
  "total_expenses": 662653.93,
  "net_profit": 1027519.30,
  "operating_margin_pct": 60.79,
  "transaction_count": 2934,
  "expense_count": 24,
  "is_profitable": true
}
```

#### 3. Operational Expenses Breakdown & Anomalies
* **Endpoint:** `GET /api/v1/accountant/expenses?merchant_id=demo-merchant-001`
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "total_expenses": 662653.93,
  "expense_count": 24,
  "top_category": "Inventory",
  "categories": [
    {
      "category": "Inventory",
      "total_amount": 359287.31,
      "percentage_of_total": 54.22,
      "expense_count": 12
    }
  ],
  "anomalies": [
    {
      "category": "Inventory",
      "current_amount": 359287.31,
      "baseline_amount": 119247.35,
      "change_percentage": 201.3,
      "is_anomaly": true,
      "message": "Inventory expenses surged by 201.3% over baseline."
    }
  ]
}
```

#### 4. Vendor Invoices Ledger
* **Endpoint:** `GET /api/v1/accountant/invoices?merchant_id=demo-merchant-001`

#### 5. Income vs Expense Trend
* **Endpoint:** `GET /api/v1/accountant/income-vs-expense?merchant_id=demo-merchant-001&months=3`

#### 6. Period-over-Period Financial Comparison
* **Endpoint:** `GET /api/v1/accountant/comparison?merchant_id=demo-merchant-001&current_days=30`

#### 7. Financial Insights
* **Endpoint:** `GET /api/v1/accountant/insights?merchant_id=demo-merchant-001`

---

### Screen 7: Forecasting & Business Health
Rolling statistical projections and 5-dimension diagnostic radar.

#### 1. Revenue Forecast Summary
* **Endpoint:** `GET /api/v1/forecast/summary?merchant_id=demo-merchant-001&horizon_days=14`

#### 2. Sales Revenue Forecast Timeline
* **Endpoint:** `GET /api/v1/forecast/sales?merchant_id=demo-merchant-001&horizon_days=14` *(or `days=14`)*
* **Response:**
```json
{
  "merchant_id": "demo-merchant-001",
  "historical_period_days": 28,
  "forecast_horizon_days": 14,
  "historical_revenue": 1025400.0,
  "projected_revenue": 263400.0,
  "lower_bound": 237060.0,
  "upper_bound": 289740.0,
  "trend_direction": "stable",
  "trend_factor_pct": 0.0,
  "forecast_method": "4-week rolling average with 2-week trend factor & day-of-week seasonality",
  "is_sufficient_data": true,
  "daily_points": [
    {
      "date": "2026-09-19",
      "amount": 21500.0,
      "lower_bound": 19350.0,
      "upper_bound": 23650.0,
      "is_forecast": true
    }
  ],
  "disclaimer": "Prototype estimate based on synthetic demo data only. Projections are statistical indications and do not guarantee actual future revenue or business performance."
}
```

#### 3. Business Health Evaluation & Radar
* **Endpoint:** `GET /api/v1/business-health?merchant_id=demo-merchant-001`

#### 4. Business Health Risks List
* **Endpoint:** `GET /api/v1/business-health/risks?merchant_id=demo-merchant-001`

#### 5. Business Health Growth Opportunities List
* **Endpoint:** `GET /api/v1/business-health/opportunities?merchant_id=demo-merchant-001`

---

### Screen 8: AI Copilot Chat
Interactive multimodal chat with natural language intent classification, grounded tool invocation, and human-in-the-loop safety.

#### 1. Send Chat Message
* **Endpoint:** `POST /api/v1/agent/chat`
* **Request Body:**
```json
{
  "merchant_id": "demo-merchant-001",
  "message": "My sales have dropped. Help me increase weekend revenue."
}
```
* **Response:**
```json
{
  "message": "I analyzed your sales trends and customer segments. Weekend revenue has dropped by 28%. I have drafted a Weekend Booster campaign offering 10% discount for orders over ₹250. It is currently PENDING your approval.",
  "intent": {
    "intent": "increase_weekend_revenue",
    "objective": "increase_revenue",
    "target_segment": "All Customers",
    "time_window": "weekend",
    "requested_action": "campaign"
  },
  "actions_taken": [
    {
      "tool_name": "analyze_sales",
      "status": "success"
    },
    {
      "tool_name": "create_campaign",
      "status": "success",
      "campaign_id": "cmp-7754c22bbf89",
      "campaign_status": "PENDING_APPROVAL"
    }
  ],
  "approval_required": true,
  "disclaimer": "This is a simulated AI assistant for demonstration purposes. Synthetic data used."
}
```

#### 2. Query Intent Directly
* **Endpoint:** `POST /api/v1/agent/intent`
* **Request Body:** `{"message": "How much profit did I make?"}`

#### 3. Agent Tool Catalog
* **Endpoint:** `GET /api/v1/agent/tools`

---

## 3. Quick Frontend Integration Snippets (TypeScript / Axios)

```typescript
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api/v1';
const MERCHANT_ID = 'demo-merchant-001';

// 1. Fetch Executive Dashboard
export async function getDashboardData() {
  const [sales, health, growth, pnl] = await Promise.all([
    axios.get(`${API_BASE}/sales/summary`, { params: { merchant_id: MERCHANT_ID } }),
    axios.get(`${API_BASE}/business-health`, { params: { merchant_id: MERCHANT_ID } }),
    axios.get(`${API_BASE}/growth/recommendations`, { params: { merchant_id: MERCHANT_ID } }),
    axios.get(`${API_BASE}/accountant/profit-loss`, { params: { merchant_id: MERCHANT_ID } }),
  ]);
  return {
    sales: sales.data,
    health: health.data,
    growth: growth.data,
    pnl: pnl.data
  };
}

// 2. Chat with AI Copilot
export async function sendCopilotMessage(userMessage: string) {
  const response = await axios.post(`${API_BASE}/agent/chat`, {
    merchant_id: MERCHANT_ID,
    message: userMessage
  });
  return response.data;
}

// 3. Approve a Campaign Draft
export async function approveCampaign(campaignId: string, notes?: string) {
  const response = await axios.post(`${API_BASE}/campaigns/${campaignId}/approve`, 
    { notes },
    { params: { merchant_id: MERCHANT_ID } }
  );
  return response.data;
}

// 4. Safe Simulated Execution
export async function executeCampaign(campaignId: string) {
  const response = await axios.post(`${API_BASE}/campaigns/${campaignId}/execute`,
    {},
    { params: { merchant_id: MERCHANT_ID } }
  );
  return response.data;
}
```
