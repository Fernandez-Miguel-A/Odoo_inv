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

import os, sys
from main_gui import MainWindow, apply_styles
from database_v1 import Database


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Nexo")
    apply_styles(app)
    try:
        database = Database()
    except sqlite3.Error as error:
        QMessageBox.critical(None, "Error de base de datos", f"No se pudo abrir la base SQLite:\n{error}")
        return 1
    window = MainWindow(database)
    app.aboutToQuit.connect(database.close)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())