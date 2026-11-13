from __future__ import annotations

import copy
import html
import sqlite3
from collections import defaultdict

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QComboBox,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from Odoo_inv.database import InvoiceDatabase
from Odoo_inv.models import Invoice, InvoiceLine


CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}
TERM_DAYS = {"Immediate": 0, "15 Days": 15, "30 Days": 30, "45 Days": 45}


def money(amount: float, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    prefix = "-" if amount < 0 else ""
    return f"{prefix}{symbol} {abs(amount):,.2f}"


class MainWindow(QMainWindow):
    def __init__(self, database: InvoiceDatabase) -> None:
        super().__init__()
        self.database = database
        self.current_invoice = Invoice()
        self._loading = False
        self._dirty = False
        self._page_names = [
            "Invoicing",
            "Dashboard",
            "Customers",
            "Vendors",
            "Reporting",
            "Configuration",
        ]
        self.setWindowTitle("Odoo Inv | Invoicing")
        self.resize(1240, 850)
        self.setMinimumSize(980, 680)
        self.setStyleSheet(self._style_sheet())
        self._build_ui()
        self._refresh_pages()
        invoices = self.database.list_invoices()
        if invoices:
            self._show_invoice(invoices[0])
        else:
            self._new_invoice()

    @staticmethod
    def _style_sheet() -> str:
        return """
            QWidget {
                color: #242a35;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {
                background: #f7f8fa;
            }
            QFrame#topBar {
                background: #ffffff;
                border-bottom: 1px solid #dfe3e8;
            }
            QFrame#invoiceCard, QFrame#pageCard {
                background: #ffffff;
                border: 1px solid #dfe3e8;
                border-radius: 5px;
            }
            QLabel#appMark {
                color: #ffffff;
                background: #168bd2;
                border-radius: 4px;
                font-weight: 700;
                padding: 5px 8px;
            }
            QLabel#appName {
                color: #252b35;
                font-size: 16px;
                font-weight: 600;
            }
            QPushButton {
                background: #f0f2f5;
                border: 1px solid #e1e4e8;
                border-radius: 4px;
                padding: 7px 12px;
            }
            QPushButton:hover { background: #e7eaee; }
            QPushButton:disabled { color: #a7adb7; background: #f4f5f7; }
            QPushButton#primaryButton {
                color: #ffffff;
                background: #714b67;
                border-color: #714b67;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover { background: #5e3d55; }
            QPushButton#navButton {
                background: transparent;
                border: none;
                padding: 9px 10px;
            }
            QPushButton#navButton:checked {
                color: #714b67;
                border-bottom: 2px solid #714b67;
                font-weight: 600;
            }
            QPushButton#linkButton {
                color: #087c86;
                background: transparent;
                border: none;
                padding: 3px 0;
                text-align: left;
            }
            QLineEdit, QDateEdit, QComboBox, QTextEdit, QDoubleSpinBox {
                background: #ffffff;
                border: 1px solid #cfd4dc;
                border-radius: 3px;
                padding: 6px;
                selection-background-color: #714b67;
            }
            QLineEdit:read-only, QTextEdit:read-only, QDoubleSpinBox:disabled {
                color: #59616c;
                background: #fafbfc;
            }
            QTableWidget {
                background: #ffffff;
                border: 1px solid #e1e4e8;
                gridline-color: #e7e9ed;
                selection-background-color: #f0eaf0;
            }
            QHeaderView::section {
                background: #fbfbfc;
                border: none;
                border-bottom: 1px solid #e1e4e8;
                color: #39414d;
                font-weight: 600;
                padding: 9px;
            }
            QLabel#invoiceNumber { font-size: 27px; font-weight: 600; }
            QLabel#sectionTitle { font-size: 22px; font-weight: 600; }
            QLabel#muted { color: #707782; }
            QLabel#totalLabel { font-size: 17px; font-weight: 700; }
            QLabel#statusBadge {
                border: 1px solid #a9d8d6;
                border-radius: 4px;
                color: #087c86;
                font-weight: 600;
                padding: 6px 12px;
            }
            QLabel#statValue { color: #714b67; font-size: 23px; font-weight: 700; }
        """

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 8, 24, 8)
        mark = QLabel("S")
        mark.setObjectName("appMark")
        name = QLabel("Invoicing")
        name.setObjectName("appName")
        top_layout.addWidget(mark)
        top_layout.addWidget(name)
        top_layout.addSpacing(14)
        self._nav_buttons: dict[str, QPushButton] = {}
        for page_name in self._page_names:
            button = QPushButton(page_name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, selected=page_name: self._select_page(selected)
            )
            self._nav_buttons[page_name] = button
            top_layout.addWidget(button)
        top_layout.addStretch(1)
        layout.addWidget(top_bar)

        self.pages = QStackedWidget()
        self._build_invoice_page()
        self._build_dashboard_page()
        self._build_customers_page()
        self._build_vendors_page()
        self._build_reporting_page()
        self._build_configuration_page()
        layout.addWidget(self.pages, 1)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")
        self._select_page("Invoicing")

    def _build_invoice_page(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(22, 16, 22, 18)
        page_layout.setSpacing(10)

        heading = QHBoxLayout()
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._new_invoice)
        heading.addWidget(self.new_button)
        self.breadcrumb = QLabel("Invoices")
        self.breadcrumb.setObjectName("linkButton")
        heading.addWidget(self.breadcrumb)
        heading.addWidget(QLabel("/"))
        self.invoice_sequence = QLabel("")
        heading.addWidget(self.invoice_sequence)
        self.payments_button = QPushButton("Payments\n0")
        self.payments_button.setFixedHeight(42)
        self.payments_button.clicked.connect(self._show_payments)
        heading.addWidget(self.payments_button)
        heading.addStretch(1)
        self.record_position = QLabel("")
        self.record_position.setObjectName("muted")
        heading.addWidget(self.record_position)
        self.previous_button = QPushButton("‹")
        self.previous_button.setFixedWidth(34)
        self.previous_button.clicked.connect(lambda: self._move_invoice(-1))
        heading.addWidget(self.previous_button)
        self.next_button = QPushButton("›")
        self.next_button.setFixedWidth(34)
        self.next_button.clicked.connect(lambda: self._move_invoice(1))
        heading.addWidget(self.next_button)
        page_layout.addLayout(heading)

        action_row = QHBoxLayout()
        self.print_send_button = QPushButton("Print & Send")
        self.print_send_button.setObjectName("primaryButton")
        self.print_send_button.setToolTip(
            "Post the invoice and open a print preview. Save it as a PDF to share."
        )
        self.print_send_button.clicked.connect(self._print_and_send)
        action_row.addWidget(self.print_send_button)
        self.pay_button = QPushButton("Pay")
        self.pay_button.clicked.connect(self._pay_invoice)
        action_row.addWidget(self.pay_button)
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self._preview_invoice)
        action_row.addWidget(self.preview_button)
        self.credit_note_button = QPushButton("Credit Note")
        self.credit_note_button.clicked.connect(self._create_credit_note)
        action_row.addWidget(self.credit_note_button)
        self.reset_button = QPushButton("Reset to Draft")
        self.reset_button.clicked.connect(self._reset_to_draft)
        action_row.addWidget(self.reset_button)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_current)
        action_row.addWidget(self.save_button)
        action_row.addStretch(1)
        self.status_badge = QLabel("DRAFT")
        self.status_badge.setObjectName("statusBadge")
        action_row.addWidget(self.status_badge)
        page_layout.addLayout(action_row)

        card = QFrame()
        card.setObjectName("invoiceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(14)
        document_type = QLabel("Customer Invoice")
        document_type.setObjectName("muted")
        self.document_type = document_type
        card_layout.addWidget(document_type)
        self.invoice_number = QLabel("")
        self.invoice_number.setObjectName("invoiceNumber")
        card_layout.addWidget(self.invoice_number)

        details = QGridLayout()
        details.setHorizontalSpacing(30)
        details.setVerticalSpacing(9)
        details.setColumnStretch(1, 2)
        details.setColumnStretch(3, 1)
        customer_label = QLabel("Customer")
        customer_label.setObjectName("muted")
        details.addWidget(customer_label, 0, 0, Qt.AlignmentFlag.AlignTop)
        self.customer_edit = QLineEdit()
        self.customer_edit.setPlaceholderText("Customer name")
        self.customer_edit.textEdited.connect(self._mark_dirty)
        details.addWidget(self.customer_edit, 0, 1)
        date_label = QLabel("Invoice Date")
        date_label.setObjectName("muted")
        details.addWidget(date_label, 0, 2)
        self.invoice_date_edit = self._date_edit()
        self.invoice_date_edit.dateChanged.connect(self._mark_dirty)
        details.addWidget(self.invoice_date_edit, 0, 3)

        address_label = QLabel("Address")
        address_label.setObjectName("muted")
        details.addWidget(address_label, 1, 0, Qt.AlignmentFlag.AlignTop)
        self.address_edit = QTextEdit()
        self.address_edit.setPlaceholderText("Billing address")
        self.address_edit.setMaximumHeight(78)
        self.address_edit.textChanged.connect(self._mark_dirty)
        details.addWidget(self.address_edit, 1, 1)
        terms_label = QLabel("Payment terms")
        terms_label.setObjectName("muted")
        details.addWidget(terms_label, 1, 2)
        self.terms_combo = QComboBox()
        self.terms_combo.addItems(["Immediate", "15 Days", "30 Days", "45 Days"])
        self.terms_combo.setCurrentText("30 Days")
        self.terms_combo.currentTextChanged.connect(self._payment_terms_changed)
        details.addWidget(self.terms_combo, 1, 3)

        email_label = QLabel("Email")
        email_label.setObjectName("muted")
        details.addWidget(email_label, 2, 0)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("customer@example.com")
        self.email_edit.textEdited.connect(self._mark_dirty)
        details.addWidget(self.email_edit, 2, 1)
        due_label = QLabel("Due Date")
        due_label.setObjectName("muted")
        details.addWidget(due_label, 2, 2)
        self.due_date_edit = self._date_edit()
        self.due_date_edit.dateChanged.connect(self._mark_dirty)
        details.addWidget(self.due_date_edit, 2, 3)

        currency_label = QLabel("Currency")
        currency_label.setObjectName("muted")
        details.addWidget(currency_label, 3, 2)
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["EUR", "USD", "GBP"])
        self.currency_combo.currentTextChanged.connect(self._mark_dirty)
        details.addWidget(self.currency_combo, 3, 3)
        card_layout.addLayout(details)

        self.tabs = QStackedWidget()
        self.tab_bar = QHBoxLayout()
        self.lines_tab_button = QPushButton("Invoice Lines")
        self.lines_tab_button.clicked.connect(lambda: self._select_invoice_tab(0))
        self.info_tab_button = QPushButton("Other Info")
        self.info_tab_button.clicked.connect(lambda: self._select_invoice_tab(1))
        self.tab_bar.addWidget(self.lines_tab_button)
        self.tab_bar.addWidget(self.info_tab_button)
        self.tab_bar.addStretch(1)
        card_layout.addLayout(self.tab_bar)
        self.tabs.addWidget(self._build_lines_tab())
        self.tabs.addWidget(self._build_other_info_tab())
        card_layout.addWidget(self.tabs)
        page_layout.addWidget(card, 1)

        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setFrameShape(QFrame.Shape.NoFrame)
        outer.setWidget(page)
        self.pages.addWidget(outer)

    @staticmethod
    def _date_edit() -> QDateEdit:
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("MM/dd/yyyy")
        return editor

    def _build_lines_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        self.lines_table = QTableWidget(0, 6)
        self.lines_table.setHorizontalHeaderLabels(
            ["Product", "Quantity", "Price", "Disc.%", "Taxes", "Amount"]
        )
        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.lines_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        header = self.lines_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        header.setSectionResizeMode(1, header.ResizeMode.Fixed)
        header.setSectionResizeMode(2, header.ResizeMode.Fixed)
        header.setSectionResizeMode(3, header.ResizeMode.Fixed)
        header.setSectionResizeMode(4, header.ResizeMode.Fixed)
        header.setSectionResizeMode(5, header.ResizeMode.Fixed)
        self.lines_table.setColumnWidth(1, 92)
        self.lines_table.setColumnWidth(2, 125)
        self.lines_table.setColumnWidth(3, 82)
        self.lines_table.setColumnWidth(4, 82)
        self.lines_table.setColumnWidth(5, 135)
        self.lines_table.verticalHeader().setVisible(False)
        layout.addWidget(self.lines_table, 1)

        line_actions = QHBoxLayout()
        self.add_line_button = QPushButton("Add a line")
        self.add_line_button.setObjectName("linkButton")
        self.add_line_button.clicked.connect(self._add_line)
        line_actions.addWidget(self.add_line_button)
        self.remove_line_button = QPushButton("Remove selected")
        self.remove_line_button.setObjectName("linkButton")
        self.remove_line_button.clicked.connect(self._remove_line)
        line_actions.addWidget(self.remove_line_button)
        line_actions.addStretch(1)
        layout.addLayout(line_actions)

        footer = QHBoxLayout()
        footer.setContentsMargins(10, 4, 10, 0)
        self.payment_note = QLabel("")
        self.payment_note.setWordWrap(True)
        self.payment_note.setObjectName("muted")
        self.payment_note.setMinimumWidth(280)
        footer.addWidget(self.payment_note, 1, Qt.AlignmentFlag.AlignTop)
        totals = QGridLayout()
        totals.setHorizontalSpacing(18)
        totals.setVerticalSpacing(5)
        totals.addWidget(QLabel("Untaxed Amount:"), 0, 0)
        self.untaxed_amount = QLabel("")
        self.untaxed_amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        totals.addWidget(self.untaxed_amount, 0, 1)
        totals.addWidget(QLabel("Tax:"), 1, 0)
        self.tax_amount = QLabel("")
        self.tax_amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        totals.addWidget(self.tax_amount, 1, 1)
        total_caption = QLabel("Total:")
        total_caption.setObjectName("totalLabel")
        totals.addWidget(total_caption, 2, 0)
        self.total_amount = QLabel("")
        self.total_amount.setObjectName("totalLabel")
        self.total_amount.setAlignment(Qt.AlignmentFlag.AlignRight)
        totals.addWidget(self.total_amount, 2, 1)
        footer.addLayout(totals)
        layout.addLayout(footer)
        return page

    def _build_other_info_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(20, 16, 20, 16)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(14)
        self.reference_edit = QLineEdit()
        self.reference_edit.textEdited.connect(self._mark_dirty)
        form.addRow("Customer Reference", self.reference_edit)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Payment instructions or additional invoice notes"
        )
        self.notes_edit.setMaximumHeight(130)
        self.notes_edit.textChanged.connect(self._mark_dirty)
        form.addRow("Terms & Notes", self.notes_edit)
        self.source_invoice_label = QLabel("—")
        form.addRow("Credit Note Origin", self.source_invoice_label)
        return page

    def _build_dashboard_page(self) -> None:
        self.dashboard_page, self.dashboard_layout = self._page_container(
            "Dashboard", "An overview of your customer invoicing."
        )
        self.pages.addWidget(self.dashboard_page)

    def _build_customers_page(self) -> None:
        page, layout = self._page_container(
            "Customers", "Customers and billing details from your invoices."
        )
        self.customers_table = self._data_table(
            ["Customer", "Address", "Invoices", "Outstanding"]
        )
        layout.addWidget(self.customers_table, 1)
        self.customers_page = page
        self.pages.addWidget(page)

    def _build_vendors_page(self) -> None:
        page, layout = self._page_container(
            "Vendors", "Vendor management is outside this customer invoicing starter."
        )
        message = QLabel(
            "This version is focused on customer invoices, matching the reference "
            "screen. Vendor bills and vendor records are not included yet."
        )
        message.setWordWrap(True)
        message.setObjectName("muted")
        message.setMaximumWidth(620)
        layout.addWidget(message)
        layout.addStretch(1)
        self.pages.addWidget(page)

    def _build_reporting_page(self) -> None:
        page, layout = self._page_container(
            "Reporting", "Invoice totals grouped by status."
        )
        self.reporting_table = self._data_table(
            ["Status", "Invoices", "Untaxed", "Tax", "Total", "Outstanding"]
        )
        layout.addWidget(self.reporting_table, 1)
        self.reporting_page = page
        self.pages.addWidget(page)

    def _build_configuration_page(self) -> None:
        page, layout = self._page_container(
            "Configuration", "Company details printed on invoice previews."
        )
        form_card = QFrame()
        form_card.setObjectName("pageCard")
        form = QFormLayout(form_card)
        form.setContentsMargins(20, 20, 20, 20)
        self.company_name_edit = QLineEdit(
            self.database.get_setting("company_name", "My Company")
        )
        self.company_address_edit = QTextEdit(
            self.database.get_setting("company_address", "")
        )
        self.company_address_edit.setMaximumHeight(90)
        self.company_email_edit = QLineEdit(
            self.database.get_setting("company_email", "")
        )
        form.addRow("Company Name", self.company_name_edit)
        form.addRow("Address", self.company_address_edit)
        form.addRow("Email", self.company_email_edit)
        save_button = QPushButton("Save Configuration")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save_configuration)
        form.addRow("", save_button)
        layout.addWidget(form_card)
        layout.addStretch(1)
        self.pages.addWidget(page)

    @staticmethod
    def _page_container(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 26, 28, 28)
        layout.setSpacing(14)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        note = QLabel(subtitle)
        note.setObjectName("muted")
        layout.addWidget(note)
        return page, layout

    @staticmethod
    def _data_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _select_page(self, name: str) -> None:
        if name != "Invoicing" and self.pages.currentIndex() == 0:
            if not self._confirm_pending_changes():
                self._nav_buttons["Invoicing"].setChecked(True)
                return
        index = self._page_names.index(name)
        self.pages.setCurrentIndex(index)
        for page_name, button in self._nav_buttons.items():
            button.setChecked(page_name == name)
        if name != "Invoicing":
            self._refresh_pages()

    def _select_invoice_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)
        self.lines_tab_button.setChecked(index == 0)
        self.info_tab_button.setChecked(index == 1)

    def _refresh_pages(self) -> None:
        invoices = self.database.list_invoices()
        self._refresh_dashboard(invoices)
        self._refresh_customers(invoices)
        self._refresh_reporting(invoices)

    def _refresh_dashboard(self, invoices: list[Invoice]) -> None:
        while self.dashboard_layout.count() > 2:
            item = self.dashboard_layout.takeAt(2)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        posted = [invoice for invoice in invoices if invoice.status != "Draft"]
        total_outstanding = sum(invoice.amount_due for invoice in posted)
        cards = QHBoxLayout()
        cards.addWidget(self._stat_card("Invoices", str(len(invoices))))
        cards.addWidget(
            self._stat_card(
                "Posted", str(sum(invoice.status in ("Posted", "Paid") for invoice in invoices))
            )
        )
        currency = invoices[0].currency if invoices else "EUR"
        cards.addWidget(
            self._stat_card("Outstanding", money(total_outstanding, currency))
        )
        card_holder = QWidget()
        card_holder.setLayout(cards)
        self.dashboard_layout.addWidget(card_holder)
        recent_label = QLabel("Recent Invoices")
        recent_label.setObjectName("sectionTitle")
        self.dashboard_layout.addWidget(recent_label)
        table = self._data_table(["Number", "Customer", "Date", "Status", "Total"])
        table.setRowCount(min(8, len(invoices)))
        for row, invoice in enumerate(invoices[:8]):
            self._set_cell(table, row, 0, invoice.number)
            self._set_cell(table, row, 1, invoice.customer)
            self._set_cell(table, row, 2, invoice.invoice_date)
            self._set_cell(table, row, 3, invoice.status)
            self._set_cell(table, row, 4, money(invoice.total, invoice.currency))
        self.dashboard_layout.addWidget(table, 1)

    @staticmethod
    def _stat_card(label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("pageCard")
        layout = QVBoxLayout(card)
        caption = QLabel(label)
        caption.setObjectName("muted")
        amount = QLabel(value)
        amount.setObjectName("statValue")
        layout.addWidget(caption)
        layout.addWidget(amount)
        card.setMinimumHeight(92)
        return card

    def _refresh_customers(self, invoices: list[Invoice]) -> None:
        customers: dict[str, dict[str, object]] = {}
        for invoice in invoices:
            entry = customers.setdefault(
                invoice.customer,
                {
                    "address": invoice.address,
                    "count": 0,
                    "outstanding": defaultdict(float),
                },
            )
            entry["count"] = int(entry["count"]) + 1
            if invoice.status != "Draft":
                balances = entry["outstanding"]
                if isinstance(balances, defaultdict):
                    balances[invoice.currency] += invoice.amount_due
        self.customers_table.setRowCount(len(customers))
        for row, (name, entry) in enumerate(sorted(customers.items())):
            self._set_cell(self.customers_table, row, 0, name)
            self._set_cell(self.customers_table, row, 1, str(entry["address"]))
            self._set_cell(self.customers_table, row, 2, str(entry["count"]))
            balances = entry["outstanding"]
            balance_text = (
                " · ".join(
                    money(amount, currency)
                    for currency, amount in sorted(balances.items())
                )
                if isinstance(balances, defaultdict) and balances
                else money(0, "EUR")
            )
            self._set_cell(self.customers_table, row, 3, balance_text)

    def _refresh_reporting(self, invoices: list[Invoice]) -> None:
        groups: dict[str, list[Invoice]] = defaultdict(list)
        for invoice in invoices:
            groups[invoice.status].append(invoice)
        statuses = ["Draft", "Posted", "Paid"]
        self.reporting_table.setRowCount(len(statuses))
        for row, status in enumerate(statuses):
            entries = groups[status]
            currency = entries[0].currency if entries else "EUR"
            self._set_cell(self.reporting_table, row, 0, status)
            self._set_cell(self.reporting_table, row, 1, str(len(entries)))
            self._set_cell(
                self.reporting_table,
                row,
                2,
                money(sum(invoice.untaxed_amount for invoice in entries), currency),
            )
            self._set_cell(
                self.reporting_table,
                row,
                3,
                money(sum(invoice.tax_amount for invoice in entries), currency),
            )
            self._set_cell(
                self.reporting_table,
                row,
                4,
                money(sum(invoice.total for invoice in entries), currency),
            )
            self._set_cell(
                self.reporting_table,
                row,
                5,
                money(sum(invoice.amount_due for invoice in entries), currency),
            )

    @staticmethod
    def _set_cell(table: QTableWidget, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        if column > 0:
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            )
        table.setItem(row, column, item)

    def _save_configuration(self) -> None:
        self.database.set_setting("company_name", self.company_name_edit.text().strip())
        self.database.set_setting(
            "company_address", self.company_address_edit.toPlainText().strip()
        )
        self.database.set_setting("company_email", self.company_email_edit.text().strip())
        self.statusBar().showMessage("Company details saved.", 4000)

    def _show_invoice(self, invoice: Invoice) -> None:
        self._loading = True
        self.current_invoice = copy.deepcopy(invoice)
        self.invoice_number.setText(invoice.number or "New Invoice")
        self.invoice_sequence.setText(invoice.number or "New Invoice")
        self.document_type.setText(
            "Credit Note" if invoice.is_credit_note else "Customer Invoice"
        )
        self.customer_edit.setText(invoice.customer)
        self.address_edit.setPlainText(invoice.address)
        self.email_edit.setText(invoice.email)
        self.invoice_date_edit.setDate(self._to_qdate(invoice.invoice_date))
        self.due_date_edit.setDate(self._to_qdate(invoice.due_date))
        self.terms_combo.setCurrentText(invoice.payment_terms)
        self.currency_combo.setCurrentText(invoice.currency)
        self.reference_edit.setText(invoice.reference)
        self.notes_edit.setPlainText(invoice.notes)
        self.source_invoice_label.setText(invoice.reference if invoice.is_credit_note else "—")
        self.payment_note.setText(
            f"Payment is due within {invoice.payment_terms.lower()} from the date "
            "of the invoice.\n"
            + (invoice.notes or f"Please reference invoice number {invoice.number}.")
        )
        self._populate_lines(invoice.lines or [InvoiceLine()])
        self._loading = False
        self._dirty = False
        self._update_totals()
        self._update_invoice_actions()
        self._update_record_navigation()

    @staticmethod
    def _to_qdate(value: str) -> QDate:
        result = QDate.fromString(value, "yyyy-MM-dd")
        return result if result.isValid() else QDate.currentDate()

    def _populate_lines(self, lines: list[InvoiceLine]) -> None:
        self.lines_table.setRowCount(0)
        for line in lines:
            row = self.lines_table.rowCount()
            self.lines_table.insertRow(row)
            product_panel = QWidget()
            product_layout = QVBoxLayout(product_panel)
            product_layout.setContentsMargins(8, 4, 8, 4)
            product_layout.setSpacing(3)
            product_edit = QLineEdit(line.product)
            product_edit.setPlaceholderText("Product")
            product_edit.setFrame(False)
            ##product_edit.setMinimumHeight(28)
            description_edit = QLineEdit(line.description)
            description_edit.setPlaceholderText("Description")
            description_edit.setFrame(False)
            description_edit.setMinimumHeight(28)
            description_edit.setStyleSheet("font-style: italic; color: #707782;")
            product_layout.addWidget(product_edit)
            product_layout.addWidget(description_edit)
            self.lines_table.setCellWidget(row, 0, product_panel)

            quantity = self._number_editor(line.quantity, 999999999, 2)
            price = self._number_editor(line.unit_price, 999999999, 2)
            discount = self._number_editor(line.discount, 100, 2)
            tax = self._number_editor(line.tax_rate, 100, 2)
            self.lines_table.setCellWidget(row, 1, quantity)
            self.lines_table.setCellWidget(row, 2, price)
            self.lines_table.setCellWidget(row, 3, discount)
            self.lines_table.setCellWidget(row, 4, tax)
            amount = QLabel("")
            amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lines_table.setCellWidget(row, 5, amount)
            for editor in (product_edit, description_edit):
                editor.textEdited.connect(self._line_changed)
            for editor in (quantity, price, discount, tax):
                editor.valueChanged.connect(self._line_changed)
            self.lines_table.setRowHeight(row, 100)
        self._set_invoice_editable(self.current_invoice.status == "Draft")

    @staticmethod
    def _number_editor(value: float, maximum: float, decimals: int) -> QDoubleSpinBox:
        editor = QDoubleSpinBox()
        editor.setRange(0, maximum)
        editor.setDecimals(decimals)
        editor.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        editor.setValue(value)
        return editor

    def _line_changed(self, *_args: object) -> None:
        self._mark_dirty()
        self._update_totals()

    def _mark_dirty(self, *_args: object) -> None:
        if not self._loading and self.current_invoice.status == "Draft":
            self._dirty = True
            self.save_button.setEnabled(True)

    def _set_invoice_editable(self, enabled: bool) -> None:
        for widget in (
            self.customer_edit,
            self.address_edit,
            self.email_edit,
            self.invoice_date_edit,
            self.due_date_edit,
            self.terms_combo,
            self.currency_combo,
            self.reference_edit,
            self.notes_edit,
            self.add_line_button,
            self.remove_line_button,
        ):
            widget.setEnabled(enabled)
        for row in range(self.lines_table.rowCount()):
            product_panel = self.lines_table.cellWidget(row, 0)
            if product_panel is not None:
                for editor in product_panel.findChildren(QLineEdit):
                    editor.setReadOnly(not enabled)
            for column in range(1, 5):
                editor = self.lines_table.cellWidget(row, column)
                if editor is not None:
                    editor.setEnabled(enabled)

    def _update_totals(self) -> None:
        invoice = self._collect_invoice() if hasattr(self, "customer_edit") else self.current_invoice
        if hasattr(self, "lines_table"):
            for row, line in enumerate(self._read_lines()):
                amount = self.lines_table.cellWidget(row, 5)
                if isinstance(amount, QLabel):
                    amount.setText(money(line.total * invoice.sign, invoice.currency))
        self.untaxed_amount.setText(money(invoice.untaxed_amount, invoice.currency))
        self.tax_amount.setText(money(invoice.tax_amount, invoice.currency))
        self.total_amount.setText(money(invoice.total, invoice.currency))

    def _read_lines(self) -> list[InvoiceLine]:
        lines: list[InvoiceLine] = []
        for row in range(self.lines_table.rowCount()):
            panel = self.lines_table.cellWidget(row, 0)
            if panel is None:
                continue
            text_edits = panel.findChildren(QLineEdit)
            product = text_edits[0].text().strip() if text_edits else ""
            description = text_edits[1].text().strip() if len(text_edits) > 1 else ""
            editors = [
                self.lines_table.cellWidget(row, column) for column in range(1, 5)
            ]
            numeric = [
                editor.value() if isinstance(editor, QDoubleSpinBox) else 0.0
                for editor in editors
            ]
            if product or description:
                lines.append(
                    InvoiceLine(
                        product=product,
                        description=description,
                        quantity=numeric[0],
                        unit_price=numeric[1],
                        discount=numeric[2],
                        tax_rate=numeric[3],
                    )
                )
        return lines

    def _collect_invoice(self) -> Invoice:
        invoice = copy.deepcopy(self.current_invoice)
        invoice.customer = self.customer_edit.text().strip()
        invoice.address = self.address_edit.toPlainText().strip()
        invoice.email = self.email_edit.text().strip()
        invoice.invoice_date = self.invoice_date_edit.date().toString("yyyy-MM-dd")
        invoice.due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        invoice.payment_terms = self.terms_combo.currentText()
        invoice.currency = self.currency_combo.currentText()
        invoice.reference = self.reference_edit.text().strip()
        invoice.notes = self.notes_edit.toPlainText().strip()
        invoice.lines = self._read_lines()
        return invoice

    def _update_invoice_actions(self) -> None:
        status = self.current_invoice.status
        self.status_badge.setText(status.upper())
        self.status_badge.setStyleSheet(
            "color: #087c86; border: 1px solid #a9d8d6; border-radius: 4px; "
            "font-weight: 600; padding: 6px 12px;"
            if status != "Draft"
            else "color: #68707b; border: 1px solid #d6d9df; border-radius: 4px; "
            "font-weight: 600; padding: 6px 12px;"
        )
        self.pay_button.setEnabled(status == "Posted" and self.current_invoice.amount_due > 0)
        self.credit_note_button.setEnabled(
            self.current_invoice.id is not None
            and status in ("Posted", "Paid")
            and not self.current_invoice.is_credit_note
        )
        self.reset_button.setEnabled(status == "Posted")
        self.save_button.setEnabled(status == "Draft")
        self._set_invoice_editable(status == "Draft")

    def _update_record_navigation(self) -> None:
        ids = [invoice.id for invoice in self.database.list_invoices()]
        ids = [invoice_id for invoice_id in ids if invoice_id is not None]
        payments = (
            self.database.list_payments(self.current_invoice.id)
            if self.current_invoice.id is not None
            else []
        )
        self.payments_button.setText(f"Payments\n{len(payments)}")
        self.payments_button.setEnabled(self.current_invoice.id is not None)
        if self.current_invoice.id in ids:
            index = ids.index(self.current_invoice.id)
            self.record_position.setText(f"{index + 1} / {len(ids)}")
            self.previous_button.setEnabled(index < len(ids) - 1)
            self.next_button.setEnabled(index > 0)
        else:
            self.record_position.setText("New")
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)

    def _confirm_pending_changes(self) -> bool:
        if not self._dirty:
            return True
        choice = QMessageBox(self)
        choice.setWindowTitle("Unsaved changes")
        choice.setText("Save changes to this invoice before leaving?")
        save = choice.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        choice.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        choice.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        choice.exec()
        clicked = choice.clickedButton()
        if clicked is save:
            return self._save_current()
        return clicked is not None and clicked.text() == "Discard"

    def _save_current(self) -> bool:
        invoice = self._collect_invoice()
        if not invoice.customer:
            QMessageBox.warning(self, "Customer required", "Enter a customer name.")
            return False
        if not invoice.lines or any(not line.product for line in invoice.lines):
            QMessageBox.warning(
                self, "Product required", "Add at least one product to the invoice."
            )
            return False
        try:
            self.database.save_invoice(invoice)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not save invoice", str(error))
            return False
        self.current_invoice = invoice
        self._dirty = False
        self._show_invoice(invoice)
        self._refresh_pages()
        self.statusBar().showMessage(f"{invoice.number} saved.", 4000)
        return True

    def _new_invoice(self) -> None:
        if hasattr(self, "pages") and self.pages.currentIndex() == 0:
            if not self._confirm_pending_changes():
                return
        today = QDate.currentDate()
        due = today.addDays(30)
        self._show_invoice(
            Invoice(
                invoice_date=today.toString("yyyy-MM-dd"),
                due_date=due.toString("yyyy-MM-dd"),
                payment_terms="30 Days",
                currency="EUR",
                status="Draft",
                lines=[InvoiceLine()],
            )
        )
        self._select_page("Invoicing")

    def _move_invoice(self, offset: int) -> None:
        if not self._confirm_pending_changes():
            return
        invoices = self.database.list_invoices()
        ids = [invoice.id for invoice in invoices]
        if self.current_invoice.id not in ids:
            return
        target = ids.index(self.current_invoice.id) + offset
        if 0 <= target < len(invoices):
            self._show_invoice(invoices[target])

    def _add_line(self) -> None:
        lines = self._read_lines()
        lines.append(InvoiceLine())
        self._populate_lines(lines)
        self._mark_dirty()
        self._update_totals()

    def _remove_line(self) -> None:
        row = self.lines_table.currentRow()
        if row < 0:
            return
        lines = self._read_lines()
        if row < len(lines):
            lines.pop(row)
        self._populate_lines(lines or [InvoiceLine()])
        self._mark_dirty()
        self._update_totals()

    def _payment_terms_changed(self, terms: str) -> None:
        if not self._loading:
            days = TERM_DAYS.get(terms)
            if days is not None:
                self.due_date_edit.setDate(self.invoice_date_edit.date().addDays(days))
            self._mark_dirty()

    def _post_current(self) -> bool:
        if not self._save_current():
            return False
        if self.current_invoice.status == "Draft":
            try:
                self.database.post_invoice(self.current_invoice.id)
            except (ValueError, sqlite3.Error) as error:
                QMessageBox.critical(self, "Could not post invoice", str(error))
                return False
            self._show_invoice(self.database.get_invoice(self.current_invoice.id))
            self._refresh_pages()
        return True

    def _print_and_send(self) -> None:
        if self.current_invoice.status == "Draft" and not self._post_current():
            return
        self._open_print_preview(self._collect_invoice())

    def _preview_invoice(self) -> None:
        self._open_print_preview(self._collect_invoice())

    def _open_print_preview(self, invoice: Invoice) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        preview = QPrintPreviewDialog(printer, self)
        document = QTextDocument()
        document.setHtml(self._invoice_html(invoice))
        preview.paintRequested.connect(lambda selected_printer: document.print_(selected_printer))
        preview.exec()

    def _invoice_html(self, invoice: Invoice) -> str:
        company = html.escape(self.database.get_setting("company_name", "My Company"))
        company_address = html.escape(
            self.database.get_setting("company_address", "")
        ).replace("\n", "<br>")
        customer = html.escape(invoice.customer)
        address = html.escape(invoice.address).replace("\n", "<br>")
        notes = html.escape(invoice.notes).replace("\n", "<br>")
        lines = "".join(
            "<tr>"
            f"<td>{html.escape(line.product)}<br><small>{html.escape(line.description)}</small></td>"
            f"<td>{line.quantity:.2f}</td>"
            f"<td>{money(line.unit_price, invoice.currency)}</td>"
            f"<td>{line.discount:.2f}%</td>"
            f"<td>{line.tax_rate:.2f}%</td>"
            f"<td>{money(line.total * invoice.sign, invoice.currency)}</td>"
            "</tr>"
            for line in invoice.lines
        )
        source = f"<p>Reference: {html.escape(invoice.reference)}</p>" if invoice.reference else ""
        return f"""
            <html><head><style>
                body {{ font-family: Arial, sans-serif; color: #242a35; }}
                h1 {{ font-size: 28px; margin-bottom: 4px; }}
                h2 {{ color: #714b67; margin-top: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
                th, td {{ border-bottom: 1px solid #dfe3e8; padding: 10px; text-align: left; }}
                th {{ background: #f5f6f8; }}
                .totals {{ margin-top: 20px; margin-left: auto; width: 320px; }}
                .grand {{ font-size: 18px; font-weight: bold; }}
            </style></head><body>
                <h2>{company}</h2><p>{company_address}</p>
                <h1>{html.escape(invoice.number or "New Invoice")}</h1>
                <p>{'Credit Note' if invoice.is_credit_note else 'Customer Invoice'} · {invoice.status}</p>
                <table><tr><td><b>Customer</b><br>{customer}<br>{address}</td>
                <td><b>Invoice Date</b><br>{html.escape(invoice.invoice_date)}<br><br>
                <b>Due Date</b><br>{html.escape(invoice.due_date)}</td></tr></table>
                <table><thead><tr><th>Product</th><th>Quantity</th><th>Price</th>
                <th>Disc.%</th><th>Taxes</th><th>Amount</th></tr></thead>
                <tbody>{lines}</tbody></table>
                {source}
                <table class="totals">
                <tr><td>Untaxed Amount</td><td>{money(invoice.untaxed_amount, invoice.currency)}</td></tr>
                <tr><td>Tax</td><td>{money(invoice.tax_amount, invoice.currency)}</td></tr>
                <tr class="grand"><td>Total</td><td>{money(invoice.total, invoice.currency)}</td></tr>
                <tr><td>Amount Due</td><td>{money(invoice.amount_due, invoice.currency)}</td></tr>
                </table><p>{notes}</p>
            </body></html>
        """

    def _pay_invoice(self) -> None:
        if self.current_invoice.id is None or self.current_invoice.status != "Posted":
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Register Payment")
        form = QFormLayout(dialog)
        amount = QDoubleSpinBox()
        amount.setRange(0.01, max(self.current_invoice.amount_due, 0.01))
        amount.setDecimals(2)
        amount.setValue(self.current_invoice.amount_due)
        method = QComboBox()
        method.addItems(["Bank", "Cash", "Card"])
        reference = QLineEdit()
        form.addRow("Amount", amount)
        form.addRow("Payment Method", method)
        form.addRow("Reference", reference)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.database.record_payment(
                self.current_invoice.id, amount.value(), method.currentText(), reference.text()
            )
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not record payment", str(error))
            return
        self._show_invoice(self.database.get_invoice(self.current_invoice.id))
        self._refresh_pages()
        self.statusBar().showMessage("Payment recorded.", 4000)

    def _show_payments(self) -> None:
        if self.current_invoice.id is None:
            return
        payments = self.database.list_payments(self.current_invoice.id)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Payments · {self.current_invoice.number}")
        layout = QVBoxLayout(dialog)
        table = self._data_table(["Date", "Method", "Reference", "Amount"])
        table.setRowCount(len(payments))
        for row, payment in enumerate(payments):
            self._set_cell(table, row, 0, payment.payment_date)
            self._set_cell(table, row, 1, payment.method)
            self._set_cell(table, row, 2, payment.reference)
            self._set_cell(
                table,
                row,
                3,
                money(payment.amount, self.current_invoice.currency),
            )
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.resize(620, 320)
        dialog.exec()

    def _create_credit_note(self) -> None:
        if self.current_invoice.id is None:
            return
        try:
            note = self.database.create_credit_note(self.current_invoice.id)
        except (ValueError, sqlite3.Error) as error:
            QMessageBox.critical(self, "Could not create credit note", str(error))
            return
        self._show_invoice(note)
        self._refresh_pages()
        self.statusBar().showMessage(f"Credit note {note.number} created.", 5000)

    def _reset_to_draft(self) -> None:
        if self.current_invoice.id is None:
            return
        answer = QMessageBox.question(
            self,
            "Reset to Draft",
            "Reset this posted invoice to draft?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.reset_to_draft(self.current_invoice.id)
        except (ValueError, sqlite_error_types()) as error:
            QMessageBox.critical(self, "Could not reset invoice", str(error))
            return
        self._show_invoice(self.database.get_invoice(self.current_invoice.id))
        self._refresh_pages()
