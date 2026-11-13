from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from Odoo_inv.database import InvoiceDatabase
from Odoo_inv.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Odoo Inv")
    app.setOrganizationName("Odoo Inv")
    window = MainWindow(InvoiceDatabase())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
