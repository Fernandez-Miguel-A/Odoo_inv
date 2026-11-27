import csv
import sqlite3
import sys
from pathlib import Path
from typing import Any

from database_v1 import Database

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

APP_DIR = Path(__file__).resolve().parent

def make_button(text: str, kind: str = "secondary") -> QPushButton:
    button = QPushButton(text)
    button.setProperty("kind", kind)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def set_table_defaults(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setShowGrid(False)


def add_form_row(layout: QFormLayout, label: str, widget: QWidget) -> None:
    widget.setMinimumHeight(20)
    layout.addRow(label, widget)



class DashboardPage(QWidget):
    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(18)

        title = QLabel("Resumen")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        intro = QLabel("Vista general de tus productos, proveedores y existencias.")
        intro.setObjectName("mutedText")
        root.addWidget(intro)

        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(14)
        root.addLayout(self.cards_layout)

        panels = QHBoxLayout()
        panels.setSpacing(16)
        low_group = QGroupBox("Productos para reponer")
        low_layout = QVBoxLayout(low_group)
        self.low_table = QTableWidget(0, 3)
        self.low_table.setHorizontalHeaderLabels(["Referencia", "Producto", "Stock"])
        set_table_defaults(self.low_table)
        low_layout.addWidget(self.low_table)
        panels.addWidget(low_group, 3)

        activity_group = QGroupBox("Actividad reciente")
        activity_layout = QVBoxLayout(activity_group)
        self.activity_list = QListWidget()
        activity_layout.addWidget(self.activity_list)
        panels.addWidget(activity_group, 2)
        root.addLayout(panels, 1)

    def refresh(self) -> None:
        summary = self.database.summary()
        metrics = [
            ("Productos", str(summary["products"]), "Referencias en catálogo"),
            ("Unidades en stock", f'{summary["units"]:,}', "Existencia total"),
            ("Valor del inventario", f'$ {summary["stock_value"]:,.2f}', "Valorizado al coste"),
            ("Proveedores", str(summary["suppliers"]), f'{summary["low_stock"]} productos por reponer'),
        ]
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for column, (heading, value, caption) in enumerate(metrics):
            card = QFrame()
            card.setObjectName("metricCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 15, 18, 15)
            label = QLabel(heading)
            label.setObjectName("mutedText")
            number = QLabel(value)
            number.setObjectName("metricValue")
            detail = QLabel(caption)
            detail.setObjectName("mutedText")
            card_layout.addWidget(label)
            card_layout.addWidget(number)
            card_layout.addWidget(detail)
            self.cards_layout.addWidget(card, 0, column)

        products = self.database.list_products(low_stock=True)
        self.low_table.setRowCount(len(products))
        for row_index, product in enumerate(products):
            self.low_table.setItem(row_index, 0, QTableWidgetItem(product["reference"]))
            self.low_table.setItem(row_index, 1, QTableWidgetItem(product["name"]))
            stock_item = QTableWidgetItem(f'{product["stock"]} / mín. {product["min_stock"]}')
            stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.low_table.setItem(row_index, 2, stock_item)
        self.activity_list.clear()
        for item in self.database.recent_activity():
            value = str(item["created_at"])
            date = QDateTime.fromString(value, "yyyy-MM-dd hh:mm:ss").toString("d-M-yyyy hh:mm")
            name = item["product_name"] or "Producto eliminado"
            self.activity_list.addItem(f'{date}  ·  {item["message"]}\n{name}')
        if not self.activity_list.count():
            self.activity_list.addItem("Todavía no hay movimientos.")


class ProductPage(QWidget):
    def __init__(self, database: Database, notify: Any) -> None:
        super().__init__()
        self.database = database
        self.notify = notify
        self.current_id: int | None = None
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(14)
        header = QHBoxLayout()
        title = QLabel("Productos")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        self.new_button = make_button("Nuevo", "primary")
        self.save_button = make_button("Guardar", "primary")
        self.delete_button = make_button("Eliminar", "danger")
        self.stock_button = make_button("Ajustar stock", "secondary")
        self.replenish_button = make_button("Reponer", "secondary")
        self.export_button = make_button("Exportar CSV", "secondary")
        for button in (
            self.new_button, self.save_button, self.delete_button,
            self.stock_button, self.replenish_button, self.export_button,
        ):
            header.addWidget(button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)

        catalog = QWidget()
        catalog_layout = QVBoxLayout(catalog)
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        catalog_layout.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre, referencia o categoría...")
        self.low_stock_checkbox = QCheckBox("Solo stock bajo")
        catalog_layout.addWidget(self.search_input)
        catalog_layout.addWidget(self.low_stock_checkbox)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Referencia", "Producto", "Stock"])
        set_table_defaults(self.table)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        catalog_layout.addWidget(self.table, 1)
        splitter.addWidget(catalog)

        editor_shell = QWidget()
        editor_layout = QVBoxLayout(editor_shell)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        self.product_heading = QLabel("Seleccioná un producto")
        self.product_heading.setObjectName("sectionTitle")
        editor_layout.addWidget(self.product_heading)
        self.tabs = QTabWidget()
        editor_layout.addWidget(self.tabs, 1)
        self._build_general_tab()
        self._build_inventory_tab()
        self._build_notes_tab()
        activity_group = QGroupBox("Actividad")
        activity_layout = QVBoxLayout(activity_group)
        self.activity_list = QListWidget()
        self.activity_list.setMaximumHeight(105)
        activity_layout.addWidget(self.activity_list)
        editor_layout.addWidget(activity_group)
        splitter.addWidget(editor_shell)
        splitter.setSizes([330, 750])

        self.new_button.clicked.connect(self.new_product)
        self.save_button.clicked.connect(self.save_product)
        self.delete_button.clicked.connect(self.delete_product)
        self.stock_button.clicked.connect(self.adjust_stock)
        self.replenish_button.clicked.connect(self.replenish)
        self.export_button.clicked.connect(self.export_csv)
        self.search_input.textChanged.connect(self.refresh_table)
        self.low_stock_checkbox.toggled.connect(self.refresh_table)
        self.table.itemSelectionChanged.connect(self._selection_changed)

        self.refresh_suppliers()
        self.refresh_table()

    def _build_general_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setHorizontalSpacing(24)
        self.name_input = QLineEdit()
        self.reference_input = QLineEdit()
        self.category_input = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Bienes", "Servicio", "Combinación"])
        self.sale_enabled = QCheckBox("Disponible para la venta")
        self.purchase_enabled = QCheckBox("Se puede comprar")
        self.sale_enabled.setChecked(True)
        self.purchase_enabled.setChecked(True)
        self.sale_price = self._money_input()
        self.sales_tax = self._percentage_input()
        self.cost = self._money_input()
        self.purchase_tax = self._percentage_input()

        ## layout.setVerticalSpacing(10)
        add_form_row(layout, "Nombre del producto", self.name_input)
        add_form_row(layout, "Referencia interna", self.reference_input)
        add_form_row(layout, "Tipo de producto", self.type_combo)
        add_form_row(layout, "Categoría", self.category_input)
        add_form_row(layout, "Precio de venta", self.sale_price)
        add_form_row(layout, "Impuesto de venta (%)", self.sales_tax)
        add_form_row(layout, "Coste", self.cost)
        add_form_row(layout, "Impuesto de compra (%)", self.purchase_tax)
        layout.addRow(self.sale_enabled)
        layout.addRow(self.purchase_enabled)
        self.tabs.addTab(tab, "Información general")

    def _build_inventory_tab(self) -> None:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setHorizontalSpacing(24)
        self.supplier_combo = QComboBox()
        self.barcode_input = QLineEdit()
        self.stock_input = QSpinBox()
        self.stock_input.setRange(0, 2_000_000_000)
        self.min_stock_input = QSpinBox()
        self.min_stock_input.setRange(0, 2_000_000_000)
        add_form_row(layout, "Proveedor", self.supplier_combo)
        add_form_row(layout, "Código de barras", self.barcode_input)
        add_form_row(layout, "Cantidad disponible", self.stock_input)
        add_form_row(layout, "Umbral de reposición", self.min_stock_input)
        helper = QLabel("El aviso de reposición aparece cuando el stock llega al umbral o queda por debajo.")
        helper.setObjectName("mutedText")
        helper.setWordWrap(True)
        layout.addRow(helper)
        self.tabs.addTab(tab, "Compras e inventario")

    def _build_notes_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(22, 20, 22, 20)
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Notas internas del producto...")
        layout.addWidget(self.notes_input)
        self.tabs.addTab(tab, "Notas internas")

    @staticmethod
    def _money_input() -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(0, 99_999_999_999)
        widget.setDecimals(2)
        widget.setPrefix("$ ")
        widget.setGroupSeparatorShown(True)
        return widget

    @staticmethod
    def _percentage_input() -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(0, 100)
        widget.setDecimals(2)
        widget.setSuffix(" %")
        return widget

    def refresh_suppliers(self, selected_id: int | None = None) -> None:
        self.supplier_combo.clear()
        self.supplier_combo.addItem("Sin proveedor", None)
        for supplier in self.database.list_suppliers():
            self.supplier_combo.addItem(supplier["name"], supplier["id"])
        index = self.supplier_combo.findData(selected_id)
        self.supplier_combo.setCurrentIndex(index if index >= 0 else 0)

    def refresh_table(self, select_id: int | None = None) -> None:
        products = self.database.list_products(
            self.search_input.text(), self.low_stock_checkbox.isChecked()
        )
        self._loading = True
        self.table.setRowCount(len(products))
        selected_row = -1
        for row, product in enumerate(products):
            reference = QTableWidgetItem(product["reference"])
            reference.setData(Qt.ItemDataRole.UserRole, product["id"])
            self.table.setItem(row, 0, reference)
            self.table.setItem(row, 1, QTableWidgetItem(product["name"]))
            stock = QTableWidgetItem(str(product["stock"]))
            stock.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if product["stock"] <= product["min_stock"]:
                stock.setForeground(Qt.GlobalColor.darkRed)
            self.table.setItem(row, 2, stock)
            if product["id"] == select_id:
                selected_row = row
        if selected_row < 0 and products:
            selected_row = 0
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self._loading = False
        if selected_row >= 0:
            item = self.table.item(selected_row, 0)
            if item is not None:
                product_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(product_id, int):
                    self.load_product(product_id)
        elif not products:
            self.new_product()

    def _selection_changed(self) -> None:
        if self._loading:
            return
        items = self.table.selectedItems()
        if items:
            item = self.table.item(items[0].row(), 0)
            if item is not None:
                product_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(product_id, int):
                    self.load_product(product_id)

    def load_product(self, product_id: int) -> None:
        product = self.database.get_product(product_id)
        if product is None:
            self.refresh_table()
            return
        self.current_id = product_id
        self.product_heading.setText(product["name"])
        self.name_input.setText(product["name"])
        self.reference_input.setText(product["reference"])
        self.category_input.setText(product["category"])
        self.type_combo.setCurrentText(product["product_type"])
        self.sale_price.setValue(product["sale_price"])
        self.sales_tax.setValue(product["sales_tax"])
        self.cost.setValue(product["cost"])
        self.purchase_tax.setValue(product["purchase_tax"])
        self.sale_enabled.setChecked(bool(product["sale_enabled"]))
        self.purchase_enabled.setChecked(bool(product["purchase_enabled"]))
        self.refresh_suppliers(product["supplier_id"])
        self.barcode_input.setText(product["barcode"])
        self.stock_input.setValue(product["stock"])
        self.min_stock_input.setValue(product["min_stock"])
        self.notes_input.setPlainText(product["notes"])
        self.activity_list.clear()
        activities = self.database.connection.execute(
            """
            SELECT message, created_at FROM activity
            WHERE product_id = ? ORDER BY id DESC LIMIT 5
            """,
            (product_id,),
        ).fetchall()
        for item in activities:
            value = str(item["created_at"])
            datetime = QDateTime.fromString(value, "yyyy-MM-dd hh:mm:ss")
            ## print(f"load_product: '{value}', '{datetime.toString("d-M-yyyy hh:mm")}'")
            self.activity_list.addItem(f'{datetime.toString("d-M-yyyy hh:mm")}  ·  {item["message"]}')
        if not activities:
            self.activity_list.addItem("Sin actividad registrada.")

    def new_product(self) -> None:
        self.current_id = None
        self.product_heading.setText("Nuevo producto")
        for widget in (self.name_input, self.reference_input, self.category_input, self.barcode_input):
            widget.clear()
        self.type_combo.setCurrentIndex(0)
        self.sale_price.setValue(0)
        self.sales_tax.setValue(0)
        self.cost.setValue(0)
        self.purchase_tax.setValue(0)
        self.stock_input.setValue(0)
        self.min_stock_input.setValue(0)
        self.sale_enabled.setChecked(True)
        self.purchase_enabled.setChecked(True)
        self.notes_input.clear()
        self.refresh_suppliers()
        self.activity_list.clear()
        self.activity_list.addItem("Guardá el producto para comenzar su historial.")
        self.name_input.setFocus()

    def save_product(self) -> None:
        name = self.name_input.text().strip()
        reference = self.reference_input.text().strip()
        if not name or not reference:
            QMessageBox.warning(self, "Datos incompletos", "El nombre y la referencia son obligatorios.")
            return
        values = {
            "name": name,
            "reference": reference,
            "barcode": self.barcode_input.text().strip(),
            "category": self.category_input.text().strip(),
            "product_type": self.type_combo.currentText(),
            "sale_price": self.sale_price.value(),
            "cost": self.cost.value(),
            "sales_tax": self.sales_tax.value(),
            "purchase_tax": self.purchase_tax.value(),
            "stock": self.stock_input.value(),
            "min_stock": self.min_stock_input.value(),
            "supplier_id": self.supplier_combo.currentData(),
            "sale_enabled": int(self.sale_enabled.isChecked()),
            "purchase_enabled": int(self.purchase_enabled.isChecked()),
            "notes": self.notes_input.toPlainText().strip(),
        }
        try:
            self.current_id = self.database.save_product(values, self.current_id)
        except sqlite3.IntegrityError as error:
            QMessageBox.warning(
                self, "No se pudo guardar",
                f"La referencia debe ser única. Revisá los datos.\n\nDetalle: {error}",
            )
            return
        except sqlite3.Error as error:
            self.notify(f"No se pudo guardar el producto: {error}", error=True)
            return
        self.refresh_table(self.current_id)
        self.notify("Producto guardado.")

    def delete_product(self) -> None:
        if self.current_id is None:
            self.notify("Seleccioná un producto para eliminar.", error=True)
            return
        answer = QMessageBox.question(
            self,
            "Eliminar producto",
            "¿Querés eliminar este producto y su historial de actividad?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.delete_product(self.current_id)
        except sqlite3.Error as error:
            self.notify(f"No se pudo eliminar el producto: {error}", error=True)
            return
        self.current_id = None
        self.refresh_table()
        self.notify("Producto eliminado.")

    def adjust_stock(self) -> None:
        if self.current_id is None:
            self.notify("Seleccioná un producto primero.", error=True)
            return
        current = self.database.get_product(self.current_id)
        if current is None:
            self.notify("El producto seleccionado ya no existe.", error=True)
            return
        quantity, accepted = self._ask_stock_delta(int(current["stock"]))
        if not accepted:
            return
        if quantity == 0:
            self.notify("El ajuste debe ser distinto de cero.", error=True)
            return
        try:
            self.database.adjust_stock(self.current_id, quantity)
        except (sqlite3.Error, ValueError) as error:
            self.notify(f"No se pudo ajustar el stock: {error}", error=True)
            return
        self.refresh_table(self.current_id)
        self.notify("Stock actualizado.")

    def _ask_stock_delta(self, current_stock: int) -> tuple[int, bool]:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle("Ajustar stock")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(f"Existencia actual: {current_stock}. Usá un valor negativo para registrar una salida."))
        quantity = QSpinBox()
        quantity.setRange(-current_stock, 2_000_000_000)
        quantity.setValue(1)
        layout.addWidget(quantity)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return quantity.value(), accepted

    def replenish(self) -> None:
        if self.current_id is None:
            self.notify("Seleccioná un producto primero.", error=True)
            return
        product = self.database.get_product(self.current_id)
        if product is None:
            self.notify("El producto seleccionado ya no existe.", error=True)
            return
        amount = max(int(product["min_stock"]) - int(product["stock"]), 1)
        try:
            self.database.adjust_stock(self.current_id, amount)
        except (sqlite3.Error, ValueError) as error:
            self.notify(f"No se pudo reponer el producto: {error}", error=True)
            return
        self.refresh_table(self.current_id)
        self.notify(f"Se agregaron {amount} unidades al stock.")

    def export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar catálogo", str(APP_DIR / "productos.csv"), "CSV (*.csv)"
        )
        if not path:
            return
        try:
            products = self.database.list_products(
                self.search_input.text(), self.low_stock_checkbox.isChecked()
            )
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(
                    ["Referencia", "Producto", "Categoría", "Proveedor", "Stock",
                     "Stock mínimo", "Precio de venta", "Coste", "Código de barras"]
                )
                for product in products:
                    writer.writerow(
                        [
                            product["reference"], product["name"], product["category"],
                            product["supplier_name"] or "", product["stock"],
                            product["min_stock"], product["sale_price"], product["cost"],
                            product["barcode"],
                        ]
                    )
        except (OSError, csv.Error, sqlite3.Error) as error:
            self.notify(f"No se pudo exportar el catálogo: {error}", error=True)
            return
        self.notify(f"Catálogo exportado: {path}")


class SupplierPage(QWidget):
    def __init__(self, database: Database, on_change: Any, notify: Any) -> None:
        super().__init__()
        self.database = database
        self.on_change = on_change
        self.notify = notify
        self.current_id: int | None = None
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(14)
        header = QHBoxLayout()
        title = QLabel("Proveedores")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        self.new_button = make_button("Nuevo proveedor", "primary")
        self.save_button = make_button("Guardar", "primary")
        self.delete_button = make_button("Eliminar", "danger")
        header.addWidget(self.new_button)
        header.addWidget(self.save_button)
        header.addWidget(self.delete_button)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter, 1)
        catalog = QWidget()
        catalog_layout = QVBoxLayout(catalog)
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar proveedor, CUIT o email...")
        catalog_layout.addWidget(self.search_input)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Proveedor", "Email", "Productos"])
        set_table_defaults(self.table)
        catalog_layout.addWidget(self.table, 1)
        splitter.addWidget(catalog)

        editor = QWidget()
        form = QFormLayout(editor)
        form.setContentsMargins(24, 20, 24, 20)
        form.setVerticalSpacing(16)
        self.name_input = QLineEdit()
        self.tax_id_input = QLineEdit()
        self.email_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.address_input = QLineEdit()
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(150)
        add_form_row(form, "Nombre / razón social", self.name_input)
        add_form_row(form, "CUIT / identificación fiscal", self.tax_id_input)
        add_form_row(form, "Email", self.email_input)
        add_form_row(form, "Teléfono", self.phone_input)
        add_form_row(form, "Dirección", self.address_input)
        add_form_row(form, "Notas", self.notes_input)
        splitter.addWidget(editor)
        splitter.setSizes([430, 650])

        self.new_button.clicked.connect(self.new_supplier)
        self.save_button.clicked.connect(self.save_supplier)
        self.delete_button.clicked.connect(self.delete_supplier)
        self.search_input.textChanged.connect(self.refresh_table)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.refresh_table()

    def refresh_table(self, select_id: int | None = None) -> None:
        suppliers = self.database.list_suppliers(self.search_input.text())
        self._loading = True
        self.table.setRowCount(len(suppliers))
        selected_row = -1
        for row, supplier in enumerate(suppliers):
            name = QTableWidgetItem(supplier["name"])
            name.setData(Qt.ItemDataRole.UserRole, supplier["id"])
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(supplier["email"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(supplier["product_count"])))
            if supplier["id"] == select_id:
                selected_row = row
        if selected_row < 0 and suppliers:
            selected_row = 0
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self._loading = False
        if selected_row >= 0:
            item = self.table.item(selected_row, 0)
            if item is not None:
                supplier_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(supplier_id, int):
                    self.load_supplier(supplier_id)
        elif not suppliers:
            self.new_supplier()

    def _selection_changed(self) -> None:
        if self._loading:
            return
        selected = self.table.selectedItems()
        if selected:
            item = self.table.item(selected[0].row(), 0)
            if item is not None:
                supplier_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(supplier_id, int):
                    self.load_supplier(supplier_id)

    def load_supplier(self, supplier_id: int) -> None:
        supplier = self.database.get_supplier(supplier_id)
        if supplier is None:
            return
        self.current_id = supplier_id
        self.name_input.setText(supplier["name"])
        self.tax_id_input.setText(supplier["tax_id"])
        self.email_input.setText(supplier["email"])
        self.phone_input.setText(supplier["phone"])
        self.address_input.setText(supplier["address"])
        self.notes_input.setPlainText(supplier["notes"])

    def new_supplier(self) -> None:
        self.current_id = None
        self.name_input.clear()
        self.tax_id_input.clear()
        self.email_input.clear()
        self.phone_input.clear()
        self.address_input.clear()
        self.notes_input.clear()
        self.name_input.setFocus()

    def save_supplier(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Dato obligatorio", "Ingresá el nombre del proveedor.")
            return
        values = {
            "name": name,
            "tax_id": self.tax_id_input.text().strip(),
            "email": self.email_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "address": self.address_input.text().strip(),
            "notes": self.notes_input.toPlainText().strip(),
        }
        try:
            self.current_id = self.database.save_supplier(values, self.current_id)
        except sqlite3.Error as error:
            self.notify(f"No se pudo guardar el proveedor: {error}", error=True)
            return
        self.refresh_table(self.current_id)
        self.on_change()
        self.notify("Proveedor guardado.")

    def delete_supplier(self) -> None:
        if self.current_id is None:
            self.notify("Seleccioná un proveedor para eliminar.", error=True)
            return
        product_count = self.database.connection.execute(
            "SELECT COUNT(*) FROM products WHERE supplier_id = ?", (self.current_id,)
        ).fetchone()[0]
        message = "¿Querés eliminar este proveedor?"
        if product_count:
            message += f"\n{product_count} producto(s) quedarán sin proveedor asignado."
        answer = QMessageBox.question(
            self, "Eliminar proveedor", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.delete_supplier(self.current_id)
        except sqlite3.Error as error:
            self.notify(f"No se pudo eliminar el proveedor: {error}", error=True)
            return
        self.current_id = None
        self.refresh_table()
        self.on_change()
        self.notify("Proveedor eliminado.")
