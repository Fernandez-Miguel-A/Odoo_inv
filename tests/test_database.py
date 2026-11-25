from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ..database import DEFAULT_DATABASE_PATH, InvoiceDatabase
from ..models import Invoice, InvoiceLine, Vendor


class InvoiceDatabaseTests(unittest.TestCase):
    def test_default_database_is_inside_project_data_directory(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        self.assertEqual(
            DEFAULT_DATABASE_PATH,
            project_root / "data" / "invoices.sqlite3",
        )

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = InvoiceDatabase(
            Path(self.temporary_directory.name) / "invoices.sqlite3"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_demo_invoice_matches_reference_totals(self) -> None:
        invoice = self.database.list_invoices()[0]

        self.assertEqual(invoice.number, "INV/2024/00005")
        self.assertEqual(invoice.status, "Posted")
        self.assertEqual(invoice.untaxed_amount, 3615.00)
        self.assertEqual(invoice.tax_amount, 542.25)
        self.assertEqual(invoice.total, 4157.25)

    def test_new_invoice_round_trips_with_generated_number(self) -> None:
        invoice = Invoice(
            customer="Example Customer",
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            lines=[
                InvoiceLine(
                    product="Desk",
                    quantity=2,
                    unit_price=100,
                    discount=10,
                    tax_rate=15,
                )
            ],
        )

        self.database.save_invoice(invoice)
        loaded = self.database.get_invoice(invoice.id)

        self.assertEqual(invoice.number, "INV/2026/00001")
        self.assertEqual(loaded.customer, "Example Customer")
        self.assertEqual(loaded.lines[0].product, "Desk")
        self.assertEqual(loaded.total, 207.0)

    def test_payment_updates_balance_and_prevents_overpayment(self) -> None:
        invoice = self.database.list_invoices()[0]

        self.database.record_payment(invoice.id, 1000, "Bank", "deposit")
        partially_paid = self.database.get_invoice(invoice.id)
        payments = self.database.list_payments(invoice.id)
        self.assertEqual(partially_paid.status, "Posted")
        self.assertEqual(partially_paid.amount_due, 3157.25)
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].reference, "deposit")

        self.database.record_payment(invoice.id, 3157.25, "Card", "final")
        paid = self.database.get_invoice(invoice.id)
        self.assertEqual(paid.status, "Paid")
        self.assertEqual(paid.amount_due, 0)
        with self.assertRaises(ValueError):
            self.database.record_payment(invoice.id, 1, "Cash")

    def test_credit_note_has_negative_total_and_keeps_source_reference(self) -> None:
        source = self.database.list_invoices()[0]

        note = self.database.create_credit_note(source.id)

        self.assertTrue(note.is_credit_note)
        self.assertEqual(note.status, "Draft")
        self.assertEqual(note.reference, source.number)
        self.assertEqual(note.total, -source.total)
        self.assertEqual(note.number.split("/")[0], "CN")

    def test_credit_note_can_be_reversed_into_positive_invoice(self) -> None:
        source = self.database.list_invoices()[0]
        credit_note = self.database.create_credit_note(source.id)
        credit_note.status = "Posted"
        self.database.save_invoice(credit_note)

        reversal = self.database.create_credit_note(credit_note.id)
        saved_reversal = self.database.get_invoice(reversal.id)

        self.assertFalse(saved_reversal.is_credit_note)
        self.assertEqual(saved_reversal.total, source.total)
        self.assertEqual(saved_reversal.reference, credit_note.number)
        self.assertEqual(saved_reversal.source_invoice_id, credit_note.id)
        self.assertEqual(saved_reversal.number.split("/")[0], "INV")

    def test_posted_invoice_can_be_reset_to_draft(self) -> None:
        invoice = self.database.list_invoices()[0]

        self.database.reset_to_draft(invoice.id)

        self.assertEqual(self.database.get_invoice(invoice.id).status, "Draft")

    def test_vendor_details_round_trip_and_archive_filter(self) -> None:
        vendor = Vendor(
            name="Northwind Supplies",
            contact_name="Morgan Lee",
            email="accounts@northwind.example",
            phone="+1 555 0100",
            tax_id="NW-1024",
            address="12 Market Street\nSpringfield",
            payment_terms="45 Days",
            currency="USD",
            notes="Deliveries before noon",
        )

        self.database.save_vendor(vendor)
        loaded = self.database.get_vendor(vendor.id)

        self.assertEqual(loaded.id, vendor.id)
        self.assertEqual(loaded.name, vendor.name)
        self.assertEqual(loaded.contact_name, vendor.contact_name)
        self.assertEqual(loaded.email, vendor.email)
        self.assertEqual(loaded.phone, vendor.phone)
        self.assertEqual(loaded.tax_id, vendor.tax_id)
        self.assertEqual(loaded.address, vendor.address)
        self.assertEqual(loaded.payment_terms, vendor.payment_terms)
        self.assertEqual(loaded.currency, vendor.currency)
        self.assertEqual(loaded.notes, vendor.notes)
        self.database.set_vendor_archived(vendor.id, archived=True)
        self.assertEqual(self.database.list_vendors(include_archived=False), [])
        self.assertFalse(self.database.list_vendors()[0].is_active)

        self.database.set_vendor_archived(vendor.id, archived=False)
        self.assertTrue(self.database.list_vendors(include_archived=False)[0].is_active)

    def test_vendor_names_are_required_and_case_insensitively_unique(self) -> None:
        with self.assertRaises(ValueError):
            self.database.save_vendor(Vendor(name="  "))

        self.database.save_vendor(Vendor(name="Northwind Supplies"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.database.save_vendor(Vendor(name="northwind supplies"))

    def test_vendor_updates_preserve_id_and_reject_missing_records(self) -> None:
        vendor = self.database.save_vendor(Vendor(name="Northwind Supplies"))
        vendor.phone = "+1 555 0199"

        self.database.save_vendor(vendor)

        self.assertEqual(self.database.get_vendor(vendor.id).phone, "+1 555 0199")
        with self.assertRaises(KeyError):
            self.database.save_vendor(Vendor(id=999, name="Missing Vendor"))


if __name__ == "__main__":
    unittest.main()
