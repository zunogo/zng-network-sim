"""Shared display formatters for the dashboard and report modules."""

from __future__ import annotations


def fmt_inr(val: float) -> str:
    """Format INR with lakhs / crores for large values."""
    if abs(val) >= 1e7:
        return f"₹{val / 1e7:,.2f} Cr"
    if abs(val) >= 1e5:
        return f"₹{val / 1e5:,.2f} L"
    return f"₹{val:,.0f}"
