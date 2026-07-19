# KBKA SHOP — Gestor de Etiquetas 2.1.1

## Archivos

- `main.py`: launcher, navegación, tema global y transición entre módulos.
- `envios.py`: clientes, SEPOMEX, etiquetas de envío, PDF e impresión.
- `modelos.py`: etiquetas individuales/listas de modelos, PDF e impresión.
- `setup.py`: configuración de cx_Freeze y generación del MSI.

Todos los módulos muestran la versión oficial **2.1.1** en “Información del Software”.

## Estructura requerida

Coloca los cuatro archivos junto a la carpeta `assets` original:

```text
proyecto/
├── main.py
├── envios.py
├── modelos.py
├── setup.py
└── assets/
    ├── db/
    ├── headers/
    ├── icons/
    └── images/
```

## Preparación del entorno

```powershell
python -m pip install --upgrade pip
python -m pip install cx-Freeze PyQt6 Pillow pandas reportlab qrcode
```

## Probar antes de empaquetar

```powershell
python main.py
```

## Generar instalador MSI limpio

```powershell
Remove-Item -Recurse -Force .\build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue
Remove-Item Env:KBKA_DEBUG -ErrorAction SilentlyContinue
python setup.py bdist_msi
```

El instalador se genera como:

```text
dist/KBKA_Gestor_Etiquetas_2.1.1_x64.msi
```

Para diagnosticar un error mostrando consola:

```powershell
$env:KBKA_DEBUG = "1"
python setup.py build
```
