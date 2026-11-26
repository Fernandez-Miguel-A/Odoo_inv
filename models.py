from __future__ import annotations

from dataclasses import dataclass, field

from main_definitions import *


@dataclass(slots=True)
class InvoiceLine:
    product: str = ""
    description: str = ""
    quantity: float = 1.0
    unit_price: float = 0.0
    discount: float = 0.0
    tax_rate: float = 15.0

    @property
    def subtotal(self) -> float:
        return round(self.quantity * self.unit_price * (1 - self.discount / 100), 2)

    @property
    def tax_amount(self) -> float:
        return round(self.subtotal * self.tax_rate / 100, 2)

    @property
    def total(self) -> float:
        return self.subtotal + self.tax_amount


@dataclass(slots=True)
class Invoice:
    id: int | None = None
    number: str = ""
    customer: str = ""
    address: str = ""
    email: str = ""
    invoice_date: str = ""
    due_date: str = ""
    payment_terms: str = "30 Days"
    currency: str = default_Currency
    status: str = "Draft"
    reference: str = ""
    notes: str = ""
    is_credit_note: bool = False
    source_invoice_id: int | None = None
    paid_amount: float = 0.0
    lines: list[InvoiceLine] = field(default_factory=list)

    @property
    def sign(self) -> int:
        return -1 if self.is_credit_note else 1

    @property
    def untaxed_amount(self) -> float:
        return round(sum(line.subtotal for line in self.lines) * self.sign, 2)

    @property
    def tax_amount(self) -> float:
        return round(sum(line.tax_amount for line in self.lines) * self.sign, 2)

    @property
    def total(self) -> float:
        return self.untaxed_amount + self.tax_amount

    @property
    def amount_due(self) -> float:
        return max(0.0, round(self.total - self.paid_amount, 2))


@dataclass(slots=True)
class Payment:
    id: int
    amount: float
    method: str
    payment_date: str
    reference: str


@dataclass(slots=True)
class Vendor:
    id: int | None = None
    name: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    tax_id: str = ""
    address: str = ""
    payment_terms: str = "30 Days"
    currency: str = default_Currency
    notes: str = ""
    is_active: bool = True
