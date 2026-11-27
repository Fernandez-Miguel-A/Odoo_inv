import csv
import sqlite3
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QDate, QDateTime
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,

)


from database import Database

from pages import DashboardPage, ProductPage, SupplierPage

class MainWindow(QMainWindow):
    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.setWindowTitle("Nexo · Productos y proveedores")
        self.resize(1360, 850)
        self.setMinimumSize(1060, 700)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("topbar")
        top_layout = QHBoxLayout(topbar)
        top_layout.setContentsMargins(26, 12, 26, 12)
        brand_mark = QLabel("N")
        brand_mark.setObjectName("brandMark")
        brand = QLabel("Nexo")
        brand.setObjectName("brandName")
        top_layout.addWidget(brand_mark)
        top_layout.addWidget(brand)
        top_layout.addSpacing(28)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("dashboard", "Inicio"),
            ("products", "Productos"),
            ("suppliers", "Proveedores"),
        ):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, page=key: self.show_page(page))
            self.nav_buttons[key] = button
            top_layout.addWidget(button)
        top_layout.addStretch()
        top_layout.addWidget(QLabel("Gestión de inventario"))
        layout.addWidget(topbar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.dashboard = DashboardPage(database)
        self.products = ProductPage(database, self.notify)
        self.suppliers = SupplierPage(database, self.refresh_supplier_data, self.notify)
        self.pages = {
            "dashboard": self.dashboard,
            "products": self.products,
            "suppliers": self.suppliers,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.statusBar().showMessage("Listo")
        self.show_page("dashboard")

    def show_page(self, key: str) -> None:
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        for nav_key, button in self.nav_buttons.items():
            button.setChecked(nav_key == key)
        if key == "dashboard":
            self.dashboard.refresh()

    def refresh_supplier_data(self) -> None:
        self.products.refresh_suppliers(
            self.products.supplier_combo.currentData()
        )
        self.products.refresh_table(self.products.current_id)
        self.dashboard.refresh()

    def notify(self, message: str, error: bool = False) -> None:
        self.statusBar().showMessage(message, 6000)
        if error:
            QMessageBox.critical(self, "Error", message)


def apply_styles(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            background: #f5f7f8;
            color: #273444;
            font-family: "Segoe UI";
            font-size: 13px;
        }
        QMainWindow { background: #f5f7f8; }
        #topbar {
            background: #ffffff;
            border-bottom: 1px solid #e3e8eb;
        }
        #brandMark {
            color: #ffffff;
            background: #168a75;
            border-radius: 8px;
            min-width: 30px;
            max-width: 30px;
            min-height: 30px;
            max-height: 30px;
            qproperty-alignment: AlignCenter;
            font-weight: 700;
            font-size: 16px;
        }
        #brandName { font-size: 17px; font-weight: 700; color: #243648; }
        #navButton {
            background: transparent;
            color: #5e6b78;
            border: none;
            border-radius: 7px;
            padding: 9px 13px;
            font-weight: 600;
        }
        #navButton:hover { background: #f0f4f3; color: #168a75; }
        #navButton:checked { color: #147c6b; background: #e8f4f1; }
        QPushButton {
            border: 1px solid #dce3e6;
            background: #ffffff;
            color: #344252;
            border-radius: 6px;
            padding: 8px 13px;
            font-weight: 600;
        }
        QPushButton:hover { background: #f2f6f5; border-color: #b8cbc6; }
        QPushButton[kind="primary"] {
            color: #ffffff;
            background: #765268;
            border-color: #765268;
        }
        QPushButton[kind="primary"]:hover { background: #644357; }
        QPushButton[kind="danger"] { color: #a94646; }
        QPushButton[kind="danger"]:hover { background: #fff1f0; border-color: #e8b7b2; }
        #pageTitle { font-size: 24px; font-weight: 700; color: #263648; }
        #sectionTitle { font-size: 20px; font-weight: 600; padding: 3px 2px 6px; }
        #mutedText { color: #7d8992; }
        #metricCard, QGroupBox {
            background: #ffffff;
            border: 1px solid #e2e8eb;
            border-radius: 9px;
        }
        #metricValue { font-size: 24px; font-weight: 700; color: #263648; }
        QGroupBox {
            margin-top: 12px;
            padding: 14px 12px 12px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 5px;
            color: #52616d;
        }
        QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QTextEdit {
            background: #ffffff;
            border: 1px solid #dce3e6;
            border-radius: 5px;
            padding: 3px 9px;
            selection-background-color: #168a75;
        }
        QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus,
        QSpinBox:focus, QTextEdit:focus { border: 1px solid #168a75; }
        QTabWidget::pane {
            background: #ffffff;
            border: 1px solid #e2e8eb;
            border-radius: 7px;
            top: -1px;
        }
        QTabBar::tab {
            background: #eef1f2;
            color: #586671;
            border: 1px solid #e2e8eb;
            padding: 9px 13px;
            margin-right: 3px;
            border-top-left-radius: 5px;
            border-top-right-radius: 5px;
        }
        QTabBar::tab:selected {
            color: #263648;
            background: #ffffff;
            border-bottom-color: #ffffff;
        }
        QTableWidget, QListWidget {
            background: #ffffff;
            alternate-background-color: #f8fafb;
            border: 1px solid #e2e8eb;
            border-radius: 7px;
            padding: 4px;
            outline: 0;
        }
        QHeaderView::section {
            background: #f3f6f7;
            color: #60707c;
            border: none;
            border-bottom: 1px solid #e2e8eb;
            padding: 9px 7px;
            font-weight: 600;
        }
        QTableWidget::item { padding: 6px; border: none; }
        QTableWidget::item:selected, QListWidget::item:selected {
            color: #1d574d;
            background: #e3f2ee;
        }
        QListWidget::item { padding: 7px 5px; border-bottom: 1px solid #eff2f3; }
        QSplitter::handle { background: #e8edef; width: 5px; }
        QStatusBar {
            background: #ffffff;
            color: #75828c;
            border-top: 1px solid #e3e8eb;
        }
        """
    )


