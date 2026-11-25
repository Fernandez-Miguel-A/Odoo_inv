# Odoo Inv

Aplicación de escritorio de facturación en PySide6, inspirada en la factura de
cliente de la imagen de referencia. Incluye una factura de demostración, cálculo
de descuentos e impuestos, almacenamiento local SQLite, registro de pagos,
notas de crédito, vista previa de impresión y paneles de resumen.

«Print & Send» publica la factura y abre la vista previa; desde allí se puede
imprimir o guardar como PDF. Esta versión no envía correos automáticamente.
El módulo de proveedores permite mantener un directorio persistente de empresas,
contactos, datos fiscales y de contacto, condiciones de pago, moneda preferida y
notas internas. Incluye búsqueda, filtros de activos/archivados y archivado
reversible. La gestión de facturas de compra y pagos a proveedores no está
incluida todavía.

## Requisitos

- Python 3.10 o posterior (se recomienda Python 3.13 para los comandos siguientes)
- PySide6

## Instalar y ejecutar

Desde la raíz del proyecto:

```powershell
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

La aplicación guarda sus datos exclusivamente en
`data/invoices.sqlite3`, dentro de la raíz de este proyecto. Esta ruta no depende
de `LOCALAPPDATA` ni del directorio personal del usuario.

## Pruebas

```powershell
py -3.13 -m unittest discover -s tests -t .. -v
```

El paquete y todo el código fuente de la aplicación están en [Odoo_inv](./Odoo_inv).