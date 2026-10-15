"""Inventory — what is on the shelf, and what it takes to get more."""

from __future__ import annotations

from .base import build_agent
from .models import StockAssessment

inventory_agent = build_agent("inventory", StockAssessment, name="inventory")
