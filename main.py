"""
KBKA SHOP - Centro de Etiquetas
Launcher unificado para etiquetas de envío y etiquetas CEDIS/modelos.
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


APP_VERSION = "2.0.0"
APP_TITLE = "KBKA SHOP - Centro de Etiquetas"
ASSETS_DIR = "assets"
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
HEADERS_DIR = os.path.join(ASSETS_DIR, "headers")


def obtener_ruta_recurso(ruta_relativa: str) -> str:
    """Devuelve la ruta correcta de un recurso en desarrollo o compilado."""
    if hasattr(sys, "_MEIPASS"):
        # Compatibilidad con PyInstaller.
        base_path = sys._MEIPASS
    elif getattr(sys, "frozen", False):
        # cx_Freeze coloca los archivos incluidos junto al ejecutable.
        base_path = sys.prefix
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, ruta_relativa)
def buscar_icono_asset(nombre_archivo: str) -> str:
    """
    Busca un icono primero en assets/ y después en assets/icons/.

    Esto permite utilizar los recursos compartidos del proyecto unificado
    sin exigir que todos estén dentro de la misma subcarpeta.
    """
    candidatos = (
        os.path.join(ASSETS_DIR, nombre_archivo),
        os.path.join(ICONS_DIR, nombre_archivo),
    )

    for ruta_relativa in candidatos:
        ruta = obtener_ruta_recurso(ruta_relativa)
        if os.path.exists(ruta):
            return ruta

    return obtener_ruta_recurso(candidatos[0])


def cargar_pixmap_adaptado_tema(
    ruta_icono: str,
    tema_oscuro: bool,
    ancho: int,
    alto: int,
) -> QPixmap:
    """
    Carga un icono y adapta su color al tema.

    Los archivos originales son negros. En modo oscuro se invierten a blanco,
    conservando el canal alpha y la transparencia del PNG. En modo claro se
    mantienen con su color original.
    """
    if not ruta_icono or not os.path.exists(ruta_icono):
        return QPixmap()

    pixmap = QPixmap(ruta_icono)
    if pixmap.isNull():
        return QPixmap()

    pixmap = pixmap.scaled(
        ancho,
        alto,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    if tema_oscuro:
        imagen = pixmap.toImage().convertToFormat(
            QImage.Format.Format_ARGB32
        )
        imagen.invertPixels(QImage.InvertMode.InvertRgb)
        pixmap = QPixmap.fromImage(imagen)

    return pixmap


def cargar_icono_adaptado_tema(
    ruta_icono: str,
    tema_oscuro: bool,
    ancho: int,
    alto: int,
) -> QIcon:
    pixmap = cargar_pixmap_adaptado_tema(
        ruta_icono,
        tema_oscuro,
        ancho,
        alto,
    )
    return QIcon(pixmap) if not pixmap.isNull() else QIcon()


def cargar_pixmap_colorizado(
    ruta_icono: str,
    color: str,
    ancho: int,
    alto: int,
) -> QPixmap:
    """
    Colorea un PNG monocromático conservando su transparencia.

    Se usa para que los iconos grandes de los módulos sean claros u oscuros
    según el tema y cambien al rojo corporativo durante el hover.
    """
    if not ruta_icono or not os.path.exists(ruta_icono):
        return QPixmap()

    pixmap = QPixmap(ruta_icono)
    if pixmap.isNull():
        return QPixmap()

    pixmap = pixmap.scaled(
        ancho,
        alto,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    imagen = pixmap.toImage().convertToFormat(
        QImage.Format.Format_ARGB32
    )
    color_destino = QColor(color)

    for y in range(imagen.height()):
        for x in range(imagen.width()):
            original = imagen.pixelColor(x, y)
            if original.alpha() == 0:
                continue

            nuevo = QColor(color_destino)
            nuevo.setAlpha(original.alpha())
            imagen.setPixelColor(x, y, nuevo)

    return QPixmap.fromImage(imagen)


def configurar_app_id() -> None:
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "kbkashop.etiquetas.unificado.2.0"
        )
    except Exception:
        pass


def obtener_db_path() -> str:
    appdata = os.getenv("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "KBKA_Shop", "kbka_data.db")


class ModuleCard(QFrame):
    clicked = pyqtSignal()

    def __init__(
        self,
        title: str,
        description: str,
        icon_filename: str,
        eyebrow: str,
        metadata: str,
        fallback_icon: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.icon_filename = icon_filename
        self.fallback_icon = fallback_icon
        self.tema_oscuro = True
        self._hovered = False

        self.setObjectName("module_card")
        self.setProperty("hovered", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(470, 365)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 9)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)
        self._shadow = shadow

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(36, 28, 36, 28)
        content_layout.setSpacing(15)
        layout.addLayout(content_layout, 1)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(25)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(9)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("module_title")
        self.title_label.setWordWrap(True)
        text_column.addWidget(self.title_label)

        top_row.addLayout(text_column, 1)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("module_icon")
        self.icon_label.setFixedSize(104, 104)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setText(self.fallback_icon)
        top_row.addWidget(
            self.icon_label,
            alignment=(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignTop
            ),
        )

        content_layout.addLayout(top_row)

        self.description_label = QLabel(description)
        self.description_label.setObjectName("module_description")
        self.description_label.setWordWrap(True)
        self.description_label.setMinimumHeight(180)
        content_layout.addWidget(self.description_label)

        metadata_label = QLabel(metadata)
        metadata_label.setObjectName("module_metadata")
        metadata_label.setWordWrap(True)
        content_layout.addWidget(metadata_label)

        content_layout.addStretch()

    def _actualizar_icono(self) -> None:
        path = buscar_icono_asset(self.icon_filename)

        if self._hovered:
            color = "#E51A1A"
        elif self.tema_oscuro:
            color = "#D8D8DA"
        else:
            color = "#353A40"

        pixmap = cargar_pixmap_colorizado(
            path,
            color,
            88,
            88,
        )

        if not pixmap.isNull():
            self.icon_label.setText("")
            self.icon_label.setPixmap(pixmap)
        else:
            self.icon_label.clear()
            self.icon_label.setText(self.fallback_icon)

    def actualizar_icono_tema(self, tema_oscuro: bool) -> None:
        self.tema_oscuro = tema_oscuro
        self._actualizar_icono()

    def _actualizar_hover(self, hovered: bool) -> None:
        self._hovered = hovered
        self.setProperty("hovered", hovered)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

        self._shadow.setBlurRadius(40 if hovered else 28)
        self._shadow.setOffset(0, 13 if hovered else 9)
        self._actualizar_icono()

    def enterEvent(self, event) -> None:
        self._actualizar_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._actualizar_hover(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

class NavegacionModuloMixin:
    """Agrega navegación al inicio a las ventanas originales."""

    def __init__(self, launcher, tema_inicial: bool):
        self._launcher = launcher
        self._regresando_inicio = False
        super().__init__()

        # Sincronizar el tema elegido en el launcher.
        self.tema_oscuro = tema_inicial
        if hasattr(self, "btn_tema"):
            self._actualizar_icono_tema_modulo()
        if hasattr(self, "aplicar_estilos"):
            self.aplicar_estilos()
        if hasattr(self, "actualizar_iconos_footer"):
            self.actualizar_iconos_footer()
        if hasattr(self, "actualizar_header_logo"):
            self.actualizar_header_logo()
        if hasattr(self, "actualizar_vista_previa"):
            self.actualizar_vista_previa()

        self._crear_boton_inicio()
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

    def _actualizar_icono_tema_modulo(self) -> None:
        """Actualiza el icono de tema según el modo activo."""
        if not hasattr(self, "btn_tema"):
            return

        nombre_icono = (
            "modo_claro.png"
            if self.tema_oscuro
            else "modo_oscuro.png"
        )
        ruta_icono = buscar_icono_asset(nombre_icono)
        color_icono = "#FFFFFF" if self.tema_oscuro else "#2B2B2B"

        self.btn_tema.setText("")
        self.btn_tema.setObjectName("btn_help")
        self.btn_tema.setFixedSize(45, 45)
        self.btn_tema.setIconSize(QSize(24, 24))
        self.btn_tema.setToolTip(
            "Cambiar a modo claro"
            if self.tema_oscuro
            else "Cambiar a modo oscuro"
        )

        pixmap = cargar_pixmap_colorizado(
            ruta_icono,
            color_icono,
            24,
            24,
        )
        self.btn_tema.setIcon(QIcon(pixmap))

        self.btn_tema.style().unpolish(self.btn_tema)
        self.btn_tema.style().polish(self.btn_tema)
        self.btn_tema.update()

    def _crear_boton_inicio(self) -> None:
        """
        Agrega Home al footer, inmediatamente antes del botón de tema.

        De esta forma los controles globales quedan agrupados y el header
        permanece dedicado únicamente a la identidad visual de KBKA SHOP.
        """
        if not hasattr(self, "btn_tema"):
            return

        footer_widget = self.btn_tema.parentWidget()
        footer_layout = footer_widget.layout() if footer_widget else None
        if footer_layout is None:
            return

        self.btn_volver_inicio = QPushButton("", footer_widget)
        # Usa exactamente el mismo estilo circular de Ayuda, Información y Tema.
        self.btn_volver_inicio.setObjectName("btn_help")
        self.btn_volver_inicio.setFixedSize(45, 45)
        self.btn_volver_inicio.setIconSize(QSize(24, 24))
        self.btn_volver_inicio.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.btn_volver_inicio.setToolTip(
            "Regresar al Centro de Etiquetas"
        )
        self.btn_volver_inicio.clicked.connect(self.volver_al_inicio)

        self._actualizar_icono_inicio()

        indice_tema = footer_layout.indexOf(self.btn_tema)
        if indice_tema < 0:
            indice_tema = 0

        footer_layout.insertWidget(indice_tema, self.btn_volver_inicio)
        self.btn_volver_inicio.show()

    def _actualizar_icono_inicio(self) -> None:
        """Actualiza home.png según el tema activo."""
        if not hasattr(self, "btn_volver_inicio"):
            return

        ruta_icono = buscar_icono_asset("home.png")
        color_icono = "#FFFFFF" if self.tema_oscuro else "#2B2B2B"
        pixmap = cargar_pixmap_colorizado(
            ruta_icono,
            color_icono,
            24,
            24,
        )
        self.btn_volver_inicio.setIcon(QIcon(pixmap))


    def alternar_tema(self) -> None:
        super().alternar_tema()
        self._actualizar_icono_tema_modulo()
        self._actualizar_icono_inicio()

    def volver_al_inicio(self) -> None:
        self._regresando_inicio = True
        self._launcher.regresar_desde_modulo(self.tema_oscuro)
        self.close()

    def closeEvent(self, event) -> None:
        if not self._regresando_inicio:
            self._launcher.regresar_desde_modulo(self.tema_oscuro)
        event.accept()


class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = QSettings("KBKA SHOP", "Etiquetas Unificado")
        self.tema_oscuro = self._leer_tema()
        self.modulo_actual = None

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1100, 720)

        icon_path = obtener_ruta_recurso(
            os.path.join(ICONS_DIR, "KBKA.ico")
        )
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._crear_interfaz()
        self._aplicar_tema()
        self._actualizar_badges()
        self._actualizar_impresora()

        # Animar directamente la opacidad de la ventana evita combinar un
        # QGraphicsOpacityEffect con las sombras de las tarjetas. Los efectos
        # gráficos anidados provocaban los avisos "Painter not active".
        self.fade_animation = QPropertyAnimation(
            self,
            b"windowOpacity",
        )
        self.fade_animation.setDuration(380)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)
        self.fade_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

    def _leer_tema(self) -> bool:
        value = self.settings.value("tema_oscuro", True)
        if isinstance(value, bool):
            return value
        return str(value).lower() not in {"false", "0", "no"}

    def _crear_interfaz(self) -> None:
        central = QWidget()
        central.setObjectName("launcher_root")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ==================== HEADER HORIZONTAL ====================
        self.launcher_header = QFrame()
        self.launcher_header.setObjectName("launcher_header")
        self.launcher_header.setFixedHeight(150)

        header_layout = QHBoxLayout(self.launcher_header)
        header_layout.setContentsMargins(42, 14, 42, 14)
        header_layout.setSpacing(0)
        header_layout.addStretch()

        self.logo_label = QLabel()
        self.logo_label.setObjectName("launcher_logo")
        self.logo_label.setFixedSize(320, 120)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.logo_label)

        header_layout.addStretch()

        root.addWidget(self.launcher_header)

        # ==================== CONTENIDO PRINCIPAL ====================
        content = QWidget()
        content.setObjectName("launcher_content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(46, 22, 46, 24)
        content_layout.setSpacing(0)

        cards_layout = QHBoxLayout()
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(28)

        self.card_envios = ModuleCard(
            "ETIQUETAS DE ENVÍO",
            (
                "Genera etiquetas para paquetes destinados a paqueterías "
                "y rutas de entrega.\n\n"
                "• Datos del cliente\n"
                "• Dirección completa\n"
                "• Modalidad y condición del envío\n"
                "• Monto total del pedido\n"
                "• Clientes frecuentes\n"
                "• Etiquetas listas para imprimir"
            ),
            "camion.png",
            "",
            "GRAN CAÑÓN   ·   TUXPAN   ·   OTRAS RUTAS",
        )
        self.card_envios.clicked.connect(
            lambda: self.abrir_modulo(
                "envios",
                "EtiquetasApp",
                "envios",
            )
        )
        cards_layout.addWidget(self.card_envios, 1)

        self.card_modelos = ModuleCard(
            "ETIQUETAS DE MODELOS",
            (
                "Genera etiquetas para identificar cajas de displays "
                "y organizar el producto.\n\n"
                "• Etiquetas individuales\n"
                "• Etiquetas con varios modelos\n"
                "• Marca, modelo y calidad\n"
                "• Generación y tipo de marco\n"
                "• Organización de producto\n"
                "• Control de inventario"
            ),
            "etiqueta.png",
            "",
            "DISPLAYS   ·   PRODUCTO   ·   INVENTARIO",
        )
        self.card_modelos.clicked.connect(
            lambda: self.abrir_modulo(
                "modelos",
                "CEDISEtiquetasApp",
                "modelos",
            )
        )
        cards_layout.addWidget(self.card_modelos, 1)

        content_layout.addLayout(cards_layout, 1)
        root.addWidget(content, 1)

        # ==================== FOOTER COMPACTO ====================
        self.status_card = QFrame()
        self.status_card.setObjectName("launcher_footer_bar")
        self.status_card.setFixedHeight(64)

        status_layout = QGridLayout(self.status_card)
        status_layout.setContentsMargins(42, 10, 42, 10)
        status_layout.setHorizontalSpacing(18)
        status_layout.setColumnStretch(0, 1)
        status_layout.setColumnStretch(1, 1)
        status_layout.setColumnStretch(2, 1)

        printer_container = QWidget()
        printer_container.setObjectName("footer_transparent")
        printer_layout = QHBoxLayout(printer_container)
        printer_layout.setContentsMargins(0, 0, 0, 0)
        printer_layout.setSpacing(9)

        self.printer_icon_label = QLabel()
        self.printer_icon_label.setObjectName("printer_status_icon")
        self.printer_icon_label.setFixedSize(25, 25)
        self.printer_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        printer_layout.addWidget(self.printer_icon_label)

        self.printer_label = QLabel()
        self.printer_label.setObjectName("printer_status")
        printer_layout.addWidget(self.printer_label)
        printer_layout.addStretch()

        status_layout.addWidget(
            printer_container,
            0,
            0,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        copyright_label = QLabel(
            "© 2026 KBKA SHOP - Todos los derechos reservados"
        )
        copyright_label.setObjectName("launcher_footer")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(copyright_label, 0, 1)

        right_container = QWidget()
        right_container.setObjectName("footer_transparent")
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)
        right_layout.addStretch()

        self.btn_info = QPushButton()
        self.btn_info.setObjectName("launcher_info_button")
        self.btn_info.setFixedSize(45, 45)
        self.btn_info.setIconSize(QSize(24, 24))
        self.btn_info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_info.setToolTip("Acerca del software")

        info_path = buscar_icono_asset("informacion.png")
        info_color = "#FFFFFF" if self.tema_oscuro else "#2B2B2B"
        info_pixmap = cargar_pixmap_colorizado(
            info_path,
            info_color,
            24,
            24,
        )
        self.btn_info.setIcon(QIcon(info_pixmap))
        self.btn_info.clicked.connect(self.abrir_informacion)
        right_layout.addWidget(self.btn_info)

        self.btn_tema = QPushButton()
        self.btn_tema.setObjectName("launcher_theme_button")
        self.btn_tema.setFixedSize(45, 45)
        self.btn_tema.setIconSize(QSize(24, 24))
        self.btn_tema.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tema.setToolTip(
            "Cambiar a modo claro"
            if self.tema_oscuro
            else "Cambiar a modo oscuro"
        )
        self.btn_tema.clicked.connect(self.alternar_tema)
        right_layout.addWidget(self.btn_tema)

        status_layout.addWidget(
            right_container,
            0,
            2,
            alignment=Qt.AlignmentFlag.AlignRight,
        )

        root.addWidget(self.status_card)

        self._actualizar_icono_impresora()
    def _cargar_logo(self) -> None:
        filename = (
            "header_fondo_oscuro.png"
            if self.tema_oscuro
            else "header_fondo_blanco.png"
        )
        path = obtener_ruta_recurso(
            os.path.join(HEADERS_DIR, filename)
        )
        if os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.logo_label.setPixmap(
                    pixmap.scaled(
                        300,
                        120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return

        self.logo_label.setText("KBKA SHOP")

    def _actualizar_icono_tema_launcher(self) -> None:
        """Muestra el icono correspondiente a la acción de cambio de tema."""
        nombre_icono = (
            "modo_claro.png"
            if self.tema_oscuro
            else "modo_oscuro.png"
        )
        ruta_icono = buscar_icono_asset(nombre_icono)

        self.btn_tema.setText("")
        self.btn_tema.setToolTip(
            "Cambiar a modo claro"
            if self.tema_oscuro
            else "Cambiar a modo oscuro"
        )

        # En modo oscuro el icono permanece blanco; en modo claro,
        # se muestra oscuro para conservar contraste con el botón claro.
        icono_tema_color = "#FFFFFF" if self.tema_oscuro else "#2B2B2B"
        icono_tema_pixmap = cargar_pixmap_colorizado(
            ruta_icono,
            icono_tema_color,
            24,
            24,
        )
        self.btn_tema.setIcon(QIcon(icono_tema_pixmap))

    def _aplicar_tema(self) -> None:
        if self.tema_oscuro:
            bg = "#1E1E1F"
            header_bg = "#1E1E1F"
            surface = "#262628"
            surface_hover = "#2B2B2E"
            text = "#F4F4F5"
            muted = "#B0B0B5"
            border = "#3C3C40"
            footer_bg = "#19191A"
            button_bg = "#303033"
            button_hover = "#39393D"
        else:
            bg = "#F3F5F7"
            header_bg = "#FFFFFF"
            surface = "#FFFFFF"
            surface_hover = "#FFFDFD"
            text = "#20242A"
            muted = "#69727D"
            border = "#D8DDE3"
            footer_bg = "#FFFFFF"
            button_bg = "#F0F2F5"
            button_hover = "#E7EAEE"

        self._actualizar_icono_tema_launcher()

        self.setStyleSheet(
            f"""
            QWidget#launcher_root {{
                background-color: {bg};
                font-family: 'Segoe UI', sans-serif;
                color: {text};
            }}

            QFrame#launcher_header {{
                background-color: {header_bg};
                border: none;
                border-bottom: 3px solid #A30302;
            }}

            QLabel#launcher_logo {{
                background-color: transparent;
                border: none;
            }}

            QWidget#launcher_content {{
                background-color: {bg};
            }}

            QFrame#module_card {{
                background-color: {surface};
                border: 1px solid {border};
                border-radius: 18px;
            }}

            QFrame#module_card[hovered="true"] {{
                background-color: {surface_hover};
                border: 2px solid #E51A1A;
            }}

            QLabel#module_icon {{
                background-color: transparent;
                border: none;
                padding: 0px;
            }}

            QLabel#module_title {{
                color: {text};
                font-size: 18pt;
                font-weight: 800;
                letter-spacing: 0.4px;
                background-color: transparent;
                border: none;
            }}

            QLabel#module_description {{
                color: {muted};
                font-size: 10.5pt;
                line-height: 1.5;
                background-color: transparent;
                border: none;
            }}

            QLabel#module_metadata {{
                color: {"#C8C8CC" if self.tema_oscuro else "#525A64"};
                font-size: 8.8pt;
                font-weight: 700;
                letter-spacing: 0.7px;
                background-color: transparent;
                border: none;
            }}
            QPushButton#launcher_info_button {{
                background-color: {"#2A2A2A" if self.tema_oscuro else "#ECEFF2"};
                color: {"#FFFFFF" if self.tema_oscuro else "#2B2B2B"};
                border: {"none" if self.tema_oscuro else "1px solid #D7DCE1"};
                border-radius: 22px;
                padding: 5px;
            }}

            QPushButton#launcher_info_button:hover {{
                background-color: #CD0403;
                color: #FFFFFF;
                border: none;
            }}

            QPushButton#launcher_info_button:pressed {{
                background-color: #A30302;
                color: #FFFFFF;
                border: none;
            }}

            QPushButton#launcher_theme_button {{
                background-color: {"#2A2A2A" if self.tema_oscuro else "#ECEFF2"};
                color: {"#FFFFFF" if self.tema_oscuro else "#2B2B2B"};
                border: {"none" if self.tema_oscuro else "1px solid #D7DCE1"};
                border-radius: 22px;
                padding: 5px;
            }}

            QPushButton#launcher_theme_button:hover {{
                background-color: #CD0403;
                color: #FFFFFF;
                border: none;
            }}

            QPushButton#launcher_theme_button:pressed {{
                background-color: #A30302;
                color: #FFFFFF;
                border: none;
            }}

            QFrame#launcher_footer_bar {{
                background-color: {footer_bg};
                border: none;
                border-top: 1px solid {border};
            }}

            QWidget#footer_transparent {{
                background-color: transparent;
            }}

            QLabel#printer_status_icon {{
                background-color: transparent;
                border: none;
            }}

            QLabel#printer_status,
            QLabel#launcher_footer {{
                color: {muted};
                font-size: 8.8pt;
                background-color: transparent;
                border: none;
            }}

            """
        )

        self._cargar_logo()
        self._actualizar_icono_impresora()

        if hasattr(self, "btn_info"):
            info_path = buscar_icono_asset("informacion.png")
            info_color = "#FFFFFF" if self.tema_oscuro else "#2B2B2B"
            info_pixmap = cargar_pixmap_colorizado(
                info_path,
                info_color,
                24,
                24,
            )
            self.btn_info.setIcon(QIcon(info_pixmap))

        if hasattr(self, "card_envios"):
            self.card_envios.actualizar_icono_tema(self.tema_oscuro)
        if hasattr(self, "card_modelos"):
            self.card_modelos.actualizar_icono_tema(self.tema_oscuro)
    def _actualizar_badges(self) -> None:
        # Se conserva el último módulo en configuración, pero ya no se muestra.
        return

    def _actualizar_icono_impresora(self) -> None:
        """Actualiza impresora.png para que contraste con el tema."""
        if not hasattr(self, "printer_icon_label"):
            return

        ruta_icono = buscar_icono_asset("impresora.png")
        pixmap = cargar_pixmap_adaptado_tema(
            ruta_icono,
            self.tema_oscuro,
            20,
            20,
        )
        self.printer_icon_label.setPixmap(pixmap)

    def _actualizar_impresora(self) -> None:
        printer = None
        db_path = obtener_db_path()

        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT valor
                    FROM configuracion
                    WHERE parametro = ?
                    """,
                    ("impresora_predeterminada",),
                )
                row = cursor.fetchone()
                conn.close()
                printer = row[0] if row else None
        except Exception:
            printer = None

        if printer:
            self.printer_label.setText(
                f"Impresora configurada: {printer}"
            )
        else:
            self.printer_label.setText(
                "Impresora configurada: pendiente"
            )


    def abrir_informacion(self) -> None:
        """Muestra la información del sistema mediante KBKADialog."""
        mensaje = (
            "KBKA SHOP\n"
            f"Centro de Etiquetas v{APP_VERSION}\n\n"
            "Sistema para la generación e impresión de etiquetas "
            "de envío y etiquetas de modelos para la operación "
            "de KBKA SHOP.\n\n"
            "Desarrollado por:\n"
            "Ángel Alexander Ramírez Navarro (Chava)\n\n"
            "© 2026 KBKA SHOP\n"
            "Todos los derechos reservados."
        )

        try:
            # Reutiliza el mismo diálogo profesional empleado por envios.py.
            from envios import KBKADialog
        except ImportError:
            # Respaldo por si el módulo de envíos no estuviera disponible.
            from modelos import KBKADialog

        KBKADialog.info(
            self,
            "Información del Software",
            mensaje,
        )
    def alternar_tema(self) -> None:
        self.tema_oscuro = not self.tema_oscuro
        self.settings.setValue("tema_oscuro", self.tema_oscuro)
        self._aplicar_tema()

    def abrir_modulo(
        self,
        module_name: str,
        class_name: str,
        key: str,
    ) -> None:
        self.settings.setValue("ultimo_modulo", key)
        self._actualizar_badges()

        try:
            module = importlib.import_module(module_name)
            configurar_app_id()
            base_class = getattr(module, class_name)

            class VentanaIntegrada(
                NavegacionModuloMixin,
                base_class,
            ):
                pass

            self.hide()
            self.modulo_actual = VentanaIntegrada(
                self,
                self.tema_oscuro,
            )
            self.modulo_actual.setWindowTitle(
                (
                    "KBKA SHOP - Etiquetas de Envío"
                    if key == "envios"
                    else "KBKA SHOP - Etiquetas de Modelos"
                )
            )
            self.modulo_actual.showMaximized()
            self.modulo_actual.raise_()
            self.modulo_actual.activateWindow()

        except Exception as error:
            self.modulo_actual = None
            self.show()
            QMessageBox.critical(
                self,
                "No fue posible abrir el módulo",
                (
                    f"Ocurrió un error al abrir {key}:\n\n"
                    f"{error}"
                ),
            )

    def regresar_desde_modulo(self, tema_oscuro: bool) -> None:
        self.tema_oscuro = bool(tema_oscuro)
        self.settings.setValue("tema_oscuro", self.tema_oscuro)
        self.modulo_actual = None
        self._aplicar_tema()
        self._actualizar_impresora()
        self.showMaximized()
        self.raise_()
        self.activateWindow()
        self.fade_animation.stop()
        self.setWindowOpacity(1.0)

    def centrar_en_pantalla(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._actualizar_impresora()

        self.fade_animation.stop()
        self.setWindowOpacity(0.0)
        self.fade_animation.start()


def main() -> None:
    configurar_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName("KBKA SHOP - Centro de Etiquetas")
    app.setOrganizationName("KBKA SHOP")

    window = LauncherWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
