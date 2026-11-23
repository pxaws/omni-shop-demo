"""Converts USD order amounts into the currency the customer pays in.

rates.json holds, per currency, the USD value of one unit ("usd") and the number of decimals
of its minor unit (ISO 4217).
"""

import json
from decimal import Decimal
from pathlib import Path

CENT = Decimal("0.01")
CURRENCIES_FILE = Path(__file__).with_name("rates.json")


def _read(path):
    with open(path) as f:
        return json.load(f)


def load_rates(path):
    return {code: Decimal(c["usd"]).quantize(CENT) for code, c in _read(path).items()}


def load_minor_units(path):
    return {code: Decimal(1).scaleb(-c["decimals"]) for code, c in _read(path).items()}


RATES = load_rates(CURRENCIES_FILE)
MINOR_UNIT = load_minor_units(CURRENCIES_FILE)


def convert(amount_usd, currency):
    if currency == "USD":
        return amount_usd
    if currency not in RATES:
        raise ValueError(f"unknown currency: {currency}")
    rate = RATES[currency]
    return (amount_usd / rate).quantize(MINOR_UNIT[currency])
