"""
Transaction repository for database operations and fallback data access.
Supports both SQLAlchemy PostgreSQL queries and in-memory fallback JSON loading.
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import logger
from app.repositories.base import BaseRepository
from app.models.transaction import Transaction

settings = get_settings()
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FALLBACK_FILE = os.path.join(BACKEND_DIR, "data", "fallback", "transactions.json")


class TransactionRepository(BaseRepository[Transaction]):
    """Repository handling transaction querying with fallback data support."""

    def __init__(self, db: Session):
        super().__init__(Transaction, db)

    def _load_fallback_data(
        self,
        merchant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load transactions from fallback JSON files when database is in memory mode or unavailable."""
        if not os.path.exists(FALLBACK_FILE):
            logger.warning(f"Fallback transaction file not found at: {FALLBACK_FILE}")
            return []

        try:
            with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
                data: List[Dict[str, Any]] = json.load(f)

            filtered = []
            for item in data:
                if item.get("merchant_id") != merchant_id:
                    continue

                if status and item.get("status") != status:
                    continue

                ts_str = item.get("timestamp")
                if ts_str:
                    try:
                        tx_time = datetime.fromisoformat(ts_str)
                        if tx_time.tzinfo is None:
                            tx_time = tx_time.replace(tzinfo=timezone.utc)

                        if start_date:
                            s_date = start_date if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)
                            if tx_time < s_date:
                                continue

                        if end_date:
                            e_date = end_date if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)
                            if tx_time > e_date:
                                continue
                    except Exception:
                        pass

                filtered.append(item)

            return filtered
        except Exception as exc:
            logger.error(f"Error reading fallback transactions: {exc}")
            return []

    def get_transactions_df(
        self,
        merchant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Retrieve transactions as a structured Pandas DataFrame.
        Queries database first, falling back to JSON dataset if needed.
        """
        rows: List[Dict[str, Any]] = []

        if settings.data_mode != "memory":
            try:
                conditions = [Transaction.merchant_id == merchant_id]
                if start_date:
                    conditions.append(Transaction.timestamp >= start_date)
                if end_date:
                    conditions.append(Transaction.timestamp <= end_date)
                if status:
                    conditions.append(Transaction.status == status)

                stmt = select(Transaction).where(and_(*conditions)).order_by(Transaction.timestamp.asc())
                results = self.db.scalars(stmt).all()

                for tx in results:
                    rows.append({
                        "transaction_id": tx.transaction_id,
                        "merchant_id": tx.merchant_id,
                        "customer_id": tx.customer_id,
                        "timestamp": tx.timestamp,
                        "amount": float(tx.amount),
                        "payment_method": tx.payment_method,
                        "status": tx.status
                    })
            except SQLAlchemyError as err:
                logger.warning(f"Database query failed, checking fallback dataset: {err}")
                rows = []

        # Use fallback if DB returned 0 records or is in memory mode
        if not rows:
            fallback_records = self._load_fallback_data(
                merchant_id=merchant_id,
                start_date=start_date,
                end_date=end_date,
                status=status
            )
            for r in fallback_records:
                rows.append({
                    "transaction_id": r.get("transaction_id"),
                    "merchant_id": r.get("merchant_id"),
                    "customer_id": r.get("customer_id"),
                    "timestamp": r.get("timestamp"),
                    "amount": float(r.get("amount", 0.0)),
                    "payment_method": r.get("payment_method", "UPI"),
                    "status": r.get("status", "success")
                })

        if not rows:
            return pd.DataFrame(columns=[
                "transaction_id", "merchant_id", "customer_id", "timestamp",
                "amount", "payment_method", "status", "date", "day_name", "day_index", "hour"
            ])

        df = pd.DataFrame(rows)
        # Parse timestamp safely
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["date"] = df["timestamp"].dt.date
        df["day_name"] = df["timestamp"].dt.day_name()
        df["day_index"] = df["timestamp"].dt.dayofweek  # 0=Monday, 6=Sunday
        df["hour"] = df["timestamp"].dt.hour
        df["amount"] = df["amount"].astype(float)

        return df
