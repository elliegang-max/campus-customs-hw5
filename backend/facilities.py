"""Facilities — the lease, the landlord, and the rent."""

from __future__ import annotations

from .base import build_agent
from .models import RentAssessment

facilities_agent = build_agent("facilities", RentAssessment, name="facilities")
