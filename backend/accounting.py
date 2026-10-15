"""Accounting — cash, invoices, and payments proposed for human approval."""

from __future__ import annotations

from .base import build_agent
from .models import MoneyAssessment

accounting_agent = build_agent("accounting", MoneyAssessment, name="accounting")
