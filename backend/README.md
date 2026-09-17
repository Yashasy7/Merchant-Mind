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

## 7. Accounting & Advisory Safety Notice

MerchantMind is an AI business copilot that organizes, analyzes, and explains merchant records and data trends. It does **not** replace a Chartered Accountant (CA) or certified tax professional, nor does it file statutory returns. All financial features provide bookkeeping assistance, trend explanations, and expense anomaly detection.
