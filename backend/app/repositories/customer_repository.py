"""
Customer repository for database operations and fallback data access.
Supports both SQLAlchemy PostgreSQL queries and in-memory fallback JSON loading.
Guarantees merchant-scoped customer retrieval and data isolation.
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
from app.models.customer import Customer
from app.models.transaction import Transaction

settings = get_settings()
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CUSTOMER_FALLBACK_FILE = os.path.join(BACKEND_DIR, "data", "fallback", "customers.json")
TRANSACTION_FALLBACK_FILE = os.path.join(BACKEND_DIR, "data", "fallback", "transactions.json")


class CustomerRepository(BaseRepository[Customer]):
    """Repository handling customer data queries with fallback data support."""

    def __init__(self, db: Session):
        super().__init__(Customer, db)

    def _load_fallback_customers(
        self,
        merchant_id: str,
        segment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load customers from fallback JSON file."""
        if not os.path.exists(CUSTOMER_FALLBACK_FILE):
            logger.warning(f"Fallback customer file not found at: {CUSTOMER_FALLBACK_FILE}")
            return []

        try:
            with open(CUSTOMER_FALLBACK_FILE, "r", encoding="utf-8") as f:
                data: List[Dict[str, Any]] = json.load(f)

            filtered = []
            for item in data:
                if item.get("merchant_id") != merchant_id:
                    continue
                if segment and item.get("segment") != segment:
                    continue
                filtered.append(item)
            return filtered
        except Exception as exc:
            logger.error(f"Error reading fallback customers: {exc}")
            return []

    def _load_fallback_customer_transactions(
        self,
        customer_id: str,
        merchant_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Load transactions for a specific customer from fallback JSON file."""
        if not os.path.exists(TRANSACTION_FALLBACK_FILE):
            return []

        try:
            with open(TRANSACTION_FALLBACK_FILE, "r", encoding="utf-8") as f:
                data: List[Dict[str, Any]] = json.load(f)

            matched = []
            for tx in data:
                if tx.get("merchant_id") == merchant_id and tx.get("customer_id") == customer_id:
                    matched.append(tx)

            # Sort descending by timestamp
            matched.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return matched[:limit]
        except Exception as exc:
            logger.error(f"Error reading fallback customer transactions: {exc}")
            return []

    def get_customers_df(
        self,
        merchant_id: str,
        segment: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Retrieve customers for a merchant as a structured Pandas DataFrame.
        Queries database first, falling back to JSON dataset only on database error,
        memory mode, or unseeded database.
        """
        rows: List[Dict[str, Any]] = []
        db_succeeded = False

        if settings.data_mode != "memory":
            try:
                conditions = [Customer.merchant_id == merchant_id]
                if segment:
                    conditions.append(Customer.segment == segment)

                stmt = select(Customer).where(and_(*conditions)).order_by(Customer.total_spend.desc())
                results = self.db.scalars(stmt).all()
                db_succeeded = True

                for c in results:
                    rows.append({
                        "customer_id": c.customer_id,
                        "merchant_id": c.merchant_id,
                        "name": c.name,
                        "phone": c.phone,
                        "transaction_count": int(c.transaction_count) if c.transaction_count is not None else 0,
                        "total_spend": float(c.total_spend) if c.total_spend is not None else 0.0,
                        "average_transaction": float(c.average_transaction) if c.average_transaction is not None else 0.0,
                        "last_transaction": c.last_transaction,
                        "segment": c.segment,
                        "created_at": c.created_at,
                    })

                # If database query succeeded and returned records, or database is populated, return records
                if rows or (db_succeeded and not self._is_table_empty()):
                    if not rows:
                        return pd.DataFrame(columns=[
                            "customer_id", "merchant_id", "name", "phone",
                            "transaction_count", "total_spend", "average_transaction",
                            "last_transaction", "segment", "created_at"
                        ])
            except SQLAlchemyError as err:
                logger.warning(f"Database query failed for customers, falling back: {err}")
                rows = []

        if not rows and (settings.data_mode == "memory" or not db_succeeded or self._is_table_empty()):
            fallback_records = self._load_fallback_customers(merchant_id=merchant_id, segment=segment)
            for r in fallback_records:
                rows.append({
                    "customer_id": r.get("customer_id"),
                    "merchant_id": r.get("merchant_id"),
                    "name": r.get("name"),
                    "phone": r.get("phone"),
                    "transaction_count": int(r.get("transaction_count", 0)),
                    "total_spend": float(r.get("total_spend", 0.0)),
                    "average_transaction": float(r.get("average_transaction", 0.0)),
                    "last_transaction": r.get("last_transaction"),
                    "segment": r.get("segment", "Regular"),
                    "created_at": r.get("created_at"),
                })

        if not rows:
            return pd.DataFrame(columns=[
                "customer_id", "merchant_id", "name", "phone",
                "transaction_count", "total_spend", "average_transaction",
                "last_transaction", "segment", "created_at"
            ])

        df = pd.DataFrame(rows)
        if "last_transaction" in df.columns:
            df["last_transaction"] = pd.to_datetime(df["last_transaction"], utc=True)
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], utc=True)
        df["total_spend"] = df["total_spend"].astype(float)
        df["transaction_count"] = df["transaction_count"].astype(int)
        df["average_transaction"] = df["average_transaction"].astype(float)
        return df

    def _is_table_empty(self) -> bool:
        """Check whether the customer table has any records at all."""
        try:
            stmt = select(Customer.customer_id).limit(1)
            res = self.db.scalars(stmt).first()
            return res is None
        except Exception:
            return True

    def get_by_customer_id(self, customer_id: str, merchant_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single customer record by customer_id and merchant_id.
        Enforces strict merchant isolation.
        """
        db_succeeded = False
        if settings.data_mode != "memory":
            try:
                stmt = select(Customer).where(
                    and_(
                        Customer.customer_id == customer_id,
                        Customer.merchant_id == merchant_id
                    )
                )
                customer = self.db.scalars(stmt).first()
                db_succeeded = True
                if customer:
                    return {
                        "customer_id": customer.customer_id,
                        "merchant_id": customer.merchant_id,
                        "name": customer.name,
                        "phone": customer.phone,
                        "transaction_count": int(customer.transaction_count) if customer.transaction_count is not None else 0,
                        "total_spend": float(customer.total_spend) if customer.total_spend is not None else 0.0,
                        "average_transaction": float(customer.average_transaction) if customer.average_transaction is not None else 0.0,
                        "last_transaction": customer.last_transaction,
                        "segment": customer.segment,
                        "created_at": customer.created_at,
                    }
                # If query executed cleanly and table has records, the customer definitely does not exist
                if not self._is_table_empty():
                    return None
            except SQLAlchemyError as err:
                logger.warning(f"Database error fetching customer {customer_id}: {err}")

        # Fallback only if memory mode, DB error, or unseeded table
        if settings.data_mode == "memory" or not db_succeeded or self._is_table_empty():
            fallback_records = self._load_fallback_customers(merchant_id=merchant_id)
            for r in fallback_records:
                if r.get("customer_id") == customer_id:
                    return {
                        "customer_id": r.get("customer_id"),
                        "merchant_id": r.get("merchant_id"),
                        "name": r.get("name"),
                        "phone": r.get("phone"),
                        "transaction_count": int(r.get("transaction_count", 0)),
                        "total_spend": float(r.get("total_spend", 0.0)),
                        "average_transaction": float(r.get("average_transaction", 0.0)),
                        "last_transaction": r.get("last_transaction"),
                        "segment": r.get("segment", "Regular"),
                        "created_at": r.get("created_at"),
                    }
        return None

    def get_recent_transactions(
        self,
        customer_id: str,
        merchant_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent transactions for a customer, strictly scoped to merchant_id.
        """
        rows: List[Dict[str, Any]] = []

        if settings.data_mode != "memory":
            try:
                stmt = select(Transaction).where(
                    and_(
                        Transaction.merchant_id == merchant_id,
                        Transaction.customer_id == customer_id
                    )
                ).order_by(Transaction.timestamp.desc()).limit(limit)

                txs = self.db.scalars(stmt).all()
                for tx in txs:
                    rows.append({
                        "transaction_id": tx.transaction_id,
                        "timestamp": tx.timestamp.isoformat() if hasattr(tx.timestamp, "isoformat") else str(tx.timestamp),
                        "amount": float(tx.amount),
                        "payment_method": tx.payment_method,
                        "status": tx.status
                    })
                if rows or not self._is_table_empty():
                    return rows
            except SQLAlchemyError as err:
                logger.warning(f"Database error fetching recent transactions: {err}")
                rows = []

        # Fallback
        fallback_txs = self._load_fallback_customer_transactions(
            customer_id=customer_id,
            merchant_id=merchant_id,
            limit=limit
        )
        for tx in fallback_txs:
            rows.append({
                "transaction_id": tx.get("transaction_id"),
                "timestamp": str(tx.get("timestamp")),
                "amount": float(tx.get("amount", 0.0)),
                "payment_method": tx.get("payment_method", "UPI"),
                "status": tx.get("status", "success")
            })
        return rows
