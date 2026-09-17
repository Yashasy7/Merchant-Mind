# Paytm MerchantMind — Backend Service

> **Hackathon:** Paytm Build for India AI Hackathon — Bengaluru Edition  
> **Track:** Merchant Growth AI  
> **Backend Developer:** Yashas H L  
> **Concept:** The AI Business Partner for Every Merchant

---

### Mandatory Synthetic Data Disclosure

**All data used and presented by this application is synthetic demonstration data generated programmatically.**  
It does **not** access, store, or represent real Paytm merchant or customer data. All metrics, transaction records, and simulations are calibrated for demonstration purposes only.

---

## 1. Overview

This service provides the backend foundation for **Paytm MerchantMind**, an AI-powered business partner designed to help merchants understand their sales, customers, and finances — recommending growth opportunities and turning approved recommendations into actions.

### Core Architectural Flow
```text
MERCHANT GOAL
      ↓
AI ORCHESTRATOR
      ↓
ANALYTICS / CUSTOMER / GROWTH / ACCOUNTANT CAPABILITIES
      ↓
DATA-BACKED RECOMMENDATION
      ↓
MERCHANT APPROVAL (Human-in-the-Loop)
      ↓
SIMULATED ACTION EXECUTION
      ↓
MEASUREMENT & LEARNING
```

---

## 2. Technology Stack

* **Language:** Python 3.11+
* **Framework:** FastAPI
* **Server:** Uvicorn (ASGI)
* **ORM:** SQLAlchemy 2.x (Modern typed models with Mapped & mapped_column)
* **Database:** PostgreSQL (with SQLite fallback for isolated testing and local development)
* **Data Validation & Settings:** Pydantic v2 & Pydantic-Settings
* **Data Processing:** Pandas, NumPy
* **Testing:** Pytest, HTTPX

---

## 3. Directory Layout

```text
backend/
├── app/
│   ├── main.py                     # FastAPI application entry, CORS, lifespan, exception handlers
│   ├── core/
│   │   ├── config.py               # Pydantic Settings and environment variable management
│   │   ├── database.py             # SQLAlchemy engine, session maker, get_db dependency, health check
│   │   └── logging.py              # Application logging configuration
│   ├── models/
│   │   ├── base.py                 # TimestampMixin and Base definition
│   │   ├── merchant.py             # Merchant profile model
│   │   ├── customer.py             # Customer profile & segmentation model
│   │   ├── transaction.py          # Payment & sales transaction model
│   │   ├── expense.py              # Operational expense model
│   │   ├── invoice.py              # Vendor invoice model
│   │   └── campaign.py             # Marketing & re-engagement campaign model
│   ├── schemas/
│   │   ├── health.py               # Health check response schemas
│   │   ├── common.py               # Unified APIResponse and ErrorResponse envelopes
│   │   ├── merchant.py             # Merchant DTOs
│   │   └── customer.py             # Customer & Transaction DTOs
│   ├── repositories/
│   │   └── base.py                 # Generic CRUD repository pattern
│   ├── services/
│   │   └── base.py                 # Base service interface
│   ├── api/
│   │   ├── router.py               # Centralized API router for all modular endpoints
│   │   └── v1/
│   │       └── health.py           # GET /api/health endpoint
│   └── utils/                      # Helper utilities
├── data/
│   └── fallback/                   # Pre-generated fallback JSON datasets (for offline/memory mode)
├── scripts/
│   └── generate_synthetic_data.py  # Deterministic synthetic data generator (seed=42)
├── tests/
│   ├── conftest.py                 # In-memory SQLite fixtures and TestClient isolation
│   ├── test_config.py              # Configuration loading tests
│   ├── test_database.py            # Database connection and session tests
│   ├── test_health.py              # Health check and root endpoint tests
│   ├── test_models.py              # SQLAlchemy model persistence & relationship tests
│   └── test_synthetic_data.py      # Synthetic generator pattern validation tests
├── .env.example                    # Environment variable template
├── requirements.txt                # Foundation dependencies
└── README.md                       # Documentation
```

---

## 4. Setup & Running Locally

### Prerequisites
* Python 3.11+
* PostgreSQL 15+ (or Docker, or use SQLite fallback for quick testing)

### Step 1: Create and Activate Virtual Environment
```bash
cd backend
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update `DATABASE_URL` with your PostgreSQL credentials:
```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/merchantmind
```
*(Optional: For testing without PostgreSQL, set `DATABASE_URL=sqlite:///./merchantmind.db`)*

### Step 4: Generate Synthetic Demo Data (Optional / Seeding)
To generate fresh fallback JSON files:
```bash
python scripts/generate_synthetic_data.py
```
To seed directly into the configured database:
```bash
python scripts/generate_synthetic_data.py --db
```

### Step 5: Start the Backend Server
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

* **Interactive API Documentation (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc Documentation:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
* **Health Check Endpoint:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 5. Running Tests

The test suite uses an in-memory SQLite database (`sqlite:///:memory:`) with complete dependency isolation, so tests run immediately without requiring external PostgreSQL services:
```bash
pytest -v
```

---

## 6. Sales Intelligence (Module 2)

### Purpose
The Sales Intelligence layer processes raw merchant transaction history into deterministic business metrics and machine-readable observations. It forms the analytical foundation for the MerchantMind intelligence loop:
```text
MERCHANT QUESTION → SALES INTELLIGENCE → DETECT PATTERNS/DECLINE → IDENTIFY OPPORTUNITY → (FUTURE RECOMMENDATIONS)
```

### Supported Analysis
1. **Sales Summary:** Total revenue, transactions, average/min/max transaction value, success/failed rates.
2. **Daily Sales Trends:** Calendar-day aggregated chronological time-series of revenue and transactions.
3. **Period Comparison:** Current vs. previous equivalent period with absolute and percentage change calculations.
4. **Decline Detection:** Detection of contraction thresholds with volume vs. basket-size root-cause diagnosis.
5. **Day-of-Week Breakdown:** Sales volume and revenue shares across Monday–Sunday; strongest and slowest days.
6. **Hourly & Time Windows:** Hourly (0–23) distribution and operational windows (Morning, Afternoon, Evening, Night).
7. **Weekday vs. Weekend Analysis:** Weekend revenue share, daily average comparisons, and underperformance gap ratios.
8. **Deterministic Insights:** Rule-based, mathematical observations without LLM hallucinations.

### Endpoint Reference
All endpoints are available under `/api/v1/sales/*`:
* `GET /api/v1/sales/summary` — Aggregate sales KPIs (revenue, volume, ATV, success rate).
* `GET /api/v1/sales/trends` — Daily time series for charts.
* `GET /api/v1/sales/comparison` — Period-over-period comparison (default 14 days).
* `GET /api/v1/sales/day-of-week` — Performance across Monday through Sunday.
* `GET /api/v1/sales/hourly` — Hourly (0–23) breakdown and 4 operational windows.
* `GET /api/v1/sales/weekend` — Weekday vs weekend metrics and performance ratio.
* `GET /api/v1/sales/insights` — Structured deterministic observations.

Query Parameters supported: `merchant_id` (defaults to `demo-merchant-001`), `start_date` (YYYY-MM-DD), `end_date` (YYYY-MM-DD), `current_days` (default 14).

### Example Request & Response
```bash
# Get sales summary for demo merchant
curl http://127.0.0.1:8000/api/v1/sales/summary
```
```json
{
  "merchant_id": "demo-merchant-001",
  "total_revenue": 1690173.23,
  "total_transactions": 2934,
  "average_transaction_value": 588.71,
  "minimum_transaction_value": 50.08,
  "maximum_transaction_value": 3196.81,
  "successful_transactions": 2871,
  "failed_transactions": 63,
  "success_rate": 97.85,
  "start_date": "2026-06-20",
  "end_date": "2026-09-17"
}
```

### Deterministic Insight Generation
Insights are generated using deterministic mathematical rules:
* **Severity Thresholds:** Critical (drop $\ge 20\%$), Warning (drop $\ge 10\%$), Moderate (drop $\ge 5\%$), Positive (growth $\ge 10\%$).
* **Driver Attribution:** Compares transaction volume change % against average basket size change % to classify decline as `volume_driven` (footfall decline), `basket_driven` (lower ticket sizes), or `volume_and_basket_driven`.
* **Zero-Hallucination:** 100% grounded in transactional calculations; no stochastic models or generative AI used in the metrics calculation layer.

---

## 7. Customer Intelligence (Module 3)

### Purpose
The Customer Intelligence layer transforms merchant transaction and customer records into actionable, customer-level business intelligence. It deterministically classifies shoppers into behavioral cohorts, measures retention, ranks top contributors, flags churn risk, and generates rule-based observations to guide merchant growth without requiring any LLM.

```text
CUSTOMER HISTORY → RFM COMPUTATION → BEHAVIORAL SEGMENTATION → RISK & LOYALTY SIGNALS → (FUTURE CAMPAIGNS)
```

### Deterministic RFM Methodology
RFM scoring evaluates each customer on a deterministic 1 to 5 scale based on successful transactions relative to an analysis reference date:

* **Recency (R Score):** Days since the customer's most recent successful transaction.
  * Score 5: $\le 7$ days
  * Score 4: $8 - 14$ days
  * Score 3: $15 - 30$ days
  * Score 2: $31 - 60$ days
  * Score 1: $> 60$ days
* **Frequency (F Score):** Total count of successful transactions.
  * Score 5: $\ge 15$ orders
  * Score 4: $8 - 14$ orders
  * Score 3: $4 - 7$ orders
  * Score 2: $2 - 3$ orders
  * Score 1: $1$ order
* **Monetary (M Score):** Cumulative lifetime spend in INR across successful transactions.
  * Score 5: $\ge ₹10,000$
  * Score 4: $₹5,000 - ₹9,999$
  * Score 3: $₹2,000 - ₹4,999$
  * Score 2: $₹500 - ₹1,999$
  * Score 1: $< ₹500$
* **RFM Code:** Standard 3-digit concatenated representation (e.g. `555` represents top-tier recency, frequency, and spend).

### Customer Segmentation Rules
Customers are assigned to mutually exclusive behavioral segments using deterministic criteria aligned with the project blueprint:

| Segment | Criteria | Description |
| :--- | :--- | :--- |
| **VIP** | Spend $\ge ₹12,000$, $\ge 8$ orders, Recency $\le 14$ days | Highest value shoppers with frequent visits and recent store activity. |
| **Loyal** | $\ge 5$ orders, Spend $\ge ₹5,000$, Recency $\le 21$ days | Consistent regular shoppers with strong repeat purchase habits. |
| **New** | $\le 2$ orders, Recency $\le 30$ days | Recently acquired shoppers with 1–2 visits within the past month. |
| **At-Risk** | $\ge 3$ orders, Recency $22 - 45$ days | Previously regular customers showing signs of churning. |
| **Inactive** | Recency $> 45$ days | Dormant shoppers with no store activity for more than 45 days. |

### Endpoint Reference
All endpoints are available under `/api/v1/customers/*` (with unversioned aliases at `/api/customers/*`):

* `GET /api/v1/customers/summary` — Merchant-level customer KPIs (total, active, inactive, at-risk, new, repeat customer rate, average spend, and lifetime revenue).
* `GET /api/v1/customers/segments` — Aggregate metrics and revenue distribution across behavioral segments (VIP, Loyal, New, At-Risk, Inactive).
* `GET /api/v1/customers/top` — Ranked leaderboard of top customers sorted by `revenue` (spend) or `frequency` (orders). Supports configurable `limit` (1–100).
* `GET /api/v1/customers/at-risk` — Customers absent for 22–45 days requiring win-back engagement, including risk level (`high` / `medium`) and reason.
* `GET /api/v1/customers/inactive` — Dormant customers absent for $> 45$ days, including dormancy duration and previous spending.
* `GET /api/v1/customers/insights` — Deterministic, structured insights covering revenue concentration, churn exposure, and loyalty strength.
* `GET /api/v1/customers/{customer_id}` — Individual customer profile with RFM score breakdown and recent transaction history.

### Query Parameters
| Parameter | Endpoints | Default | Description |
| :--- | :--- | :--- | :--- |
| `merchant_id` | All | `demo-merchant-001` | Merchant identifier (enforces strict data isolation) |
| `as_of_date` | `/summary` | Latest transaction date | Reference date for recency calculations (`YYYY-MM-DD`) |
| `by` | `/top` | `revenue` | Sorting criterion: `revenue` or `frequency` |
| `limit` | `/top`, `/at-risk`, `/inactive` | `10` or `50` | Maximum number of customer records to return |

### Example Request & Response
```bash
# Get customer summary for demo merchant
curl http://127.0.0.1:8000/api/v1/customers/summary
```
```json
{
  "merchant_id": "demo-merchant-001",
  "total_customers": 299,
  "active_customers": 143,
  "inactive_customers": 126,
  "at_risk_customers": 45,
  "new_customers": 45,
  "repeat_customers": 279,
  "repeat_customer_rate": 93.31,
  "average_customer_spend": 5441.6,
  "average_transactions_per_customer": 9.62,
  "total_customer_revenue": 1627038.31
}
```

```bash
# Get single customer profile with RFM scoring
curl http://127.0.0.1:8000/api/v1/customers/cust-001-0001
```
```json
{
  "customer_id": "cust-001-0001",
  "merchant_id": "demo-merchant-001",
  "name": "Deepa Sharma",
  "phone": "+91 9846913810",
  "total_spend": 14901.74,
  "transaction_count": 22,
  "average_transaction_value": 677.35,
  "first_transaction_date": "2026-05-06T18:47:52.124157+00:00",
  "last_transaction_date": "2026-09-16T07:47:52.124157+00:00",
  "days_since_last_transaction": 1,
  "segment": "VIP",
  "rfm": {
    "recency_days": 1,
    "frequency": 22,
    "monetary": 14901.74,
    "r_score": 5,
    "f_score": 5,
    "m_score": 5,
    "rfm_code": "555"
  },
  "recent_transactions": [
    {
      "transaction_id": "tx-001-2856",
      "timestamp": "2026-09-16T07:47:52.124157+00:00",
      "amount": 745.5,
      "payment_method": "UPI",
      "status": "success"
    }
  ]
}
```

### Business Rules & Safeguards
1. **Success-Only Transactions:** Only transactions with `status == "success"` contribute to monetary spend and frequency metrics. Failed payments are excluded.
2. **Strict Merchant Isolation:** All queries filter on `merchant_id`. Attempting to retrieve another merchant's customer ID returns HTTP 404.
3. **Deterministic Recency:** When `as_of_date` is omitted, recency is anchored to the latest recorded transaction date in the dataset, ensuring stable metrics.
4. **NaN & Infinity Sanitization:** All floating-point figures are sanitized and rounded to 2 decimal places. Zero-customer stores cleanly return 0.0 without division errors.
5. **Zero-LLM Operation:** Segmentation, RFM scores, and insights are calculated entirely through deterministic mathematics and business logic.

---

## 8. Growth Recommendation Engine (Module 4)

### Purpose
The Growth Recommendation Engine deterministically combines Sales Intelligence (Module 2) and Customer Intelligence (Module 3) to identify business growth opportunities and generate prioritized, evidence-backed recommendations for the merchant.

```text
SALES INTELLIGENCE (Module 2)
              +
CUSTOMER INTELLIGENCE (Module 3)
              ↓
GROWTH OPPORTUNITY EVALUATION
              ↓
ACTIONABLE RECOMMENDATION (Module 4)
              ↓
[FUTURE: MERCHANT APPROVAL → SIMULATED EXECUTION]
```

> **Architectural Boundary:** Module 4 identifies opportunities and recommends strategic interventions. It does **not** execute campaigns, optimize discount budgets, or ask for merchant approval. Those capabilities belong to subsequent modules.

### Supported Opportunity Types

| Opportunity Type | Trigger Condition | Target Cohort | Strategic Objective | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **`sales_decline_recovery`** | 14-day sales drop $\ge 5\%$ vs. prior period | At-Risk | Recover declining revenue | High / Medium |
| **`at_risk_reengagement`** | Regulars absent for 22–45 days | At-Risk | Reactivate at-risk customers | High / Medium |
| **`inactive_winback`** | $\ge 5$ customers absent for $> 45$ days | Inactive | Reactivate dormant customers | Medium |
| **`vip_retention`** | VIP cohort generates $\ge 15\%$ of store revenue | VIP | Protect core revenue foundation | High |
| **`weekend_growth`** | Weekend daily run-rate lags weekdays | All Customers | Close weekend sales gap | High / Medium |
| **`time_of_day_opportunity`** | Slowest operational window $< 60\%$ of peak | All Customers | Increase off-peak footfall | Medium |
| **`revenue_concentration_risk`** | Top 10% of customers generate $\ge 40\%$ of revenue | Loyal | Broaden high-value customer base | Medium |

### Deterministic Priority & Confidence Scoring
* **Priority Classification:**
  * **`high`:** Immediate revenue protection or recovery (steep sales drops $\ge 15\%$, high VIP revenue exposure, substantial at-risk customer base).
  * **`medium`:** Incremental growth and operational efficiency (dormant customer reactivation, off-peak day/hour stimulation, revenue diversification).
  * **`low`:** Minor adjustments with limited short-term financial leverage.
* **Evidence Confidence:**
  * Categorized as `strong` ($0.85 - 0.95$), `moderate` ($0.70 - 0.80$), or `weak` ($< 0.70$) based strictly on underlying transaction sample size and magnitude of observed variances.
  * Zero probabilistic or stochastic hallucination.

### Endpoint Reference
Available under `/api/v1/growth/*` with unversioned aliases at `/api/growth/*`:

* `GET /api/v1/growth/recommendations` — Prioritized, evidence-backed growth recommendations. Supports optional filtering by `goal` and truncation via `limit`.
* `GET /api/v1/growth/opportunities` — Listing of all identified opportunities ranked by priority.
* `GET /api/v1/growth/summary` — Executive overview including total opportunities, revenue at risk, current sales trend, and the primary key recommendation.

### Query Parameters
| Parameter | Endpoints | Default | Description |
| :--- | :--- | :--- | :--- |
| `merchant_id` | All | `demo-merchant-001` | Merchant identifier (enforces strict data isolation) |
| `goal` | `/recommendations` | `all` | Filter by strategic intent: `revenue`, `retention`, `recovery`, `reactivation`, `weekend`, `frequency` |
| `limit` | `/recommendations`, `/opportunities` | `None` / `10` | Maximum recommendations to return (1–50) |

### Example Request & Response
```bash
# Fetch growth recommendations filtered by retention goal
curl "http://127.0.0.1:8000/api/v1/growth/recommendations?merchant_id=demo-merchant-001&goal=retention"
```
```json
{
  "merchant_id": "demo-merchant-001",
  "goal_filter": "retention",
  "total_recommendations": 2,
  "high_priority_count": 2,
  "medium_priority_count": 0,
  "low_priority_count": 0,
  "recommendations": [
    {
      "recommendation_id": "rec-demo-mer-vip-retention",
      "type": "vip_retention",
      "title": "Protect and Nurture VIP Customer Relationships",
      "description": "18 VIP customers generate 20.2% (₹328,567.74) of store revenue with an average spend of ₹18,253.76.",
      "priority": "high",
      "confidence": "strong",
      "confidence_score": 0.95,
      "target_segment": "VIP",
      "objective": "protect VIP revenue",
      "suggested_action": "Establish dedicated VIP perks, express billing, and personal previews for incoming seasonal merchandise.",
      "rationale": "VIP customers represent your core financial foundation. Losing even a single VIP materially impairs monthly profitability.",
      "estimated_scope": "18 VIP shoppers contributing ₹328,567.74",
      "evidence": [
        {
          "metric_name": "vip_revenue_percentage",
          "metric_value": 20.19,
          "baseline_value": 15.0,
          "threshold_applied": ">= 15.0% revenue share",
          "context": "Disproportionate revenue contribution"
        }
      ],
      "supporting_metrics": {
        "vip_customer_count": 18.0,
        "vip_total_revenue": 328567.74,
        "vip_revenue_share_percentage": 20.19,
        "vip_average_spend": 18253.76
      }
    }
  ]
}
```

---

## 9. Accounting & Advisory Safety Notice

MerchantMind is an AI business copilot that organizes, analyzes, and explains merchant records and data trends. It does **not** replace a Chartered Accountant (CA) or certified tax professional, nor does it file statutory returns. All financial features provide bookkeeping assistance, trend explanations, and expense anomaly detection.


