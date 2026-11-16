"""Card and UPI checkout for credit plans and top-ups (build plan 17.4).

The processor only ever carries platform fees. Trade money moves through the
bank and the trade ledger (M5), never through here.

    configure(PaymentsConfig(provider="razorpay", key_id=..., key_secret=..., webhook_secret=...))
    order = await get_provider().create_order(amount_minor=99900, currency="INR", receipt="…")
    event = get_provider().read_webhook(raw_body, headers)   # raises InvalidSignature

Providers: ``razorpay`` (live), ``test`` (no network; signs like Razorpay with
a local secret, for development and the test suite), ``none`` (checkout off).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

SIGNATURE_HEADER = "x-razorpay-signature"
EVENT_ID_HEADER = "x-razorpay-event-id"


class PaymentsError(Exception):
    """The processor could not be reached or refused the request."""


class PaymentsNotConfigured(PaymentsError):
    """No processor is set up in this environment."""


class InvalidSignature(PaymentsError):
    """A webhook did not carry a valid signature for its body."""


class InvalidEvent(PaymentsError):
    """A signed webhook whose body is not an event we can read."""


@dataclass(frozen=True)
class PaymentsConfig:
    provider: str = "none"
    key_id: str = ""
    key_secret: str = ""
    webhook_secret: str = ""
    http_timeout_sec: float = 10.0


@dataclass(frozen=True)
class Order:
    id: str
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class WebhookEvent:
    """A payment outcome, already signature-checked. ``paid`` is true only
    for a captured payment; the amount is what the processor says it took."""

    event_id: str
    event_type: str
    order_id: str | None
    payment_id: str | None
    amount_minor: int | None
    currency: str | None
    paid: bool
    failed: bool


class PaymentProvider(ABC):
    name: str

    def __init__(self, config: PaymentsConfig) -> None:
        self.config = config

    @property
    def public_key(self) -> str:
        """The key the browser checkout needs. Never the secret."""
        return self.config.key_id

    @abstractmethod
    async def create_order(self, *, amount_minor: int, currency: str, receipt: str) -> Order: ...

    def read_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        """Verify the signature over the raw body, then parse the event."""
        signature = headers.get(SIGNATURE_HEADER, "")
        expected = sign(raw_body, self.config.webhook_secret)
        if not self.config.webhook_secret or not hmac.compare_digest(signature, expected):
            raise InvalidSignature("Webhook signature does not match.")
        return parse_event(raw_body, headers.get(EVENT_ID_HEADER, ""))


def sign(raw_body: bytes, secret: str) -> str:
    """Razorpay's webhook signature: hex HMAC-SHA256 of the raw body."""
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def parse_event(raw_body: bytes, event_id: str) -> WebhookEvent:
    """Read a Razorpay ``payment.*`` event. Anything else parses with
    ``paid`` and ``failed`` both false, and is ignored by the caller."""
    try:
        body = json.loads(raw_body)
        event_type = str(body["event"])
        entity = (body.get("payload", {}).get("payment", {}) or {}).get("entity") or {}
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        raise InvalidEvent("Webhook body is not a payment event.") from exc
    if not event_id:
        raise InvalidEvent("Webhook has no event id.")
    amount = entity.get("amount")
    return WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        order_id=entity.get("order_id"),
        payment_id=entity.get("id"),
        amount_minor=amount if isinstance(amount, int) else None,
        currency=(entity.get("currency") or None),
        paid=event_type == "payment.captured" and entity.get("status") == "captured",
        failed=event_type == "payment.failed",
    )


class RazorpayProvider(PaymentProvider):
    name = "razorpay"
    ORDERS_URL = "https://api.razorpay.com/v1/orders"

    def __init__(self, config: PaymentsConfig, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(config)
        self._transport = transport

    async def create_order(self, *, amount_minor: int, currency: str, receipt: str) -> Order:
        try:
            async with httpx.AsyncClient(timeout=self.config.http_timeout_sec, transport=self._transport) as client:
                response = await client.post(
                    self.ORDERS_URL,
                    auth=(self.config.key_id, self.config.key_secret),
                    json={"amount": amount_minor, "currency": currency, "receipt": receipt},
                )
        except httpx.HTTPError as exc:
            raise PaymentsError("The payment processor did not answer.") from exc
        if response.status_code != 200:
            raise PaymentsError(f"The payment processor refused the order ({response.status_code}).")
        try:
            data = response.json()
            order = Order(id=str(data["id"]), amount_minor=int(data["amount"]), currency=str(data["currency"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise PaymentsError("The payment processor sent an order we could not read.") from exc
        # Treat the answer as untrusted: it must be the order we asked for.
        if order.amount_minor != amount_minor or order.currency != currency or not order.id.startswith("order_"):
            raise PaymentsError("The payment processor returned a different order.")
        return order


class TestProvider(PaymentProvider):
    """No network. Orders are local ids; webhooks are signed with
    ``webhook_secret`` exactly as Razorpay signs them."""

    name = "test"
    __test__ = False  # not a pytest class

    async def create_order(self, *, amount_minor: int, currency: str, receipt: str) -> Order:
        return Order(id=f"order_test_{secrets.token_hex(8)}", amount_minor=amount_minor, currency=currency)


class _NoProvider(PaymentProvider):
    name = "none"

    async def create_order(self, *, amount_minor: int, currency: str, receipt: str) -> Order:
        raise PaymentsNotConfigured("Payments are not set up in this environment.")

    def read_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        raise PaymentsNotConfigured("Payments are not set up in this environment.")


_PROVIDERS = {"razorpay": RazorpayProvider, "test": TestProvider, "none": _NoProvider}
_provider: PaymentProvider = _NoProvider(PaymentsConfig())


def configure(config: PaymentsConfig) -> None:
    global _provider
    try:
        _provider = _PROVIDERS[config.provider](config)
    except KeyError:
        raise ValueError(f"Unknown payment provider {config.provider!r}.") from None


def get_provider() -> PaymentProvider:
    return _provider
