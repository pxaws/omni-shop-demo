import socket
from urllib.parse import urlsplit

import pytest

import app as shop


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeDownstreams:
    """Stands in for requests.post and records every call the app makes."""

    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "host": headers["Host"], "timeout": timeout})
        status, body = self.replies[urlsplit(url).path]
        return FakeResponse(status, body)

    def paths(self):
        return [urlsplit(call["url"]).path for call in self.calls]


@pytest.fixture
def downstreams(monkeypatch):
    def fake_getaddrinfo(host, port, family, type_):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port))]

    monkeypatch.setattr(shop.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setenv("PAYMENT_URLS", "http://payment.shop:8000")
    monkeypatch.setenv("INVENTORY_URLS", "http://inventory.shop:8000")
    monkeypatch.setenv("AUDIT_URLS", "http://audit.shop:8000")
    fake = FakeDownstreams({
        "/charges": (200, {"charged": "50.00", "currency": "USD"}),
        "/reservations": (200, {}),
        "/audit": (200, {}),
    })
    monkeypatch.setattr(shop.requests, "post", fake.post)
    return fake


def test_healthz_reports_role():
    client = shop.create_app("payment").test_client()
    body = client.get("/healthz").get_json()
    assert body["ok"] is True
    assert body["role"] == "payment"


def test_payment_charges_eur_and_records_audit(downstreams):
    client = shop.create_app("payment").test_client()
    resp = client.post("/charges", json={"amount": "50.00", "currency": "EUR"})
    assert resp.status_code == 200
    assert resp.get_json() == {"charged": "46.30", "currency": "EUR"}
    assert downstreams.paths() == ["/audit"]
    call = downstreams.calls[0]
    assert call["url"] == "http://10.0.0.5:8000/audit"
    assert call["host"] == "audit.shop:8000"
    assert call["timeout"] == 5


def test_checkout_charges_payment_and_reserves_stock(downstreams):
    client = shop.create_app("checkout").test_client()
    order = {"amount": "50.00", "currency": "USD"}
    resp = client.post("/checkout", json=order)
    assert resp.status_code == 200
    assert resp.get_json() == {"charged": "50.00", "currency": "USD"}
    assert downstreams.paths() == ["/charges", "/reservations"]
    assert downstreams.calls[0]["json"] == order
    assert downstreams.calls[0]["host"] == "payment.shop:8000"


@pytest.mark.parametrize("statuses, expected", [
    ([200, 200], None),
    ([200, None], None),
    ([429, 429], 429),
    ([429, 503], 500),
    ([404, 200], 500),
])
def test_failure_status_takes_the_worst_downstream(statuses, expected):
    responses = [None if s is None else FakeResponse(s, {}) for s in statuses]
    assert shop.failure_status(responses) == expected
