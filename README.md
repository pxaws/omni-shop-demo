# Shop service

A small shop backend in Python and Flask. One code base runs as two services, picked by the
`ROLE` environment variable:

- **checkout** takes an order, charges it through payment, and reserves stock in inventory.
- **payment** converts the order amount from USD into the currency the customer pays in, then
  records the charge in audit.

Order amounts are in USD. `rates.json` holds, for each supported currency, the USD value of one
unit and the number of decimals of its minor unit (ISO 4217). `pricing.py` converts the amount
and rounds the charge to that minor unit.

## API

| Role | Request | Response |
|---|---|---|
| both | `GET /healthz` | `{"ok": true, "role": "...", "pid": 123}` |
| checkout | `POST /checkout` with `{"amount": "50.00", "currency": "EUR"}` | the charge from payment |
| payment | `POST /charges` with the same order body | `{"charged": "46.30", "currency": "EUR"}` |

Checkout calls payment `POST /charges` and inventory `POST /reservations`. Payment calls audit
`POST /audit` after it has converted the amount. If a downstream service fails, the caller fails
too: with 429 when every failure was 429, else with 500. A downstream that does not answer at
all is not counted as a failure.

## Configuration

| Variable | Used by | Value |
|---|---|---|
| `ROLE` | both | `checkout` or `payment` |
| `PAYMENT_URLS` | checkout | comma-separated base URLs, for example `http://payment.internal:8000` |
| `INVENTORY_URLS` | checkout | comma-separated base URLs |
| `AUDIT_URLS` | payment | comma-separated base URLs |

Each host name is resolved to all of its IPv4 addresses. A call goes to one address picked at
random and moves on to the next if that address does not answer.

## Run

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
ROLE=payment AUDIT_URLS=http://127.0.0.1:8002 .venv/bin/gunicorn -w 1 --threads 16 -b 127.0.0.1:8001 app:app
```

## Test

```sh
.venv/bin/python -m pytest tests
```
