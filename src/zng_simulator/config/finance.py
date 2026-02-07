"""Financial configuration — Phase 3 debt & valuation inputs."""

from typing import Literal

from pydantic import BaseModel, Field


class FinanceConfig(BaseModel):
    """Debt structure, depreciation, tax, and terminal-value assumptions.

    These inputs drive the DCF engine, debt schedule, DSCR calculation,
    and financial statement generation.  All fields have sensible defaults
    so that Phase 1/2 code never breaks.
    """

    # --- Debt structure ---
    debt_pct_of_capex: float = Field(
        default=0.70, ge=0, le=1.0,
        description="Portion of initial CapEx funded by debt (0–1). "
                    "0 = all equity, 1 = fully leveraged.",
    )
    interest_rate_annual: float = Field(
        default=0.12, ge=0, le=0.50,
        description="Annual interest rate on debt.",
    )
    loan_tenor_months: int = Field(
        default=60, ge=1, le=360,
        description="Loan repayment period in months.",
    )
    grace_period_months: int = Field(
        default=6, ge=0,
        description="Interest-only period before principal repayment starts.",
    )

    # --- Depreciation ---
    depreciation_method: Literal["straight_line", "wdv"] = Field(
        default="straight_line",
        description="Depreciation method. straight_line = equal monthly; "
                    "wdv = Written Down Value (declining balance).",
    )
    asset_useful_life_months: int = Field(
        default=60, ge=1, le=360,
        description="Accounting useful life of battery + charger assets.",
    )
    wdv_rate_annual: float = Field(
        default=0.25, ge=0, le=1.0,
        description="Annual WDV depreciation rate (only used if method='wdv').",
    )

    # --- Tax ---
    tax_rate: float = Field(
        default=0.25, ge=0, le=0.60,
        description="Corporate tax rate for after-tax DCF.",
    )

    # --- Terminal value ---
    terminal_value_method: Literal["salvage", "gordon_growth", "none"] = Field(
        default="salvage",
        description="How to value the business at horizon end. "
                    "'salvage' = sum of battery 2nd-life + charger residual; "
                    "'gordon_growth' = perpetuity model; 'none' = zero.",
    )
    terminal_growth_rate: float = Field(
        default=0.02, ge=0, le=0.10,
        description="For Gordon growth model: g in NCF×(1+g)/(r−g). "
                    "Ignored if terminal_value_method != 'gordon_growth'.",
    )

    # --- DSCR covenant ---
    dscr_covenant_threshold: float = Field(
        default=1.20, ge=0,
        description="Minimum DSCR for SLB covenant compliance. "
                    "Months below this are flagged as breaches.",
    )
