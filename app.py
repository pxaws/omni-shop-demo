"""Shop service. One app, two roles picked by the ROLE env var:

- checkout: takes an order, charges it through payment, reserves stock in inventory.
- payment: converts the USD amount into the order currency and records the charge in audit.
"""

import os
import random
import socket
from decimal import Decimal
from urllib.parse import urlsplit

import requests
from flask import Flask, jsonify, request

import pricing

ROLES = ("checkout", "payment")


def base_urls(env_name):
    return [url.strip() for url in os.environ.get(env_name, "").split(",") if url.strip()]


def post_downstream(urls, path, body):
    """POST to the first host behind `urls` that answers. Returns the response, or None."""
    # requests only tries the first address of a name. Expanding every name to all its
    # IPv4 addresses spreads calls over all hosts and skips a host that is down.
    targets = []
    for base in urls:
        parts = urlsplit(base)
        try:
            infos = socket.getaddrinfo(parts.hostname, parts.port, socket.AF_INET, socket.SOCK_STREAM)
            addresses = sorted({info[4][0] for info in infos})
        except socket.gaierror:
            addresses = [parts.hostname]
        for address in addresses:
            netloc = address if parts.port is None else f"{address}:{parts.port}"
            url = f"{parts.scheme}://{netloc}{parts.path.rstrip('/')}{path}"
            targets.append((url, parts.netloc))
    random.shuffle(targets)
    for url, host in targets:
        try:
            return requests.post(url, json=body, headers={"Host": host}, timeout=5)
        except requests.RequestException:
            continue
    return None


def failure_status(responses):
    """The status to return for the downstream calls, or None when none of them failed.

    A downstream that never answered has no status and does not count as a failure.
    """
    failures = [r.status_code for r in responses if r is not None and r.status_code >= 400]
    if not failures:
        return None
    return 429 if all(status == 429 for status in failures) else 500


def checkout():
    order = request.get_json()
    charge = post_downstream(base_urls("PAYMENT_URLS"), "/charges", order)
    reservation = post_downstream(base_urls("INVENTORY_URLS"), "/reservations", {})
    status = failure_status([charge, reservation])
    if status is not None:
        return jsonify(ok=False), status
    return jsonify(charge.json() if charge is not None else {})


def charges():
    order = request.get_json()
    currency = order["currency"]
    charged = pricing.convert(Decimal(str(order["amount"])), currency)
    audit = post_downstream(base_urls("AUDIT_URLS"), "/audit", {})
    status = failure_status([audit])
    if status is not None:
        return jsonify(ok=False), status
    return jsonify(charged=str(charged), currency=currency)


def create_app(role):
    if role not in ROLES:
        raise ValueError(f"ROLE must be one of {ROLES}, got {role!r}")
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True, role=role, pid=os.getpid())

    if role == "checkout":
        app.add_url_rule("/checkout", view_func=checkout, methods=["POST"])
    else:
        app.add_url_rule("/charges", view_func=charges, methods=["POST"])
    return app


app = create_app(os.environ.get("ROLE"))
