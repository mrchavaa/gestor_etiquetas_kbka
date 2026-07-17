"""Configuración de compilación de KBKA SHOP con cx_Freeze."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cx_Freeze import Executable, setup


ROOT = Path(__file__).resolve().parent
APP_NAME = "KBKA SHOP - Centro de Etiquetas"
APP_VERSION = "2.0.0"
TARGET_NAME = "CentroEtiquetas"

ASSETS_DIR = ROOT / "assets"
ICON_PATH = ASSETS_DIR / "icons" / "KBKA.ico"
LICENSE_PATH = ROOT / "LICENSE_cx_Freeze.md"


def comprobar_archivos() -> None:
    """Detiene la compilación con un mensaje claro si faltan recursos."""
    requeridos = [
        ROOT / "main.py",
        ROOT / "envios.py",
        ROOT / "modelos.py",
        ASSETS_DIR,
        ICON_PATH,
        ASSETS_DIR / "db" / "sepomex_consolidado.csv",
        ASSETS_DIR / "headers" / "header_fondo_oscuro.png",
        ASSETS_DIR / "headers" / "header_fondo_blanco.png",
        LICENSE_PATH,
    ]

    faltantes = [ruta for ruta in requeridos if not ruta.exists()]
    if faltantes:
        lista = "\n".join(f"  - {ruta.relative_to(ROOT)}" for ruta in faltantes)
        raise SystemExit(
            "\nNo se puede generar el ejecutable porque faltan archivos:\n"
            f"{lista}\n\n"
            "Copia la carpeta assets original dentro de esta carpeta y "
            "vuelve a ejecutar el archivo .bat.\n"
        )


comprobar_archivos()

include_files = [
    (str(ASSETS_DIR), "assets"),
    (str(LICENSE_PATH), "licenses/LICENSE_cx_Freeze.md"),
]

build_exe_options = {
    # main.py abre estos módulos mediante importlib.import_module().
    "includes": [
        "envios",
        "modelos",
        "pythoncom",
        "pywintypes",
        "win32api",
        "win32print",
        "win32ui",
        "PIL.ImageWin",
        "qrcode.image.pil",
    ],
    "packages": [
        "PyQt6",
        "PIL",
        "pandas",
        "reportlab",
        "qrcode",
    ],
    "include_files": include_files,
    "include_msvcr": True,
    "excludes": [
        "tkinter",
        "unittest",
    ],
    "optimize": 1,
}

bdist_msi_options = {
    # No cambies este GUID en versiones futuras: permite actualizar el MSI.
    "upgrade_code": "{A29D80B2-4B61-4A71-9BB3-80DC0C279A5F}",
    "product_name": APP_NAME,
    "product_version": APP_VERSION,
    "initial_target_dir": (
        r"[ProgramFiles64Folder]KBKA SHOP\Centro de Etiquetas"
    ),
    "install_icon": str(ICON_PATH),
    "all_users": True,
    "launch_on_finish": True,
    "output_name": f"KBKA_Centro_Etiquetas_{APP_VERSION}_x64.msi",
    "summary_data": {
        "author": "KBKA SHOP",
        "comments": (
            "Sistema unificado para generar etiquetas de envío "
            "y etiquetas de modelos."
        ),
        "keywords": "KBKA, etiquetas, envíos, modelos, CEDIS",
    },
}

# KBKA_DEBUG=1 genera una aplicación con consola para diagnosticar errores.
base = "console" if os.environ.get("KBKA_DEBUG") == "1" else "gui"

executables = [
    Executable(
        script="main.py",
        base=base,
        target_name=TARGET_NAME,
        icon=str(ICON_PATH),
        shortcut_name="Centro de Etiquetas KBKA",
        shortcut_dir="DesktopFolder",
        copyright="© 2026 KBKA SHOP - Todos los derechos reservados",
    )
]

setup(
    name="KBKA-Centro-Etiquetas",
    version=APP_VERSION,
    description="Sistema unificado de etiquetas de KBKA SHOP",
    author="KBKA SHOP",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
