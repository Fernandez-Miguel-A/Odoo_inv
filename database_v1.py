import csv
import sqlite3
import sys
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
DATABASE_PATH = APP_DIR / "gestor_productos.db"


def inserted_id(cursor: sqlite3.Cursor) -> int:
    row_id = cursor.lastrowid
    if row_id is None:
        raise sqlite3.DatabaseError("SQLite no devolvió el identificador de la fila creada.")
    return row_id


class Database:
    """SQLite persistence for the product and supplier catalog."""

    def __init__(self, path: Path = DATABASE_PATH) -> None:
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()
        self._seed_if_empty()

    def _create_schema(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    tax_id TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    address TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    reference TEXT NOT NULL UNIQUE,
                    barcode TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    product_type TEXT NOT NULL DEFAULT 'Bienes',
                    sale_price REAL NOT NULL DEFAULT 0,
                    cost REAL NOT NULL DEFAULT 0,
                    sales_tax REAL NOT NULL DEFAULT 0,
                    purchase_tax REAL NOT NULL DEFAULT 0,
                    stock INTEGER NOT NULL DEFAULT 0,
                    min_stock INTEGER NOT NULL DEFAULT 0,
                    supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
                    sale_enabled INTEGER NOT NULL DEFAULT 1,
                    purchase_enabled INTEGER NOT NULL DEFAULT 1,
                    notes TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def _seed_if_empty(self) -> None:
        count = self.connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count:
            return
        with self.connection:
            supplier_id = inserted_id(
                self.connection.execute(
                    """
                    INSERT INTO suppliers (name, email, phone, address, notes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "Suministros San Francisco",
                        "ventas@sanfrancisco.example",
                        "+54 11 5555-0100",
                        "Av. de la Industria 1250",
                        "Proveedor de muestra. Podés editarlo o eliminarlo.",
                    ),
                )
            )
            product_id = inserted_id(
                self.connection.execute(
                    """
                    INSERT INTO products (
                        name, reference, barcode, category, product_type, sale_price,
                        cost, sales_tax, purchase_tax, stock, min_stock, supplier_id,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Caja de administración de cables",
                        "FURN_5555",
                        "6016478556318",
                        "Oficina / Accesorios",
                        "Bienes",
                        100.00,
                        70.00,
                        15.0,
                        15.0,
                        90,
                        10,
                        supplier_id,
                        "Organizador de cables para escritorio.",
                    ),
                )
            )
            self.add_activity(product_id, "Producto de ejemplo creado")

    def add_activity(self, product_id: int, message: str) -> None:
        self.connection.execute(
            "INSERT INTO activity (product_id, message) VALUES (?, ?)",
            (product_id, message),
        )

    def list_products(self, search: str = "", low_stock: bool = False) -> list[sqlite3.Row]:
        conditions: list[str] = []
        params: list[Any] = []
        if search.strip():
            like = f"%{search.strip()}%"
            conditions.append(
                "(p.name LIKE ? OR p.reference LIKE ? OR p.barcode LIKE ? OR p.category LIKE ?)"
            )
            params.extend([like, like, like, like])
        if low_stock:
            conditions.append("p.stock <= p.min_stock")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self.connection.execute(
            f"""
            SELECT p.*, s.name AS supplier_name
            FROM products p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            {where}
            ORDER BY p.name COLLATE NOCASE
            """,
            params,
        ).fetchall()

    def get_product(self, product_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT p.*, s.name AS supplier_name
            FROM products p
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE p.id = ?
            """,
            (product_id,),
        ).fetchone()

    def save_product(self, values: dict[str, Any], product_id: int | None = None) -> int:
        fields = (
            "name", "reference", "barcode", "category", "product_type",
            "sale_price", "cost", "sales_tax", "purchase_tax", "stock",
            "min_stock", "supplier_id", "sale_enabled", "purchase_enabled", "notes",
        )
        data = tuple(values[field] for field in fields)
        with self.connection:
            if product_id is None:
                cursor = self.connection.execute(
                    f"""
                    INSERT INTO products ({", ".join(fields)})
                    VALUES ({", ".join("?" for _ in fields)})
                    """,
                    data,
                )
                product_id = inserted_id(cursor)
                self.add_activity(product_id, "Producto creado")
            else:
                assignments = ", ".join(f"{field} = ?" for field in fields)
                self.connection.execute(
                    f"""
                    UPDATE products
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (*data, product_id),
                )
                self.add_activity(product_id, "Ficha de producto actualizada")
        if product_id is None:
            raise RuntimeError("No se pudo determinar el identificador del producto guardado.")
        return product_id

    def delete_product(self, product_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM products WHERE id = ?", (product_id,))

    def adjust_stock(self, product_id: int, quantity: int) -> None:
        with self.connection:
            current = self.connection.execute(
                "SELECT stock FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            if current is None:
                raise ValueError("El producto ya no existe.")
            new_stock = int(current["stock"]) + quantity
            if new_stock < 0:
                raise ValueError("El stock no puede quedar por debajo de cero.")
            self.connection.execute(
                "UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_stock, product_id),
            )
            action = "entrada" if quantity > 0 else "salida"
            self.add_activity(product_id, f"Ajuste de stock: {action} de {abs(quantity)} unidades")

    def list_suppliers(self, search: str = "") -> list[sqlite3.Row]:
        if search.strip():
            like = f"%{search.strip()}%"
            return self.connection.execute(
                """
                SELECT s.*, COUNT(p.id) AS product_count
                FROM suppliers s
                LEFT JOIN products p ON p.supplier_id = s.id
                WHERE s.name LIKE ? OR s.tax_id LIKE ? OR s.email LIKE ?
                GROUP BY s.id
                ORDER BY s.name COLLATE NOCASE
                """,
                (like, like, like),
            ).fetchall()
        return self.connection.execute(
            """
            SELECT s.*, COUNT(p.id) AS product_count
            FROM suppliers s
            LEFT JOIN products p ON p.supplier_id = s.id
            GROUP BY s.id
            ORDER BY s.name COLLATE NOCASE
            """
        ).fetchall()

    def get_supplier(self, supplier_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()

    def save_supplier(self, values: dict[str, str], supplier_id: int | None = None) -> int:
        fields = ("name", "tax_id", "email", "phone", "address", "notes")
        data = tuple(values[field] for field in fields)
        with self.connection:
            if supplier_id is None:
                cursor = self.connection.execute(
                    f"""
                    INSERT INTO suppliers ({", ".join(fields)})
                    VALUES ({", ".join("?" for _ in fields)})
                    """,
                    data,
                )
                supplier_id = inserted_id(cursor)
            else:
                assignments = ", ".join(f"{field} = ?" for field in fields)
                self.connection.execute(
                    f"UPDATE suppliers SET {assignments} WHERE id = ?",
                    (*data, supplier_id),
                )
        if supplier_id is None:
            raise RuntimeError("No se pudo determinar el identificador del proveedor guardado.")
        return supplier_id

    def delete_supplier(self, supplier_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))

    def summary(self) -> dict[str, int | float]:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS products,
                   COALESCE(SUM(stock), 0) AS units,
                   COALESCE(SUM(stock * cost), 0) AS stock_value,
                   SUM(CASE WHEN stock <= min_stock THEN 1 ELSE 0 END) AS low_stock
            FROM products
            """
        ).fetchone()
        supplier_count = self.connection.execute(
            "SELECT COUNT(*) FROM suppliers"
        ).fetchone()[0]
        return {
            "products": int(row["products"]),
            "units": int(row["units"]),
            "stock_value": float(row["stock_value"]),
            "low_stock": int(row["low_stock"] or 0),
            "suppliers": int(supplier_count),
        }

    def recent_activity(self, limit: int = 8) -> list[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT a.message, a.created_at, p.name AS product_name
            FROM activity a
            LEFT JOIN products p ON p.id = a.product_id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def close(self) -> None:
        self.connection.close()

