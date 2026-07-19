"""Configuración de compilación de KBKA SHOP con cx_Freeze.

Versión oficial: 2.1.1

Este archivo valida los recursos obligatorios, incluye los módulos y paquetes
necesarios, genera el ejecutable de Windows y construye un instalador MSI.
La impresión utiliza PyQt6.QtPrintSupport, por lo que no requiere pywin32,
win32ui, pythoncom ni mfc140u.dll.
"""

from __future__ import annotations

import os
from pathlib import Path

from cx_Freeze import Executable, setup


# Directorio raíz utilizado como base para código, assets y salida del instalador.
ROOT = Path(__file__).resolve().parent
APP_NAME = "KBKA SHOP - Gestor de Etiquetas"
APP_VERSION = "2.1.1"
TARGET_NAME = "GestorEtiquetas"

ASSETS_DIR = ROOT / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
ICON_PATH = ICONS_DIR / "KBKA.ico"


def comprobar_archivos() -> None:
    """Detiene la compilación si falta código o algún recurso esencial."""
    requeridos = [
        ROOT / "main.py",
        ROOT / "envios.py",
        ROOT / "modelos.py",
        ASSETS_DIR,
        ICON_PATH,
        ASSETS_DIR / "db" / "sepomex_consolidado.csv",
        ASSETS_DIR / "headers" / "header_fondo_oscuro.png",
        ASSETS_DIR / "headers" / "header_fondo_blanco.png",
        ICONS_DIR / "engranaje.png",
        ICONS_DIR / "guardar.png",
        ICONS_DIR / "imprimir.png",
        ICONS_DIR / "limpiar.png",
        ICONS_DIR / "cliente.png",
        ICONS_DIR / "celular.png",
        ICONS_DIR / "ubicacion.png",
        ICONS_DIR / "envio.png",
        ICONS_DIR / "vista_previa.png",
        ICONS_DIR / "problema.png",
        ICONS_DIR / "lupa.png",
        ICONS_DIR / "pesos.png",
        ICONS_DIR / "foco.png",
        ICONS_DIR / "eliminar.png",
        ICONS_DIR / "editar_cliente.png",
        ICONS_DIR / "agregar.png",
        ICONS_DIR / "subir.png",
        ICONS_DIR / "bajar.png",
        ICONS_DIR / "modelo.png",
    ]

    datos_modelos_disponible = any(
        ruta.exists()
        for ruta in (
            ICONS_DIR / "datos_modelos.png",
            ICONS_DIR / "datos_modelos",
        )
    )

    faltantes = [ruta for ruta in requeridos if not ruta.exists()]
    if not datos_modelos_disponible:
        faltantes.append(ICONS_DIR / "datos_modelos.png")
    if faltantes:
        lista = "\n".join(f"  - {ruta.relative_to(ROOT)}" for ruta in faltantes)
        raise SystemExit(
            "\nNo se puede generar el ejecutable porque faltan archivos:\n"
            f"{lista}\n\n"
            "Copia la carpeta assets original junto a estos cuatro archivos "
            "y vuelve a ejecutar la compilación.\n"
        )


comprobar_archivos()

# Opciones del ejecutable congelado: dependencias Python, recursos y runtime de C++.
build_exe_options = {
    "includes": [
        "envios",
        "modelos",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtPrintSupport",
        "qrcode.image.pil",
    ],
    "packages": [
        "PyQt6",
        "PIL",
        "pandas",
        "reportlab",
        "qrcode",
    ],
    "include_files": [
        (str(ASSETS_DIR), "assets"),
    ],
    "include_msvcr": True,
    "excludes": [
        "tkinter",
        "unittest",
    ],
    "optimize": 1,
}

# Metadatos y comportamiento del instalador MSI. El upgrade_code debe conservarse.
bdist_msi_options = {
    "upgrade_code": "{A29D80B2-4B61-4A71-9BB3-80DC0C279A5F}",
    "product_name": APP_NAME,
    "product_version": APP_VERSION,
    "initial_target_dir": r"[ProgramFiles64Folder]KBKA SHOP\Gestor de Etiquetas",
    "install_icon": str(ICON_PATH),
    "all_users": True,
    "launch_on_finish": True,
    "output_name": f"KBKA_Gestor_Etiquetas_{APP_VERSION}_x64.msi",
    "summary_data": {
        "author": "KBKA SHOP",
        "comments": "Gestor unificado para generar etiquetas de envío y etiquetas de modelos.",
        "keywords": "KBKA, etiquetas, envíos, modelos, CEDIS",
    },
}

base = "console" if os.environ.get("KBKA_DEBUG") == "1" else "gui"

executables = [
    Executable(
        script="main.py",
        base=base,
        target_name=TARGET_NAME,
        icon=str(ICON_PATH),
        shortcut_name="Gestor de Etiquetas KBKA",
        shortcut_dir="DesktopFolder",
        copyright="© 2026 KBKA SHOP - Todos los derechos reservados",
    )
]

setup(
    name="KBKA-Gestor-Etiquetas",
    version=APP_VERSION,
    description="Gestor unificado de etiquetas de KBKA SHOP",
    author="KBKA SHOP",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
