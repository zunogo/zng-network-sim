"""Charger NPV comparison — discounted TCO analysis (§7.3).

Re-computes charger TCO with time-value-of-money, producing:
  - NPV of charger TCO per variant
  - Discounted CPC trajectory
  - NPV-ranked comparison table
"""

from __future__ import annotations

from dataclasses import dataclass

from zng_simulator.config.charger import ChargerVariant
from zng_simulator.config.station import StationConfig
from zng_simulator.config.scenario import SimulationConfig
from zng_simulator.models.results import ChargerTCOBreakdown, DerivedParams


@dataclass(frozen=True)
class ChargerNPVResult:
    """Discounted charger TCO for one variant."""

    charger_name: str
    undiscounted_tco: float
    """Fleet-level undiscounted TCO (from Phase 1)."""

    pv_purchase: float
    """PV of purchase (month 0 → no discounting)."""

    pv_repairs: float
    """PV of repair costs spread over horizon."""

    pv_replacements: float
    """PV of replacement costs spread over horizon."""

    pv_lost_revenue: float
    """PV of lost revenue from downtime."""

    pv_spares: float
    """PV of spare inventory (month 0)."""

    npv_tco: float
    """Total NPV of charger TCO."""

    discounted_cpc: float
    """NPV_TCO / discounted_cycles_served."""

    # Monthly trajectory
    monthly_discounted_cpc: list[float]
    """Running discounted CPC at each month."""


def compute_charger_npv(
    charger: ChargerVariant,
    tco: ChargerTCOBreakdown,
    derived: DerivedParams,
    sim: SimulationConfig,
    station: StationConfig,
) -> ChargerNPVResult:
    """Compute discounted charger TCO and CPC.

    Approach:
      - Purchase cost: month 0 (no discounting)
      - Repairs/replacements: distributed uniformly across horizon, discounted monthly
      - Lost revenue: distributed uniformly, discounted
      - Spares: month 0 (no discounting)
      - Cycles served: discounted monthly for PV-weighted CPC
    """
    horizon = sim.horizon_months
    r_annual = sim.discount_rate_annual
    r_monthly = (1 + r_annual) ** (1 / 12) - 1

    # Purchase and spares are upfront (month 0)
    pv_purchase = tco.purchase_cost
    pv_spares = tco.spare_inventory_cost

    # Repairs, replacements, and lost revenue distributed monthly
    monthly_repair = tco.total_repair_cost / horizon if horizon > 0 else 0
    monthly_replace = tco.total_replacement_cost / horizon if horizon > 0 else 0
    monthly_lost_rev = tco.lost_revenue_from_downtime / horizon if horizon > 0 else 0
    monthly_cycles = tco.cycles_served_over_horizon / horizon if horizon > 0 else 0

    pv_repairs = 0.0
    pv_replacements = 0.0
    pv_lost_revenue = 0.0
    pv_cycles = 0.0
    running_pv_tco = pv_purchase + pv_spares
    running_pv_cycles = 0.0

    monthly_dcpc: list[float] = []

    for t in range(1, horizon + 1):
        df = 1 / (1 + r_monthly) ** t
        pv_repairs += monthly_repair * df
        pv_replacements += monthly_replace * df
        pv_lost_revenue += monthly_lost_rev * df
        pv_cycles += monthly_cycles * df

        running_pv_tco += (monthly_repair + monthly_replace + monthly_lost_rev) * df
        running_pv_cycles += monthly_cycles * df

        dcpc = running_pv_tco / running_pv_cycles if running_pv_cycles > 0 else 0
        monthly_dcpc.append(round(dcpc, 4))

    npv_tco = pv_purchase + pv_repairs + pv_replacements + pv_lost_revenue + pv_spares
    discounted_cpc = npv_tco / pv_cycles if pv_cycles > 0 else 0

    return ChargerNPVResult(
        charger_name=charger.name,
        undiscounted_tco=round(tco.total_tco, 2),
        pv_purchase=round(pv_purchase, 2),
        pv_repairs=round(pv_repairs, 2),
        pv_replacements=round(pv_replacements, 2),
        pv_lost_revenue=round(pv_lost_revenue, 2),
        pv_spares=round(pv_spares, 2),
        npv_tco=round(npv_tco, 2),
        discounted_cpc=round(discounted_cpc, 4),
        monthly_discounted_cpc=monthly_dcpc,
    )
