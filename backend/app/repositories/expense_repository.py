"""
Expense repository for database operations and fallback data access.
Supports both SQLAlchemy PostgreSQL queries and in-memory fallback JSON loading.
Provides data access for operational expenses and vendor invoices.
"""

import os
import json
from typing import Optional, List, Dict, Any
from datetime import date
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import logger
from app.repositories.base import BaseRepository
from app.models.expense import Expense
from app.models.invoice import Invoice

settings = get_settings()
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXPENSES_FALLBACK_FILE = os.path.join(BACKEND_DIR, "data", "fallback", "expenses.json")
INVOICES_FALLBACK_FILE = os.path.join(BACKEND_DIR, "data", "fallback", "invoices.json")


class ExpenseRepository(BaseRepository[Expense]):
    """Repository handling expense and invoice querying with fallback data support."""

    def __init__(self, db: Session):
        super().__init__(Expense, db)

    def _load_fallback_expenses(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Load expenses from fallback JSON files when database is in memory mode or unavailable."""
        if not os.path.exists(EXPENSES_FALLBACK_FILE):
            logger.warning(f"Fallback expense file not found at: {EXPENSES_FALLBACK_FILE}")
            return []

        try:
            with open(EXPENSES_FALLBACK_FILE, "r", encoding="utf-8") as f:
                data: List[Dict[str, Any]] = json.load(f)

            filtered = []
            for item in data:
                if item.get("merchant_id") != merchant_id:
                    continue

                if category and item.get("category", "").lower() != category.lower():
                    continue

                d_str = item.get("date")
                if d_str:
                    try:
                        exp_date = date.fromisoformat(d_str)
                        if start_date and exp_date < start_date:
                            continue
                        if end_date and exp_date > end_date:
                            continue
                    except Exception:
                        pass

                filtered.append(item)

            return filtered
        except Exception as exc:
            logger.error(f"Error reading fallback expenses: {exc}")
            return []

    def _load_fallback_invoices(
        self,
        merchant_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Load invoices from fallback JSON files."""
        if not os.path.exists(INVOICES_FALLBACK_FILE):
            logger.warning(f"Fallback invoice file not found at: {INVOICES_FALLBACK_FILE}")
            return []

        try:
            with open(INVOICES_FALLBACK_FILE, "r", encoding="utf-8") as f:
                data: List[Dict[str, Any]] = json.load(f)

            filtered = []
            for item in data:
                if item.get("merchant_id") != merchant_id:
                    continue

                if status and item.get("status", "").lower() != status.lower():
                    continue

                filtered.append(item)

            return filtered
        except Exception as exc:
            logger.error(f"Error reading fallback invoices: {exc}")
            return []

    def get_expenses_df(
        self,
        merchant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Retrieve expenses as a structured Pandas DataFrame.
        Queries database first, falling back to JSON dataset if needed.
        """
        rows: List[Dict[str, Any]] = []

        if settings.data_mode != "memory":
            try:
                conditions = [Expense.merchant_id == merchant_id]
                if start_date:
                    conditions.append(Expense.date >= start_date)
                if end_date:
                    conditions.append(Expense.date <= end_date)
                if category:
                    conditions.append(Expense.category == category)

                stmt = select(Expense).where(and_(*conditions)).order_by(Expense.date.asc())
                results = self.db.scalars(stmt).all()

                for exp in results:
                    rows.append({
                        "expense_id": exp.expense_id,
                        "merchant_id": exp.merchant_id,
                        "date": exp.date,
                        "category": exp.category,
                        "amount": float(exp.amount),
                        "vendor": exp.vendor,
                        "notes": exp.notes,
                    })
            except SQLAlchemyError as err:
                logger.warning(f"Database query failed for expenses, checking fallback dataset: {err}")
                rows = []

        # If no database records found, load fallback dataset
        if not rows:
            fallback_records = self._load_fallback_expenses(
                merchant_id=merchant_id,
                start_date=start_date,
                end_date=end_date,
                category=category,
            )
            for item in fallback_records:
                d_val = item.get("date")
                parsed_date = date.fromisoformat(d_val) if isinstance(d_val, str) else d_val
                rows.append({
                    "expense_id": item.get("expense_id"),
                    "merchant_id": item.get("merchant_id"),
                    "date": parsed_date,
                    "category": item.get("category"),
                    "amount": float(item.get("amount", 0.0)),
                    "vendor": item.get("vendor"),
                    "notes": item.get("notes"),
                })

        if not rows:
            return pd.DataFrame(columns=[
                "expense_id", "merchant_id", "date", "category", "amount", "vendor", "notes"
            ])

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        return df

    def get_invoices(
        self,
        merchant_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve invoices for a merchant.
        Queries database first, falling back to JSON dataset if needed.
        """
        rows: List[Dict[str, Any]] = []

        if settings.data_mode != "memory":
            try:
                conditions = [Invoice.merchant_id == merchant_id]
                if status:
                    conditions.append(Invoice.status == status)

                stmt = select(Invoice).where(and_(*conditions)).order_by(Invoice.date.desc())
                results = self.db.scalars(stmt).all()

                for inv in results:
                    rows.append({
                        "invoice_id": inv.invoice_id,
                        "merchant_id": inv.merchant_id,
                        "vendor": inv.vendor,
                        "amount": float(inv.amount),
                        "date": inv.date.isoformat() if inv.date else None,
                        "due_date": inv.due_date.isoformat() if inv.due_date else None,
                        "status": inv.status,
                    })
            except SQLAlchemyError as err:
                logger.warning(f"Database query failed for invoices, checking fallback: {err}")
                rows = []

        if not rows:
            fallback_records = self._load_fallback_invoices(merchant_id=merchant_id, status=status)
            for item in fallback_records:
                rows.append({
                    "invoice_id": item.get("invoice_id"),
                    "merchant_id": item.get("merchant_id"),
                    "vendor": item.get("vendor"),
                    "amount": float(item.get("amount", 0.0)),
                    "date": item.get("date"),
                    "due_date": item.get("due_date"),
                    "status": item.get("status"),
                })

        return rows
