from decimal import Decimal
from pathlib import Path

import pytest

import pricing

RATES_FILE = Path(pricing.__file__).with_name("rates.json")


def test_loader_keeps_rates_at_cents():
    rates = pricing.load_rates(RATES_FILE)
    assert rates["EUR"] == Decimal("1.08")
    assert rates["USD"] == Decimal("1.00")


def test_loader_reads_each_currency_minor_unit():
    minor_units = pricing.load_minor_units(RATES_FILE)
    assert minor_units["EUR"] == Decimal("0.01")
    assert set(minor_units) == set(pricing.load_rates(RATES_FILE))


def test_converts_usd_to_eur():
    assert pricing.convert(Decimal("50.00"), "EUR") == Decimal("46.30")


def test_charge_rounds_to_the_order_currency_minor_unit(monkeypatch):
    monkeypatch.setattr(pricing, "RATES", {"XTS": Decimal("0.50")})
    monkeypatch.setattr(pricing, "MINOR_UNIT", {"XTS": Decimal("1")})
    assert pricing.convert(Decimal("10.30"), "XTS") == Decimal("21")


def test_usd_order_needs_no_rate(monkeypatch):
    monkeypatch.setattr(pricing, "RATES", {"EUR": Decimal("1.08")})
    assert pricing.convert(Decimal("50.00"), "USD") == Decimal("50.00")


def test_unknown_currency_is_rejected():
    with pytest.raises(ValueError, match="unknown currency: XYZ"):
        pricing.convert(Decimal("50.00"), "XYZ")
