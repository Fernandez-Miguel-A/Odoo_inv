# Nexo · Gestión de productos y proveedores

Aplicación de escritorio hecha con Python, PySide6 y SQLite.

## Ejecutar

```powershell
python -m pip install -r requirements.txt
python main.py
```

La base de datos `gestor_productos.db` se crea en la carpeta de la aplicación.
Al iniciar por primera vez se cargan un producto y un proveedor de ejemplo.

## Funcionalidades

- Alta, edición, búsqueda, eliminación y exportación CSV de productos.
- Datos comerciales, impuestos, categorías, proveedor, código de barras y notas.
- Control de existencias, ajuste de entradas/salidas y reposición al mínimo.
- Alta, edición, búsqueda y eliminación de proveedores.
- Resumen de inventario, alertas de stock bajo e historial de actividad.
