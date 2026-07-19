"""KBKA SHOP - Generador de Etiquetas de Modelos/CEDIS.

Versión oficial: 2.1.1
Autor: Ángel Alexander Ramírez Navarro (Chava)

Este módulo administra las etiquetas cuadradas para modelos y CEDIS:

- Etiqueta individual y etiqueta con lista ordenable de modelos.
- Selección editable de marca, calidad, generación y tipo de marco.
- Autocompletado dinámico de marcas y calidades.
- Vista previa, exportación PDF e impresión térmica con QtPrintSupport.
- Configuración persistente de impresora y tema visual.
- Diálogos KBKA, ayuda, confirmaciones e información del software.

Los recursos se leen desde ``assets`` y la configuración compartida se conserva
en AppData/QSettings para mantener consistencia con el launcher y envíos.
"""

from PyQt6.QtWidgets import (
	QApplication,
	QAbstractItemView,
	QButtonGroup,
	QComboBox,
	QCompleter,
	QDialog,
	QFileDialog,
	QFrame,
	QListWidget,
	QListWidgetItem,
	QGraphicsColorizeEffect,
	QGraphicsDropShadowEffect,
	QGraphicsOpacityEffect,
	QProgressBar,
	QGridLayout,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QMainWindow,
	QMessageBox,
	QPushButton,
	QRadioButton,
	QSizePolicy,
	QScrollArea,
	QStyle,
	QVBoxLayout,
	QWidget,
)
from PyQt6.QtCore import Qt, QSize, QSizeF, QMarginsF, QRect, QStringListModel, QPropertyAnimation, QEasingCurve, QTimer, QSettings
from PyQt6.QtGui import QPixmap, QImage, QIcon, QColor, QFont, QFontMetrics, QPainter, QPageSize, QPageLayout
import os
import re
import sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
try:
	import qrcode
except Exception:
	qrcode = None
	print("Advertencia: módulo 'qrcode' no disponible. El QR no se generará.")
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
import pandas as pd
import sqlite3

# Versión pública mostrada en los diálogos de información.
APP_VERSION = "2.1.1"

# ==================== IMPRESIÓN CON QT PRINT SUPPORT ====================
# QtPrintSupport usa el sistema nativo de impresión de Windows y evita la
# dependencia de win32ui/pywin32 y sus DLL MFC.
QT_PRINT_AVAILABLE = False
QT_PRINT_ERROR = ""
QT_PRINT_DIAGNOSTIC_PATH = ""
QPrinter = None
QPrinterInfo = None


def guardar_diagnostico_impresion(etapa, detalle):
	"""Guarda errores de QtPrintSupport en AppData para facilitar el diagnóstico."""
	global QT_PRINT_DIAGNOSTIC_PATH

	try:
		appdata = os.getenv("APPDATA") or os.path.expanduser("~")
		carpeta = os.path.join(appdata, "KBKA_Shop")
		os.makedirs(carpeta, exist_ok=True)
		ruta = os.path.join(carpeta, "diagnostico_impresion_modelos.txt")

		with open(ruta, "w", encoding="utf-8") as archivo:
			archivo.write("DIAGNÓSTICO DE IMPRESIÓN QT - MODELOS\n")
			archivo.write("=======================================\n\n")
			archivo.write(f"Etapa: {etapa}\n\n")
			archivo.write(detalle)

		QT_PRINT_DIAGNOSTIC_PATH = ruta
		return ruta
	except Exception:
		return ""


def pil_a_qimage(imagen):
	"""Convierte una imagen PIL en una QImage independiente de su búfer original."""
	if imagen.mode != "RGB":
		imagen = imagen.convert("RGB")

	datos = imagen.tobytes("raw", "RGB")
	bytes_por_linea = imagen.width * 3
	return QImage(
		datos,
		imagen.width,
		imagen.height,
		bytes_por_linea,
		QImage.Format.Format_RGB888,
	).copy()


def crear_impresora_qt(nombre_impresora, ancho_mm, alto_mm, nombre_formato):
	"""Crea y configura un QPrinter cuadrado con tamaño personalizado."""
	if not QT_PRINT_AVAILABLE:
		raise RuntimeError("Qt PrintSupport no está disponible.")

	nombres = [str(nombre) for nombre in QPrinterInfo.availablePrinterNames()]
	if nombre_impresora not in nombres:
		raise RuntimeError(
			f"La impresora '{nombre_impresora}' ya no está disponible en Windows."
		)

	printer = QPrinter(QPrinter.PrinterMode.HighResolution)
	printer.setPrinterName(nombre_impresora)
	printer.setDocName("Etiquetas CEDIS")
	printer.setFullPage(True)

	tamano_pagina = QPageSize(
		QSizeF(ancho_mm, alto_mm),
		QPageSize.Unit.Millimeter,
		nombre_formato,
		QPageSize.SizeMatchPolicy.ExactMatch,
	)
	orientacion = QPageLayout.Orientation.Portrait
	layout = QPageLayout(
		tamano_pagina,
		orientacion,
		QMarginsF(0, 0, 0, 0),
		QPageLayout.Unit.Millimeter,
	)
	layout.setMode(QPageLayout.Mode.FullPageMode)

	if not printer.setPageLayout(layout):
		printer.setPageSize(tamano_pagina)
		printer.setPageOrientation(orientacion)
	printer.setFullPage(True)

	if not printer.isValid():
		raise RuntimeError(
			f"Windows no pudo inicializar la impresora '{nombre_impresora}'."
		)

	return printer


try:
	from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo

	QT_PRINT_AVAILABLE = True
	print("Qt PrintSupport cargado correctamente.")
except Exception:
	import traceback

	QT_PRINT_AVAILABLE = False
	QT_PRINT_ERROR = traceback.format_exc()
	guardar_diagnostico_impresion("Carga de Qt PrintSupport", QT_PRINT_ERROR)
	print("Error al cargar Qt PrintSupport:")
	print(QT_PRINT_ERROR)

# ==================== PATH CONFIGURATION ====================
ICONS_DIR = os.path.join("assets", "icons")
IMAGES_DIR = os.path.join("assets", "images")
DB_DIR = os.path.join("assets", "db")
HEADERS_DIR = os.path.join("assets", "headers")


def recolorear_icono_footer(ruta_icono, color, ancho=24, alto=24):
    """Recolorea un icono PNG conservando su transparencia."""
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

    imagen = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
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


def obtener_ruta_recurso(ruta_relativa):
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


def buscar_icono_asset(nombre_archivo):
	"""Busca un icono en assets/icons y conserva assets como respaldo."""
	candidatos = (
		os.path.join(ICONS_DIR, nombre_archivo),
		os.path.join("assets", nombre_archivo),
	)
	for ruta_relativa in candidatos:
		ruta = obtener_ruta_recurso(ruta_relativa)
		if os.path.exists(ruta):
			return ruta
	return obtener_ruta_recurso(candidatos[0])


# ==================== TEMA GLOBAL COMPARTIDO ====================
THEME_SETTINGS_ORG = "KBKA SHOP"
THEME_SETTINGS_APP = "Etiquetas Unificado"
THEME_SETTINGS_KEY = "tema_oscuro"


def leer_tema_global(settings=None):
	"""Lee el tema compartido sin alterar la paleta propia de cada módulo."""
	settings = settings or QSettings(THEME_SETTINGS_ORG, THEME_SETTINGS_APP)
	value = settings.value(THEME_SETTINGS_KEY, True)
	if isinstance(value, bool):
		return value
	return str(value).strip().lower() not in {"false", "0", "no", "off"}


def guardar_tema_global(tema_oscuro, settings=None):
	"""Guarda el modo activo para launcher, Envíos y Modelos."""
	settings = settings or QSettings(THEME_SETTINGS_ORG, THEME_SETTINGS_APP)
	settings.setValue(THEME_SETTINGS_KEY, bool(tema_oscuro))
	settings.sync()


class ComboBoxSinRueda(QComboBox):
	"""Evita cambios accidentales de opción al desplazar el formulario."""

	def wheelEvent(self, event):
		# La rueda sigue desplazando el contenedor padre y no cambia la selección.
		"""Ignora la rueda sobre el combo para evitar cambios accidentales y permite el scroll del formulario."""
		event.ignore()


# ==================== CONFIGURACIÓN DE BASE DE DATOS ====================
appdata_dir = os.getenv("APPDATA") or os.path.expanduser("~")
kbka_shop_dir = os.path.join(appdata_dir, "KBKA_Shop")
os.makedirs(kbka_shop_dir, exist_ok=True)
DB_PATH = os.path.join(kbka_shop_dir, "kbka_data.db")


try:
	import ctypes

	myappid = "kbkashop.cedis.etiquetas.app.1.0"
	ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
	pass


class KBKADialog(QDialog):
	"""
	Diálogo personalizado premium con diseño moderno para KBKA SHOP.

	Proporciona diálogos modales con animaciones suaves, diseño sin bordes,
	y soporte para temas claro/oscuro. Incluye métodos estáticos para
	mostrar diferentes tipos de notificaciones.
	"""

	def __init__(self, parent=None, title="", message="", dialog_type="info", buttons=None):
		"""Inicializa el objeto, crea su estado interno y prepara sus componentes visuales."""
		super().__init__(parent)

		self.result_value = False
		self.dialog_type = dialog_type
		self._parent = parent

		self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
		self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
		self.setModal(True)

		self._setup_ui(title, message, buttons)

		self.opacity_effect = QGraphicsOpacityEffect(self)
		self.setGraphicsEffect(self.opacity_effect)

		self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
		self.fade_in_animation.setDuration(250)
		self.fade_in_animation.setStartValue(0.0)
		self.fade_in_animation.setEndValue(1.0)
		self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

	def _setup_ui(self, title, message, buttons):
		"""Ejecuta la lógica asociada a setup ui."""
		main_layout = QVBoxLayout(self)
		main_layout.setContentsMargins(0, 0, 0, 0)

		container = QFrame()
		container.setObjectName("dialog_container")

		tema_oscuro_dialogo = bool(
			hasattr(self._parent, "tema_oscuro") and self._parent.tema_oscuro
		)
		if tema_oscuro_dialogo:
			bg_color = "#1E1E1E"
			border_color = "#3A3A3A"
			self.setStyleSheet("QDialog { background-color: transparent; }")
		else:
			bg_color = "#FFFFFF"
			border_color = "#D0D0D0"
			self.setStyleSheet("QDialog { background-color: transparent; }")

		container.setStyleSheet(
			f"""
			QFrame#dialog_container {{
				background-color: {bg_color};
				border: 2px solid {border_color};
				border-radius: 15px;
			}}
			"""
		)

		container_layout = QVBoxLayout(container)
		container_layout.setContentsMargins(30, 25, 30, 25)
		container_layout.setSpacing(15)

		icon_label = QLabel()
		icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		icon_path = self._get_icon_path()
		if icon_path and os.path.exists(icon_path):
			if self.dialog_type == "question":
				# Tono neutro coherente con el tema, igual que en Gestión de Clientes.
				color_pregunta = "#D8DADD" if tema_oscuro_dialogo else "#343A40"
				pixmap = recolorear_icono_footer(
					icon_path,
					color_pregunta,
					48,
					48,
				)
			else:
				pixmap = QPixmap(icon_path)
				pixmap = pixmap.scaled(
					48,
					48,
					Qt.AspectRatioMode.KeepAspectRatio,
					Qt.TransformationMode.SmoothTransformation,
				)
			icon_label.setPixmap(pixmap)
			icon_label.setStyleSheet("background: transparent; border: none;")
		else:
			icon_label.setText(self._get_icon_text())
			icon_color = self._get_icon_color()
			icon_label.setStyleSheet(
				f"""
				font-size: 48px;
				color: {icon_color};
				font-weight: bold;
				background: transparent;
				border: none;
				"""
			)
		container_layout.addWidget(icon_label)

		title_label = QLabel(title)
		title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		title_label.setWordWrap(True)

		parent = self.parent()
		if hasattr(parent, "tema_oscuro") and parent.tema_oscuro:
			title_color = "#FFFFFF"
			message_color = "#E0E0E0"
		else:
			title_color = "#2C2C2C"
			message_color = "#666666"

		title_label.setStyleSheet(
			f"""
			font-size: 16pt;
			font-weight: bold;
			color: {title_color};
			padding: 5px 0px;
			background: transparent;
			border: none;
			"""
		)
		container_layout.addWidget(title_label)

		message_label = QLabel(message)
		message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		message_label.setWordWrap(True)
		message_label.setStyleSheet(
			f"""
			font-size: 11pt;
			color: {message_color};
			line-height: 1.6;
			padding: 10px 15px;
			background: transparent;
			border: none;
			"""
		)
		container_layout.addWidget(message_label)

		container_layout.addSpacing(10)

		buttons_layout = QHBoxLayout()
		buttons_layout.setSpacing(10)
		buttons_layout.addStretch()

		if buttons is None:
			btn_accept = self._create_button("Aceptar", "primary")
			btn_accept.clicked.connect(self._on_accept)
			buttons_layout.addWidget(btn_accept)
		else:
			for btn_text, btn_type in buttons:
				btn = self._create_button(btn_text, btn_type)
				if btn_type == "primary":
					btn.clicked.connect(self._on_accept)
				else:
					btn.clicked.connect(self._on_reject)
				buttons_layout.addWidget(btn)

		buttons_layout.addStretch()
		container_layout.addLayout(buttons_layout)

		main_layout.addWidget(container)

		self.setFixedWidth(450)
		self.adjustSize()

	def _create_button(self, text, btn_type):
		"""Ejecuta la lógica asociada a create button."""
		btn = QPushButton(text)
		btn.setFixedSize(100, 35)
		btn.setCursor(Qt.CursorShape.PointingHandCursor)

		parent = self.parent()
		is_dark = hasattr(parent, "tema_oscuro") and parent.tema_oscuro

		if btn_type == "primary":
			btn.setStyleSheet(
				"""
				QPushButton {
					background-color: #CD0403;
					color: white;
					border: none;
					border-radius: 6px;
					font-size: 10pt;
					font-weight: 600;
				}
				QPushButton:hover {
					background-color: #B10302;
				}
				QPushButton:pressed {
					background-color: #8F0201;
				}
				"""
			)
		else:
			if is_dark:
				bg_color = "#2A2A2A"
				hover_color = "#333333"
				pressed_color = "#3A3A3A"
				text_color = "#FFFFFF"
				border_color = "#4A4A4A"
			else:
				bg_color = "#F5F5F5"
				hover_color = "#E8E8E8"
				pressed_color = "#DCDCDC"
				text_color = "#4A4A4A"
				border_color = "#DCDCDC"

			btn.setStyleSheet(
				f"""
				QPushButton {{
					background-color: {bg_color};
					color: {text_color};
					border: 1px solid {border_color};
					border-radius: 6px;
					font-size: 10pt;
					font-weight: 600;
				}}
				QPushButton:hover {{
					background-color: {hover_color};
					border: 1px solid {border_color};
				}}
				QPushButton:pressed {{
					background-color: {pressed_color};
				}}
				"""
			)

		return btn

	def _get_icon_path(self):
		"""Devuelve icon path."""
		icons = {
			"success": os.path.join(ICONS_DIR, "icon_success.png"),
			"error": os.path.join(ICONS_DIR, "icon_error.png"),
			"warning": os.path.join(ICONS_DIR, "icon_warning.png"),
			"info": os.path.join(ICONS_DIR, "icon_info.png"),
			"question": os.path.join(ICONS_DIR, "icon_question.png"),
		}
		icon_file = icons.get(self.dialog_type, os.path.join(ICONS_DIR, "icon_info.png"))
		return obtener_ruta_recurso(icon_file)

	def _get_icon_text(self):
		"""Devuelve icon text."""
		icons = {
			"success": "✓",
			"error": "✗",
			"warning": "⚠",
			"info": "ℹ",
			"question": "?",
		}
		return icons.get(self.dialog_type, "ℹ")

	def _get_icon_color(self):
		"""Devuelve icon color."""
		if self.dialog_type == "question":
			tema_oscuro = bool(
				hasattr(self._parent, "tema_oscuro") and self._parent.tema_oscuro
			)
			return "#D8DADD" if tema_oscuro else "#343A40"

		colors = {
			"success": "#00C853",
			"error": "#CD0403",
			"warning": "#FF9800",
			"info": "#2196F3",
		}
		return colors.get(self.dialog_type, "#2196F3")

	def _on_accept(self):
		"""Marca el diálogo como aceptado y lo cierra con resultado positivo."""
		self.result_value = True
		self.accept()

	def _on_reject(self):
		"""Marca el diálogo como cancelado y lo cierra con resultado negativo."""
		self.result_value = False
		self.reject()

	def showEvent(self, event):
		"""Responde a la aparición del widget y ejecuta las acciones visuales necesarias."""
		super().showEvent(event)
		self.fade_in_animation.start()

	@staticmethod
	def success(parent, title, message):
		"""Muestra un KBKADialog de operación completada correctamente."""
		dialog = KBKADialog(parent, title, message, "success", [("Aceptar", "primary")])
		dialog.exec()

	@staticmethod
	def error(parent, title, message):
		"""Muestra un KBKADialog con información de error."""
		dialog = KBKADialog(parent, title, message, "error", [("Aceptar", "primary")])
		dialog.exec()

	@staticmethod
	def warning(parent, title, message):
		"""Muestra un KBKADialog de advertencia."""
		dialog = KBKADialog(parent, title, message, "warning", [("Aceptar", "primary")])
		dialog.exec()

	@staticmethod
	def info(parent, title, message):
		"""Muestra un KBKADialog informativo."""
		dialog = KBKADialog(parent, title, message, "info", [("Aceptar", "primary")])
		dialog.exec()

	@staticmethod
	def confirm(parent, title, message):
		"""Muestra un KBKADialog de confirmación y devuelve la decisión del usuario."""
		dialog = KBKADialog(
			parent,
			title,
			message,
			"question",
			[("Cancelar", "secondary"), ("Sí, continuar", "primary")],
		)
		dialog.exec()
		return dialog.result_value


class CEDISEtiquetasApp(QMainWindow):
	"""Ventana principal para crear, previsualizar, guardar e imprimir etiquetas de modelos."""
	COLORS = {
		"primary": "#D40103",
		"secondary": "#D10E0E",
		"gray1": "#808080",
		"gray2": "#9F9F9F",
		"gray_dark": "#2B2B2B",
		"white": "#FFFFFF",
		"success": "#00C853",
	}

	LABEL_SIZE_PX = 340
	LABEL_PAGE_MM = 102
	LABEL_CONTENT_MM = 96
	LABEL_LEFT_MM = 5
	LABEL_BOTTOM_MM = 5
	SHOW_QR_ON_LABEL = False
	PREVIEW_SCALE = 2.0
	PDF_SCALE = 4.0

	EMPRESA_NOMBRE = "KBKA SHOP"

	BRAND_OPTIONS = [
		"APPLE",
		"SAMSUNG",
		"XIAOMI",
		"REDMI",
		"POCO",
		"OPPO",
		"MOTOROLA",
		"HUAWEI",
		"HONOR",
		"VIVO",
		"REALME",
		"INFINIX",
		"TECNO",
		"ITEL",
		"CUBOT",
		"ONEPLUS",
		"GOOGLE",
		"NOTHING",
		"NOKIA",
		"HMD",
		"LG",
		"ZTE",
		"ALCATEL",
		"HTC",
		"TCL",
		"ASUS",
		"SONY",
		"MEIZU",
		"DOOGEE",
		"OUKITEL"
	]

	QUALITY_OPTIONS = ["INCELL", "OLED", "TIPO ORIGINAL", "ORIGINAL", "SIN CALIDAD"]
	LABEL_TYPE_OPTIONS = ["Etiqueta individual", "Lista de modelos"]

	def __init__(self):
		"""Inicializa el objeto, crea su estado interno y prepara sus componentes visuales."""
		super().__init__()

		self._intro_animation_started = False
		self._intro_opacity_animation = None
		self.setWindowOpacity(0.0)

		self.inicializar_db()

		self.setWindowTitle("KBKA SHOP - Etiquetas CEDIS")
		try:
			icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, "KBKA.ico"))
			if os.path.exists(icon_path):
				self.setWindowIcon(QIcon(icon_path))
		except Exception:
			pass

		self._ajustes_tema = QSettings(THEME_SETTINGS_ORG, THEME_SETTINGS_APP)
		self.tema_oscuro = leer_tema_global(self._ajustes_tema)
		self.ayuda_dialog = None

		self.init_ui()
		# La ventana se muestra y maximiza desde el launcher unificado.

	def showEvent(self, event):
		"""Responde a la aparición del widget y ejecuta las acciones visuales necesarias."""
		super().showEvent(event)
		if self._intro_animation_started:
			return

		self._intro_animation_started = True
		self.setWindowOpacity(0.0)

		self._intro_opacity_animation = QPropertyAnimation(self, b"windowOpacity")
		self._intro_opacity_animation.setDuration(700)
		self._intro_opacity_animation.setStartValue(0.0)
		self._intro_opacity_animation.setEndValue(1.0)
		self._intro_opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
		self._intro_opacity_animation.start()

	def inicializar_db(self):
		"""Inicializa db y mantiene actualizado el estado relacionado."""
		try:
			os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
			self.db_path = DB_PATH
			conn = sqlite3.connect(self.db_path)
			cursor = conn.cursor()

			cursor.execute(
				"""
				CREATE TABLE IF NOT EXISTS configuracion (
					parametro TEXT PRIMARY KEY,
					valor TEXT
				)
				"""
			)

			cursor.execute(
				"""
				CREATE TABLE IF NOT EXISTS cedis_labels (
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					marca TEXT NOT NULL,
					modelo TEXT NOT NULL,
					calidad TEXT NOT NULL,
					accion TEXT NOT NULL,
					archivo TEXT,
					created_at TEXT DEFAULT CURRENT_TIMESTAMP
				)
				"""
			)

			conn.commit()
			conn.close()
		except Exception as e:
			print(f"Error al inicializar base de datos: {e}")

	def guardar_impresora_config(self, nombre_impresora):
		"""Guarda impresora config y mantiene actualizado el estado relacionado."""
		try:
			conn = sqlite3.connect(self.db_path)
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT OR REPLACE INTO configuracion (parametro, valor)
				VALUES (?, ?)
				""",
				("impresora_predeterminada", nombre_impresora),
			)
			conn.commit()
			conn.close()
		except Exception as e:
			print(f"Error al guardar impresora: {e}")

	def cargar_impresora_config(self):
		"""Carga impresora config y mantiene actualizado el estado relacionado."""
		try:
			conn = sqlite3.connect(self.db_path)
			cursor = conn.cursor()
			cursor.execute(
				"SELECT valor FROM configuracion WHERE parametro = ?",
				("impresora_predeterminada",),
			)
			resultado = cursor.fetchone()
			conn.close()
			return resultado[0] if resultado else None
		except Exception as e:
			print(f"Error al cargar impresora: {e}")
			return None

	def obtener_impresoras(self):
		"""Obtiene los nombres de impresoras disponibles mediante QtPrintSupport."""
		if not QT_PRINT_AVAILABLE:
			return []

		try:
			return [
				str(nombre)
				for nombre in QPrinterInfo.availablePrinterNames()
				if str(nombre).strip()
			]
		except Exception:
			import traceback

			error = traceback.format_exc()
			guardar_diagnostico_impresion("Enumeración de impresoras con Qt", error)
			print("Error al obtener impresoras con QtPrintSupport:")
			print(error)
			return []

	def registrar_historial(self, accion, archivo=None):
		"""Registra historial y mantiene actualizado el estado relacionado."""
		try:
			conn = sqlite3.connect(self.db_path)
			cursor = conn.cursor()
			cursor.execute(
				"""
				INSERT INTO cedis_labels (marca, modelo, calidad, accion, archivo)
				VALUES (?, ?, ?, ?, ?)
				""",
				(
					self.obtener_marca(),
					self.obtener_modelo_historial(),
					self.obtener_calidad_historial(),
					accion,
					archivo,
				),
			)
			conn.commit()
			conn.close()
		except Exception as e:
			print(f"Error al registrar historial CEDIS: {e}")

	def abrir_ayuda(self):
		"""
		Abre el diálogo de ayuda y soporte.

		Muestra problemas comunes, soluciones y datos de contacto
		de soporte técnico.
		"""
		dialogo = AyudaDialog(self)
		self.ayuda_dialog = dialogo  # Guardar referencia
		dialogo.exec()
		self.ayuda_dialog = None  # Limpiar referencia al cerrar

	def abrir_configuracion_impresora(self):
		"""
		Abre el diálogo de configuración de impresora definido en este módulo.
		"""
		try:
			dialogo = ConfiguracionImpresoraDialog(self)
			dialogo.exec()
		except Exception as e:
			KBKADialog.info(self, "Configurar Impresora", "La configuración de impresora no está disponible en este módulo.\n\nDetalles: " + str(e))

	def abrir_informacion(self):
		"""Abre el diálogo con información del software y desarrollador"""
		mensaje = (
			"KBKA Shop\n"
			f"Sistema de Gestión de Etiquetas v{APP_VERSION}\n\n"
			"Desarrollado por: Angel Alexander Ramírez Navarro (Chava)\n"
			"© 2026 Todos los derechos reservados."
		)
		KBKADialog.info(self, "Información del Software", mensaje)

	def init_ui(self):
		"""Ejecuta la lógica asociada a init ui."""
		central_widget = QWidget()
		self.setCentralWidget(central_widget)

		main_layout = QVBoxLayout(central_widget)
		main_layout.setContentsMargins(0, 0, 0, 0)
		main_layout.setSpacing(0)

		self.crear_header(main_layout)
		self.crear_formulario(main_layout)
		self.crear_footer(main_layout)
		self.aplicar_estilos()

		# Los iconos del formulario se registran mientras se construyen los
		# widgets. Se aplican al final, cuando todos los botones y títulos ya
		# existen y el tema inicial está completamente configurado.
		if hasattr(self, "_actualizar_iconos_formulario"):
			self._actualizar_iconos_formulario()

	def crear_header(self, main_layout):
		"""Crea y configura header y mantiene actualizado el estado relacionado."""
		header = QFrame()
		header.setObjectName("header")
		header.setFixedHeight(150)

		header_layout = QHBoxLayout(header)
		header_layout.setContentsMargins(20, 10, 20, 10)
		header_layout.addStretch()

		try:
			header_filename = "header_fondo_oscuro.png" if self.tema_oscuro else "header_fondo_blanco.png"
			logo_path = obtener_ruta_recurso(os.path.join(HEADERS_DIR, header_filename))
			if os.path.exists(logo_path):
				self.header_logo_label = QLabel()
				self.header_logo_label.setObjectName("header_logo")
				pixmap = QPixmap(logo_path)
				pixmap = pixmap.scaled(
					300,
					150,
					Qt.AspectRatioMode.KeepAspectRatio,
					Qt.TransformationMode.SmoothTransformation,
				)
				self.header_logo_label.setPixmap(pixmap)
				self.header_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
				header_layout.addWidget(self.header_logo_label)
		except Exception as e:
			print(f"No se pudo cargar el logo: {e}")

		header_layout.addStretch()
		main_layout.addWidget(header)

	def actualizar_header_logo(self):
		"""Actualiza header logo y mantiene actualizado el estado relacionado."""
		if not hasattr(self, "header_logo_label"):
			return
		try:
			header_filename = "header_fondo_oscuro.png" if self.tema_oscuro else "header_fondo_blanco.png"
			logo_path = obtener_ruta_recurso(os.path.join(HEADERS_DIR, header_filename))
			if os.path.exists(logo_path):
				pixmap = QPixmap(logo_path)
				pixmap = pixmap.scaled(
					300,
					150,
					Qt.AspectRatioMode.KeepAspectRatio,
					Qt.TransformationMode.SmoothTransformation,
				)
				self.header_logo_label.setPixmap(pixmap)
		except Exception as e:
			print(f"No se pudo actualizar el logo del header: {e}")

	def crear_formulario(self, main_layout):
		"""Crea y configura formulario y mantiene actualizado el estado relacionado."""
		form_container = QWidget()
		form_container.setObjectName("main_content_container")
		form_layout = QHBoxLayout(form_container)
		form_layout.setContentsMargins(30, 20, 30, 24)
		form_layout.setSpacing(18)
		form_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

		self._iconos_titulos_formulario = []
		self._iconos_botones_formulario = []

		def resolver_icono_asset(*nombres):
			"""Resuelve icono asset y mantiene actualizado el estado relacionado."""
			for nombre in nombres:
				ruta = buscar_icono_asset(nombre)
				if os.path.exists(ruta):
					return ruta
			return buscar_icono_asset(nombres[0])

		def actualizar_iconos_formulario():
			"""Actualiza iconos formulario y mantiene actualizado el estado relacionado."""
			color_titulo = "#F2F2F2" if self.tema_oscuro else "#343A40"
			color_tema = "#F2F2F2" if self.tema_oscuro else "#343A40"
			color_muted = "#BFC3C7" if self.tema_oscuro else "#666666"

			for etiqueta, nombres, tamano in self._iconos_titulos_formulario:
				ruta = resolver_icono_asset(*nombres)
				pixmap = recolorear_icono_footer(
					ruta, color_titulo, tamano, tamano
				)
				if pixmap.isNull():
					etiqueta.clear()
					continue

				# Añade margen transparente alrededor del PNG para evitar
				# que iconos anchos, como vista_previa.png, se recorten.
				margen = 4
				lienzo = QPixmap(
					pixmap.width() + (margen * 2),
					pixmap.height() + (margen * 2),
				)
				lienzo.fill(Qt.GlobalColor.transparent)
				pintor_icono = QPainter(lienzo)
				pintor_icono.drawPixmap(margen, margen, pixmap)
				pintor_icono.end()
				etiqueta.setPixmap(lienzo)

			for boton, nombres, modo, tamano in self._iconos_botones_formulario:
				ruta = resolver_icono_asset(*nombres)
				if modo == "primary":
					color = "#FFFFFF"
				elif modo == "muted":
					color = color_muted
				elif modo == "danger":
					color = "#FFFFFF" if self.tema_oscuro else "#8E2C2C"
				else:
					color = color_tema
				pixmap = recolorear_icono_footer(ruta, color, tamano, tamano)
				boton.setIcon(QIcon(pixmap))
				boton.setIconSize(QSize(tamano, tamano))

		self._actualizar_iconos_formulario = actualizar_iconos_formulario

		def agregar_titulo_tarjeta(
			layout, texto, ancho_linea=190, iconos_archivo=None
		):
			"""Agrega titulo tarjeta y mantiene actualizado el estado relacionado."""
			fila_titulo = QHBoxLayout()
			fila_titulo.setContentsMargins(0, 0, 0, 0)
			fila_titulo.setSpacing(8)

			if iconos_archivo:
				if isinstance(iconos_archivo, str):
					iconos_archivo = (iconos_archivo,)
				icono_label = QLabel()
				# Espacio adicional para que los iconos no se recorten.
				icono_label.setFixedSize(32, 32)
				icono_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
				icono_label.setStyleSheet(
					"background: transparent; border: none;"
				)
				self._iconos_titulos_formulario.append(
					(icono_label, tuple(iconos_archivo), 22)
				)
				fila_titulo.addWidget(icono_label)

			titulo = QLabel(texto)
			titulo.setObjectName("card_title")
			fila_titulo.addWidget(titulo)
			fila_titulo.addStretch()
			layout.addLayout(fila_titulo)

			linea = QFrame()
			linea.setObjectName("card_separator")
			linea.setFrameShape(QFrame.Shape.HLine)
			linea.setFixedHeight(2)
			linea.setFixedWidth(ancho_linea)
			layout.addWidget(linea)

		def registrar_icono_boton(
			boton, icono_archivo, modo="theme", tamano=20
		):
			# QPushButton no expone una propiedad directa para separar el icono
			# del texto. Un espacio tipográfico ancho mantiene una separación
			# uniforme sin depender de la fuente ni de espacios normales.
			"""Registra icono boton y mantiene actualizado el estado relacionado."""
			texto_actual = boton.text()
			if texto_actual and not texto_actual.startswith("\u2003"):
				boton.setText("\u2003" + texto_actual)

			self._iconos_botones_formulario.append(
				(boton, (icono_archivo,), modo, tamano)
			)

		def crear_etiqueta_campo(texto, icono_archivo=None):
			"""Crea y configura etiqueta campo y mantiene actualizado el estado relacionado."""
			label = QLabel(texto)
			label.setObjectName("field_label")

			if not icono_archivo:
				return label

			contenedor = QWidget()
			contenedor.setObjectName("transparent_widget")
			fila = QHBoxLayout(contenedor)
			fila.setContentsMargins(0, 0, 0, 0)
			fila.setSpacing(5)

			icono_label = QLabel()
			icono_label.setFixedSize(24, 24)
			icono_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
			icono_label.setStyleSheet(
				"background: transparent; border: none;"
			)
			self._iconos_titulos_formulario.append(
				(icono_label, (icono_archivo,), 16)
			)
			fila.addWidget(icono_label)
			fila.addWidget(label)
			fila.addStretch()
			return contenedor

		# ==================== PANEL IZQUIERDO ====================
		left_widget = QWidget()
		left_widget.setSizePolicy(
			QSizePolicy.Policy.Preferred,
			QSizePolicy.Policy.Expanding,
		)
		left_layout = QVBoxLayout(left_widget)
		left_layout.setContentsMargins(0, 0, 0, 0)
		left_layout.setSpacing(10)

		# -------------------- TARJETA DE DATOS --------------------
		self.datos_card = QFrame()
		self.datos_card.setObjectName("panel_card")
		datos_layout = QVBoxLayout(self.datos_card)
		datos_layout.setContentsMargins(20, 18, 20, 18)
		datos_layout.setSpacing(10)

		agregar_titulo_tarjeta(
			datos_layout,
			"DATOS DE LA ETIQUETA",
			250,
			("datos_modelos.png", "datos_modelos"),
		)

		datos_layout.addWidget(crear_etiqueta_campo("Tipo de etiqueta"))
		self.combo_tipo_etiqueta = ComboBoxSinRueda()
		self.combo_tipo_etiqueta.addItems(self.LABEL_TYPE_OPTIONS)
		self.combo_tipo_etiqueta.setCurrentIndex(0)
		self.combo_tipo_etiqueta.currentTextChanged.connect(
			lambda _texto=None: self._actualizar_modo_etiqueta()
		)
		datos_layout.addWidget(self.combo_tipo_etiqueta)

		# Marca y modelo comparten fila. Al ocultar Modelo en el modo lista,
		# Marca se expande automáticamente y ocupa todo el ancho.
		identidad_layout = QHBoxLayout()
		identidad_layout.setContentsMargins(0, 0, 0, 0)
		identidad_layout.setSpacing(12)

		marca_widget = QWidget()
		marca_layout = QVBoxLayout(marca_widget)
		marca_layout.setContentsMargins(0, 0, 0, 0)
		marca_layout.setSpacing(5)
		marca_layout.addWidget(crear_etiqueta_campo("Marca"))

		self.combo_marca = ComboBoxSinRueda()
		self.combo_marca.setEditable(True)
		self.combo_marca.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
		self.combo_marca.addItems(self.BRAND_OPTIONS)
		self.combo_marca.setCompleter(
			self._crear_completer(self.BRAND_OPTIONS, self.combo_marca)
		)
		self._conectar_autocompletado_dinamico(self.combo_marca)
		self.combo_marca.setCurrentIndex(0)
		self.combo_marca.currentTextChanged.connect(self.actualizar_vista_previa)
		marca_layout.addWidget(self.combo_marca)
		identidad_layout.addWidget(marca_widget, 1)

		self.individual_widget = QWidget()
		modelo_layout = QVBoxLayout(self.individual_widget)
		modelo_layout.setContentsMargins(0, 0, 0, 0)
		modelo_layout.setSpacing(5)
		modelo_layout.addWidget(crear_etiqueta_campo("Modelo", "modelo.png"))

		self.entry_modelo = QLineEdit()
		self.entry_modelo.setPlaceholderText("Ingrese el modelo")
		self.entry_modelo.textChanged.connect(self.actualizar_vista_previa)
		modelo_layout.addWidget(self.entry_modelo)
		identidad_layout.addWidget(self.individual_widget, 1)

		datos_layout.addLayout(identidad_layout)

		# Opciones exclusivas de la etiqueta individual.
		self.individual_options_widget = QWidget()
		individual_options_layout = QVBoxLayout(self.individual_options_widget)
		individual_options_layout.setContentsMargins(0, 0, 0, 0)
		individual_options_layout.setSpacing(9)

		individual_options_layout.addWidget(crear_etiqueta_campo("Calidad"))
		self.combo_calidad = ComboBoxSinRueda()
		self.combo_calidad.setEditable(True)
		self.combo_calidad.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
		self.combo_calidad.addItems(self.QUALITY_OPTIONS)
		self.combo_calidad.setCompleter(
			self._crear_completer(self.QUALITY_OPTIONS, self.combo_calidad)
		)
		self._conectar_autocompletado_dinamico(self.combo_calidad)
		if self.combo_calidad.lineEdit() is not None:
			self.combo_calidad.lineEdit().setPlaceholderText(
				"Seleccione o escriba una calidad"
			)
		self.combo_calidad.setCurrentIndex(0)
		self.combo_calidad.currentTextChanged.connect(self.actualizar_vista_previa)
		individual_options_layout.addWidget(self.combo_calidad)

		self.label_generacion = crear_etiqueta_campo("Generación")
		individual_options_layout.addWidget(self.label_generacion)

		self.botones_gen_layout = QHBoxLayout()
		self.botones_gen_layout.setContentsMargins(0, 0, 0, 0)
		self.botones_gen_layout.setSpacing(8)
		self.group_generacion = QButtonGroup(self)
		self.group_generacion.setExclusive(False)
		self.radio_generacion_4g = QRadioButton("4G")
		self.radio_generacion_5g = QRadioButton("5G")
		for radio in (self.radio_generacion_4g, self.radio_generacion_5g):
			radio.setAutoExclusive(False)
			radio.setSizePolicy(
				QSizePolicy.Policy.Expanding,
				QSizePolicy.Policy.Fixed,
			)
			radio.setMinimumHeight(34)
			radio.toggled.connect(
				lambda checked, group="generacion": self._manejar_seleccion_radio(
					group, checked
				)
			)
			self.group_generacion.addButton(radio)
			self.botones_gen_layout.addWidget(radio, 1)
		individual_options_layout.addLayout(self.botones_gen_layout)

		self.label_marco = crear_etiqueta_campo("Con marco")
		individual_options_layout.addWidget(self.label_marco)

		self.botones_marco_layout = QHBoxLayout()
		self.botones_marco_layout.setContentsMargins(0, 0, 0, 0)
		self.botones_marco_layout.setSpacing(8)
		self.group_marco = QButtonGroup(self)
		self.group_marco.setExclusive(False)
		self.radio_marco_si = QRadioButton("Sí")
		self.radio_marco_no = QRadioButton("No")
		for radio in (self.radio_marco_si, self.radio_marco_no):
			radio.setAutoExclusive(False)
			radio.setSizePolicy(
				QSizePolicy.Policy.Expanding,
				QSizePolicy.Policy.Fixed,
			)
			radio.setMinimumHeight(34)
			radio.toggled.connect(
				lambda checked, group="marco": self._manejar_seleccion_radio(
					group, checked
				)
			)
			self.group_marco.addButton(radio)
			self.botones_marco_layout.addWidget(radio, 1)
		individual_options_layout.addLayout(self.botones_marco_layout)
		self.radio_marco_no.setChecked(True)

		datos_layout.addWidget(self.individual_options_widget)

		# Opciones exclusivas del modo Lista de modelos.
		self.lista_widget = QWidget()
		lista_layout = QVBoxLayout(self.lista_widget)
		lista_layout.setContentsMargins(0, 0, 0, 0)
		lista_layout.setSpacing(9)

		lista_layout.addWidget(crear_etiqueta_campo("Modelo", "modelo.png"))

		lista_entrada_layout = QHBoxLayout()
		lista_entrada_layout.setContentsMargins(0, 0, 0, 0)
		lista_entrada_layout.setSpacing(8)

		self.entry_modelo_lista = QLineEdit()
		self.entry_modelo_lista.setPlaceholderText(
			"Ingrese el modelo y presione Enter"
		)
		self.entry_modelo_lista.returnPressed.connect(self.agregar_modelo_lista)
		lista_entrada_layout.addWidget(self.entry_modelo_lista, 1)

		self.btn_agregar_modelo_lista = QPushButton("Agregar")
		self.btn_agregar_modelo_lista.setObjectName("btn_list_primary")
		registrar_icono_boton(
			self.btn_agregar_modelo_lista, "agregar.png", "primary", 18
		)
		self.btn_agregar_modelo_lista.setMinimumHeight(42)
		self.btn_agregar_modelo_lista.setMinimumWidth(110)
		self.btn_agregar_modelo_lista.setCursor(
			Qt.CursorShape.PointingHandCursor
		)
		self.btn_agregar_modelo_lista.clicked.connect(self.agregar_modelo_lista)
		lista_entrada_layout.addWidget(self.btn_agregar_modelo_lista)
		lista_layout.addLayout(lista_entrada_layout)

		lista_contenedor_layout = QHBoxLayout()
		lista_contenedor_layout.setContentsMargins(0, 0, 0, 0)
		lista_contenedor_layout.setSpacing(10)

		self.lista_modelos_widget = QListWidget()
		self.lista_modelos_widget.setObjectName("lista_modelos_widget")
		self.lista_modelos_widget.setSelectionMode(
			QAbstractItemView.SelectionMode.SingleSelection
		)
		self.lista_modelos_widget.setEditTriggers(
			QAbstractItemView.EditTrigger.DoubleClicked
			| QAbstractItemView.EditTrigger.EditKeyPressed
		)
		self.lista_modelos_widget.setToolTip(
			"Doble clic o F2 para editar un modelo. Enter guarda y Esc cancela."
		)
		self.lista_modelos_widget.itemChanged.connect(self.editar_modelo_lista)
		self.lista_modelos_widget.setMinimumHeight(220)
		self.lista_modelos_widget.setUniformItemSizes(True)
		self.lista_modelos_widget.setSpacing(2)
		lista_contenedor_layout.addWidget(self.lista_modelos_widget, 1)

		lista_botones_layout = QVBoxLayout()
		lista_botones_layout.setSpacing(8)

		self.btn_subir_modelo = QPushButton("Subir")
		self.btn_subir_modelo.setObjectName("btn_list_secondary")
		registrar_icono_boton(
			self.btn_subir_modelo, "subir.png", "primary", 18
		)
		self.btn_subir_modelo.setMinimumHeight(38)
		self.btn_subir_modelo.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_subir_modelo.clicked.connect(self.subir_modelo_lista)
		lista_botones_layout.addWidget(self.btn_subir_modelo)

		self.btn_bajar_modelo = QPushButton("Bajar")
		self.btn_bajar_modelo.setObjectName("btn_list_secondary")
		registrar_icono_boton(
			self.btn_bajar_modelo, "bajar.png", "primary", 18
		)
		self.btn_bajar_modelo.setMinimumHeight(38)
		self.btn_bajar_modelo.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_bajar_modelo.clicked.connect(self.bajar_modelo_lista)
		lista_botones_layout.addWidget(self.btn_bajar_modelo)

		self.btn_eliminar_modelo = QPushButton("Eliminar")
		self.btn_eliminar_modelo.setObjectName("btn_list_danger")
		registrar_icono_boton(
			self.btn_eliminar_modelo, "eliminar.png", "danger", 18
		)
		self.btn_eliminar_modelo.setMinimumHeight(38)
		self.btn_eliminar_modelo.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_eliminar_modelo.clicked.connect(self.eliminar_modelo_lista)
		lista_botones_layout.addWidget(self.btn_eliminar_modelo)
		lista_botones_layout.addStretch()

		lista_contenedor_layout.addLayout(lista_botones_layout)
		lista_layout.addLayout(lista_contenedor_layout)
		datos_layout.addWidget(self.lista_widget)

		left_layout.addWidget(self.datos_card)

		# -------------------- TARJETA DE ACCIONES --------------------
		self.acciones_card = QFrame()
		self.acciones_card.setObjectName("panel_card")
		acciones_layout = QVBoxLayout(self.acciones_card)
		acciones_layout.setContentsMargins(20, 16, 20, 16)
		acciones_layout.setSpacing(10)

		agregar_titulo_tarjeta(
			acciones_layout, "ACCIONES", 145, "engranaje.png"
		)

		# Imprimir es la acción principal y más utilizada.
		self.btn_imprimir = QPushButton("IMPRIMIR")
		self.btn_imprimir.setObjectName("btn_print_primary")
		registrar_icono_boton(self.btn_imprimir, "imprimir.png", "primary", 22)
		self.btn_imprimir.setMinimumHeight(46)
		self.btn_imprimir.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_imprimir.clicked.connect(self.imprimir_etiqueta)
		acciones_layout.addWidget(self.btn_imprimir)

		acciones_secundarias_layout = QHBoxLayout()
		acciones_secundarias_layout.setContentsMargins(0, 0, 0, 0)
		acciones_secundarias_layout.setSpacing(8)

		self.btn_guardar = QPushButton("GUARDAR PDF")
		self.btn_guardar.setObjectName("btn_success")
		registrar_icono_boton(self.btn_guardar, "guardar.png", "theme", 20)
		self.btn_guardar.setMinimumHeight(43)
		self.btn_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_guardar.clicked.connect(self.guardar_pdf)
		acciones_secundarias_layout.addWidget(self.btn_guardar, 1)

		self.btn_config_impresora = QPushButton("CONFIGURAR IMPRESORA")
		self.btn_config_impresora.setObjectName("btn_config")
		registrar_icono_boton(
			self.btn_config_impresora, "engranaje.png", "theme", 20
		)
		self.btn_config_impresora.setMinimumHeight(43)
		self.btn_config_impresora.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_config_impresora.clicked.connect(
			self.abrir_configuracion_impresora
		)
		acciones_secundarias_layout.addWidget(self.btn_config_impresora, 1)

		acciones_layout.addLayout(acciones_secundarias_layout)

		self.btn_limpiar = QPushButton("LIMPIAR")
		self.btn_limpiar.setObjectName("btn_clean_link")
		registrar_icono_boton(self.btn_limpiar, "limpiar.png", "muted", 18)
		self.btn_limpiar.setMinimumHeight(34)
		self.btn_limpiar.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_limpiar.clicked.connect(self.limpiar_campos)
		acciones_layout.addWidget(
			self.btn_limpiar,
			alignment=Qt.AlignmentFlag.AlignCenter,
		)

		left_layout.addWidget(self.acciones_card)
		left_layout.addStretch()

		# ==================== PANEL DERECHO ====================
		right_widget = QWidget()
		right_widget.setSizePolicy(
			QSizePolicy.Policy.Expanding,
			QSizePolicy.Policy.Expanding,
		)
		right_layout = QVBoxLayout(right_widget)
		right_layout.setContentsMargins(0, 0, 0, 0)
		right_layout.setSpacing(0)

		self.preview_card = QFrame()
		self.preview_card.setObjectName("panel_card")
		self.preview_card.setSizePolicy(
			QSizePolicy.Policy.Expanding,
			QSizePolicy.Policy.Expanding,
		)

		preview_card_layout = QVBoxLayout(self.preview_card)
		preview_card_layout.setContentsMargins(18, 16, 18, 18)
		preview_card_layout.setSpacing(12)

		agregar_titulo_tarjeta(
			preview_card_layout,
			"VISTA PREVIA",
			155,
			"vista_previa.png",
		)

		self.preview_container = QFrame()
		self.preview_container.setObjectName("preview_container")
		self.preview_container.setMinimumSize(420, 420)
		self.preview_container.setSizePolicy(
			QSizePolicy.Policy.Expanding,
			QSizePolicy.Policy.Expanding,
		)

		self.preview_layout = QVBoxLayout(self.preview_container)
		self.preview_layout.setContentsMargins(18, 18, 18, 18)
		self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

		self.preview_label = QLabel()
		self.preview_label.setObjectName("preview_image")
		self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.preview_label.setSizePolicy(
			QSizePolicy.Policy.Expanding,
			QSizePolicy.Policy.Expanding,
		)
		self.preview_label.setMinimumSize(1, 1)
		self.preview_layout.addWidget(self.preview_label, 1)
		self.preview_container.installEventFilter(self)

		preview_card_layout.addWidget(self.preview_container, 1)
		right_layout.addWidget(self.preview_card, 1)

		self.left_scroll = QScrollArea()
		self.left_scroll.setObjectName("left_form_scroll")
		self.left_scroll.setWidgetResizable(True)
		self.left_scroll.setFrameShape(QFrame.Shape.NoFrame)
		self.left_scroll.setHorizontalScrollBarPolicy(
			Qt.ScrollBarPolicy.ScrollBarAlwaysOff
		)
		self.left_scroll.setVerticalScrollBarPolicy(
			Qt.ScrollBarPolicy.ScrollBarAsNeeded
		)
		self.left_scroll.setWidget(left_widget)

		form_layout.addWidget(self.left_scroll, 36)
		form_layout.addWidget(right_widget, 64)
		main_layout.addWidget(form_container, 1)

		actualizar_iconos_formulario()
		self._actualizar_modo_etiqueta()
		self.actualizar_vista_previa()
	def _crear_completer(self, items, parent_widget):
		"""Crea un autocompletado que encuentra coincidencias en cualquier posición."""
		model = QStringListModel(items, parent_widget)
		completer = QCompleter(model, parent_widget)
		completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
		completer.setFilterMode(Qt.MatchFlag.MatchContains)
		completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
		completer.setMaxVisibleItems(10)
		completer.setWrapAround(False)
		return completer

	def _conectar_autocompletado_dinamico(self, combo):
		"""Actualiza el popup de sugerencias después de cada carácter escrito."""
		line_edit = combo.lineEdit()
		if line_edit is None:
			return

		line_edit.textEdited.connect(
			lambda texto, combo_objetivo=combo: self._mostrar_sugerencias_combo(
				combo_objetivo, texto
			)
		)

	def _mostrar_sugerencias_combo(self, combo, texto):
		"""Filtra y muestra las coincidencias de Marca o Calidad en tiempo real."""
		completer = combo.completer()
		if completer is None:
			return

		texto_busqueda = texto.strip()
		if not texto_busqueda:
			completer.popup().hide()
			return

		completer.setCompletionPrefix(texto_busqueda)

		# Mantiene el popup al menos tan ancho como el combo para que las
		# sugerencias se lean completas mientras se sigue escribiendo.
		rect = combo.rect()
		ancho_popup = completer.popup().sizeHintForColumn(0)
		ancho_scroll = completer.popup().verticalScrollBar().sizeHint().width()
		rect.setWidth(max(combo.width(), ancho_popup + ancho_scroll + 18))
		completer.complete(rect)

	def obtener_tipo_etiqueta(self):
		"""Obtiene tipo etiqueta y mantiene actualizado el estado relacionado."""
		if hasattr(self, "combo_tipo_etiqueta"):
			return self.combo_tipo_etiqueta.currentText().strip()
		return self.LABEL_TYPE_OPTIONS[0]

	def es_modo_lista_modelos(self):
		"""Indica si modo lista modelos y mantiene actualizado el estado relacionado."""
		return self.obtener_tipo_etiqueta() == "Lista de modelos"

	def _obtener_modelos_lista(self):
		"""Obtiene modelos lista y mantiene actualizado el estado relacionado."""
		modelos = []
		if not hasattr(self, "lista_modelos_widget"):
			return modelos
		for index in range(self.lista_modelos_widget.count()):
			item = self.lista_modelos_widget.item(index)
			modelo = item.data(Qt.ItemDataRole.UserRole)
			if modelo is None:
				texto = item.text().strip()
				modelo = texto.split(". ", 1)[-1] if ". " in texto else texto
			modelos.append(str(modelo).strip().upper())
		return modelos

	def _refrescar_lista_modelos_widget(self, modelos=None, selected_row=None):
		"""Ejecuta la lógica asociada a refrescar lista modelos widget."""
		if not hasattr(self, "lista_modelos_widget"):
			return
		if modelos is None:
			modelos = self._obtener_modelos_lista()

		self.lista_modelos_widget.blockSignals(True)
		try:
			self.lista_modelos_widget.clear()
			for index, modelo in enumerate(modelos, start=1):
				item = QListWidgetItem(f"{index}. {modelo}")
				item.setData(Qt.ItemDataRole.UserRole, modelo)
				item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
				# La altura adicional evita que el QLineEdit temporal recorte el texto.
				item.setSizeHint(QSize(0, 46))
				self.lista_modelos_widget.addItem(item)
		finally:
			self.lista_modelos_widget.blockSignals(False)

		if selected_row is not None and 0 <= selected_row < self.lista_modelos_widget.count():
			self.lista_modelos_widget.setCurrentRow(selected_row)

	def _actualizar_modo_etiqueta(self):
		"""Actualiza modo etiqueta y mantiene actualizado el estado relacionado."""
		es_lista_modelos = self.es_modo_lista_modelos()

		if hasattr(self, "individual_widget"):
			self.individual_widget.setVisible(not es_lista_modelos)
		if hasattr(self, "individual_options_widget"):
			self.individual_options_widget.setVisible(not es_lista_modelos)
		if hasattr(self, "lista_widget"):
			self.lista_widget.setVisible(es_lista_modelos)

		if hasattr(self, "combo_marca"):
			marca_actual = self.combo_marca.currentText().strip()
			self.combo_marca.setEditable(True)
			if self.combo_marca.completer() is None:
				self.combo_marca.setCompleter(
					self._crear_completer(self.BRAND_OPTIONS, self.combo_marca)
				)
				self._conectar_autocompletado_dinamico(self.combo_marca)
			self.combo_marca.setEditText(marca_actual)

		self.actualizar_vista_previa()
	def agregar_modelo_lista(self):
		"""Agrega modelo lista y mantiene actualizado el estado relacionado."""
		if not hasattr(self, "entry_modelo_lista"):
			return

		modelo = self.entry_modelo_lista.text().strip().upper()
		if not modelo:
			KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese un modelo válido")
			return

		modelos = self._obtener_modelos_lista()
		modelos.append(modelo)
		self._refrescar_lista_modelos_widget(modelos, len(modelos) - 1)
		self.entry_modelo_lista.clear()
		self.entry_modelo_lista.setFocus()
		self.actualizar_vista_previa()

	def editar_modelo_lista(self, item):
		"""Guarda una edición directa realizada con doble clic o F2."""
		if getattr(self, "_actualizando_edicion_modelo", False):
			return
		if not hasattr(self, "lista_modelos_widget") or item is None:
			return

		row = self.lista_modelos_widget.row(item)
		if row < 0:
			return

		modelo_anterior = str(item.data(Qt.ItemDataRole.UserRole) or "").strip().upper()
		# La lista muestra "1. MODELO". Al terminar de editar, conservamos
		# únicamente el modelo y reconstruimos la numeración automáticamente.
		modelo_editado = re.sub(r"^\s*\d+\.\s*", "", item.text()).strip().upper()

		self._actualizando_edicion_modelo = True
		try:
			if not modelo_editado:
				item.setData(Qt.ItemDataRole.UserRole, modelo_anterior)
				item.setText(f"{row + 1}. {modelo_anterior}")
			else:
				item.setData(Qt.ItemDataRole.UserRole, modelo_editado)
				item.setText(f"{row + 1}. {modelo_editado}")
		finally:
			self._actualizando_edicion_modelo = False

		if not modelo_editado:
			KBKADialog.warning(
				self,
				"Modelo inválido",
				"El modelo no puede quedar vacío. Se restauró el valor anterior.",
			)
			return

		self.lista_modelos_widget.setCurrentItem(item)
		self.actualizar_vista_previa()

	def eliminar_modelo_lista(self):
		"""Elimina modelo lista y mantiene actualizado el estado relacionado."""
		if not hasattr(self, "lista_modelos_widget"):
			return
		row = self.lista_modelos_widget.currentRow()
		if row < 0:
			return

		modelos = self._obtener_modelos_lista()
		if 0 <= row < len(modelos):
			modelos.pop(row)
			new_row = min(row, len(modelos) - 1) if modelos else None
			self._refrescar_lista_modelos_widget(modelos, new_row)
			self.actualizar_vista_previa()

	def subir_modelo_lista(self):
		"""Mueve hacia arriba modelo lista y mantiene actualizado el estado relacionado."""
		if not hasattr(self, "lista_modelos_widget"):
			return
		row = self.lista_modelos_widget.currentRow()
		if row <= 0:
			return

		modelos = self._obtener_modelos_lista()
		modelos[row - 1], modelos[row] = modelos[row], modelos[row - 1]
		self._refrescar_lista_modelos_widget(modelos, row - 1)
		self.actualizar_vista_previa()

	def bajar_modelo_lista(self):
		"""Mueve hacia abajo modelo lista y mantiene actualizado el estado relacionado."""
		if not hasattr(self, "lista_modelos_widget"):
			return
		row = self.lista_modelos_widget.currentRow()
		if row < 0 or row >= self.lista_modelos_widget.count() - 1:
			return

		modelos = self._obtener_modelos_lista()
		modelos[row + 1], modelos[row] = modelos[row], modelos[row + 1]
		self._refrescar_lista_modelos_widget(modelos, row + 1)
		self.actualizar_vista_previa()

	def _manejar_seleccion_radio(self, grupo, checked):
		"""Gestiona seleccion radio."""
		if not hasattr(self, "preview_label"):
			return

		if not checked:
			self.actualizar_vista_previa()
			return

		if grupo == "generacion":
			actual = self.sender()
			for radio in (self.radio_generacion_4g, self.radio_generacion_5g):
				if radio is not actual and radio.isChecked():
					radio.blockSignals(True)
					radio.setChecked(False)
					radio.blockSignals(False)
		elif grupo == "marco":
			actual = self.sender()
			for radio in (self.radio_marco_si, self.radio_marco_no):
				if radio is not actual and radio.isChecked():
					radio.blockSignals(True)
					radio.setChecked(False)
					radio.blockSignals(False)

		self.actualizar_vista_previa()

	def obtener_generacion(self):
		"""Obtiene generacion y mantiene actualizado el estado relacionado."""
		if hasattr(self, "radio_generacion_4g") and self.radio_generacion_4g.isChecked():
			return "4G"
		if hasattr(self, "radio_generacion_5g") and self.radio_generacion_5g.isChecked():
			return "5G"
		return ""

	def obtener_marco(self):
		"""Obtiene marco y mantiene actualizado el estado relacionado."""
		if hasattr(self, "radio_marco_si") and self.radio_marco_si.isChecked():
			return "C/M"
		return ""

	def crear_footer(self, main_layout):
		"""Crea el footer de la aplicación con botón de ayuda y toggle de tema"""
		footer = QFrame()
		footer.setObjectName("footer")
		footer.setFixedHeight(60)

		footer_layout = QHBoxLayout(footer)
		footer_layout.setContentsMargins(20, 10, 20, 10)

		self.btn_tema = QPushButton()
		self.btn_tema.setObjectName("btn_theme_toggle")
		self.btn_tema.setText("☀️ Modo Claro" if self.tema_oscuro else "🌙 Modo Oscuro")
		self.btn_tema.setFixedHeight(35)
		self.btn_tema.setCursor(Qt.CursorShape.PointingHandCursor)
		self.btn_tema.setToolTip("Cambiar entre modo claro y oscuro")
		self.btn_tema.clicked.connect(self.alternar_tema)
		footer_layout.addWidget(self.btn_tema)

		footer_layout.addStretch()

		footer_label = QLabel(f"© 2026 {self.EMPRESA_NOMBRE} - Todos los derechos reservados")
		footer_label.setObjectName("footer_text")
		footer_layout.addWidget(footer_label)

		footer_layout.addStretch()

		btn_ayuda = QPushButton()
		btn_ayuda.setObjectName("btn_help")

		try:
			ayuda_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, "ayuda.png"))
			if os.path.exists(ayuda_icon_path):
				ayuda_icon_pixmap = QPixmap(ayuda_icon_path)
				ayuda_icon_pixmap = ayuda_icon_pixmap.scaled(
					24,
					24,
					Qt.AspectRatioMode.KeepAspectRatio,
					Qt.TransformationMode.SmoothTransformation,
				)
				btn_ayuda.setIcon(QIcon(ayuda_icon_pixmap))
				btn_ayuda.setIconSize(QSize(24, 24))
				self.ayuda_icon_pixmap = ayuda_icon_pixmap
				self.ayuda_icon_path = ayuda_icon_path
			else:
				btn_ayuda.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
		except Exception:
			btn_ayuda.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))

		btn_ayuda.setFixedSize(45, 45)
		btn_ayuda.setCursor(Qt.CursorShape.PointingHandCursor)
		btn_ayuda.setToolTip("¿Necesitas ayuda? Haz clic para ver problemas comunes y soluciones")
		btn_ayuda.clicked.connect(self.abrir_ayuda)
		self.btn_ayuda = btn_ayuda
		footer_layout.addWidget(btn_ayuda)

		btn_info = QPushButton()
		btn_info.setObjectName("btn_help")

		try:
			info_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, "informacion.png"))
			if os.path.exists(info_icon_path):
				info_icon_pixmap = QPixmap(info_icon_path)
				info_icon_pixmap = info_icon_pixmap.scaled(
					24,
					24,
					Qt.AspectRatioMode.KeepAspectRatio,
					Qt.TransformationMode.SmoothTransformation,
				)
				btn_info.setIcon(QIcon(info_icon_pixmap))
				btn_info.setIconSize(QSize(24, 24))
				self.info_icon_pixmap = info_icon_pixmap
				self.info_icon_path = info_icon_path
			else:
				btn_info.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
		except Exception:
			btn_info.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))

		btn_info.setFixedSize(45, 45)
		btn_info.setCursor(Qt.CursorShape.PointingHandCursor)
		btn_info.setToolTip("Información del software y créditos del desarrollador")
		btn_info.clicked.connect(self.abrir_informacion)
		self.btn_info = btn_info
		footer_layout.addWidget(btn_info)

		main_layout.addWidget(footer)
		self.actualizar_iconos_footer()

	def alternar_tema(self):
		"""Alterna tema y mantiene actualizado el estado relacionado."""
		self.tema_oscuro = not self.tema_oscuro
		guardar_tema_global(
			self.tema_oscuro,
			getattr(self, "_ajustes_tema", None),
		)
		self.btn_tema.setText("☀️ Modo Claro" if self.tema_oscuro else "🌙 Modo Oscuro")
		self.aplicar_estilos()
		self.actualizar_header_logo()
		self.actualizar_iconos_footer()
		if hasattr(self, "_actualizar_iconos_formulario"):
			self._actualizar_iconos_formulario()
		self.actualizar_vista_previa()

		if self.ayuda_dialog:
			self.ayuda_dialog.aplicar_estilos()

	def actualizar_iconos_footer(self):
		"""Actualiza ayuda e información según el tema activo."""
		color_icono = "#FFFFFF" if self.tema_oscuro else "#3F454B"

		if hasattr(self, "btn_ayuda"):
			self.btn_ayuda.setGraphicsEffect(None)
			ruta_ayuda = getattr(
				self,
				"ayuda_icon_path",
				obtener_ruta_recurso(os.path.join(ICONS_DIR, "ayuda.png")),
			)
			pixmap_ayuda = recolorear_icono_footer(
				ruta_ayuda,
				color_icono,
				24,
				24,
			)
			if not pixmap_ayuda.isNull():
				self.btn_ayuda.setIcon(QIcon(pixmap_ayuda))

		if hasattr(self, "btn_info"):
			self.btn_info.setGraphicsEffect(None)
			ruta_info = getattr(
				self,
				"info_icon_path",
				obtener_ruta_recurso(
					os.path.join(ICONS_DIR, "informacion.png")
				),
			)
			pixmap_info = recolorear_icono_footer(
				ruta_info,
				color_icono,
				24,
				24,
			)
			if not pixmap_info.isNull():
				self.btn_info.setIcon(QIcon(pixmap_info))

	def aplicar_estilos(self):
		"""Aplica estilos y mantiene actualizado el estado relacionado."""
		if self.tema_oscuro:
			bg_main = "#121212"
			bg_secondary = "#1E1E1E"
			bg_container = "#2A2A2A"
			bg_input = "#2A2A2A"
			bg_input_hover = "#333333"
			bg_input_readonly = "#1A1A1A"
			bg_header = "#1E1E1E"
			bg_footer = "#1E1E1E"
			footer_text = "#FFFFFF"
			footer_button_bg = "#2A2A2A"
			footer_button_border = "transparent"
			footer_icon_color = "#FFFFFF"
			footer_button_hover_bg = "#CD0403"
			footer_button_hover_border = "#CD0403"
			footer_button_hover_color = "#FFFFFF"
			footer_button_pressed_bg = "#A30302"
			text_primary = "#E0E0E0"
			text_secondary = "#B0B0B0"
			text_disabled = "#666666"
			border_color = "#3A3A3A"
			border_hover = "#4A4A4A"
			scrollbar_bg = "#2A2A2A"
			scrollbar_handle = "#4A4A4A"
			scrollbar_hover = "#5A5A5A"
			preview_bg = "#2B2B2B"
			preview_border = "#E0E0E0"
			radio_text = "#E0E0E0"
			radio_indicator_bg = "#2D2D2D"
			radio_indicator_border = "#555555"
			radio_checked_bg = "#FF4444"
			radio_checked_ring = "#2D2D2D"
			radio_hover_border = "#FF4444"
		else:
			bg_main = "#F8F9FA"
			bg_secondary = "#FFFFFF"
			bg_container = "#FFFFFF"
			bg_input = "#FFFFFF"
			bg_input_hover = "#FAFBFC"
			bg_input_readonly = "#F5F5F5"
			bg_header = "#FFFFFF"
			bg_footer = "#FFFFFF"
			footer_text = "#5D6670"
			footer_button_bg = "#ECEFF2"
			footer_button_border = "#D7DCE1"
			footer_icon_color = "#2B2B2B"
			footer_button_hover_bg = "#F2D2D2"
			footer_button_hover_border = "#D98A8A"
			footer_button_hover_color = "#2B2B2B"
			footer_button_pressed_bg = "#E7BDBD"
			text_primary = "#1A1A1A"
			text_secondary = "#2C3E50"
			text_disabled = "#9E9E9E"
			border_color = "#DCDCDC"
			border_hover = "#B8B8B8"
			scrollbar_bg = "transparent"
			scrollbar_handle = "#DCDCDC"
			scrollbar_hover = "#BDBDBD"
			preview_bg = "#2B2B2B"
			preview_border = "#E0E0E0"
			radio_text = "#333333"
			radio_indicator_bg = "#FFFFFF"
			radio_indicator_border = "#A0A0A0"
			radio_checked_bg = "#FF4444"
			radio_checked_ring = "#FFFFFF"
			radio_hover_border = "#FF4444"

		self.setStyleSheet(
			f"""
			QWidget {{
				background-color: {bg_secondary};
				font-family: 'Segoe UI', 'Inter', sans-serif;
				font-size: 10pt;
				color: {text_primary};
			}}

			QMainWindow {{
				background-color: {bg_main};
			}}

			QLabel {{
				color: {text_secondary};
				padding: 2px;
				font-size: 10pt;
			}}

			QFrame#panel_card {{
				background-color: {bg_container};
				border: 1px solid {border_color};
				border-radius: 12px;
			}}

			QFrame#panel_card QWidget {{
				background-color: transparent;
			}}

			QLabel#card_title {{
				color: #E51A1A;
				font-size: 11pt;
				font-weight: 700;
				letter-spacing: 0.4px;
				padding: 0px;
				border: none;
				background: transparent;
			}}

			QFrame#card_separator {{
				background-color: #CD0403;
				border: none;
				margin: 0px 0px 4px 0px;
			}}

			QLabel#field_label {{
				color: {text_primary};
				font-size: 9.5pt;
				font-weight: 500;
				padding: 0px 0px 1px 0px;
				background: transparent;
				border: none;
			}}

			QLabel#section_title {{
				color: #CD0403;
				font-size: 11pt;
				font-weight: 600;
				letter-spacing: 0.5px;
				text-transform: uppercase;
				padding: 10px 0px 8px 0px;
				border-bottom: 2px solid #CD0403;
				margin-bottom: 15px;
			}}

			QLineEdit {{
				padding: 12px 14px;
				border: 1px solid {border_color};
				border-radius: 8px;
				background-color: {bg_input};
				color: {text_primary};
				font-size: 10pt;
				selection-background-color: #CD0403;
				selection-color: white;
			}}

			QLineEdit:hover {{
				border: 1px solid {border_hover};
				background-color: {bg_input_hover};
			}}

			QLineEdit:focus {{
				border: 2px solid #CD0403;
				background-color: {bg_input};
				outline: none;
			}}

			QComboBox {{
				padding: 12px 14px;
				border: 1px solid {border_color};
				border-radius: 8px;
				background-color: {bg_input};
				color: {text_primary};
				font-size: 10pt;
				selection-background-color: #CD0403;
				selection-color: white;
				min-height: 20px;
			}}

			QComboBox:hover {{
				border: 1px solid {border_hover};
				background-color: {bg_input_hover};
			}}

			QComboBox:focus {{
				border: 2px solid #CD0403;
				background-color: {bg_input};
			}}

			QComboBox::drop-down {{
				border: none;
				width: 30px;
				padding-right: 5px;
			}}

			QComboBox::down-arrow {{
				image: none;
				border: 2px solid {text_disabled};
				width: 8px;
				height: 8px;
				border-top: none;
				border-left: none;
			}}

			QComboBox QAbstractItemView {{
				background-color: {"#232323" if self.tema_oscuro else "#FFFFFF"};
				color: {text_primary};
				selection-background-color: #CD0403;
				selection-color: white;
				border: 1px solid {border_color};
				border-radius: 8px;
				outline: none;
				padding: 6px;
			}}

			QComboBox QAbstractItemView::item {{
				padding: 10px 12px;
				margin: 2px 0px;
				color: {text_primary};
				background-color: transparent;
				border-radius: 6px;
			}}

			QComboBox QAbstractItemView::item:hover {{
				background-color: {"#313131" if self.tema_oscuro else "#FCE8E8"};
				color: {"#FFFFFF" if self.tema_oscuro else "#CD0403"};
			}}

			QComboBox QAbstractItemView::item:selected {{
				background-color: #CD0403;
				color: white;
			}}

			QRadioButton {{
				background-color: {"#2D2D2D" if self.tema_oscuro else "#F0F0F0"};
				color: {radio_text};
				border: 1px solid {"#444444" if self.tema_oscuro else "#DCDCDC"};
				border-radius: 6px;
				padding: 5px 12px;
				font-size: 10pt;
				font-weight: bold;
				font-family: 'Segoe UI', sans-serif;
				text-align: center;
			}}

			QRadioButton::indicator {{
				width: 0px;
				height: 0px;
				image: none;
			}}

			QRadioButton::indicator:hover {{
				width: 0px;
				height: 0px;
			}}

			QRadioButton::indicator:checked {{
				width: 0px;
				height: 0px;
				image: none;
			}}

			QRadioButton::indicator:checked:pressed {{
				width: 0px;
				height: 0px;
			}}

			QRadioButton::indicator:checked:hover {{
				width: 0px;
				height: 0px;
			}}

			QRadioButton:hover {{
				background-color: {"#3D3D3D" if self.tema_oscuro else "#E5E5E5"};
				color: {"#FFFFFF" if self.tema_oscuro else "#333333"};
				border: 1px solid {"#555555" if self.tema_oscuro else "#D0D0D0"};
			}}

			QRadioButton:checked {{
				background-color: #FF4444;
				color: #FFFFFF;
				border: 1px solid #FF4444;
			}}

			QRadioButton:checked:hover {{
				background-color: #FF4444;
				color: #FFFFFF;
				border: 1px solid #FF4444;
			}}

			QPushButton#btn_print_primary {{
				background-color: #CD0403;
				color: #FFFFFF;
				border: 1px solid #F04B4A;
				border-radius: 10px;
				padding: 10px 14px;
				font-size: 11pt;
				font-weight: bold;
				letter-spacing: 0.5px;
			}}

			QPushButton#btn_print_primary:hover {{
				background-color: #E00504;
				border: 1px solid #FF6A69;
			}}

			QPushButton#btn_print_primary:pressed {{
				background-color: #A50302;
				border: 1px solid #CD0403;
			}}

			QPushButton#btn_primary {{
				background-color: #CD0403;
				color: white;
				border: 1px solid #E03535;
				border-radius: 10px;
				padding: 10px 14px;
				font-size: 11pt;
				font-weight: bold;
				letter-spacing: 0.5px;
			}}

			QPushButton#btn_primary:hover {{
				background-color: #B10302;
				border: 1px solid #F04B4A;
			}}

			QPushButton#btn_primary:pressed {{
				background-color: #8F0201;
				border: 1px solid #A50302;
			}}

			QPushButton#btn_success {{
				background-color: {"#2D3440" if self.tema_oscuro else "#F5F7FA"};
				color: {text_primary};
				border: 1px solid {border_color};
				border-radius: 10px;
				padding: 10px 14px;
				font-size: 10.5pt;
				font-weight: 700;
				letter-spacing: 0.3px;
			}}

			QPushButton#btn_success:hover {{
				background-color: {"#394252" if self.tema_oscuro else "#EBEEF3"};
				border: 1px solid #CD0403;
			}}

			QPushButton#btn_success:pressed {{
				background-color: {"#252B35" if self.tema_oscuro else "#DDE2E8"};
				border: 1px solid #B10302;
			}}

			QPushButton#btn_limpiar {{
				background-color: transparent;
				color: {"#B0B0B0" if self.tema_oscuro else "#666666"};
				border: 1px solid {"#555555" if self.tema_oscuro else "#CCCCCC"};
				border-radius: 8px;
				padding: 10px;
				font-size: 10pt;
				font-weight: 600;
			}}

			QPushButton#btn_limpiar:hover {{
				background-color: {"transparent" if self.tema_oscuro else "#FEE2E2"};
				color: {"#FFFFFF" if self.tema_oscuro else "#CD0403"};
				border: 1px solid #CD0403;
			}}

			QPushButton#btn_limpiar:pressed {{
				background-color: {"#2A2A2A" if self.tema_oscuro else "#FDD0D0"};
				border: 1px solid #A30302;
			}}

			QPushButton#btn_clean_link {{
				background-color: transparent;
				color: {text_secondary};
				border: none;
				padding: 4px 14px;
				font-size: 9.5pt;
				font-weight: 600;
				text-decoration: underline;
			}}

			QPushButton#btn_clean_link:hover {{
				color: #FF4A4A;
			}}

			QPushButton#btn_clean_link:pressed {{
				color: #CD0403;
			}}

			/* ==================== BOTÓN DE CONFIGURACIÓN ==================== */
			QPushButton#btn_config {{
				background-color: {"#343434" if self.tema_oscuro else "#EEF1F4"};
				color: {text_primary};
				border: 1px solid {border_color};
				border-radius: 10px;
				padding: 9px 12px;
				font-family: 'Segoe UI', 'Inter', sans-serif;
				font-size: 9.5pt;
				font-weight: 650;
			}}

			QPushButton#btn_config:hover {{
				background-color: {"#404040" if self.tema_oscuro else "#E2E7EC"};
				border: 1px solid #CD0403;
			}}

			QPushButton#btn_config:pressed {{
				background-color: {"#2B2B2B" if self.tema_oscuro else "#D5DCE3"};
				border: 1px solid #B10302;
			}}

			QPushButton#btn_list_primary {{
				background-color: #CD0403;
				color: white;
				border: none;
				border-radius: 8px;
				padding: 10px;
				font-size: 10pt;
				font-weight: bold;
			}}

			QPushButton#btn_list_primary:hover {{ background-color: #A50302; }}
			QPushButton#btn_list_primary:pressed {{ background-color: #8F0201; }}

			QPushButton#btn_list_secondary {{
				background-color: #2C3E50;
				color: white;
				border: none;
				border-radius: 8px;
				padding: 9px;
				font-size: 10pt;
				font-weight: bold;
			}}

			QPushButton#btn_list_secondary:hover {{ background-color: #34495E; }}
			QPushButton#btn_list_secondary:pressed {{ background-color: #1A252F; }}

			QPushButton#btn_list_danger {{
				background-color: #8E2C2C;
				color: white;
				border: none;
				border-radius: 8px;
				padding: 9px;
				font-size: 10pt;
				font-weight: bold;
			}}

			QPushButton#btn_list_danger:hover {{ background-color: #A63A3A; }}
			QPushButton#btn_list_danger:pressed {{ background-color: #742424; }}

			QListWidget#lista_modelos_widget {{
				background-color: {bg_input};
				color: {text_primary};
				border: 1px solid {border_color};
				border-radius: 8px;
				padding: 6px;
			}}

			QListWidget#lista_modelos_widget::item {{
				padding: 7px 10px;
				border-radius: 4px;
			}}

			/* Editor temporal que aparece al hacer doble clic o presionar F2.
			   Sobrescribe el padding global de QLineEdit para evitar texto recortado. */
			QListWidget#lista_modelos_widget QLineEdit {{
				padding: 4px 8px;
				min-height: 26px;
				background-color: {bg_input};
				color: {text_primary};
				border: 2px solid #CD0403;
				border-radius: 6px;
				selection-background-color: #CD0403;
				selection-color: white;
			}}

			QListWidget#lista_modelos_widget::item:selected {{
				background-color: {"#5A2929" if self.tema_oscuro else "#FEE2E2"};
				color: {"#FFE1E1" if self.tema_oscuro else "#CD0403"};
			}}

			/* Mantiene contraste suficiente al pasar el mouse sobre una fila. */
			QListWidget#lista_modelos_widget::item:hover:!selected {{
				background-color: {"#3A3A3A" if self.tema_oscuro else "#F3F4F6"};
				color: {"#FFFFFF" if self.tema_oscuro else "#1A1A1A"};
			}}

			/* Evita que el hover sobrescriba los colores de la selección. */
			QListWidget#lista_modelos_widget::item:selected:hover {{
				background-color: {"#663030" if self.tema_oscuro else "#FEE2E2"};
				color: {"#FFFFFF" if self.tema_oscuro else "#CD0403"};
			}}

			QFrame#preview_container {{
				background-color: {preview_bg};
				border-radius: 12px;
				padding: 20px;
				border: none;
			}}

			QLabel#preview_image {{
				background-color: transparent;
				border: none;
				outline: none;
				padding: 0px;
			}}

			QScrollArea {{
				border: none;
				background-color: transparent;
			}}

			QScrollArea#left_form_scroll {{
				border: none;
				background-color: transparent;
			}}

			QScrollArea#left_form_scroll > QWidget > QWidget {{
				background-color: transparent;
			}}

			QWidget#main_content_container {{
				background-color: transparent;
			}}

			QScrollBar:vertical {{
				background: {scrollbar_bg};
				width: 10px;
				margin: 0px;
			}}

			QScrollBar::handle:vertical {{
				background: {scrollbar_handle};
				border-radius: 5px;
				min-height: 30px;
			}}

			QScrollBar::handle:vertical:hover {{
				background: {scrollbar_hover};
			}}

			QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
			QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

			QFrame#header {{
				background-color: {bg_header};
				border: none;
				border-bottom: 3px solid #A30302;
			}}

			QLabel#header_logo {{
				border: none;
				background: transparent;
				padding: 0px;
			}}

			QFrame#footer {{
				background-color: {bg_footer};
				border: none;
				border-top: 1px solid {border_color};
			}}

			QFrame#footer QLabel,
			QLabel#footer_text {{
				color: {footer_text};
				font-size: 9pt;
				font-weight: 500;
				background: transparent;
			}}

			QPushButton#btn_theme_toggle {{
				background-color: {footer_button_bg};
				color: {footer_icon_color};
				border: 1px solid {footer_button_border};
				border-radius: 17px;
				padding: 6px 12px;
				font-size: 9pt;
			}}

			QPushButton#btn_theme_toggle:hover {{
				background-color: {footer_button_hover_bg};
				border: 1px solid {footer_button_hover_border};
				color: {footer_button_hover_color};
			}}

			QPushButton#btn_theme_toggle:pressed {{
				background-color: {footer_button_pressed_bg};
			}}

			QPushButton#btn_help {{
				background-color: {footer_button_bg};
				border: 1px solid {footer_button_border};
				border-radius: 22px;
				padding: 5px;
			}}

			QPushButton#btn_help:hover {{
				background-color: {footer_button_hover_bg};
				border: 1px solid {footer_button_hover_border};
			}}

			QPushButton#btn_help:pressed {{
				background-color: {footer_button_pressed_bg};
			}}

			QMessageBox {{
				background-color: {bg_secondary};
				color: {text_primary};
				border-radius: 15px;
			}}

			QMessageBox QLabel {{
				color: {text_primary};
				background: transparent;
				border: none;
				padding: 5px;
				min-width: 300px;
			}}

			QMessageBox QPushButton {{
				background-color: #CD0403;
				color: white;
				border: none;
				border-radius: 8px;
				padding: 8px 20px;
				font-size: 10pt;
				font-weight: 600;
				min-width: 80px;
				min-height: 32px;
			}}

			QMessageBox QPushButton:hover {{ background-color: #E00504; }}
			QMessageBox QPushButton:pressed {{ background-color: #A50302; }}
			"""
		)

		# Algunos controles de Qt (especialmente los popups de QComboBox)
		# necesitan estilos directos para respetar correctamente el tema.
		self._aplicar_estilos_especificos_tema()

	def _aplicar_estilos_especificos_tema(self):
		"""Aplica estilos robustos a controles que cambian con el tema."""
		if self.tema_oscuro:
			popup_bg = "#2B2B2B"
			popup_text = "#F0F0F0"
			popup_hover = "#3A3A3A"
			popup_border = "#4A4A4A"

			radio_bg = "#2D2D2D"
			radio_text = "#F0F0F0"
			radio_border = "#4A4A4A"
			radio_hover = "#3A3A3A"

			secondary_bg = "#303846"
			secondary_text = "#FFFFFF"
			secondary_border = "#465164"
			secondary_hover = "#3B4657"

			danger_bg = "#8E2C2C"
			danger_text = "#FFFFFF"
			danger_border = "#B24A4A"
			danger_hover = "#A63A3A"

			config_bg = "#343434"
			config_text = "#F0F0F0"
			config_border = "#4A4A4A"
			config_hover = "#414141"

			clean_text = "#C5C5C5"
		else:
			popup_bg = "#FAFAFA"
			popup_text = "#1A1A1A"
			popup_hover = "#F3E3E3"
			popup_border = "#CFCFCF"

			radio_bg = "#F3F4F6"
			radio_text = "#202020"
			radio_border = "#C8CDD3"
			radio_hover = "#E6E9ED"

			secondary_bg = "#E9EEF4"
			secondary_text = "#1F2933"
			secondary_border = "#AEB8C3"
			secondary_hover = "#DDE5ED"

			danger_bg = "#FCE8E8"
			danger_text = "#8E2C2C"
			danger_border = "#D98282"
			danger_hover = "#F6D4D4"

			config_bg = "#EEF1F4"
			config_text = "#1F2933"
			config_border = "#B8C0C8"
			config_hover = "#E1E6EB"

			clean_text = "#555555"

		# Menús desplegables: el popup no siempre hereda bien el tema del padre.
		combo_names = (
			"combo_tipo_etiqueta",
			"combo_marca",
			"combo_calidad",
		)
		for name in combo_names:
			combo = getattr(self, name, None)
			if combo is None:
				continue

			combo.view().setStyleSheet(
				f"""
				QAbstractItemView {{
					background-color: {popup_bg};
					color: {popup_text};
					border: 1px solid {popup_border};
					border-radius: 8px;
					outline: none;
					padding: 6px;
					selection-background-color: #CD0403;
					selection-color: #FFFFFF;
				}}
				QAbstractItemView::item {{
					background-color: transparent;
					color: {popup_text};
					padding: 10px 12px;
					margin: 2px 0px;
					border-radius: 6px;
				}}
				QAbstractItemView::item:hover {{
					background-color: {popup_hover};
					color: {popup_text};
				}}
				QAbstractItemView::item:selected {{
					background-color: #CD0403;
					color: #FFFFFF;
				}}
				"""
			)

		# Opciones segmentadas de Generación y Con marco.
		radio_style = f"""
			QRadioButton {{
				background-color: {radio_bg};
				color: {radio_text};
				border: 1px solid {radio_border};
				border-radius: 7px;
				padding: 6px 12px;
				font-size: 10pt;
				font-weight: 700;
			}}
			QRadioButton::indicator {{
				width: 0px;
				height: 0px;
				image: none;
			}}
			QRadioButton:hover {{
				background-color: {radio_hover};
				color: {radio_text};
				border: 1px solid #CD0403;
			}}
			QRadioButton:checked {{
				background-color: #FF4444;
				color: #FFFFFF;
				border: 1px solid #E22222;
			}}
			QRadioButton:checked:hover {{
				background-color: #E93636;
				color: #FFFFFF;
				border: 1px solid #CD0403;
			}}
		"""
		for name in (
			"radio_generacion_4g",
			"radio_generacion_5g",
			"radio_marco_si",
			"radio_marco_no",
		):
			radio = getattr(self, name, None)
			if radio is not None:
				radio.setStyleSheet(radio_style)

		# Acción principal: siempre roja, con texto blanco en ambos temas.
		if hasattr(self, "btn_imprimir"):
			self.btn_imprimir.setStyleSheet(
				"""
				QPushButton {
					background-color: #CD0403;
					color: #FFFFFF;
					border: 1px solid #F04B4A;
					border-radius: 10px;
					padding: 10px 14px;
					font-size: 11pt;
					font-weight: 700;
				}
				QPushButton:hover {
					background-color: #E00504;
					color: #FFFFFF;
					border: 1px solid #FF6A69;
				}
				QPushButton:pressed {
					background-color: #A50302;
					color: #FFFFFF;
					border: 1px solid #CD0403;
				}
				"""
			)

		# Guardar PDF y Configurar impresora.
		if hasattr(self, "btn_guardar"):
			self.btn_guardar.setStyleSheet(
				f"""
				QPushButton {{
					background-color: {secondary_bg};
					color: {secondary_text};
					border: 1px solid {secondary_border};
					border-radius: 10px;
					padding: 9px 12px;
					font-size: 10pt;
					font-weight: 700;
				}}
				QPushButton:hover {{
					background-color: {secondary_hover};
					color: {secondary_text};
					border: 1px solid #CD0403;
				}}
				QPushButton:pressed {{
					background-color: {secondary_bg};
					color: {secondary_text};
					border: 1px solid #A50302;
				}}
				"""
			)

		if hasattr(self, "btn_config_impresora"):
			self.btn_config_impresora.setStyleSheet(
				f"""
				QPushButton {{
					background-color: {config_bg};
					color: {config_text};
					border: 1px solid {config_border};
					border-radius: 10px;
					padding: 9px 12px;
					font-size: 9.5pt;
					font-weight: 650;
				}}
				QPushButton:hover {{
					background-color: {config_hover};
					color: {config_text};
					border: 1px solid #CD0403;
				}}
				QPushButton:pressed {{
					background-color: {config_bg};
					color: {config_text};
					border: 1px solid #A50302;
				}}
				"""
			)

		if hasattr(self, "btn_limpiar"):
			self.btn_limpiar.setStyleSheet(
				f"""
				QPushButton {{
					background-color: transparent;
					color: {clean_text};
					border: none;
					padding: 4px 14px;
					font-size: 9.5pt;
					font-weight: 600;
					text-decoration: underline;
				}}
				QPushButton:hover {{
					color: #CD0403;
				}}
				"""
			)

		# Botones del modo Lista de modelos.
		if hasattr(self, "btn_agregar_modelo_lista"):
			self.btn_agregar_modelo_lista.setStyleSheet(
				"""
				QPushButton {
					background-color: #CD0403;
					color: #FFFFFF;
					border: 1px solid #E03535;
					border-radius: 8px;
					padding: 9px 12px;
					font-size: 10pt;
					font-weight: 700;
				}
				QPushButton:hover {
					background-color: #E00504;
					color: #FFFFFF;
					border: 1px solid #FF6A69;
				}
				QPushButton:pressed {
					background-color: #A50302;
					color: #FFFFFF;
				}
				"""
			)

		secondary_style = f"""
			QPushButton {{
				background-color: {secondary_bg};
				color: {secondary_text};
				border: 1px solid {secondary_border};
				border-radius: 8px;
				padding: 8px 10px;
				font-size: 10pt;
				font-weight: 700;
			}}
			QPushButton:hover {{
				background-color: {secondary_hover};
				color: {secondary_text};
				border: 1px solid #CD0403;
			}}
			QPushButton:pressed {{
				background-color: {secondary_bg};
				color: {secondary_text};
				border: 1px solid #A50302;
			}}
		"""
		for name in ("btn_subir_modelo", "btn_bajar_modelo"):
			button = getattr(self, name, None)
			if button is not None:
				button.setStyleSheet(secondary_style)

		if hasattr(self, "btn_eliminar_modelo"):
			self.btn_eliminar_modelo.setStyleSheet(
				f"""
				QPushButton {{
					background-color: {danger_bg};
					color: {danger_text};
					border: 1px solid {danger_border};
					border-radius: 8px;
					padding: 8px 10px;
					font-size: 10pt;
					font-weight: 700;
				}}
				QPushButton:hover {{
					background-color: {danger_hover};
					color: {danger_text};
					border: 1px solid #CD0403;
				}}
				QPushButton:pressed {{
					background-color: {danger_bg};
					color: {danger_text};
					border: 1px solid #A50302;
				}}
				"""
			)

	def obtener_marca(self):
		"""Obtiene marca y mantiene actualizado el estado relacionado."""
		return self.combo_marca.currentText().strip().upper()

	def obtener_modelo(self):
		"""Obtiene modelo y mantiene actualizado el estado relacionado."""
		return self.entry_modelo.text().strip().upper()

	def obtener_modelo_historial(self):
		"""Obtiene modelo historial y mantiene actualizado el estado relacionado."""
		if self.es_modo_lista_modelos():
			return " ; ".join(self._obtener_modelos_lista())
		return self.obtener_modelo()

	def obtener_calidad(self):
		"""Obtiene calidad y mantiene actualizado el estado relacionado."""
		return self.combo_calidad.currentText().strip().upper()

	def obtener_calidad_historial(self):
		"""Obtiene calidad historial y mantiene actualizado el estado relacionado."""
		if self.es_modo_lista_modelos():
			return "LISTA DE MODELOS"
		return self.obtener_calidad()

	def obtener_calidad_etiqueta(self):
		"""Obtiene calidad etiqueta y mantiene actualizado el estado relacionado."""
		calidad = self.obtener_calidad()
		return "" if calidad == "SIN CALIDAD" else calidad

	def validar_datos(self):
		"""Valida datos y mantiene actualizado el estado relacionado."""
		marca = self.obtener_marca()
		if self.es_modo_lista_modelos():
			modelos = self._obtener_modelos_lista()
			if not marca:
				KBKADialog.warning(self, "Datos Incompletos", "Por favor seleccione la marca")
				return False
			if not modelos:
				KBKADialog.warning(self, "Datos Incompletos", "Por favor agregue al menos un modelo")
				return False
			return True

		modelo = self.obtener_modelo()
		calidad = self.obtener_calidad()

		if not marca:
			KBKADialog.warning(self, "Datos Incompletos", "Por favor seleccione la marca")
			return False
		if not modelo:
			KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese el modelo")
			return False
		if not calidad:
			KBKADialog.warning(self, "Datos Incompletos", "Por favor seleccione la calidad")
			return False
		return True

	def limpiar_campos(self):
		"""Ejecuta la lógica asociada a limpiar campos."""
		confirmado = KBKADialog.confirm(
			self,
			"Limpiar Campos",
			"¿Estás seguro de que deseas limpiar todos los campos?\n\nEsta acción borrará la información ingresada.",
		)
		if confirmado:
			# Dejar Marca y Calidad sin selección por defecto (vacío)
			try:
				self.combo_marca.setCurrentIndex(-1)
			except Exception:
				# Fallback: limpiar texto si el combo es editable
				try:
					self.combo_marca.setEditText("")
				except Exception:
					pass
			self.entry_modelo.clear()
			try:
				self.combo_calidad.setCurrentIndex(-1)
			except Exception:
				try:
					self.combo_calidad.setEditText("")
				except Exception:
					pass
			if hasattr(self, "entry_modelo_lista"):
				self.entry_modelo_lista.clear()
			if hasattr(self, "lista_modelos_widget"):
				self.lista_modelos_widget.clear()
			if hasattr(self, "radio_generacion_4g"):
				self.radio_generacion_4g.setChecked(False)
			if hasattr(self, "radio_generacion_5g"):
				self.radio_generacion_5g.setChecked(False)
			if hasattr(self, "radio_marco_no"):
				self.radio_marco_no.setChecked(True)
			self.actualizar_vista_previa()
			self.combo_marca.setFocus()

	def _font(self, font_name, size):
		"""Ejecuta la lógica asociada a font."""
		font_candidates = [font_name]
		if os.name == "nt":
			font_candidates.extend([
				os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", font_name),
				os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", font_name.lower()),
			])

		for candidate in font_candidates:
			try:
				return ImageFont.truetype(candidate, max(1, int(size)))
			except Exception:
				continue
		return ImageFont.load_default()

	def _fit_single_line_font(self, draw, text, font_name, start_size, min_size, max_width):
		"""Ejecuta la lógica asociada a fit single line font."""
		for size in range(start_size, min_size - 1, -1):
			font = self._font(font_name, size)
			if self._measure(draw, text, font)[0] <= max_width:
				return font
		return self._font(font_name, min_size)

	def _measure(self, draw, text, font):
		"""Ejecuta la lógica asociada a measure."""
		bbox = draw.textbbox((0, 0), text, font=font)
		return bbox[2] - bbox[0], bbox[3] - bbox[1]

	def _wrap_text(self, draw, text, font, max_width):
		"""Ejecuta la lógica asociada a wrap text."""
		words = text.split()
		if not words:
			return [""]
		lines = []
		current = words[0]
		for word in words[1:]:
			candidate = f"{current} {word}"
			width, _ = self._measure(draw, candidate, font)
			if width <= max_width:
				current = candidate
			else:
				lines.append(current)
				current = word
		lines.append(current)
		return lines

	def _wrap_text_fixed_size(self, draw, text, font, max_width):
		"""Ejecuta la lógica asociada a wrap text fixed size."""
		words = text.split()
		if not words:
			return [""]

		lines = []
		current = ""

		def split_long_token(token):
			"""Ejecuta la lógica asociada a split long token."""
			chunks = []
			chunk = ""
			for char in token:
				candidate = chunk + char
				if chunk and self._measure(draw, candidate, font)[0] > max_width:
					chunks.append(chunk)
					chunk = char
				else:
					chunk = candidate
			if chunk:
				chunks.append(chunk)
			return chunks

		for word in words:
			candidate = word if not current else f"{current} {word}"
			if self._measure(draw, candidate, font)[0] <= max_width:
				current = candidate
				continue

			if current:
				lines.append(current)
				current = ""

			if self._measure(draw, word, font)[0] <= max_width:
				current = word
			else:
				long_parts = split_long_token(word)
				for part in long_parts[:-1]:
					lines.append(part)
				current = long_parts[-1]

		if current:
			lines.append(current)
		return lines

	def _fit_font_and_lines(self, draw, text, font_name, start_size, min_size, max_width):
		"""Ejecuta la lógica asociada a fit font and lines."""
		for size in range(start_size, min_size - 1, -1):
			font = self._font(font_name, size)
			lines = self._wrap_text(draw, text, font, max_width)
			if all(self._measure(draw, line, font)[0] <= max_width for line in lines):
				return font, lines
		font = self._font(font_name, min_size)
		return font, self._wrap_text(draw, text, font, max_width)

	def _mm_to_px(self, value_mm, dpi):
		"""Ejecuta la lógica asociada a mm to px."""
		return int((value_mm / 25.4) * dpi)

	def _mm_to_cm(self, value_mm):
		"""Ejecuta la lógica asociada a mm to cm."""
		return value_mm / 10.0

	def _generar_qr_imagen(self, payload, qr_target):
		"""Ejecuta la lógica asociada a generar qr imagen."""
		if qrcode is None:
			return None
		try:
			qr = qrcode.QRCode(
				version=None,
				error_correction=qrcode.constants.ERROR_CORRECT_M,
				box_size=2,
				border=0,
			)
			qr.add_data(payload)
			qr.make(fit=True)
			qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
			return qr_img.resize((qr_target, qr_target), Image.NEAREST)
		except Exception as e:
			print(f"Error al generar QR: {e}")
			return None

	def _pegar_qr_en_etiqueta(self, img, base_size, payload):
		"""Ejecuta la lógica asociada a pegar qr en etiqueta."""
		qr_target = max(12, int(base_size * 0.10))
		qr_img = self._generar_qr_imagen(payload, qr_target)
		if qr_img is None:
			return
		margin_for_qr = max(6, int(base_size * 0.03))
		qr_x = base_size - qr_target - margin_for_qr
		qr_y = base_size - qr_target - margin_for_qr
		img.paste(qr_img, (qr_x, qr_y))

	def _dividir_modelos_en_columnas(self, modelos):
		"""Ejecuta la lógica asociada a dividir modelos en columnas."""
		if len(modelos) < 7:
			return [modelos]
		mitad = (len(modelos) + 1) // 2
		return [modelos[:mitad], modelos[mitad:]]

	def _ajustar_fuente_encabezado_lista(self, draw, texto, usable_width, escala):
		"""Ajusta el encabezado de la lista usando tipografía en negrita."""
		for size in range(max(1, int(30 * escala)), 0, -1):
			font = self._font("segoeuib.ttf", size)
			qt_font = QFont("Segoe UI")
			qt_font.setBold(True)
			qt_font.setPixelSize(size)
			metrics = QFontMetrics(qt_font)
			pil_width = self._measure(draw, texto, font)[0]
			if max(metrics.horizontalAdvance(texto), pil_width) <= usable_width:
				return font, metrics
		font = self._font("segoeuib.ttf", 1)
		qt_font.setBold(True)
		qt_font.setPixelSize(1)
		return font, QFontMetrics(qt_font)

	def _ajustar_fuente_lista_modelos(self, draw, modelos, usable_width, usable_height, escala):
		"""Ejecuta la lógica asociada a ajustar fuente lista modelos."""
		columnas = self._dividir_modelos_en_columnas(modelos)
		column_gap = int(14 * escala) if len(columnas) > 1 else 0
		line_gap = max(1, int(6 * escala))
		# En dos columnas se limita ligeramente el tamaño máximo para conservar
		# aire visual junto al marco, incluso cuando hay pocos modelos cortos.
		max_size_base = 42 if len(columnas) > 1 else 46
		start_size = max(1, int(max_size_base * escala))
		min_size = 1

		for size in range(start_size, min_size - 1, -1):
			font = self._font("segoeui.ttf", size)
			qt_font = QFont("Segoe UI")
			qt_font.setWeight(QFont.Weight.Normal)
			qt_font.setPixelSize(max(1, size))
			metrics = QFontMetrics(qt_font)

			column_widths = []
			for columna in columnas:
				# QFontMetrics gobierna el posicionamiento; la medida PIL evita que
				# diferencias entre motores tipográficos recorten el texto al dibujarlo.
				column_widths.append(max((
					max(metrics.horizontalAdvance(modelo), self._measure(draw, modelo, font)[0])
					for modelo in columna
				), default=0))
			# El bloque se calcula con el ancho real de cada columna. Así, si una
			# columna contiene nombres más largos, el conjunto visible completo
			# sigue centrado y la columna larga no queda cargada hacia un borde.
			block_width = sum(column_widths) + column_gap * max(0, len(columnas) - 1)
			if block_width > usable_width:
				continue

			line_height = max(
				metrics.height(),
				max((self._measure(draw, modelo, font)[1] for modelo in modelos), default=0),
			)
			column_heights = [
				(len(columna) * line_height) + (max(0, len(columna) - 1) * line_gap)
				for columna in columnas
			]

			block_height = max(column_heights) if column_heights else 0
			if block_height <= usable_height:
				return font, columnas, column_widths, column_gap, line_gap, line_height, block_width, block_height

		font = self._font("segoeui.ttf", min_size)
		qt_font = QFont("Segoe UI")
		qt_font.setWeight(QFont.Weight.Normal)
		qt_font.setPixelSize(min_size)
		metrics = QFontMetrics(qt_font)
		column_widths = [max((
			max(metrics.horizontalAdvance(modelo), self._measure(draw, modelo, font)[0])
			for modelo in columna
		), default=0) for columna in columnas]
		block_width = sum(column_widths) + column_gap * max(0, len(columnas) - 1)
		line_height = max(metrics.height(), max((self._measure(draw, modelo, font)[1] for modelo in modelos), default=0))
		column_heights = [
			(len(columna) * line_height) + (max(0, len(columna) - 1) * line_gap)
			for columna in columnas
		]
		block_height = max(column_heights) if column_heights else 0
		return font, columnas, column_widths, column_gap, line_gap, line_height, block_width, block_height

	def _generar_imagen_etiqueta_lista(self, escala=1.0):
		"""Ejecuta la lógica asociada a generar imagen etiqueta lista."""
		base_size = int(self.LABEL_SIZE_PX * escala)
		img = Image.new("RGB", (base_size, base_size), "white")
		draw = ImageDraw.Draw(img)

		# Margen lateral de seguridad: deja espacio visible entre el texto y el
		# borde negro. Al reducir el ancho útil, la fuente se ajusta sola.
		margin_x = int(30 * escala)
		upper_margin = int(37 * escala)
		lower_margin = int(40 * escala)
		brand = self.obtener_marca() or "MARCA"
		modelos = self._obtener_modelos_lista() or ["MODELO"]

		usable_width = base_size - (margin_x * 2)
		brand_font, brand_metrics = self._ajustar_fuente_encabezado_lista(draw, brand, usable_width, escala)
		brand_left, brand_top, brand_right, brand_bottom = draw.textbbox((0, 0), brand, font=brand_font)
		brand_h = max(brand_bottom - brand_top, brand_metrics.height())
		brand_x = ((base_size - (brand_right - brand_left)) // 2) - brand_left
		brand_y = upper_margin - brand_top
		draw.text((brand_x, brand_y), brand, fill="#111111", font=brand_font)

		list_top = upper_margin + brand_h + int(14 * escala)
		usable_height = max(1, base_size - list_top - lower_margin)
		font, columnas, column_widths, column_gap, line_gap, line_height, block_width, block_height = self._ajustar_fuente_lista_modelos(
			draw,
			modelos,
			usable_width,
			usable_height,
			escala,
		)

		start_y = list_top + max(0, (usable_height - block_height) // 2)
		if len(columnas) == 1:
			y = start_y
			for modelo in columnas[0]:
				left, top, right, bottom = draw.textbbox((0, 0), modelo, font=font)
				text_w = right - left
				x = ((base_size - text_w) // 2) - left
				draw.text((x, y - top), modelo, fill="#111111", font=font)
				y += line_height + line_gap
		else:
			# Centrar el bloque visible usando el ancho real de cada columna.
			# Esto evita que una columna con nombres largos empuje visualmente
			# todo el contenido hacia la derecha.
			total_block_width = sum(column_widths) + column_gap * (len(columnas) - 1)
			block_x = (base_size - total_block_width) // 2
			col_x_start = block_x

			for col_index, columna in enumerate(columnas):
				col_width = column_widths[col_index]
				y = start_y
				for modelo in columna:
					left, top, right, bottom = draw.textbbox((0, 0), modelo, font=font)
					text_w = right - left
					# Cada modelo queda centrado dentro del ancho natural de su columna.
					x = col_x_start + (col_width - text_w) // 2 - left
					draw.text((x, y - top), modelo, fill="#111111", font=font)
					y += line_height + line_gap

				col_x_start += col_width + column_gap

		try:
			border_cm = 0.25
			border_px = max(1, int((border_cm / 9.0) * base_size))
			for i in range(border_px):
				draw.rectangle([i, i, base_size - 1 - i, base_size - 1 - i], outline="black")
		except Exception as e:
			print(f"Error al dibujar contorno: {e}")

		return img

	def generar_imagen_etiqueta(self, escala=1.0):
		"""Ejecuta la lógica asociada a generar imagen etiqueta."""
		if self.es_modo_lista_modelos():
			return self._generar_imagen_etiqueta_lista(escala)

		base_size = int(self.LABEL_SIZE_PX * escala)
		img = Image.new("RGB", (base_size, base_size), "white")
		draw = ImageDraw.Draw(img)

		margin_x = int(18 * escala)
		margin_top = int(12 * escala)
		margin_bottom = int(12 * escala)
		y = margin_top

		# Encabezado de empresa eliminado: no insertar logo en la etiqueta

		content_top = y
		content_bottom = base_size - margin_bottom
		content_height = max(1, content_bottom - content_top)

		brand = self.obtener_marca() or "MARCA"
		model = self.obtener_modelo() or "MODELO"
		quality = self.obtener_calidad_etiqueta()

		usable_width = base_size - (margin_x * 2)
		brand = brand.upper()
		model = model.upper()
		quality = quality.upper()

		brand_font = self._fit_single_line_font(draw, brand, "segoeui.ttf", int(30 * escala), int(18 * escala), usable_width)
		# Dynamic sizing for model: use a larger single-line font for short models,
		# otherwise keep default size and allow wrapping.
		default_model_size = int(54 * escala)
		max_model_size = int(90 * escala)
		model_font = None
		# Try larger sizes first so short models use a big font
		for size in range(max_model_size, default_model_size - 1, -1):
			f = self._font("segoeuib.ttf", size)
			if self._measure(draw, model, f)[0] <= usable_width:
				model_font = f
				model_lines = [model]
				break

		if model_font is None:
			# Couldn't fit single-line even at default size: use default and wrap
			model_font = self._font("segoeuib.ttf", default_model_size)
			model_lines = self._wrap_text_fixed_size(draw, model, model_font, usable_width)

		quality_font = None
		if quality:
			quality_font = self._fit_single_line_font(draw, quality, "segoeuiz.ttf", int(30 * escala), int(18 * escala), usable_width)
		submodelo_parts = [parte for parte in [self.obtener_generacion(), self.obtener_marco()] if parte]
		submodelo_text = " ".join(submodelo_parts)

		brand_left, brand_top, brand_right, brand_bottom = draw.textbbox((0, 0), brand, font=brand_font)
		if quality_font is not None:
			quality_left, quality_top, quality_right, quality_bottom = draw.textbbox((0, 0), quality, font=quality_font)
		else:
			quality_left = quality_top = quality_right = quality_bottom = 0
		brand_w = brand_right - brand_left
		brand_h = brand_bottom - brand_top
		quality_w = quality_right - quality_left
		quality_h = quality_bottom - quality_top

		model_metrics = []
		for line in model_lines:
			line_left, line_top, line_right, line_bottom = draw.textbbox((0, 0), line, font=model_font)
			model_metrics.append((line, line_left, line_top, line_right, line_bottom))

		model_height = 0
		# Cuando el modelo ocupa varias líneas, agregamos un poco más de
		# interlineado para que no se vean tan juntas, sin cambiar mucho
		# la composición general de la etiqueta.
		line_spacing = int(6 * escala) if len(model_metrics) > 1 else int(2 * escala)
		for index, (_, _, line_top, _, line_bottom) in enumerate(model_metrics):
			model_height += line_bottom - line_top
			if index < len(model_metrics) - 1:
				model_height += line_spacing

		# Altura total del bloque Modelo (+ Submodelo si existe) -> centra el bloque completo
		h_modelo = model_height
		# obtener top del primer renglón del modelo (para offset al dibujar)
		top_m = model_metrics[0][2] if model_metrics else 0

		submodelo_parts = [parte for parte in [self.obtener_generacion(), self.obtener_marco()] if parte]
		submodelo_text = " ".join(submodelo_parts)

		h_sub = 0
		top_s = 0
		if submodelo_text:
			# calcular altura real del subtexto
			sub_left, sub_top, sub_right, sub_bottom = draw.textbbox((0, 0), submodelo_text, font=self._fit_single_line_font(draw, submodelo_text, "segoeuib.ttf", int(53 * escala), int(37 * escala), usable_width))
			h_sub = sub_bottom - sub_top
			top_s = sub_top

		separacion = int(15 * escala)

		if h_sub > 0:
			altura_total_bloque = h_modelo + separacion + h_sub
		else:
			altura_total_bloque = h_modelo

		label_center_y = base_size // 2
		y_inicio_bloque = label_center_y - (altura_total_bloque // 2)

		# Marca y calidad quedan ancladas a los bordes superior e inferior.
		# Se escalan los márgenes para que la vista previa e impresión se vean iguales.
		upper_margin = int(37 * escala)
		lower_margin = int(40 * escala)
		brand_y = upper_margin - brand_top
		quality_y = base_size - quality_h - lower_margin - quality_top if quality_font is not None else 0

		brand_x = (base_size - brand_w) // 2
		quality_x = (base_size - quality_w) // 2

		draw.text((brand_x, brand_y), brand, fill="#111111", font=brand_font)

		# Dibujar modelo: tratamos el bloque modelo (+ submodelo) como una sola unidad centrada
		current_visual_top = y_inicio_bloque
		for index, (line, line_left, line_top, line_right, line_bottom) in enumerate(model_metrics):
			line_w = line_right - line_left
			line_h = line_bottom - line_top
			line_x = (base_size - line_w) // 2
			line_y = current_visual_top - line_top
			draw.text((line_x, line_y), line, fill="#111111", font=model_font)
			current_visual_top += line_h + line_spacing

		# Dibujar submodelo centrado respecto al bloque (si existe)
		if submodelo_text:
			# recalcular fuente y medidas reales para dibujo
			submodelo_font = self._fit_single_line_font(
				draw,
				submodelo_text,
				"segoeuib.ttf",
				int(53 * escala),
				int(37 * escala),
				usable_width,
			)
			sub_left, sub_top, sub_right, sub_bottom = draw.textbbox((0, 0), submodelo_text, font=submodelo_font)
			sub_w = sub_right - sub_left
			sub_x = (base_size - sub_w) // 2
			# y_sub según fórmula: y_inicio_bloque + h_modelo + separacion - top_s
			y_sub = y_inicio_bloque + h_modelo + separacion - sub_top
			draw.text((sub_x, y_sub), submodelo_text, fill="#111111", font=submodelo_font)

		if quality_font is not None:
			draw.text((quality_x, quality_y), quality, fill="#111111", font=quality_font)

		# Añadir contorno negro alrededor de la etiqueta.
		try:
			border_cm = 0.25
			border_px = max(1, int((border_cm / 9.0) * base_size))
			for i in range(border_px):
				draw.rectangle(
					[i, i, base_size - 1 - i, base_size - 1 - i],
					outline="black",
				)
		except Exception as e:
			print(f"Error al dibujar contorno: {e}")

		if self.SHOW_QR_ON_LABEL:
			payload = f"{brand}|{model}|{quality}|{submodelo_text}"
			self._pegar_qr_en_etiqueta(img, base_size, payload)

		return img

	def eventFilter(self, objeto, evento):
		"""Ejecuta la lógica asociada a eventFilter."""
		if (
			hasattr(self, "preview_container")
			and objeto is self.preview_container
			and evento.type() == evento.Type.Resize
		):
			QTimer.singleShot(0, self.ajustar_vista_previa)
		return super().eventFilter(objeto, evento)

	def ajustar_vista_previa(self):
		"""Ejecuta la lógica asociada a ajustar vista previa."""
		if not hasattr(self, "preview_pixmap_original"):
			return
		if self.preview_pixmap_original.isNull():
			return
		if not hasattr(self, "preview_container"):
			return

		rect = self.preview_container.contentsRect()
		margenes = self.preview_layout.contentsMargins()
		ancho = max(1, rect.width() - margenes.left() - margenes.right())
		alto = max(1, rect.height() - margenes.top() - margenes.bottom())

		pixmap = self.preview_pixmap_original.scaled(
			ancho,
			alto,
			Qt.AspectRatioMode.KeepAspectRatio,
			Qt.TransformationMode.SmoothTransformation,
		)
		self.preview_label.setPixmap(pixmap)
		self.preview_label.setText("")

	def actualizar_vista_previa(self):
		"""Actualiza vista previa y mantiene actualizado el estado relacionado."""
		if not hasattr(self, "preview_label"):
			return
		try:
			img = self.generar_imagen_etiqueta(escala=self.PREVIEW_SCALE)
			buffer = io.BytesIO()
			img.save(buffer, format="PNG")

			pixmap = QPixmap()
			if not pixmap.loadFromData(buffer.getvalue(), "PNG"):
				raise RuntimeError("No fue posible convertir la vista previa")

			self.preview_pixmap_original = pixmap
			QTimer.singleShot(0, self.ajustar_vista_previa)
		except Exception as e:
			print(f"Error al actualizar vista previa: {e}")
			self.preview_label.clear()
			self.preview_label.setText("No se pudo generar la vista previa")
	def guardar_pdf(self):
		"""Genera la etiqueta actual y la guarda como archivo PDF."""
		if not self.validar_datos():
			return

		try:
			fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
			nombre_archivo = f"Etiqueta_CEDIS_{self.obtener_marca()}_{fecha}.pdf"

			filepath, _ = QFileDialog.getSaveFileName(
				self,
				"Guardar Etiqueta CEDIS",
				nombre_archivo,
				"PDF files (*.pdf)",
			)

			if not filepath:
				return
			if not filepath.lower().endswith(".pdf"):
				filepath += ".pdf"

			img = self.generar_imagen_etiqueta(escala=self.PDF_SCALE)
			page_size_cm = self._mm_to_cm(self.LABEL_PAGE_MM)
			content_size_cm = self._mm_to_cm(self.LABEL_CONTENT_MM)
			left_cm = self._mm_to_cm(self.LABEL_LEFT_MM)
			bottom_cm = self._mm_to_cm(self.LABEL_BOTTOM_MM)
			c = canvas.Canvas(filepath, pagesize=(page_size_cm * cm, page_size_cm * cm))

			img_buffer = io.BytesIO()
			img.save(img_buffer, format="PNG")
			img_buffer.seek(0)
			img_reader = ImageReader(img_buffer)
			c.drawImage(
				img_reader,
				left_cm * cm,
				bottom_cm * cm,
				width=content_size_cm * cm,
				height=content_size_cm * cm,
			)
			c.save()

			self.registrar_historial("guardado", filepath)
			KBKADialog.success(
				self,
				"Guardado Exitoso",
				f"La etiqueta se ha guardado correctamente en:\n{filepath}",
			)
		except Exception as e:
			KBKADialog.error(self, "Error", f"Error al guardar el PDF:\n{str(e)}")

	def imprimir_etiqueta(self):
		"""Imprime la etiqueta de modelos mediante QtPrintSupport."""
		if not self.validar_datos():
			return

		if not QT_PRINT_AVAILABLE:
			detalle = (
				"No fue posible cargar Qt PrintSupport.\n\n"
				"Se generó un diagnóstico en:\n"
				+ (
					QT_PRINT_DIAGNOSTIC_PATH
					or r"%APPDATA%\KBKA_Shop\diagnostico_impresion_modelos.txt"
				)
			)
			KBKADialog.warning(self, "Impresión No Disponible", detalle)
			return

		nombre_impresora = self.cargar_impresora_config()
		if not nombre_impresora:
			nombre_impresora = str(QPrinterInfo.defaultPrinterName() or "").strip()

		if not nombre_impresora:
			KBKADialog.warning(
				self,
				"Impresora No Configurada",
				"No se encontró una impresora predeterminada para imprimir.",
			)
			return

		painter = None
		try:
			img = self.generar_imagen_etiqueta(escala=self.PDF_SCALE)
			if img.mode != "RGB":
				img = img.convert("RGB")
			qimage = pil_a_qimage(img)

			printer = crear_impresora_qt(
				nombre_impresora=nombre_impresora,
				ancho_mm=self.LABEL_PAGE_MM,
				alto_mm=self.LABEL_PAGE_MM,
				nombre_formato=f"KBKA Modelos {self.LABEL_PAGE_MM}x{self.LABEL_PAGE_MM} mm",
			)

			painter = QPainter()
			if not painter.begin(printer):
				raise RuntimeError(
					"Qt no pudo iniciar el trabajo de impresión. "
					"Revise el estado de la impresora y su controlador."
				)

			painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
			dpi = max(1, printer.resolution())
			mm_a_px = lambda mm: int(round((float(mm) / 25.4) * dpi))
			pagina = painter.viewport()
			destino = QRect(
				pagina.x() + mm_a_px(self.LABEL_LEFT_MM),
				pagina.y() + mm_a_px(self.LABEL_BOTTOM_MM),
				mm_a_px(self.LABEL_CONTENT_MM),
				mm_a_px(self.LABEL_CONTENT_MM),
			)
			painter.drawImage(destino, qimage)
			painter.end()
			painter = None

			self.registrar_historial("impreso", None)
			KBKADialog.success(
				self,
				"Impresión Exitosa",
				f"La etiqueta se envió correctamente a:\n{nombre_impresora}",
			)
		except Exception:
			import traceback

			error = traceback.format_exc()
			guardar_diagnostico_impresion("Impresión con QtPrintSupport", error)
			KBKADialog.error(
				self,
				"Error al imprimir",
				"No se pudo imprimir la etiqueta.\n\n"
				+ (error.splitlines()[-1] if error else "Error desconocido")
				+ "\n\nRevise el diagnóstico en:\n"
				+ (
					QT_PRINT_DIAGNOSTIC_PATH
					or r"%APPDATA%\KBKA_Shop\diagnostico_impresion_modelos.txt"
				),
			)
		finally:
			if painter is not None and painter.isActive():
				painter.end()


class AyudaDialog(QDialog):
	"""
	Diálogo de ayuda y solución de problemas.

	Muestra una interfaz premium con:
	- Lista de problemas comunes y sus soluciones
	- Banner de contacto para soporte técnico
	- Animaciones y efectos visuales según el tema
	- Soporte para temas claro/oscuro

	:param parent: Ventana principal de la aplicación.
	:type parent: EtiquetasApp
	"""

	def __init__(self, parent=None):
		"""Inicializa el objeto, crea su estado interno y prepara sus componentes visuales."""
		super().__init__(parent)
		self.parent_window = parent
		self.setWindowTitle("Centro de Ayuda y Solución de Problemas")
		self.setMinimumSize(800, 500)
		self.setModal(True)

		self.init_ui()
		self.aplicar_estilos()  # Aplicar estilos según el tema actual

	@property
	def tema_oscuro(self):
		"""
		Propiedad para acceder al tema de la ventana principal.

		:return: True si el tema oscuro está activo, False si es tema claro.
		:rtype: bool
		"""
		return self.parent_window.tema_oscuro if self.parent_window else False

	def init_ui(self):
		"""
		Inicializa la interfaz del diálogo premium de ayuda.

		Crea:
		- Header con icono y título
		- Área de scroll con cards de problemas/soluciones
		- Banner de soporte con email
		- Botón de cerrar
		"""
		main_layout = QVBoxLayout(self)
		main_layout.setContentsMargins(0, 0, 0, 0)
		main_layout.setSpacing(0)

		self.problema_frames = []

		header_frame = QFrame()
		self.header_frame = header_frame
		header_frame.setFixedHeight(65)
		header_frame.setStyleSheet(
			"""
			QFrame {
				background-color: white;
				border: none;
				border-bottom: 1px solid #EEEEEE;
			}
			"""
		)

		shadow_effect = QGraphicsDropShadowEffect()
		shadow_effect.setBlurRadius(10)
		shadow_effect.setXOffset(0)
		shadow_effect.setYOffset(2)
		shadow_effect.setColor(QColor(0, 0, 0, int(255 * 0.15)))
		header_frame.setGraphicsEffect(shadow_effect)

		header_layout = QHBoxLayout(header_frame)
		header_layout.setContentsMargins(20, 0, 20, 0)
		header_layout.setSpacing(12)
		header_layout.addStretch()

		icon_label = QLabel()
		icon_label.setStyleSheet("background: transparent; border: none;")
		try:
			ayuda_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, "ayuda.png"))
			if os.path.exists(ayuda_icon_path):
				icon_pixmap = QPixmap(ayuda_icon_path)
				icon_pixmap = icon_pixmap.scaled(
					30,
					30,
					Qt.AspectRatioMode.KeepAspectRatio,
					Qt.TransformationMode.SmoothTransformation,
				)
				icon_label.setPixmap(icon_pixmap)
			else:
				icon_label.setText("❓")
				icon_label.setStyleSheet("font-size: 24pt; background: transparent; border: none;")
		except Exception:
			icon_label.setText("❓")
			icon_label.setStyleSheet("font-size: 24pt; background: transparent; border: none;")

		self.icon_label = icon_label
		header_layout.addWidget(icon_label)

		titulo_header = QLabel("Centro de Ayuda y Soporte")
		self.titulo_header = titulo_header
		titulo_header.setStyleSheet(
			"""
			color: #2D2D2D;
			font-size: 14pt;
			font-weight: bold;
			font-family: 'Segoe UI', 'Inter', sans-serif;
			"""
		)
		header_layout.addWidget(titulo_header)
		header_layout.addStretch()

		main_layout.addWidget(header_frame)

		scroll = QScrollArea()
		self.scroll = scroll
		scroll.setWidgetResizable(True)
		scroll.setFrameShape(QFrame.Shape.NoFrame)
		scroll.setStyleSheet(
			"""
			QScrollArea {
				background-color: #F8F9FA;
				border: none;
			}
			"""
		)

		content_widget = QWidget()
		self.content_widget = content_widget
		content_widget.setStyleSheet("background-color: #F8F9FA;")
		content_layout = QVBoxLayout(content_widget)
		content_layout.setContentsMargins(40, 30, 40, 30)
		content_layout.setSpacing(15)

		problema1_data = self.crear_problema_frame(
			"La etiqueta sale en blanco, cortada o con orientación incorrecta",
			"<b>Chequeos rápidos:</b><br><br>"
			"<b>1) Campos:</b> Asegúrate de que <b>Marca</b>, <b>Modelo</b> y <b>Calidad</b> estén completos. <b>Modelo</b> es obligatorio.<br><br>"
			"<b>2) Vista previa:</b> Revisa la vista previa en la aplicación; si se ve correctamente, pulsa <b>'GUARDAR PDF'</b> y abre el PDF para imprimir desde el visor.<br><br>"
			"<b>3) Configurar impresora:</b> En <b>'CONFIGURAR IMPRESORA'</b> selecciona tu impresora y confirma el tamaño de etiqueta (ej. <b>102x102 mm</b>) y que el diseño quede centrado con un margen mínimo. Guarda y vuelve a probar.<br><br>"
			"<b>4) Reinicia y prueba:</b> Apaga y enciende la impresora, cierra y abre la app, y vuelve a intentar. Si sigue el problema, guarda el PDF y comparte la captura de la vista previa con Chava." 
		)
		self.problema_frames.append(problema1_data)
		content_layout.addWidget(problema1_data["frame"])

		problema2_data = self.crear_problema_frame(
			"No se guardan o no aparecen Marca/Modelo/Calidad",
			"<b>1) Completa los campos:</b> Selecciona una <b>Marca</b>, escribe el <b>Modelo</b> y elige la <b>Calidad</b>. No dejes campos vacíos.<br><br>"
			"<b>2) Guardar:</b> Usa <b>'GUARDAR PDF'</b> o <b>'IMPRIMIR'</b> para que la etiqueta y el historial se registren.<br><br>"
			"<b>3) Historial:</b> Revisa el historial en la aplicación; si no aparece, cierra y vuelve a abrir la app y vuelve a intentarlo.<br><br>"
			"<b>4) Contactar a Chava:</b> Si continúas teniendo problemas, contacta a Chava indicando qué pasos realizaste." 
		)
		self.problema_frames.append(problema2_data)
		content_layout.addWidget(problema2_data["frame"])

		problema3_data = self.crear_problema_frame(
			"No puedo imprimir desde la aplicación",
			"<b>Qué hacer:</b><br><br>"
			"<b>1) Selección en la app:</b> Ve a <b>'CONFIGURAR IMPRESORA'</b> y elige la impresora correcta. Guarda y reinicia la app.<br><br>"
			"<b>2) Conexión:</b> Asegúrate de que la impresora esté encendida y conectada al equipo.",
		)
		self.problema_frames.append(problema3_data)
		content_layout.addWidget(problema3_data["frame"])

		content_layout.addSpacing(20)

		soporte_banner = QFrame()
		soporte_banner.setStyleSheet(
			f"""
			QFrame {{
				background-color: {self.parent_window.COLORS['primary']};
				border-radius: 15px;
				padding: 25px;
			}}
			"""
		)
		soporte_layout = QVBoxLayout(soporte_banner)
		soporte_layout.setSpacing(15)

		soporte_titulo = QLabel("¿No pudiste resolverlo?")
		soporte_titulo.setStyleSheet(
			"""
			color: white;
			font-size: 16pt;
			font-weight: bold;
			font-family: 'Segoe UI', sans-serif;
			"""
		)
		soporte_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
		soporte_layout.addWidget(soporte_titulo)

		mensaje = QLabel("Contacta a Chava para apoyarte con el problema")
		mensaje.setStyleSheet(
			"""
			color: rgba(255, 255, 255, 0.95);
			font-size: 12pt;
			font-family: 'Segoe UI', sans-serif;
			"""
		)
		mensaje.setAlignment(Qt.AlignmentFlag.AlignCenter)
		soporte_layout.addWidget(mensaje)

		soporte_layout.addSpacing(10)

		email_container = QHBoxLayout()
		email_container.addStretch()

		email_label = QLabel("📧 chavitachava2007@gmail.com")
		email_label.setStyleSheet(
			"""
			color: white;
			font-size: 12pt;
			font-family: 'Segoe UI', monospace;
			background-color: rgba(0, 0, 0, 0.2);
			padding: 10px 15px;
			border-radius: 8px;
			"""
		)
		email_container.addWidget(email_label)

		btn_copiar = QPushButton("Copiar")
		btn_copiar.setCursor(Qt.CursorShape.PointingHandCursor)
		btn_copiar.setFixedSize(80, 35)
		btn_copiar.clicked.connect(lambda: self.copiar_email())
		btn_copiar.setStyleSheet(
			"""
			QPushButton {
				background-color: white;
				color: #CD0403;
				border: none;
				border-radius: 6px;
				font-size: 10pt;
				font-weight: 600;
				font-family: 'Segoe UI', sans-serif;
			}
			QPushButton:hover {
				background-color: #F0F0F0;
			}
			QPushButton:pressed {
				background-color: #E0E0E0;
			}
			"""
		)
		email_container.addWidget(btn_copiar)

		email_container.addStretch()
		soporte_layout.addLayout(email_container)

		instrucciones = QLabel(
			"Incluye:<br>"
			"• Descripción detallada del problema<br>"
			"• Capturas de pantalla si es posible<br>"
			"• Mensajes de error completos"
		)
		instrucciones.setWordWrap(True)
		instrucciones.setStyleSheet(
			"""
			color: rgba(255, 255, 255, 0.85);
			font-size: 10pt;
			font-family: 'Segoe UI', sans-serif;
			line-height: 1.6;
			"""
		)
		instrucciones.setAlignment(Qt.AlignmentFlag.AlignCenter)
		soporte_layout.addWidget(instrucciones)

		content_layout.addWidget(soporte_banner)

		scroll.setWidget(content_widget)
		main_layout.addWidget(scroll)

		btn_cerrar = QPushButton("✕ Cerrar")
		self.btn_cerrar = btn_cerrar
		btn_cerrar.setMinimumHeight(50)
		btn_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
		btn_cerrar.clicked.connect(self.accept)
		btn_cerrar.setStyleSheet(
			"""
			QPushButton {
				background-color: #F8F9FA;
				color: #4A4A4A;
				border: none;
				border-top: 1px solid #E0E0E0;
				padding: 10px;
				font-size: 11pt;
				font-weight: 600;
				font-family: 'Segoe UI', sans-serif;
			}
			QPushButton:hover {
				background-color: #E8E8E8;
			}
			QPushButton:pressed {
				background-color: #D8D8D8;
			}
			"""
		)
		main_layout.addWidget(btn_cerrar)

	def copiar_email(self):
		"""
		Copia el email de soporte al portapapeles.

		Usa QGuiApplication.clipboard() para copiar el email
		y muestra un diálogo de confirmación.
		"""
		try:
			from PyQt6.QtGui import QGuiApplication

			clipboard = QGuiApplication.clipboard()
			clipboard.setText("chavitachava2007@gmail.com")
			KBKADialog.success(self, "¡Copiado!", "El correo electrónico se copió al portapapeles.")
		except Exception as e:
			print(f"Error al copiar email: {e}")

	def crear_problema_frame(self, titulo, solucion):
		"""Crea una card por problema con problema.png junto al título."""
		frame = QFrame()
		frame.setObjectName("problema_card")
		frame.setStyleSheet(
			"""
			QFrame#problema_card {
				background-color: white;
				border: 1px solid #E8E8E8;
				border-radius: 10px;
			}
			QFrame#problema_card:hover {
				border: 1px solid #CD0403;
			}
			"""
		)

		layout = QVBoxLayout(frame)
		layout.setSpacing(12)
		layout.setContentsMargins(20, 18, 20, 18)

		titulo_fila = QHBoxLayout()
		titulo_fila.setContentsMargins(0, 0, 0, 0)
		titulo_fila.setSpacing(10)

		icono_label = QLabel()
		icono_label.setFixedSize(28, 28)
		icono_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		icono_label.setStyleSheet("background: transparent; border: none; padding: 0;")
		icono = recolorear_icono_footer(
			buscar_icono_asset("problema.png"),
			self.parent_window.COLORS["primary"],
			22,
			22,
		)
		if not icono.isNull():
			icono_label.setPixmap(icono)
		titulo_fila.addWidget(icono_label, 0, Qt.AlignmentFlag.AlignTop)

		titulo_label = QLabel(titulo)
		titulo_label.setWordWrap(True)
		titulo_label.setStyleSheet(
			f"""
			font-size: 13pt;
			font-weight: bold;
			color: {self.parent_window.COLORS['primary']};
			font-family: 'Segoe UI', sans-serif;
			background-color: transparent;
			border: none;
			padding: 0;
			"""
		)
		titulo_fila.addWidget(titulo_label, 1)
		layout.addLayout(titulo_fila)

		separador = QFrame()
		separador.setObjectName("problema_separador")
		separador.setFrameShape(QFrame.Shape.HLine)
		separador.setFixedHeight(1)
		separador.setStyleSheet(
			"QFrame#problema_separador { background-color: #F0F0F0; border: none; }"
		)
		layout.addWidget(separador)

		solucion_label = QLabel(solucion)
		solucion_label.setWordWrap(True)
		solucion_label.setTextFormat(Qt.TextFormat.RichText)
		solucion_label.setStyleSheet(
			"""
			font-size: 10pt;
			color: #4A4A4A;
			line-height: 1.7;
			font-family: 'Segoe UI', sans-serif;
			background-color: transparent;
			border: none;
			padding: 0;
			"""
		)
		layout.addWidget(solucion_label)

		return {
			"frame": frame,
			"titulo": titulo_label,
			"solucion": solucion_label,
			"titulo_label": titulo_label,
			"solucion_label": solucion_label,
			"separador": separador,
			"icono": icono_label,
		}

	def aplicar_estilos(self):
		"""
		Aplica los estilos según el tema actual de la ventana principal.

		Ajusta header, contenido, cards, botón de cerrar e icono.
		"""
		if hasattr(self.parent_window, "tema_oscuro") and self.parent_window.tema_oscuro:
			bg_header = "#1E1E1E"
			bg_content = "#1E1E1E"
			bg_card = "#2A2A2A"
			bg_card_hover = "#333333"
			text_primary = "#E0E0E0"
			text_secondary = "#B0B0B0"
			text_title = "#CD0403"
			border_color = "#3A3A3A"
			border_hover = "#CD0403"
			separador_color = "#3A3A3A"
			btn_cerrar_bg = "#2A2A2A"
			btn_cerrar_hover = "#333333"
			btn_cerrar_text = "#E0E0E0"
		else:
			bg_header = "#FFFFFF"
			bg_content = "#F8F9FA"
			bg_card = "#FFFFFF"
			bg_card_hover = "#FFFFFF"
			text_primary = "#2D2D2D"
			text_secondary = "#4A4A4A"
			text_title = "#CD0403"
			border_color = "#E8E8E8"
			border_hover = "#CD0403"
			separador_color = "#F0F0F0"
			btn_cerrar_bg = "#F8F9FA"
			btn_cerrar_hover = "#E8E8E8"
			btn_cerrar_text = "#4A4A4A"

		if hasattr(self, "header_frame"):
			self.header_frame.setStyleSheet(
				f"""
				QFrame {{
					background-color: {bg_header};
					border: none;
					border-bottom: 1px solid {border_color};
				}}
				"""
			)

		if hasattr(self, "titulo_header"):
			self.titulo_header.setStyleSheet(
				f"""
				color: {text_primary};
				font-size: 14pt;
				font-weight: bold;
				font-family: 'Segoe UI', 'Inter', sans-serif;
				"""
			)

		if hasattr(self, "scroll"):
			self.scroll.setStyleSheet(
				f"""
				QScrollArea {{
					background-color: {bg_content};
					border: none;
				}}
				"""
			)

		if hasattr(self, "content_widget"):
			self.content_widget.setStyleSheet(f"background-color: {bg_content};")

		if hasattr(self, "problema_frames"):
			for frame_data in self.problema_frames:
				frame = frame_data["frame"]
				titulo_label = frame_data["titulo_label"]
				solucion_label = frame_data["solucion_label"]
				separador = frame_data["separador"]

				frame.setStyleSheet(
					f"""
					QFrame#problema_card {{
						background-color: {bg_card};
						border: 1px solid {border_color};
						border-radius: 10px;
					}}
					QFrame#problema_card:hover {{
						border: 1px solid {border_hover};
						background-color: {bg_card_hover};
					}}
					"""
				)

				titulo_label.setStyleSheet(
					f"""
					font-size: 13pt;
					font-weight: bold;
					color: {text_title};
					font-family: 'Segoe UI', sans-serif;
					padding-bottom: 3px;
					background-color: transparent;
					border: none;
					"""
				)

				solucion_label.setStyleSheet(
					f"""
					font-size: 10pt;
					color: {text_secondary};
					line-height: 1.7;
					font-family: 'Segoe UI', sans-serif;
					background-color: transparent;
					border: none;
					padding: 0;
					"""
				)

				separador.setStyleSheet(f"background-color: {separador_color}; border: none;")

		if hasattr(self, "btn_cerrar"):
			self.btn_cerrar.setStyleSheet(
				f"""
				QPushButton {{
					background-color: {btn_cerrar_bg};
					color: {btn_cerrar_text};
					border: none;
					border-top: 1px solid {border_color};
					padding: 10px;
					font-size: 11pt;
					font-weight: 600;
					font-family: 'Segoe UI', sans-serif;
				}}
				QPushButton:hover {{
					background-color: {btn_cerrar_hover};
				}}
				QPushButton:pressed {{
					background-color: {btn_cerrar_bg};
				}}
				"""
			)

		if hasattr(self, "icon_label"):
			if hasattr(self.parent_window, "tema_oscuro") and self.parent_window.tema_oscuro:
				efecto = QGraphicsColorizeEffect()
				efecto.setColor(QColor(255, 255, 255))
				efecto.setStrength(1.0)
				self.icon_label.setGraphicsEffect(efecto)
			else:
				self.icon_label.setGraphicsEffect(None)


class ConfiguracionImpresoraDialog(QDialog):
	"""
	Diálogo para configurar la impresora predeterminada.

	Permite al usuario:
	- Ver lista de impresoras disponibles en el sistema
	- Seleccionar impresora predeterminada
	- Guardar la configuración automáticamente

	Usa QtPrintSupport para enumerar las impresoras del sistema.

	:param parent: Ventana principal de la aplicación.
	:type parent: CEDISEtiquetasApp
	"""

	def __init__(self, parent=None):
		"""Inicializa el objeto, crea su estado interno y prepara sus componentes visuales."""
		super().__init__(parent)
		self.parent_window = parent
		self.setWindowTitle("Configuración de Impresión")
		self.setMinimumSize(450, 200)
		self.setMaximumSize(500, 250)
		self.setModal(True)

		self.init_ui()

	@property
	def tema_oscuro(self):
		"""Ejecuta la lógica asociada a tema oscuro."""
		return self.parent_window.tema_oscuro if self.parent_window else False

	def init_ui(self):
		"""Ejecuta la lógica asociada a init ui."""
		layout = QVBoxLayout(self)
		layout.setContentsMargins(20, 20, 20, 20)
		layout.setSpacing(15)

		titulo_fila = QHBoxLayout()
		titulo_fila.addStretch()

		icono_titulo = QLabel()
		ruta_engranaje = buscar_icono_asset("engranaje.png")
		color_icono_titulo = "#FFFFFF" if self.tema_oscuro else "#111111"
		pixmap_engranaje = recolorear_icono_footer(
			ruta_engranaje, color_icono_titulo, 24, 24
		)
		icono_titulo.setPixmap(pixmap_engranaje)
		icono_titulo.setFixedSize(28, 28)
		icono_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
		titulo_fila.addWidget(icono_titulo)

		titulo = QLabel("CONFIGURACIÓN DE IMPRESIÓN")
		titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
		titulo.setStyleSheet(f"""
			color: {self.parent_window.COLORS['primary']};
			font-size: 14pt;
			font-weight: bold;
			padding: 5px 0px;
		""")
		titulo_fila.addWidget(titulo)
		titulo_fila.addStretch()
		layout.addLayout(titulo_fila)

		layout.addSpacing(10)

		label_impresora = QLabel("Selecciona la impresora predeterminada:")
		label_impresora.setStyleSheet("font-size: 11pt; font-weight: bold;")
		layout.addWidget(label_impresora)

		self.combo_impresoras = ComboBoxSinRueda()
		self.combo_impresoras.setPlaceholderText("Seleccione una impresora...")
		self.combo_impresoras.setMinimumHeight(40)

		impresoras = []
		try:
			impresoras = self.parent_window.obtener_impresoras() if self.parent_window else []
		except Exception:
			impresoras = []

		if impresoras:
			self.combo_impresoras.addItems(impresoras)
			impresora_guardada = None
			try:
				impresora_guardada = self.parent_window.cargar_impresora_config()
			except Exception:
				impresora_guardada = None
			if impresora_guardada and impresora_guardada in impresoras:
				index = self.combo_impresoras.findText(impresora_guardada)
				if index >= 0:
					self.combo_impresoras.setCurrentIndex(index)
		elif not QT_PRINT_AVAILABLE:
			self.combo_impresoras.addItem("Qt PrintSupport no disponible")
			self.combo_impresoras.setEnabled(False)
		else:
			self.combo_impresoras.addItem("No hay impresoras disponibles")
			self.combo_impresoras.setEnabled(False)

		self.combo_impresoras.currentTextChanged.connect(self.on_impresora_changed)

		if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
			bg_input = "#2A2A2A"
			text_color = "#E0E0E0"
			border_color = "#3A3A3A"
		else:
			bg_input = "white"
			text_color = "#212121"
			border_color = "#CCCCCC"

		self.combo_impresoras.setStyleSheet(f"""
			QComboBox {{
				padding: 10px;
				border: 2px solid {border_color};
				border-radius: 6px;
				background-color: {bg_input};
				color: {text_color};
				font-size: 10pt;
			}}
			QComboBox:hover {{
				border: 2px solid {self.parent_window.COLORS['primary']};
			}}
			QComboBox:focus {{
				border: 2px solid {self.parent_window.COLORS['primary']};
			}}
			QComboBox::drop-down {{
				border: none;
				width: 30px;
			}}
			QComboBox QAbstractItemView {{
				background-color: {bg_input};
				color: {text_color};
				selection-background-color: {self.parent_window.COLORS['primary']};
				selection-color: white;
				border: 1px solid #CCCCCC;
			}}
		""")

		layout.addWidget(self.combo_impresoras)

		layout.addSpacing(15)

		# Mensaje informativo con icono
		info_contenedor = QWidget()
		info_contenedor.setObjectName("transparent_widget")
		info_fila = QHBoxLayout(info_contenedor)
		info_fila.setContentsMargins(0, 0, 0, 0)
		info_fila.setSpacing(7)

		icono_foco = QLabel()
		ruta_foco = buscar_icono_asset("foco.png")
		color_foco = "#E0E0E0" if self.tema_oscuro else "#343A40"
		pixmap_foco = recolorear_icono_footer(
			ruta_foco, color_foco, 17, 17
		)
		icono_foco.setPixmap(pixmap_foco)
		icono_foco.setFixedSize(22, 22)
		icono_foco.setAlignment(Qt.AlignmentFlag.AlignCenter)
		icono_foco.setStyleSheet(
			"background: transparent; border: none;"
		)
		info_fila.addWidget(icono_foco)

		info_label = QLabel(
			"La impresora seleccionada se guardará automáticamente."
		)
		info_color = "#E0E0E0" if self.tema_oscuro else "#666666"
		info_label.setStyleSheet(
			f"color: {info_color}; font-size: 9pt; font-style: italic; "
			"background: transparent; border: none;"
		)
		info_label.setWordWrap(True)
		info_fila.addWidget(info_label, 1)
		layout.addWidget(info_contenedor)

		layout.addStretch()

		btn_cerrar = QPushButton("Cerrar")
		btn_cerrar.setMinimumHeight(45)
		btn_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
		btn_cerrar.clicked.connect(self.accept)
		btn_cerrar.setStyleSheet(f"""
			QPushButton {{
				background-color: {self.parent_window.COLORS['primary']};
				color: white;
				border: none;
				border-radius: 6px;
				padding: 10px;
				font-size: 11pt;
				font-weight: bold;
			}}
			QPushButton:hover {{
				background-color: {self.parent_window.COLORS['secondary']};
			}}
			QPushButton:pressed {{
				background-color: #A00302;
			}}
		""")

		layout.addWidget(btn_cerrar)

	def on_impresora_changed(self, nombre_impresora):
		"""Ejecuta la lógica asociada a on impresora changed."""
		if nombre_impresora and nombre_impresora not in ["No hay impresoras disponibles", "Qt PrintSupport no disponible"]:
			try:
				self.parent_window.guardar_impresora_config(nombre_impresora)
			except Exception as e:
				print(f"Error al guardar impresora desde diálogo: {e}")

	def copiar_email(self):
		"""
		Copia el email de soporte al portapapeles.

		Usa QGuiApplication.clipboard() para copiar el email
		y muestra un diálogo de confirmación.
		"""
		try:
			from PyQt6.QtGui import QGuiApplication

			clipboard = QGuiApplication.clipboard()
			clipboard.setText("chavitachava2007@gmail.com")
			KBKADialog.success(self, "¡Copiado!", "El correo electrónico se copió al portapapeles.")
		except Exception as e:
			print(f"Error al copiar email: {e}")

	def crear_problema_frame(self, titulo, solucion):
		"""Crea una card por problema con problema.png junto al título."""
		frame = QFrame()
		frame.setObjectName("problema_card")
		frame.setStyleSheet(
			"""
			QFrame#problema_card {
				background-color: white;
				border: 1px solid #E8E8E8;
				border-radius: 10px;
			}
			QFrame#problema_card:hover {
				border: 1px solid #CD0403;
			}
			"""
		)

		layout = QVBoxLayout(frame)
		layout.setSpacing(12)
		layout.setContentsMargins(20, 18, 20, 18)

		titulo_fila = QHBoxLayout()
		titulo_fila.setContentsMargins(0, 0, 0, 0)
		titulo_fila.setSpacing(10)

		icono_label = QLabel()
		icono_label.setFixedSize(28, 28)
		icono_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		icono_label.setStyleSheet("background: transparent; border: none; padding: 0;")
		icono = recolorear_icono_footer(
			buscar_icono_asset("problema.png"),
			self.parent_window.COLORS["primary"],
			22,
			22,
		)
		if not icono.isNull():
			icono_label.setPixmap(icono)
		titulo_fila.addWidget(icono_label, 0, Qt.AlignmentFlag.AlignTop)

		titulo_label = QLabel(titulo)
		titulo_label.setWordWrap(True)
		titulo_label.setStyleSheet(
			f"""
			font-size: 13pt;
			font-weight: bold;
			color: {self.parent_window.COLORS['primary']};
			font-family: 'Segoe UI', sans-serif;
			background-color: transparent;
			border: none;
			padding: 0;
			"""
		)
		titulo_fila.addWidget(titulo_label, 1)
		layout.addLayout(titulo_fila)

		separador = QFrame()
		separador.setObjectName("problema_separador")
		separador.setFrameShape(QFrame.Shape.HLine)
		separador.setFixedHeight(1)
		separador.setStyleSheet(
			"QFrame#problema_separador { background-color: #F0F0F0; border: none; }"
		)
		layout.addWidget(separador)

		solucion_label = QLabel(solucion)
		solucion_label.setWordWrap(True)
		solucion_label.setTextFormat(Qt.TextFormat.RichText)
		solucion_label.setStyleSheet(
			"""
			font-size: 10pt;
			color: #4A4A4A;
			line-height: 1.7;
			font-family: 'Segoe UI', sans-serif;
			background-color: transparent;
			border: none;
			padding: 0;
			"""
		)
		layout.addWidget(solucion_label)

		return {
			"frame": frame,
			"titulo": titulo_label,
			"solucion": solucion_label,
			"titulo_label": titulo_label,
			"solucion_label": solucion_label,
			"separador": separador,
			"icono": icono_label,
		}

	def aplicar_estilos(self):
		"""
		Aplica los estilos según el tema actual del parent.

		Actualiza colores de:
		- Header y título
		- Cards de problemas
		- Botón de cerrar
		- Iconos (usando QGraphicsColorizeEffect en modo oscuro)
		"""
		if hasattr(self.parent_window, "tema_oscuro") and self.parent_window.tema_oscuro:
			bg_header = "#1E1E1E"
			bg_content = "#1E1E1E"
			bg_card = "#2A2A2A"
			bg_card_hover = "#333333"
			text_primary = "#E0E0E0"
			text_secondary = "#B0B0B0"
			text_title = "#CD0403"
			border_color = "#3A3A3A"
			border_hover = "#CD0403"
			separador_color = "#3A3A3A"
			btn_cerrar_bg = "#2A2A2A"
			btn_cerrar_hover = "#333333"
			btn_cerrar_text = "#E0E0E0"
		else:
			bg_header = "#FFFFFF"
			bg_content = "#F8F9FA"
			bg_card = "#FFFFFF"
			bg_card_hover = "#FFFFFF"
			text_primary = "#2D2D2D"
			text_secondary = "#4A4A4A"
			text_title = "#CD0403"
			border_color = "#E8E8E8"
			border_hover = "#CD0403"
			separador_color = "#F0F0F0"
			btn_cerrar_bg = "#F8F9FA"
			btn_cerrar_hover = "#E8E8E8"
			btn_cerrar_text = "#4A4A4A"

		if hasattr(self, "header_frame"):
			self.header_frame.setStyleSheet(
				f"""
				QFrame {{
					background-color: {bg_header};
					border: none;
					border-bottom: 1px solid {border_color};
				}}
				"""
			)

		if hasattr(self, "titulo_header"):
			self.titulo_header.setStyleSheet(
				f"""
				color: {text_primary};
				font-size: 14pt;
				font-weight: bold;
				font-family: 'Segoe UI', 'Inter', sans-serif;
				"""
			)

		if hasattr(self, "scroll"):
			self.scroll.setStyleSheet(
				f"""
				QScrollArea {{
					background-color: {bg_content};
					border: none;
				}}
				"""
			)

		if hasattr(self, "content_widget"):
			self.content_widget.setStyleSheet(f"background-color: {bg_content};")

		if hasattr(self, "problema_frames"):
			for frame_data in self.problema_frames:
				frame = frame_data["frame"]
				titulo_label = frame_data["titulo"]
				solucion_label = frame_data["solucion"]
				separador = frame_data["separador"]

				frame.setStyleSheet(
					f"""
					QFrame {{
						background-color: {bg_card};
						border: 1px solid {border_color};
						border-radius: 10px;
						padding: 20px;
					}}
					QFrame:hover {{
						border: 1px solid {border_hover};
						background-color: {bg_card_hover};
					}}
					"""
				)

				titulo_label.setStyleSheet(
					f"""
					font-size: 13pt;
					font-weight: bold;
					color: {text_title};
					font-family: 'Segoe UI', sans-serif;
					padding-bottom: 3px;
					"""
				)

				solucion_label.setStyleSheet(
					f"""
					font-size: 10pt;
					color: {text_secondary};
					line-height: 1.7;
					font-family: 'Segoe UI', sans-serif;
					"""
				)

				separador.setStyleSheet(f"background-color: {separador_color}; border: none;")

		if hasattr(self, "btn_cerrar"):
			self.btn_cerrar.setStyleSheet(
				f"""
				QPushButton {{
					background-color: {btn_cerrar_bg};
					color: {btn_cerrar_text};
					border: none;
					border-top: 1px solid {border_color};
					padding: 10px;
					font-size: 11pt;
					font-weight: 600;
					font-family: 'Segoe UI', sans-serif;
				}}
				QPushButton:hover {{
					background-color: {btn_cerrar_hover};
				}}
				QPushButton:pressed {{
					background-color: {btn_cerrar_bg};
				}}
				"""
			)

		if hasattr(self, "icon_label"):
			if hasattr(self.parent_window, "tema_oscuro") and self.parent_window.tema_oscuro:
				efecto = QGraphicsColorizeEffect()
				efecto.setColor(QColor(255, 255, 255))
				efecto.setStrength(1.0)
				self.icon_label.setGraphicsEffect(efecto)
			else:
				self.icon_label.setGraphicsEffect(None)

class ModernSplashScreen(QWidget):
	"""
	Pantalla de inicio ultra-premium para KBKA SHOP (copiada desde main.py).
	"""
	def __init__(self):
		"""Inicializa el objeto, crea su estado interno y prepara sus componentes visuales."""
		super().__init__()
		self.main_window = None
		self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
		self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
		self.setFixedSize(650, 420)
		try:
			icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'KBKA.ico'))
			if os.path.exists(icon_path):
				self.setWindowIcon(QIcon(icon_path))
		except:
			pass
		self._center_on_screen()
		self._setup_ui()
		self._setup_animations()

	def _center_on_screen(self):
		"""Ejecuta la lógica asociada a center on screen."""
		screen = QApplication.primaryScreen().geometry()
		x = (screen.width() - self.width()) // 2
		y = (screen.height() - self.height()) // 2
		self.move(x, y)

	def _setup_ui(self):
		"""Ejecuta la lógica asociada a setup ui."""
		main_layout = QVBoxLayout(self)
		main_layout.setContentsMargins(20, 20, 20, 20)
		self.container = QFrame()
		self.container.setObjectName("splash_container")
		self.container.setStyleSheet("""
			#splash_container {
				background-color: #FCFCFC;
				border-radius: 20px;
				border: 1px solid rgba(0, 0, 0, 0.1);
			}
		""")
		container_layout = QVBoxLayout(self.container)
		container_layout.setContentsMargins(40, 60, 40, 60)
		container_layout.setSpacing(30)
		container_layout.addStretch()
		self.logo_label = QLabel()
		logo_path = obtener_ruta_recurso(os.path.join(IMAGES_DIR, 'splash.png'))
		if os.path.exists(logo_path):
			pixmap = QPixmap(logo_path)
			scaled_pixmap = pixmap.scaled(500, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
			self.logo_label.setPixmap(scaled_pixmap)
		else:
			self.logo_label.setText("KBKA SHOP")
			self.logo_label.setStyleSheet("""
				color: #CF1312;
				font-size: 48px;
				font-weight: bold;
				font-family: 'Segoe UI', Arial, sans-serif;
			""")
		self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		container_layout.addWidget(self.logo_label)
		container_layout.addSpacing(20)
		progress_container = QWidget()
		progress_layout = QVBoxLayout(progress_container)
		progress_layout.setContentsMargins(50, 0, 50, 0)
		progress_layout.setSpacing(10)
		self.progress_bar = QProgressBar()
		self.progress_bar.setFixedHeight(10)
		self.progress_bar.setTextVisible(False)
		self.progress_bar.setMinimum(0)
		self.progress_bar.setMaximum(100)
		self.progress_bar.setValue(0)
		self.progress_bar.setStyleSheet("""
			QProgressBar {
				border: none;
				border-radius: 5px;
				background-color: #E9ECEF;
			}
			QProgressBar::chunk {
				border-radius: 5px;
				background-color: #CF1312;
			}
		""")
		progress_layout.addWidget(self.progress_bar)
		self.status_label = QLabel("Cargando...")
		self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.status_label.setStyleSheet("""
			color: #6C757D;
			font-size: 14px;
			font-family: 'Segoe UI', Arial, sans-serif;
			letter-spacing: 0.5px;
		""")
		progress_layout.addWidget(self.status_label)
		container_layout.addWidget(progress_container)
		container_layout.addStretch()
		main_layout.addWidget(self.container)

	def _setup_animations(self):
		"""Ejecuta la lógica asociada a setup animations."""
		self.splash_opacity_effect = QGraphicsOpacityEffect(self)
		self.setGraphicsEffect(self.splash_opacity_effect)
		self.splash_opacity_effect.setOpacity(0.0)
		self.fade_in_animation = QPropertyAnimation(self.splash_opacity_effect, b"opacity")
		self.fade_in_animation.setDuration(600)
		self.fade_in_animation.setStartValue(0.0)
		self.fade_in_animation.setEndValue(1.0)
		self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
		if self.logo_label.pixmap() and not self.logo_label.pixmap().isNull():
			self.original_pixmap = self.logo_label.pixmap()
			scaled_down = self.original_pixmap.scaled(int(self.original_pixmap.width() * 0.98), int(self.original_pixmap.height() * 0.98), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
			self.logo_label.setPixmap(scaled_down)
		self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
		self.progress_animation.setDuration(2000)
		self.progress_animation.setStartValue(0)
		self.progress_animation.setEndValue(100)
		self.progress_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
		self.progress_animation.finished.connect(self._on_progress_finished)

	def _on_progress_finished(self):
		"""Ejecuta la lógica asociada a on progress finished."""
		QTimer.singleShot(1000, self._close_and_show_main)

	def show(self):
		"""Ejecuta la lógica asociada a show."""
		super().show()
		self.fade_in_animation.start()
		if hasattr(self, 'original_pixmap'):
			QTimer.singleShot(50, self._animate_logo_scale)
		self.progress_animation.start()

	def _animate_logo_scale(self):
		"""Ejecuta la lógica asociada a animate logo scale."""
		if not hasattr(self, 'original_pixmap'):
			return
		steps = 6
		duration = 300
		step_time = duration // steps

		def update_scale(step):
			"""Actualiza la escala de la vista previa de acuerdo con el tamaño disponible."""
			if step > steps:
				return
			scale = 0.98 + (0.02 * step / steps)
			scaled = self.original_pixmap.scaled(int(self.original_pixmap.width() * scale), int(self.original_pixmap.height() * scale), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
			self.logo_label.setPixmap(scaled)
			if step < steps:
				QTimer.singleShot(step_time, lambda: update_scale(step + 1))

		update_scale(0)

	def _close_and_show_main(self):
		# Crear la ventana principal aquí para asegurar inicialización completa
		"""Ejecuta la lógica asociada a close and show main."""
		self.main_window = CEDISEtiquetasApp()
		self.main_window.show()
		self.close()


def main():
	"""Inicia QApplication, crea la ventana principal y ejecuta el ciclo de eventos de Qt."""
	app = QApplication(sys.argv)
	splash = ModernSplashScreen()
	splash.show()
	sys.exit(app.exec())


if __name__ == "__main__":
	main()
