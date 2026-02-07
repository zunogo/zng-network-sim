"""Validation tests for FinanceConfig (Phase 3)."""

import pytest
from pydantic import ValidationError
from zng_simulator.config.finance import FinanceConfig


class TestFinanceConfigDefaults:
    """FinanceConfig should have reasonable defaults."""

    def test_default_construction(self):
        cfg = FinanceConfig()
        assert cfg.debt_pct_of_capex == 0.70
        assert cfg.interest_rate_annual == 0.12
        assert cfg.loan_tenor_months == 60
        assert cfg.grace_period_months == 6
        assert cfg.depreciation_method == "straight_line"
        assert cfg.asset_useful_life_months == 60
        assert cfg.tax_rate == 0.25
        assert cfg.terminal_value_method == "salvage"
        assert cfg.dscr_covenant_threshold == 1.20


class TestFinanceConfigValidation:
    """Edge-case validation tests."""

    def test_debt_pct_range(self):
        FinanceConfig(debt_pct_of_capex=0)  # 0% ok
        FinanceConfig(debt_pct_of_capex=1.0)  # 100% ok
        with pytest.raises(ValidationError):
            FinanceConfig(debt_pct_of_capex=-0.1)
        with pytest.raises(ValidationError):
            FinanceConfig(debt_pct_of_capex=1.1)

    def test_interest_rate_range(self):
        FinanceConfig(interest_rate_annual=0.0)  # zero ok
        with pytest.raises(ValidationError):
            FinanceConfig(interest_rate_annual=-0.01)
        with pytest.raises(ValidationError):
            FinanceConfig(interest_rate_annual=0.51)

    def test_loan_tenor_range(self):
        FinanceConfig(loan_tenor_months=1)  # min ok
        with pytest.raises(ValidationError):
            FinanceConfig(loan_tenor_months=0)

    def test_depreciation_method(self):
        FinanceConfig(depreciation_method="straight_line")
        FinanceConfig(depreciation_method="wdv")
        with pytest.raises(ValidationError):
            FinanceConfig(depreciation_method="invalid")

    def test_tax_rate_range(self):
        FinanceConfig(tax_rate=0)  # 0 ok
        FinanceConfig(tax_rate=0.60)  # 60% ok
        with pytest.raises(ValidationError):
            FinanceConfig(tax_rate=-0.1)
        with pytest.raises(ValidationError):
            FinanceConfig(tax_rate=0.61)

    def test_terminal_value_method(self):
        FinanceConfig(terminal_value_method="salvage")
        FinanceConfig(terminal_value_method="gordon_growth")
        FinanceConfig(terminal_value_method="none")
        with pytest.raises(ValidationError):
            FinanceConfig(terminal_value_method="invalid")

    def test_dscr_threshold(self):
        FinanceConfig(dscr_covenant_threshold=0.5)  # min ok
        with pytest.raises(ValidationError):
            FinanceConfig(dscr_covenant_threshold=-1)

    def test_zero_debt_is_valid(self):
        cfg = FinanceConfig(debt_pct_of_capex=0)
        assert cfg.debt_pct_of_capex == 0

    def test_full_equity(self):
        """Debt pct = 0 → fully equity funded."""
        cfg = FinanceConfig(debt_pct_of_capex=0.0)
        assert cfg.debt_pct_of_capex == 0.0

    def test_json_round_trip(self):
        """FinanceConfig should survive JSON serialization."""
        orig = FinanceConfig(debt_pct_of_capex=0.80, tax_rate=0.30)
        js = orig.model_dump_json()
        restored = FinanceConfig.model_validate_json(js)
        assert restored.debt_pct_of_capex == orig.debt_pct_of_capex
        assert restored.tax_rate == orig.tax_rate

    def test_scenario_includes_finance(self):
        """Scenario should have a finance field."""
        from zng_simulator.config.scenario import Scenario
        s = Scenario()
        assert hasattr(s, "finance")
        assert isinstance(s.finance, FinanceConfig)
