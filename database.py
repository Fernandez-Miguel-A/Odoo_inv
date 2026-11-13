from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

from Odoo_inv.models import Invoice, InvoiceLine, Payment


class InvoiceDatabase:
    """SQLite persistence for invoices and their payment history."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            data_root = Path(os.environ.get("LOCALAPPDATA", Path.home()))
            path = data_root / "Odoo_inv" / "invoices.sqlite3"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    number TEXT NOT NULL UNIQUE,
                    customer TEXT NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    invoice_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    payment_terms TEXT NOT NULL DEFAULT '30 Days',
                    currency TEXT NOT NULL DEFAULT 'EUR',
                    status TEXT NOT NULL DEFAULT 'Draft',
                    reference TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    is_credit_note INTEGER NOT NULL DEFAULT 0,
                    source_invoice_id INTEGER REFERENCES invoices(id),
                    paid_amount REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS invoice_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    product TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    quantity REAL NOT NULL DEFAULT 1,
                    unit_price REAL NOT NULL DEFAULT 0,
                    discount REAL NOT NULL DEFAULT 0,
                    tax_rate REAL NOT NULL DEFAULT 15
                );
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
                    amount REAL NOT NULL,
                    method TEXT NOT NULL,
                    payment_date TEXT NOT NULL,
                    reference TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            count = connection.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
            if count == 0:
                self._insert_demo_invoice(connection)

    @staticmethod
    def _insert_demo_invoice(connection: sqlite3.Connection) -> None:
        cursor = connection.execute(
            """
            INSERT INTO invoices (
                number, customer, address, email, invoice_date, due_date,
                payment_terms, currency, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INV/2024/00005",
                "Deco Addict, Addison Olson",
                "77 Santa Barbara Rd\nPleasant Hill CA 94523\nUnited States — US12345673",
                "",
                "2024-11-08",
                "2024-12-08",
                "30 Days",
                "EUR",
                "Posted",
                "Please reference invoice number INV/2024/00005 during the payment.",
            ),
        )
        invoice_id = cursor.lastrowid
        connection.executemany(
            """
            INSERT INTO invoice_lines (
                invoice_id, position, product, description, quantity,
                unit_price, discount, tax_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    invoice_id,
                    0,
                    "[FURN_8220] Four Person Desk",
                    "Four person modern office workstation",
                    1,
                    2350,
                    10,
                    15,
                ),
                (
                    invoice_id,
                    1,
                    "[FURN_8999] Three-Seat Sofa",
                    "Three Seater Sofa with Lounger in Steel Grey Colour",
                    1,
                    1500,
                    0,
                    15,
                ),
            ],
        )

    def save_invoice(self, invoice: Invoice) -> Invoice:
        with self._connection() as connection:
            values = (
                invoice.customer.strip(),
                invoice.address.strip(),
                invoice.email.strip(),
                invoice.invoice_date,
                invoice.due_date,
                invoice.payment_terms,
                invoice.currency,
                invoice.status,
                invoice.reference.strip(),
                invoice.notes.strip(),
                int(invoice.is_credit_note),
                invoice.source_invoice_id,
            )
            if invoice.id is None:
                prefix = "CN" if invoice.is_credit_note else "INV"
                year = invoice.invoice_date[:4]
                count = connection.execute(
                    "SELECT COUNT(*) FROM invoices WHERE number LIKE ?",
                    (f"{prefix}/{year}/%",),
                ).fetchone()[0]
                invoice.number = f"{prefix}/{year}/{count + 1:05d}"
                cursor = connection.execute(
                    """
                    INSERT INTO invoices (
                        number, customer, address, email, invoice_date, due_date,
                        payment_terms, currency, status, reference, notes,
                        is_credit_note, source_invoice_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (invoice.number, *values),
                )
                invoice.id = cursor.lastrowid
            else:
                connection.execute(
                    """
                    UPDATE invoices SET
                        customer = ?, address = ?, email = ?, invoice_date = ?,
                        due_date = ?, payment_terms = ?, currency = ?, status = ?,
                        reference = ?, notes = ?, is_credit_note = ?,
                        source_invoice_id = ?
                    WHERE id = ?
                    """,
                    (*values, invoice.id),
                )
                connection.execute(
                    "DELETE FROM invoice_lines WHERE invoice_id = ?",
                    (invoice.id,),
                )
            connection.executemany(
                """
                INSERT INTO invoice_lines (
                    invoice_id, position, product, description, quantity,
                    unit_price, discount, tax_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        invoice.id,
                        position,
                        line.product.strip(),
                        line.description.strip(),
                        line.quantity,
                        line.unit_price,
                        line.discount,
                        line.tax_rate,
                    )
                    for position, line in enumerate(invoice.lines)
                ],
            )
        return invoice

    def get_invoice(self, invoice_id: int) -> Invoice:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Invoice {invoice_id} does not exist")
            lines = connection.execute(
                "SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY position",
                (invoice_id,),
            ).fetchall()
        return self._invoice_from_rows(row, lines)

    def list_invoices(self) -> list[Invoice]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM invoices ORDER BY id DESC"
            ).fetchall()
            line_rows = connection.execute(
                "SELECT * FROM invoice_lines ORDER BY invoice_id, position"
            ).fetchall()
        lines_by_invoice: dict[int, list[sqlite3.Row]] = {}
        for line in line_rows:
            lines_by_invoice.setdefault(line["invoice_id"], []).append(line)
        return [
            self._invoice_from_rows(row, lines_by_invoice.get(row["id"], []))
            for row in rows
        ]

    @staticmethod
    def _invoice_from_rows(
        row: sqlite3.Row, lines: list[sqlite3.Row]
    ) -> Invoice:
        return Invoice(
            id=row["id"],
            number=row["number"],
            customer=row["customer"],
            address=row["address"],
            email=row["email"],
            invoice_date=row["invoice_date"],
            due_date=row["due_date"],
            payment_terms=row["payment_terms"],
            currency=row["currency"],
            status=row["status"],
            reference=row["reference"],
            notes=row["notes"],
            is_credit_note=bool(row["is_credit_note"]),
            source_invoice_id=row["source_invoice_id"],
            paid_amount=row["paid_amount"],
            lines=[
                InvoiceLine(
                    product=line["product"],
                    description=line["description"],
                    quantity=line["quantity"],
                    unit_price=line["unit_price"],
                    discount=line["discount"],
                    tax_rate=line["tax_rate"],
                )
                for line in lines
            ],
        )

    def post_invoice(self, invoice_id: int) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE invoices SET status = 'Posted' WHERE id = ? AND status = 'Draft'",
                (invoice_id,),
            )
            if cursor.rowcount != 1:
                raise ValueError("Only draft invoices can be posted.")

    def reset_to_draft(self, invoice_id: int) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE invoices SET status = 'Draft' WHERE id = ? AND status = 'Posted'",
                (invoice_id,),
            )
            if cursor.rowcount != 1:
                raise ValueError("Only posted, unpaid invoices can be reset to draft.")

    def record_payment(
        self,
        invoice_id: int,
        amount: float,
        method: str,
        reference: str = "",
    ) -> None:
        invoice = self.get_invoice(invoice_id)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT status, paid_amount FROM invoices WHERE id = ?",
                (invoice_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Invoice {invoice_id} does not exist")
            if row["status"] != "Posted":
                raise ValueError("Payments can only be recorded for posted invoices.")
            if amount <= 0:
                raise ValueError("The payment amount must be greater than zero.")
            if amount > round(invoice.total - row["paid_amount"], 2):
                raise ValueError("The payment amount exceeds the outstanding balance.")
            connection.execute(
                """
                INSERT INTO payments (invoice_id, amount, method, payment_date, reference)
                VALUES (?, ?, ?, ?, ?)
                """,
                (invoice_id, amount, method, date.today().isoformat(), reference.strip()),
            )
            paid_amount = round(row["paid_amount"] + amount, 2)
            status = "Paid" if paid_amount >= invoice.total else "Posted"
            connection.execute(
                "UPDATE invoices SET paid_amount = ?, status = ? WHERE id = ?",
                (paid_amount, status, invoice_id),
            )

    def list_payments(self, invoice_id: int) -> list[Payment]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, amount, method, payment_date, reference
                FROM payments WHERE invoice_id = ? ORDER BY id
                """,
                (invoice_id,),
            ).fetchall()
        return [
            Payment(
                id=row["id"],
                amount=row["amount"],
                method=row["method"],
                payment_date=row["payment_date"],
                reference=row["reference"],
            )
            for row in rows
        ]

    def create_credit_note(self, invoice_id: int) -> Invoice:
        source = self.get_invoice(invoice_id)
        if source.status == "Draft":
            raise ValueError("Post the invoice before creating a credit note.")
        note = Invoice(
            customer=source.customer,
            address=source.address,
            email=source.email,
            invoice_date=date.today().isoformat(),
            due_date=date.today().isoformat(),
            payment_terms="Immediate",
            currency=source.currency,
            reference=source.number,
            notes=f"Credit note for {source.number}",
            is_credit_note=True,
            source_invoice_id=source.id,
            lines=[
                InvoiceLine(
                    product=line.product,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount=line.discount,
                    tax_rate=line.tax_rate,
                )
                for line in source.lines
            ],
        )
        return self.save_invoice(note)

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
