"""
KBKA SHOP - Sistema de Generación de Etiquetas de Envío
Versión: 1.0.0 (PyQt6)
Fecha: 2026
author: Chava R.
"""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QLineEdit, QPushButton, QRadioButton, 
    QComboBox, QMessageBox, QFileDialog, QFrame, QScrollArea, QButtonGroup, QCompleter,
    QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QStyle, QAbstractItemView,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QGraphicsColorizeEffect, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QStringListModel, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPixmap, QImage, QIcon, QFont, QColor
import os
import sys
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
import pandas as pd
import sqlite3

# ==================== IMPORTACIONES DE PYWIN32 ====================
# Bloque de importación robusto para compatibilidad con PyInstaller
# Estos módulos son necesarios para la impresión directa en impresoras térmicas
WIN32_AVAILABLE = False
win32print = None
win32ui = None
win32api = None
ImageWin = None

try:
    # Importar pythoncom primero (necesario para inicializar COM en PyInstaller)
    import pythoncom
    pythoncom.CoInitialize()  # Inicializar COM para evitar errores en PyInstaller
    # Luego importar los módulos de pywin32
    import win32print
    import win32ui
    import win32api
    from PIL import ImageWin
    
    WIN32_AVAILABLE = True
    print("Módulos de impresión cargados correctamente (win32print, win32ui, win32api)")
    
except ImportError as e:
    WIN32_AVAILABLE = False
    print(f"Advertencia: win32print no disponible. Impresión directa deshabilitada.")
    print(f"Detalles del error: {e}")
    print("Solución: Ejecute 'pip install pywin32' y luego 'python -m pywin32_postinstall -install'")
except Exception as e:
    WIN32_AVAILABLE = False
    print(f"Error al cargar módulos de impresión: {e}")

# ==================== PATH CONFIGURATION ====================
# Configuración centralizada de rutas de recursos
# Si necesitas mover carpetas, solo modifica estas constantes

ICONS_DIR = os.path.join('assets', 'icons')
IMAGES_DIR = os.path.join('assets', 'images')
DB_DIR = os.path.join('assets', 'db')
HEADERS_DIR = os.path.join('assets', 'headers')

# ==================== FUNCIONES AUXILIARES ====================

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
# ==================== CONFIGURACIÓN DE BASE DE DATOS ====================
# La base de datos de trabajo (kbka_data.db) se guarda en AppData del usuario
# para evitar problemas de permisos y permitir escritura en modo producción

# Obtener la ruta de AppData (Windows)
appdata_dir = os.getenv('APPDATA') or os.path.expanduser('~')
kbka_shop_dir = os.path.join(appdata_dir, 'KBKA_Shop')

# Crear la carpeta KBKA_Shop si no existe
os.makedirs(kbka_shop_dir, exist_ok=True)

# Ruta final para la base de datos de trabajo
DB_PATH = os.path.join(kbka_shop_dir, 'kbka_data.db')


# Configuración del icono en la barra de tareas de Windows
try:
    import ctypes
    myappid = 'kbkashop.etiquetas.app.3.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass


class KBKADialog(QDialog):
    """
    Diálogo personalizado premium con diseño moderno para KBKA SHOP.
    
    Proporciona diálogos modales con animaciones suaves, diseño sin bordes,
    y soporte para temas claro/oscuro. Incluye métodos estáticos para
    mostrar diferentes tipos de notificaciones.
    
    :param parent: Widget padre del diálogo.
    :type parent: QWidget, optional
    :param title: Título del diálogo.
    :type title: str
    :param message: Mensaje a mostrar en el diálogo.
    :type message: str
    :param dialog_type: Tipo de diálogo ('info', 'success', 'error', 'warning', 'question').
    :type dialog_type: str
    :param buttons: Lista de tuplas (texto, tipo) para botones personalizados.
    :type buttons: list, optional
    """
    
    def __init__(self, parent=None, title="", message="", dialog_type="info", buttons=None):
        super().__init__(parent)
        
        self.result_value = False
        self.dialog_type = dialog_type
        self._parent = parent  # Referencia al widget padre para acceder al tema
        
        # Configurar ventana sin marco
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        
        # Configurar UI
        self._setup_ui(title, message, buttons)
        
        # Configurar efecto de fade-in
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # Animación de entrada
        self.fade_in_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(250)  # 250ms
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def _setup_ui(self, title, message, buttons):
        """
        Configura la interfaz visual del diálogo.
        
        Crea el layout principal, contenedor con bordes redondeados,
        icono, título, mensaje y botones de acción.
        
        :param title: Título a mostrar en el diálogo.
        :type title: str
        :param message: Mensaje principal del diálogo.
        :type message: str
        :param buttons: Lista de tuplas (texto, tipo) para los botones.
        :type buttons: list, optional
        """
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Contenedor con bordes redondeados y sombra sutil
        container = QFrame()
        container.setObjectName("dialog_container")
        
        # Determinar colores según el tema del padre
        if hasattr(self._parent, 'tema_oscuro') and self._parent.tema_oscuro:
            bg_color = "#1E1E1E"
            border_color = "#3A3A3A"
            self.setStyleSheet("QDialog { background-color: transparent; }")
        else:
            bg_color = "#FFFFFF"
            border_color = "#D0D0D0"
            self.setStyleSheet("QDialog { background-color: transparent; }")
        
        container.setStyleSheet(f"""
            QFrame#dialog_container {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 15px;
            }}
        """)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(30, 25, 30, 25)
        container_layout.setSpacing(15)
        
        # Icono
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_path = self._get_icon_path()
        if icon_path and os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, 
                                  Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            icon_label.setStyleSheet("background: transparent; border: none;")
        else:
            # Icono de texto como respaldo
            icon_label.setText(self._get_icon_text())
            icon_color = self._get_icon_color()
            icon_label.setStyleSheet(f"""
                font-size: 48px;
                color: {icon_color};
                font-weight: bold;
                background: transparent;
                border: none;
            """)
        container_layout.addWidget(icon_label)
        
        # Título
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        
        # Determinar colores según el tema
        parent = self.parent()
        if hasattr(parent, 'tema_oscuro') and parent.tema_oscuro:
            title_color = "#FFFFFF"  # Blanco brillante para máxima visibilidad
            message_color = "#E0E0E0"  # Gris claro para el mensaje
        else:
            title_color = "#2C2C2C"
            message_color = "#666666"
        
        title_label.setStyleSheet(f"""
            font-size: 16pt;
            font-weight: bold;
            color: {title_color};
            padding: 5px 0px;
            background: transparent;
            border: none;
        """)
        container_layout.addWidget(title_label)
        
        # Mensaje
        message_label = QLabel(message)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setStyleSheet(f"""
            font-size: 11pt;
            color: {message_color};
            line-height: 1.6;
            padding: 10px 15px;
            background: transparent;
            border: none;
        """)
        container_layout.addWidget(message_label)
        
        container_layout.addSpacing(10)
        
        # Botones
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_layout.addStretch()
        
        if buttons is None:
            # Botón por defecto (Aceptar)
            btn_accept = self._create_button("Aceptar", "primary")
            btn_accept.clicked.connect(self._on_accept)
            buttons_layout.addWidget(btn_accept)
        else:
            # Botones personalizados
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
        
        # Ajustar tamaño
        self.setFixedWidth(450)
        self.adjustSize()
    
    def _create_button(self, text, btn_type):
        """
        Crea un botón estilizado según el tipo especificado.
        
        :param text: Texto a mostrar en el botón.
        :type text: str
        :param btn_type: Tipo de botón ('primary' o 'secondary').
        :type btn_type: str
        :return: Botón configurado y estilizado.
        :rtype: QPushButton
        """
        btn = QPushButton(text)
        btn.setFixedSize(100, 35)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Obtener tema del padre si está disponible
        parent = self.parent()
        is_dark = hasattr(parent, 'tema_oscuro') and parent.tema_oscuro
        
        if btn_type == "primary":
            btn.setStyleSheet("""
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
            """)
        else:  # secondary/cancel
            if is_dark:
                bg_color = "#2A2A2A"
                hover_color = "#333333"
                pressed_color = "#3A3A3A"
                text_color = "#FFFFFF"  # Blanco brillante para mejor visibilidad
                border_color = "#4A4A4A"
            else:
                bg_color = "#F5F5F5"
                hover_color = "#E8E8E8"
                pressed_color = "#DCDCDC"
                text_color = "#4A4A4A"
                border_color = "#DCDCDC"
            
            btn.setStyleSheet(f"""
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
            """)
        
        return btn
    
    def _get_icon_path(self):
        """
        Obtiene la ruta del icono correspondiente al tipo de diálogo.
        
        Los iconos se buscan en la carpeta ICONS_DIR según la estructura
        reorganizada de assets/.
        
        :return: Ruta absoluta del archivo de icono.
        :rtype: str
        """
        icons = {
            "success": os.path.join(ICONS_DIR, "icon_success.png"),
            "error": os.path.join(ICONS_DIR, "icon_error.png"),
            "warning": os.path.join(ICONS_DIR, "icon_warning.png"),
            "info": os.path.join(ICONS_DIR, "icon_info.png"),
            "question": os.path.join(ICONS_DIR, "icon_question.png")
        }
        icon_file = icons.get(self.dialog_type, os.path.join(ICONS_DIR, "icon_info.png"))
        return obtener_ruta_recurso(icon_file)
    
    def _get_icon_text(self):
        """
        Obtiene el texto del icono como respaldo si no se encuentra la imagen.
        
        :return: Carácter Unicode representando el tipo de diálogo.
        :rtype: str
        """
        icons = {
            "success": "✓",
            "error": "✗",
            "warning": "⚠",
            "info": "ℹ",
            "question": "?"
        }
        return icons.get(self.dialog_type, "ℹ")
    
    def _get_icon_color(self):
        """
        Obtiene el color del icono según el tipo de diálogo.
        
        :return: Código hexadecimal del color.
        :rtype: str
        """
        colors = {
            "success": "#00C853",
            "error": "#CD0403",
            "warning": "#FF9800",
            "info": "#2196F3",
            "question": "#546E7A"
        }
        return colors.get(self.dialog_type, "#2196F3")
    
    def _on_accept(self):
        """
        Maneja la aceptación del diálogo.
        Establece result_value a True y cierra el diálogo.
        """
        self.result_value = True
        self.accept()
    
    def _on_reject(self):
        """
        Maneja el rechazo del diálogo.
        Establece result_value a False y cierra el diálogo.
        """
        self.result_value = False
        self.reject()
    
    def showEvent(self, event):
        """
        Sobrescribe el evento de mostrar para iniciar animación de fade-in.
        
        :param event: Evento de mostrar el widget.
        :type event: QShowEvent
        """
        super().showEvent(event)
        self.fade_in_animation.start()
    
    # ==================== MÉTODOS ESTÁTICOS ====================
    
    # ==================== MÉTODOS ESTÁTICOS ====================
    
    @staticmethod
    def success(parent, title, message):
        """
        Muestra un diálogo de éxito.
        
        :param parent: Widget padre del diálogo.
        :type parent: QWidget
        :param title: Título del diálogo.
        :type title: str
        :param message: Mensaje a mostrar.
        :type message: str
        """
        dialog = KBKADialog(parent, title, message, "success", [("Aceptar", "primary")])
        dialog.exec()
    
    @staticmethod
    def error(parent, title, message):
        """
        Muestra un diálogo de error.
        
        :param parent: Widget padre del diálogo.
        :type parent: QWidget
        :param title: Título del diálogo.
        :type title: str
        :param message: Mensaje de error a mostrar.
        :type message: str
        """
        dialog = KBKADialog(parent, title, message, "error", [("Aceptar", "primary")])
        dialog.exec()
    
    @staticmethod
    def warning(parent, title, message):
        """
        Muestra un diálogo de advertencia.
        
        :param parent: Widget padre del diálogo.
        :type parent: QWidget
        :param title: Título del diálogo.
        :type title: str
        :param message: Mensaje de advertencia a mostrar.
        :type message: str
        """
        dialog = KBKADialog(parent, title, message, "warning", [("Aceptar", "primary")])
        dialog.exec()
    
    @staticmethod
    def info(parent, title, message):
        """
        Muestra un diálogo informativo.
        
        :param parent: Widget padre del diálogo.
        :type parent: QWidget
        :param title: Título del diálogo.
        :type title: str
        :param message: Mensaje informativo a mostrar.
        :type message: str
        """
        dialog = KBKADialog(parent, title, message, "info", [("Aceptar", "primary")])
        dialog.exec()
    
    @staticmethod
    def confirm(parent, title, message):
        """
        Muestra un diálogo de confirmación.
        
        :param parent: Widget padre del diálogo.
        :type parent: QWidget
        :param title: Título del diálogo.
        :type title: str
        :param message: Pregunta a confirmar.
        :type message: str
        :return: True si el usuario acepta, False si cancela.
        :rtype: bool
        """
        dialog = KBKADialog(parent, title, message, "question", 
                          [("Cancelar", "secondary"), ("Sí, continuar", "primary")])
        dialog.exec()
        return dialog.result_value


class EtiquetasApp(QMainWindow):
    """
    Aplicación principal para generación de etiquetas de envío KBKA SHOP.
    
    Proporciona una interfaz gráfica completa para:
    - Ingresar datos de clientes y envíos
    - Generar etiquetas de 4x6 pulgadas
    - Guardar etiquetas en PDF
    - Imprimir directamente en impresoras térmicas
    - Gestionar base de datos de clientes
    - Autocompletar direcciones usando base de datos SEPOMEX
    - Soporte para temas claro/oscuro
    
    Attributes:
        COLORS (dict): Paleta de colores corporativos de KBKA SHOP.
        LABEL_WIDTH (int): Ancho de la etiqueta en píxeles (576px = 6 pulgadas).
        LABEL_HEIGHT (int): Alto de la etiqueta en píxeles (384px = 4 pulgadas).
        df_sepomex (DataFrame): Datos de códigos postales de México (SEPOMEX).
    """
    
    # Paleta de colores corporativos
    COLORS = {
        'primary': '#D40103',      # Rojo corporativo
        'secondary': '#D10E0E',    # Rojo de acento
        'gray1': '#808080',        # Texto secundario
        'gray2': '#9F9F9F',        # Fondo de footer
        'gray_dark': '#2B2B2B',    # Fondo oscuro para vista previa
        'white': '#FFFFFF',        # Fondo principal
        'success': '#00C853'       # Indicadores de éxito
    }
    
    # Dimensiones de la etiqueta para VISTA PREVIA (4x6 pulgadas horizontal a 96 DPI)
    LABEL_WIDTH = 576  # 6 pulgadas * 96 DPI (horizontal)
    LABEL_HEIGHT = 384  # 4 pulgadas * 96 DPI (horizontal)

    # Dimensiones para PDF e IMPRESIÓN (4x3 pulgadas horizontal a 96 DPI)
    PDF_LABEL_WIDTH = 384   # 4 pulgadas * 96 DPI
    PDF_LABEL_HEIGHT = 288  # 3 pulgadas * 96 DPI
    
    # Datos fijos de la empresa
    EMPRESA_NOMBRE = "KBKA SHOP"
    EMPRESA_DESCRIPCION = "DISTRIBUIDORA DE REFACCIONES PARA CELULAR"
    EMPRESA_DIRECCION = "Av. 16 de Septiembre 140\nCol. Centro\nC.P. 44100\nGuadalajara, Jalisco\nMéxico"
    
    # DataFrame global para datos de SEPOMEX
    df_sepomex = None
    
    def __init__(self):
        """
        Inicializa la aplicación principal.
        
        Configura la base de datos, carga datos de SEPOMEX, establece el tema
        por defecto y maximiza la ventana.
        """
        super().__init__()

        # Transición visual de entrada, igual que en el módulo de modelos.
        self._intro_animation_started = False
        self._intro_opacity_animation = None
        self.setWindowOpacity(0.0)

        # Inicializar base de datos
        self.inicializar_db()
        
        # Cargar datos de SEPOMEX al inicio
        self.cargar_sepomex()
        
        # Configuración de la ventana principal
        self.setWindowTitle("KBKA SHOP - Gestor de Etiquetas")
        
        # Establecer icono si existe
        try:
            icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'KBKA.ico'))
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except:
            pass
        
        # Datos del formulario
        self.opcion_envio = "Paquetería"
        self.condicion = "Pagado"
        
        # Tema (por defecto: oscuro)
        self.tema_oscuro = True
        
        # Referencia a ventanas de diálogo abiertas
        self.gestion_clientes_dialog = None
        self.ayuda_dialog = None

        # Control de búsqueda de CP en el formulario principal.
        self._cargando_cliente_en_formulario = False
        self._ultimo_cp_invalido_formulario = None
        
        # Configurar UI
        self.init_ui()
        
        # Maximizar ventana
        # La ventana se muestra y maximiza desde el launcher unificado.
    
    def showEvent(self, event):
        """Ejecuta una transición suave al abrir el módulo de envíos."""
        super().showEvent(event)

        if self._intro_animation_started:
            return

        self._intro_animation_started = True
        self.setWindowOpacity(0.0)

        self._intro_opacity_animation = QPropertyAnimation(
            self,
            b"windowOpacity",
        )
        self._intro_opacity_animation.setDuration(700)
        self._intro_opacity_animation.setStartValue(0.0)
        self._intro_opacity_animation.setEndValue(1.0)
        self._intro_opacity_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )
        self._intro_opacity_animation.start()

    def inicializar_db(self):
        """
        Inicializa la base de datos SQLite y crea las tablas necesarias.
        
        Crea dos tablas:
        - 'clientes': Almacena información de clientes (nombre, dirección, teléfono).
        - 'configuracion': Guarda configuraciones de la app (impresora predeterminada).
        
        La base de datos se almacena en %APPDATA%\\KBKA_Shop\\kbka_data.db.
        Si el directorio no existe, se crea automáticamente.
        """
        try:
            # Verificar y crear directorio si no existe
            db_directory = os.path.dirname(DB_PATH)
            os.makedirs(db_directory, exist_ok=True)
            
            # Conectar a la base de datos (se crea si no existe)
            self.db_path = DB_PATH
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Crear tabla clientes si no existe
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clientes (
                    nombre TEXT PRIMARY KEY,
                    celular TEXT,
                    calle TEXT,
                    cp TEXT,
                    colonia TEXT,
                    estado TEXT,
                    municipio TEXT
                )
            ''')
            
            # Crear tabla configuracion si no existe
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuracion (
                    parametro TEXT PRIMARY KEY,
                    valor TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error al inicializar base de datos: {e}")
    
    def obtener_nombres_clientes(self):
        """
        Obtiene la lista de nombres de clientes de la base de datos.
        
        :return: Lista de nombres de clientes ordenados alfabéticamente.
        :rtype: list
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT nombre FROM clientes ORDER BY nombre')
            nombres = [row[0] for row in cursor.fetchall()]
            conn.close()
            return nombres
        except Exception as e:
            print(f"Error al obtener nombres de clientes: {e}")
            return []
    
    def obtener_impresoras(self):
        """
        Obtiene la lista de impresoras disponibles en el sistema.
        
        Utiliza win32print para enumerar impresoras locales y de red.
        Requiere que pywin32 esté instalado.
        
        :return: Lista de nombres de impresoras disponibles.
        :rtype: list
        """
        print("WIN32AVAILABLE: ", WIN32_AVAILABLE)
        if not WIN32_AVAILABLE:
            return []
        try:
            impresoras = []
            # Obtener impresoras locales y de red
            printers = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )
            print("printers raw: ", printers)
            for printer in printers:
                impresoras.append(printer[2])  # printer[2] es el nombre de la impresora
            return impresoras
        except Exception as e:
            print(f"Error al obtener impresoras: {e}")
            return []
    
    def guardar_impresora_config(self, nombre_impresora):
        """
        Guarda la impresora seleccionada en la base de datos.
        
        :param nombre_impresora: Nombre de la impresora a guardar como predeterminada.
        :type nombre_impresora: str
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO configuracion (parametro, valor)
                VALUES (?, ?)
            ''', ('impresora_predeterminada', nombre_impresora))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error al guardar impresora: {e}")
    
    def cargar_impresora_config(self):
        """
        Carga la impresora guardada desde la base de datos.
        
        :return: Nombre de la impresora predeterminada o None si no existe.
        :rtype: str or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT valor FROM configuracion WHERE parametro = ?
            ''', ('impresora_predeterminada',))
            resultado = cursor.fetchone()
            conn.close()
            return resultado[0] if resultado else None
        except Exception as e:
            print(f"Error al cargar impresora: {e}")
            return None
    
    def configurar_completer(self):
        """
        Configura el autocompletado para el campo de nombre de cliente.
        
        Crea un QCompleter que busca coincidencias en la base de datos de clientes
        mientras el usuario escribe. Al seleccionar un nombre, carga automáticamente
        todos los datos del cliente.
        """
        # Obtener lista de nombres
        nombres = self.obtener_nombres_clientes()
        
        # Crear modelo
        self.completer_model = QStringListModel(nombres)
        
        # Crear y configurar completer
        self.completer = QCompleter(self.completer_model, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        
        # Conectar señal para cargar datos
        self.completer.activated.connect(self.cargar_datos_cliente)
        
        # Asignar completer al campo de nombre
        self.entry_nombre.setCompleter(self.completer)
    
    def actualizar_completer(self):
        """
        Actualiza la lista de nombres en el autocompletado.
        
        Debe llamarse después de agregar, modificar o eliminar clientes
        para reflejar los cambios en el autocompletado.
        """
        nombres = self.obtener_nombres_clientes()
        self.completer_model.setStringList(nombres)
    
    def cargar_datos_cliente(self, nombre):
        """
        Carga los datos del cliente seleccionado desde la base de datos.
        
        Busca el cliente por nombre (case insensitive) y rellena automáticamente
        todos los campos del formulario. También dispara la búsqueda por CP
        para cargar las colonias disponibles.
        
        :param nombre: Nombre del cliente a cargar.
        :type nombre: str
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar cliente por nombre (case insensitive)
            cursor.execute('''
                SELECT celular, calle, cp, colonia, estado, municipio 
                FROM clientes 
                WHERE UPPER(nombre) = UPPER(?)
            ''', (nombre,))
            
            resultado = cursor.fetchone()
            conn.close()
            
            if resultado:
                # Rellenar campos del formulario
                self.entry_celular.setText(resultado[0] or '')
                self.entry_calle.setText(resultado[1] or '')
                
                # Guardar la colonia antes de disparar la búsqueda por CP
                colonia_guardada = resultado[3]

                self._cargando_cliente_en_formulario = True
                try:
                    self.entry_cp.setText(resultado[2] or "")
                    if colonia_guardada:
                        self.combo_colonia.setCurrentText(
                            colonia_guardada.upper()
                        )
                finally:
                    self._cargando_cliente_en_formulario = False

                # Si no se encontró por CP, usar datos guardados
                if not self.entry_estado.text() and resultado[4]:
                    self.entry_estado.setText(resultado[4])
                if not self.entry_ciudad.text() and resultado[5]:
                    self.entry_ciudad.setText(resultado[5])

                # La cantidad pertenece al pedido, no al cliente.
                if hasattr(self, "entry_cantidad"):
                    self.entry_cantidad.clear()

                
                # Actualizar vista previa
                self.actualizar_vista_previa()
                
        except Exception as e:
            print(f"Error al cargar datos del cliente: {e}")
    
    def guardar_cliente(self):
        """
        Guarda o actualiza los datos del cliente en la base de datos (UPSERT).
        
        Utiliza INSERT OR REPLACE para actualizar si el cliente ya existe
        o crear uno nuevo si no existe. El nombre es la clave primaria.
        Todos los datos se convierten a mayúsculas antes de guardar.
        """
        try:
            # Obtener datos del formulario en mayúsculas
            nombre = self.entry_nombre.text().strip().upper()
            celular = self.entry_celular.text().strip()
            calle = self.entry_calle.text().strip().upper()
            cp = self.entry_cp.text().strip()
            colonia = self.combo_colonia.currentText().strip().upper()
            estado = self.entry_estado.text().strip().upper()
            municipio = self.entry_ciudad.text().strip().upper()
            
            # Conectar a la base de datos
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # INSERT OR REPLACE (UPSERT)
            cursor.execute('''
                INSERT OR REPLACE INTO clientes 
                (nombre, celular, calle, cp, colonia, estado, municipio)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (nombre, celular, calle, cp, colonia, estado, municipio))
            
            conn.commit()
            conn.close()
            
            # Actualizar el completer con el nuevo/actualizado nombre
            self.actualizar_completer()
            
        except Exception as e:
            print(f"Error al guardar cliente: {e}")
    
    def init_ui(self):
        """
        Inicializa la interfaz de usuario completa.
        
        Crea y configura todos los componentes visuales:
        - Header con logo
        - Formulario de entrada de datos
        - Vista previa de etiqueta
        - Footer con controles de tema y ayuda
        """
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Crear componentes
        self.crear_header(main_layout)
        self.crear_formulario(main_layout)
        self.crear_footer(main_layout)
        
        # Configurar completer después de crear el formulario
        self.configurar_completer()
        
        # Aplicar estilos QSS
        self.aplicar_estilos()
    
    def crear_header(self, main_layout):
        """
        Crea el header de la aplicación con el logo de KBKA SHOP.
        
        El logo se carga desde HEADERS_DIR/header_main.png según la
        estructura reorganizada de assets/.
        
        :param main_layout: Layout principal donde agregar el header.
        :type main_layout: QVBoxLayout
        """
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(150)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        # Agregar espacio antes del logo para centrarlo
        header_layout.addStretch()
        
        # Intentar cargar logo
        try:
            # Seleccionar header según el modo (claro/oscuro)
            header_filename = 'header_fondo_oscuro.png' if self.tema_oscuro else 'header_fondo_blanco.png'
            logo_path = obtener_ruta_recurso(os.path.join(HEADERS_DIR, header_filename))
            if os.path.exists(logo_path):
                self.header_logo_label = QLabel()
                self.header_logo_label.setObjectName("header_logo")
                pixmap = QPixmap(logo_path)
                pixmap = pixmap.scaled(300, 150, Qt.AspectRatioMode.KeepAspectRatio, 
                                      Qt.TransformationMode.SmoothTransformation)
                self.header_logo_label.setPixmap(pixmap)
                self.header_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                header_layout.addWidget(self.header_logo_label)
        except Exception as e:
            print(f"No se pudo cargar el logo: {e}")
        
        # Agregar espacio después del logo para centrarlo
        header_layout.addStretch()
        
        main_layout.addWidget(header)
    
    def actualizar_header_logo(self):
        """
        Actualiza el logo del header según el tema actual (claro/oscuro).
        """
        if not hasattr(self, 'header_logo_label'):
            return
            
        try:
            # Seleccionar header según el modo (claro/oscuro)
            header_filename = 'header_fondo_oscuro.png' if self.tema_oscuro else 'header_fondo_blanco.png'
            logo_path = obtener_ruta_recurso(os.path.join(HEADERS_DIR, header_filename))
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                pixmap = pixmap.scaled(300, 150, Qt.AspectRatioMode.KeepAspectRatio, 
                                      Qt.TransformationMode.SmoothTransformation)
                self.header_logo_label.setPixmap(pixmap)
        except Exception as e:
            print(f"No se pudo actualizar el logo del header: {e}")
    
    def cargar_sepomex(self):
        """
        Carga el archivo CSV de SEPOMEX al inicio para búsquedas rápidas.
        
        El archivo se carga desde DB_DIR/sepomex_consolidado.csv (estructura reorganizada).
        Contiene códigos postales, colonias, municipios y estados de México.
        Se guarda en la variable de clase df_sepomex para acceso global.
        """
        try:
            csv_path = obtener_ruta_recurso(os.path.join(DB_DIR, 'sepomex_consolidado.csv'))
            if os.path.exists(csv_path):
                # Cargar CSV con dtype específico para código postal
                EtiquetasApp.df_sepomex = pd.read_csv(
                    csv_path,
                    dtype={'d_codigo': str},
                    usecols=['d_codigo', 'd_asenta', 'D_mnpio', 'd_estado']
                )
                print(f"Base de datos SEPOMEX cargada: {len(EtiquetasApp.df_sepomex)} registros")
            else:
                KBKADialog.warning(
                    self,
                    "Advertencia",
                    "No se encontró el archivo sepomex_consolidado.csv\n"
                    "El autocompletado no estará disponible."
                )
        except Exception as e:
            KBKADialog.error(
                self,
                "Error",
                f"Error al cargar base de datos SEPOMEX:\n{str(e)}"
            )
    
    def buscar_por_cp(self):
        """
        Actualiza los datos de ubicación del formulario principal.

        Reglas:
        - Con menos de 5 dígitos, colonia, estado y municipio quedan vacíos.
        - Con un CP válido de 5 dígitos, se cargan las colonias sin seleccionar
          ninguna y el combo se abre automáticamente.
        - Con un CP inexistente en SEPOMEX, no se muestran colonias y se lanza
          un KBKADialog informativo.
        """
        cp = self.entry_cp.text().strip()

        # Limpiar siempre los datos correspondientes al CP anterior.
        self.entry_estado.clear()
        self.entry_ciudad.clear()

        self.combo_colonia.blockSignals(True)
        self.combo_colonia.clear()
        self.combo_colonia.setCurrentIndex(-1)
        self.combo_colonia.blockSignals(False)

        if not cp:
            self.combo_colonia.setPlaceholderText(
                "Ingrese CP para ver colonias"
            )
            self._ultimo_cp_invalido_formulario = None
            self.actualizar_vista_previa()
            return

        # No consultar SEPOMEX ni mostrar colonias hasta tener 5 dígitos.
        if len(cp) != 5 or not cp.isdigit():
            self.combo_colonia.setPlaceholderText(
                "Complete un CP de 5 dígitos"
            )
            self._ultimo_cp_invalido_formulario = None
            self.actualizar_vista_previa()
            return

        if EtiquetasApp.df_sepomex is None:
            return

        try:
            resultados = EtiquetasApp.df_sepomex[
                EtiquetasApp.df_sepomex["d_codigo"] == cp
            ]

            if resultados.empty:
                self.combo_colonia.setPlaceholderText(
                    "No hay colonias disponibles"
                )
                self.actualizar_vista_previa()

                if (
                    not self._cargando_cliente_en_formulario
                    and self._ultimo_cp_invalido_formulario != cp
                ):
                    self._ultimo_cp_invalido_formulario = cp
                    KBKADialog.info(
                        self,
                        "CP no encontrado",
                        f"No se encontró información para el CP: {cp}."
                    )
                return

            self._ultimo_cp_invalido_formulario = None

            primer_resultado = resultados.iloc[0]
            self.entry_estado.setText(
                str(primer_resultado["d_estado"]).upper()
            )
            self.entry_ciudad.setText(
                str(primer_resultado["D_mnpio"]).upper()
            )

            colonias = sorted(
                {
                    str(colonia).strip().upper()
                    for colonia in resultados["d_asenta"].dropna().tolist()
                    if str(colonia).strip()
                }
            )

            self.combo_colonia.blockSignals(True)
            self.combo_colonia.addItems(colonias)
            self.combo_colonia.setCurrentIndex(-1)
            self.combo_colonia.setPlaceholderText(
                "Seleccione una colonia"
            )
            self.combo_colonia.blockSignals(False)

            self.actualizar_vista_previa()

            # Al capturar manualmente un CP válido, abrir inmediatamente
            # el listado para que el usuario seleccione una colonia.
            if colonias and not self._cargando_cliente_en_formulario:
                QTimer.singleShot(
                    0,
                    self.combo_colonia.showPopup,
                )

        except Exception as error:
            print(f"Error al buscar CP: {error}")
    def crear_formulario(self, main_layout):
        """
        Crea la interfaz principal con Cliente, Logística y Acciones en la
        columna izquierda, y una vista previa amplia en la derecha.
        """
        form_container = QWidget()
        form_container.setObjectName("main_content_container")
        form_layout = QHBoxLayout(form_container)
        form_layout.setContentsMargins(30, 20, 30, 24)
        form_layout.setSpacing(18)

        def crear_titulo_tarjeta(texto, ancho_linea):
            contenedor = QWidget()
            contenedor.setObjectName("transparent_widget")
            layout = QVBoxLayout(contenedor)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)

            titulo = QLabel(texto)
            titulo.setObjectName("card_title")
            layout.addWidget(titulo)

            linea = QFrame()
            linea.setObjectName("card_separator")
            linea.setFrameShape(QFrame.Shape.HLine)
            linea.setFixedHeight(2)
            linea.setFixedWidth(ancho_linea)
            layout.addWidget(linea)
            return contenedor

        def crear_label_campo(texto):
            label = QLabel(texto)
            label.setObjectName("field_label")
            return label

        def crear_campo_vertical(label_texto, widget):
            contenedor = QWidget()
            contenedor.setObjectName("transparent_widget")
            layout = QVBoxLayout(contenedor)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)
            layout.addWidget(crear_label_campo(label_texto))
            layout.addWidget(widget)
            return contenedor

        # ==================== COLUMNA IZQUIERDA ====================
        left_widget = QWidget()
        left_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # -------------------- DATOS DEL CLIENTE --------------------
        self.card_cliente = QFrame()
        self.card_cliente.setObjectName("panel_card")
        cliente_layout = QVBoxLayout(self.card_cliente)
        cliente_layout.setContentsMargins(20, 17, 20, 18)
        cliente_layout.setSpacing(10)
        cliente_layout.addWidget(
            crear_titulo_tarjeta("📋  DATOS DEL CLIENTE", 215)
        )

        fila_nombre = QHBoxLayout()
        fila_nombre.setContentsMargins(0, 0, 0, 0)
        fila_nombre.setSpacing(12)

        self.entry_nombre = QLineEdit()
        self.entry_nombre.setPlaceholderText("Ingrese nombre completo")
        self.entry_nombre.textChanged.connect(self.convertir_mayusculas)
        self.entry_nombre.textChanged.connect(self.actualizar_vista_previa)
        fila_nombre.addWidget(
            crear_campo_vertical("Nombre del cliente", self.entry_nombre),
            2,
        )

        self.entry_celular = QLineEdit()
        self.entry_celular.setPlaceholderText("10 dígitos")
        self.entry_celular.setMaxLength(10)
        self.entry_celular.textChanged.connect(self.validar_celular)
        self.entry_celular.textChanged.connect(self.actualizar_vista_previa)
        fila_nombre.addWidget(
            crear_campo_vertical("Número de celular", self.entry_celular),
            1,
        )
        cliente_layout.addLayout(fila_nombre)

        self.entry_calle = QLineEdit()
        self.entry_calle.setPlaceholderText(
            "Calle y número exterior/interior"
        )
        self.entry_calle.textChanged.connect(self.convertir_mayusculas)
        self.entry_calle.textChanged.connect(self.actualizar_vista_previa)
        cliente_layout.addWidget(
            crear_campo_vertical("Calle y número", self.entry_calle)
        )

        fila_ubicacion = QHBoxLayout()
        fila_ubicacion.setContentsMargins(0, 0, 0, 0)
        fila_ubicacion.setSpacing(12)

        self.entry_cp = QLineEdit()
        self.entry_cp.setPlaceholderText("5 dígitos")
        self.entry_cp.setMaxLength(5)
        self.entry_cp.textChanged.connect(self.buscar_por_cp)
        self.entry_cp.textChanged.connect(self.actualizar_vista_previa)
        fila_ubicacion.addWidget(
            crear_campo_vertical("Código postal (CP)", self.entry_cp),
            1,
        )

        self.combo_colonia = QComboBox()
        self.combo_colonia.setEditable(False)
        self.combo_colonia.setPlaceholderText(
            "Ingrese CP para ver colonias"
        )
        self.combo_colonia.currentTextChanged.connect(
            self.actualizar_vista_previa
        )
        fila_ubicacion.addWidget(
            crear_campo_vertical("Colonia", self.combo_colonia),
            2,
        )
        cliente_layout.addLayout(fila_ubicacion)

        fila_estado = QHBoxLayout()
        fila_estado.setContentsMargins(0, 0, 0, 0)
        fila_estado.setSpacing(12)

        self.entry_estado = QLineEdit()
        self.entry_estado.setReadOnly(True)
        self.entry_estado.setPlaceholderText("Se completa con el CP")
        fila_estado.addWidget(
            crear_campo_vertical("Estado", self.entry_estado),
            1,
        )

        self.entry_ciudad = QLineEdit()
        self.entry_ciudad.setReadOnly(True)
        self.entry_ciudad.setPlaceholderText("Se completa con el CP")
        fila_estado.addWidget(
            crear_campo_vertical("Ciudad / Municipio", self.entry_ciudad),
            1,
        )
        cliente_layout.addLayout(fila_estado)

        left_layout.addWidget(self.card_cliente)

        # -------------------- LOGÍSTICA Y ENVÍO --------------------
        self.card_logistica = QFrame()
        self.card_logistica.setObjectName("panel_card")
        logistica_layout = QVBoxLayout(self.card_logistica)
        logistica_layout.setContentsMargins(20, 16, 20, 17)
        logistica_layout.setSpacing(9)
        logistica_layout.addWidget(
            crear_titulo_tarjeta("🚚  LOGÍSTICA Y ENVÍO", 220)
        )

        logistica_layout.addWidget(crear_label_campo("Opción de envío"))

        self.radio_group_envio = QButtonGroup(self)
        self.radio_group_envio.setExclusive(True)
        envio_layout = QHBoxLayout()
        envio_layout.setContentsMargins(0, 0, 0, 0)
        envio_layout.setSpacing(7)

        for opcion in ("Paquetería", "Camión", "Servicio a Domicilio"):
            radio = QPushButton(opcion)
            radio.setObjectName("segment_option")
            radio.setCheckable(True)
            radio.setAutoDefault(False)
            radio.setDefault(False)
            radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            radio.setCursor(Qt.CursorShape.PointingHandCursor)
            radio.setMinimumHeight(38)
            radio.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            radio.toggled.connect(self.on_radio_changed)
            self.radio_group_envio.addButton(radio)
            envio_layout.addWidget(radio, 1)
            if opcion == "Paquetería":
                radio.setChecked(True)

        logistica_layout.addLayout(envio_layout)
        logistica_layout.addSpacing(3)
        logistica_layout.addWidget(
            crear_label_campo("Condición del envío")
        )

        self.radio_group_condicion = QButtonGroup(self)
        self.radio_group_condicion.setExclusive(True)
        condicion_layout = QHBoxLayout()
        condicion_layout.setContentsMargins(0, 0, 0, 0)
        condicion_layout.setSpacing(7)

        for opcion in ("Pagado", "Pago al recibir", "Por cobrar"):
            radio = QPushButton(opcion)
            radio.setObjectName("segment_option")
            radio.setCheckable(True)
            radio.setAutoDefault(False)
            radio.setDefault(False)
            radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            radio.setCursor(Qt.CursorShape.PointingHandCursor)
            radio.setMinimumHeight(38)
            radio.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            radio.toggled.connect(self.on_radio_changed)
            self.radio_group_condicion.addButton(radio)
            condicion_layout.addWidget(radio, 1)
            if opcion == "Pagado":
                radio.setChecked(True)

        logistica_layout.addLayout(condicion_layout)
        logistica_layout.addSpacing(3)

        self.entry_cantidad = QLineEdit()
        self.entry_cantidad.setPlaceholderText("Ej. 1,250.00")
        self.entry_cantidad.setMaxLength(14)
        self.entry_cantidad.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.entry_cantidad.setToolTip(
            "Monto total del pedido. No se guarda como dato del cliente."
        )
        self.entry_cantidad.textChanged.connect(self.validar_cantidad)
        self.entry_cantidad.textChanged.connect(
            self.actualizar_vista_previa
        )
        self.entry_cantidad.editingFinished.connect(
            self.formatear_cantidad
        )
        logistica_layout.addWidget(
            crear_campo_vertical(
                "Monto total del pedido",
                self.entry_cantidad,
            )
        )

        left_layout.addWidget(self.card_logistica)

        # -------------------- ACCIONES --------------------
        self.card_acciones = QFrame()
        self.card_acciones.setObjectName("panel_card")
        acciones_layout = QVBoxLayout(self.card_acciones)
        acciones_layout.setContentsMargins(20, 16, 20, 16)
        acciones_layout.setSpacing(9)
        acciones_layout.addWidget(
            crear_titulo_tarjeta("⚙  ACCIONES", 125)
        )

        self.btn_imprimir = QPushButton("🖨️  IMPRIMIR")
        self.btn_imprimir.setObjectName("btn_print_primary")
        self.btn_imprimir.setMinimumHeight(46)
        self.btn_imprimir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_imprimir.clicked.connect(self.imprimir_etiqueta)
        acciones_layout.addWidget(self.btn_imprimir)

        acciones_secundarias = QHBoxLayout()
        acciones_secundarias.setContentsMargins(0, 0, 0, 0)
        acciones_secundarias.setSpacing(8)

        self.btn_guardar = QPushButton("💾  GUARDAR PDF")
        self.btn_guardar.setObjectName("btn_action_secondary")
        self.btn_guardar.setMinimumHeight(42)
        self.btn_guardar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_guardar.clicked.connect(self.guardar_pdf)
        acciones_secundarias.addWidget(self.btn_guardar, 1)

        self.btn_gestionar = QPushButton("👥  GESTIONAR CLIENTES")
        self.btn_gestionar.setObjectName("btn_action_secondary")
        self.btn_gestionar.setMinimumHeight(42)
        self.btn_gestionar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_gestionar.clicked.connect(self.abrir_gestion_clientes)
        acciones_secundarias.addWidget(self.btn_gestionar, 1)

        acciones_layout.addLayout(acciones_secundarias)

        self.btn_config_impresora = QPushButton(
            "⚙️  CONFIGURAR IMPRESORA"
        )
        self.btn_config_impresora.setObjectName("btn_config_modern")
        self.btn_config_impresora.setMinimumHeight(42)
        self.btn_config_impresora.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.btn_config_impresora.clicked.connect(
            self.abrir_configuracion_impresora
        )
        acciones_layout.addWidget(self.btn_config_impresora)

        self.btn_limpiar = QPushButton("🧹  LIMPIAR")
        self.btn_limpiar.setObjectName("btn_clean_link")
        self.btn_limpiar.setMinimumHeight(30)
        self.btn_limpiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_limpiar.setToolTip(
            "Limpia todos los campos del formulario"
        )
        self.btn_limpiar.clicked.connect(self.limpiar_campos)
        acciones_layout.addWidget(
            self.btn_limpiar,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        left_layout.addWidget(self.card_acciones)
        left_layout.addStretch()

        # ==================== COLUMNA DERECHA ====================
        right_widget = QWidget()
        right_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.card_preview = QFrame()
        self.card_preview.setObjectName("panel_card")
        self.card_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        preview_card_layout = QVBoxLayout(self.card_preview)
        preview_card_layout.setContentsMargins(18, 16, 18, 18)
        preview_card_layout.setSpacing(11)
        preview_card_layout.addWidget(
            crear_titulo_tarjeta("👁️  VISTA PREVIA", 150)
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

        # Reajustar la etiqueta cuando cambie el tamaño del panel derecho.
        self.preview_container.installEventFilter(self)

        preview_card_layout.addWidget(self.preview_container, 1)
        right_layout.addWidget(self.card_preview, 1)

        # Solo la columna izquierda tiene desplazamiento vertical.
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

        form_layout.addWidget(self.left_scroll, 38)
        form_layout.addWidget(right_widget, 62)

        # El panel derecho queda fijo mientras se desplaza el formulario.
        main_layout.addWidget(form_container, 1)

        self.actualizar_vista_previa()
    def convertir_mayusculas(self):
        """
        Convierte el texto del QLineEdit a mayúsculas automáticamente.
        
        Se ejecuta cuando el usuario escribe en campos de texto para
        mantener consistencia en el formato de datos almacenados.
        """
        sender = self.sender()
        if isinstance(sender, QLineEdit):
            cursor_position = sender.cursorPosition()
            sender.setText(sender.text().upper())
            sender.setCursorPosition(cursor_position)
    
    def validar_celular(self):
        """
        Valida que el campo de celular solo contenga números.
        
        Filtra automáticamente caracteres no numéricos mientras
        el usuario escribe, limitando a 10 dígitos.
        """
        texto = self.entry_celular.text()
        # Filtrar solo dígitos
        texto_filtrado = ''.join(filter(str.isdigit, texto))
        if texto != texto_filtrado:
            cursor_position = self.entry_celular.cursorPosition()
            self.entry_celular.setText(texto_filtrado)
            # Ajustar posición del cursor
            nuevo_cursor = max(0, cursor_position - (len(texto) - len(texto_filtrado)))
            self.entry_celular.setCursorPosition(nuevo_cursor)
    
    def validar_cantidad(self):
        """
        Permite únicamente un monto positivo con hasta dos decimales.
        """
        if not hasattr(self, "entry_cantidad"):
            return

        texto_original = self.entry_cantidad.text()
        cursor_original = self.entry_cantidad.cursorPosition()

        texto = (
            texto_original
            .replace("$", "")
            .replace(",", "")
            .replace(" ", "")
        )

        resultado = []
        punto_encontrado = False
        decimales = 0

        for caracter in texto:
            if caracter.isdigit():
                if punto_encontrado:
                    if decimales >= 2:
                        continue
                    decimales += 1
                resultado.append(caracter)
            elif caracter == "." and not punto_encontrado:
                punto_encontrado = True
                if not resultado:
                    resultado.append("0")
                resultado.append(caracter)

        texto_filtrado = "".join(resultado)

        if texto_filtrado != texto_original:
            self.entry_cantidad.blockSignals(True)
            self.entry_cantidad.setText(texto_filtrado)
            self.entry_cantidad.setCursorPosition(
                min(cursor_original, len(texto_filtrado))
            )
            self.entry_cantidad.blockSignals(False)
            self.actualizar_vista_previa()

    def formatear_cantidad(self):
        """Muestra el monto con separadores de miles y dos decimales."""
        if not hasattr(self, "entry_cantidad"):
            return

        texto = (
            self.entry_cantidad.text()
            .strip()
            .replace("$", "")
            .replace(",", "")
        )
        if not texto:
            return

        try:
            cantidad = float(texto)
        except ValueError:
            return

        self.entry_cantidad.blockSignals(True)
        self.entry_cantidad.setText(f"{cantidad:,.2f}")
        self.entry_cantidad.blockSignals(False)
        self.actualizar_vista_previa()

    def obtener_cantidad_formateada(self):
        """Devuelve el monto del pedido con formato de moneda."""
        if not hasattr(self, "entry_cantidad"):
            return "[CANTIDAD]"

        texto = (
            self.entry_cantidad.text()
            .strip()
            .replace("$", "")
            .replace(",", "")
        )
        if not texto:
            return "[CANTIDAD]"

        try:
            return f"${float(texto):,.2f}"
        except ValueError:
            return f"${texto}"

    def limpiar_campos(self):
        """
        Limpia todos los campos del formulario con confirmación.
        
        Muestra un diálogo de confirmación antes de borrar. Si el usuario
        confirma, limpia todos los campos de entrada y actualiza la vista previa.
        """
        # Mostrar diálogo de confirmación
        confirmado = KBKADialog.confirm(
            self,
            "Limpiar Campos",
            "¿Estás seguro de que deseas limpiar todos los campos?\n\n"
            "Esta acción borrará toda la información ingresada."
        )
        
        if confirmado:
            # Limpiar todos los campos de entrada
            self.entry_nombre.clear()
            self.entry_celular.clear()
            self.entry_calle.clear()
            self.entry_cp.clear()
            self.combo_colonia.clear()
            self.entry_estado.clear()
            self.entry_ciudad.clear()
            self.entry_cantidad.clear()
            
            # Actualizar vista previa
            self.actualizar_vista_previa()
            
            # Opcional: Enfocar el primer campo
            self.entry_nombre.setFocus()
    
    def abrir_gestion_clientes(self):
        """
        Abre el diálogo de gestión de clientes.
        
        Permite ver, editar y eliminar clientes de la base de datos.
        Actualiza el autocompletado al cerrar el diálogo.
        """
        dialogo = GestionClientesDialog(self)
        self.gestion_clientes_dialog = dialogo  # Guardar referencia
        dialogo.exec()
        self.gestion_clientes_dialog = None  # Limpiar referencia al cerrar
        # Actualizar completer después de cerrar el diálogo
        self.actualizar_completer()
    
    def abrir_configuracion_impresora(self):
        """
        Abre el diálogo de configuración de impresora.
        
        Permite seleccionar la impresora térmica predeterminada
        para impresión directa de etiquetas.
        """
        dialogo = ConfiguracionImpresoraDialog(self)
        dialogo.exec()
    
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
    
    def abrir_informacion(self):
        """Abre el diálogo con información del software y desarrollador"""
        mensaje = (
            "KBKA Shop\n"
            "Sistema de Gestión de Etiquetas v1.0.0\n\n"
            "Desarrollado por: Angel Alexander Ramírez Navarro (Chava 😉)\n"
            "© 2026 Todos los derechos reservados."
        )
        KBKADialog.info(self, "Información del Software", mensaje)
    
    def cargar_cliente_desde_gestion(self, datos_cliente):
        """
        Carga los datos de un cliente en el formulario principal para editar.
        
        Llamado desde el diálogo de gestión de clientes cuando el usuario
        hace clic en "Editar".
        
        :param datos_cliente: Tupla con datos del cliente (nombre, celular, calle, cp, colonia, estado, municipio).
        :type datos_cliente: tuple
        """
        # Datos: (nombre, celular, calle, cp, colonia, estado, municipio)
        self.entry_nombre.setText(datos_cliente[0] or '')
        self.entry_celular.setText(datos_cliente[1] or '')
        self.entry_calle.setText(datos_cliente[2] or '')

        self._cargando_cliente_en_formulario = True
        try:
            self.entry_cp.setText(datos_cliente[3] or "")
            if datos_cliente[4]:
                self.combo_colonia.setCurrentText(
                    datos_cliente[4].upper()
                )
        finally:
            self._cargando_cliente_en_formulario = False

        # Si no se encontró por CP, usar datos guardados
        if not self.entry_estado.text() and datos_cliente[5]:
            self.entry_estado.setText(datos_cliente[5])
        if not self.entry_ciudad.text() and datos_cliente[6]:
            self.entry_ciudad.setText(datos_cliente[6])

        # La cantidad pertenece al pedido, no al cliente importado.
        if hasattr(self, "entry_cantidad"):
            self.entry_cantidad.clear()

        
        # Actualizar vista previa
        self.actualizar_vista_previa()
    
    def on_radio_changed(self):
        """
        Maneja cambios en los radio buttons de envío y condición.
        
        Actualiza las variables de estado y regenera la vista previa
        de la etiqueta cuando cambian las opciones seleccionadas.
        """
        # Actualizar opción de envío
        if hasattr(self, 'radio_group_envio'):
            for button in self.radio_group_envio.buttons():
                if button.isChecked():
                    self.opcion_envio = button.text()
        
        # Actualizar condición
        if hasattr(self, 'radio_group_condicion'):
            for button in self.radio_group_condicion.buttons():
                if button.isChecked():
                    self.condicion = button.text()
        
        # Solo actualizar vista previa si todos los widgets están creados
        if hasattr(self, 'preview_label'):
            self.actualizar_vista_previa()
    
    def crear_footer(self, main_layout):
        """Crea el footer de la aplicación con botón de ayuda y toggle de tema"""
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(60)
        
        # Usar HBoxLayout para poder colocar elementos
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 10)
        
        # Botón de alternancia de tema (lado izquierdo)
        self.btn_tema = QPushButton()
        self.btn_tema.setObjectName("btn_theme_toggle")
        self.btn_tema.setText(
            "☀️ Modo Claro" if self.tema_oscuro else "🌙 Modo Oscuro"
        )
        self.btn_tema.setFixedHeight(35)
        self.btn_tema.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tema.setToolTip("Cambiar entre modo claro y oscuro")
        self.btn_tema.clicked.connect(self.alternar_tema)
        footer_layout.addWidget(self.btn_tema)
        
        # Añadir espacio después del botón de tema
        footer_layout.addStretch()
        
        # Label de copyright centrado
        footer_label = QLabel(f"© 2026 {self.EMPRESA_NOMBRE} - Todos los derechos reservados")
        footer_label.setObjectName("footer_text")
        footer_layout.addWidget(footer_label)
        
        # Añadir espacio a la derecha
        footer_layout.addStretch()
        
        # Botón de ayuda circular en la esquina derecha
        btn_ayuda = QPushButton()
        btn_ayuda.setObjectName("btn_help")
        
        # Intentar cargar icono personalizado
        try:
            ayuda_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'ayuda.png'))
            if os.path.exists(ayuda_icon_path):
                ayuda_icon_pixmap = QPixmap(ayuda_icon_path)
                ayuda_icon_pixmap = ayuda_icon_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, 
                                                             Qt.TransformationMode.SmoothTransformation)
                btn_ayuda.setIcon(QIcon(ayuda_icon_pixmap))
                btn_ayuda.setIconSize(QSize(24, 24))
                # Guardar pixmap para aplicar efectos de tema
                self.ayuda_icon_pixmap = ayuda_icon_pixmap
                self.ayuda_icon_path = ayuda_icon_path
            else:
                btn_ayuda.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
        except:
            btn_ayuda.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion))
        
        btn_ayuda.setFixedSize(45, 45)
        btn_ayuda.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ayuda.setToolTip("¿Necesitas ayuda? Haz clic para ver problemas comunes y soluciones")
        btn_ayuda.clicked.connect(self.abrir_ayuda)
        self.btn_ayuda = btn_ayuda  # Guardar referencia para cambio de tema
        footer_layout.addWidget(btn_ayuda)
        
        # Botón de información circular (a la derecha del botón de ayuda)
        btn_info = QPushButton()
        btn_info.setObjectName("btn_help")  # Usar el mismo estilo que btn_help
        
        # Intentar cargar icono personalizado
        try:
            info_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'informacion.png'))
            if os.path.exists(info_icon_path):
                info_icon_pixmap = QPixmap(info_icon_path)
                info_icon_pixmap = info_icon_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, 
                                                           Qt.TransformationMode.SmoothTransformation)
                btn_info.setIcon(QIcon(info_icon_pixmap))
                btn_info.setIconSize(QSize(24, 24))
                # Guardar pixmap para aplicar efectos de tema
                self.info_icon_pixmap = info_icon_pixmap
                self.info_icon_path = info_icon_path
            else:
                btn_info.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        except:
            btn_info.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        
        btn_info.setFixedSize(45, 45)
        btn_info.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_info.setToolTip("Información del software y créditos del desarrollador")
        btn_info.clicked.connect(self.abrir_informacion)
        self.btn_info = btn_info  # Guardar referencia para cambio de tema
        footer_layout.addWidget(btn_info)
        
        main_layout.addWidget(footer)
    
    def alternar_tema(self):
        """
        Alterna entre tema claro y oscuro.
        
        Cambia la variable tema_oscuro, actualiza el texto del botón,
        reaplica todos los estilos QSS y actualiza ventanas abiertas
        (gestión de clientes y ayuda) si existen.
        
        El cambio de tema afecta:
        - Colores de fondo y texto globales
        - Estilos de botones e inputs
        - Iconos en diálogos abiertos (usando QGraphicsColorizeEffect)
        """
        self.tema_oscuro = not self.tema_oscuro        # Actualizar texto del botón
        if self.tema_oscuro:
            self.btn_tema.setText("☀️ Modo Claro")
        else:
            self.btn_tema.setText("🌙 Modo Oscuro")
        
        # Aplicar nuevos estilos
        self.aplicar_estilos()
        
        # Actualizar el logo del header
        self.actualizar_header_logo()
        
        # Actualizar iconos en ventana de gestión de clientes si está abierta
        if self.gestion_clientes_dialog:
            self.gestion_clientes_dialog.actualizar_iconos_tema()
        
        # Actualizar estilos en ventana de ayuda si está abierta
        if self.ayuda_dialog:
            self.ayuda_dialog.aplicar_estilos()
        
        # Actualizar iconos de los botones de ayuda e información en el footer
        self.actualizar_iconos_footer()
    
    def aplicar_estilos(self):
        """
        Aplica los estilos QSS premium según el tema seleccionado.
        
        Define colores específicos para cada tema (claro/oscuro) y
        establece estilos CSS completos para todos los widgets:
        - Labels, inputs, combobox, radiobuttons
        - Botones (primary, secondary, success, config)
        - Scrollbars, tablas, diálogos
        - Header, footer y contenedores especiales
        
        La vista previa mantiene un fondo gris oscuro (#2B2B2B) en ambos temas
        para mejor contraste con las etiquetas blancas.
        """
        
        # Definir colores según el tema
        if self.tema_oscuro:
            # TEMA OSCURO
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
            text_primary = "#E0E0E0"
            text_secondary = "#B0B0B0"
            text_disabled = "#666666"
            border_color = "#3A3A3A"
            border_hover = "#4A4A4A"
            scrollbar_bg = "#2A2A2A"
            scrollbar_handle = "#4A4A4A"
            scrollbar_hover = "#5A5A5A"
            preview_bg = "transparent"
            preview_border = "#555555"  # Borde sutil para la etiqueta en preview
        else:
            # TEMA CLARO (colores actuales)
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
            text_primary = "#1A1A1A"
            text_secondary = "#2C3E50"
            text_disabled = "#9E9E9E"
            border_color = "#DCDCDC"
            border_hover = "#B8B8B8"
            scrollbar_bg = "transparent"
            scrollbar_handle = "#DCDCDC"
            scrollbar_hover = "#BDBDBD"
            preview_bg = "transparent"
            preview_border = "#000000"  # Borde negro uniforme en modo claro
        
        self.setStyleSheet(f"""
            /* ==================== ESTILOS GENERALES ==================== */
            QWidget {{
                background-color: {bg_secondary};
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 10pt;
                color: {text_primary};
            }}
            
            QMainWindow {{
                background-color: {bg_main};
            }}
            
            /* ==================== LABELS ==================== */
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

            QWidget#transparent_widget {{
                background-color: transparent;
            }}

            QLabel#card_title {{
                color: #CD0403;
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
                margin: 0px 0px 3px 0px;
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
            
            /* ==================== INPUTS (LineEdit) ==================== */
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
            
            QLineEdit:read-only {{
                background-color: {"#252525" if self.tema_oscuro else "#F3F4F6"};
                color: {"#B7BDC5" if self.tema_oscuro else "#5F6873"};
                border: 1px solid {"#444444" if self.tema_oscuro else "#D5D9DE"};
            }}

            QLineEdit:read-only:hover {{
                background-color: {"#292929" if self.tema_oscuro else "#F6F7F8"};
                color: {"#C5CAD0" if self.tema_oscuro else "#4F5964"};
                border: 1px solid {"#505050" if self.tema_oscuro else "#C9CED4"};
            }}

            QLineEdit:disabled {{
                background-color: {"#252525" if self.tema_oscuro else "#F3F4F6"};
                color: {"#9298A0" if self.tema_oscuro else "#7B8490"};
                border: 1px solid {"#444444" if self.tema_oscuro else "#D5D9DE"};
            }}
            
            /* ==================== COMBOBOX ==================== */
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
            
            /* ComboBox Dropdown (Popup) */
            QComboBox QAbstractItemView {{
                background-color: {"#252525" if self.tema_oscuro else "#FFFFFF"};
                color: {text_primary};
                selection-background-color: #CD0403;
                selection-color: #FFFFFF;
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
                background-color: {"#343434" if self.tema_oscuro else "#FCE8E8"};
                color: {"#FFFFFF" if self.tema_oscuro else "#CD0403"};
            }}

            QComboBox QAbstractItemView::item:selected {{
                background-color: #CD0403;
                color: #FFFFFF;
            }}
            
            /* ==================== RADIOBUTTONS ==================== */
            QRadioButton {{
                spacing: 10px;
                padding: 8px 4px;
                color: {text_secondary};
                font-size: 10pt;
            }}
            
            QRadioButton::indicator {{
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid {border_color};
                background-color: {bg_input};
            }}
            
            QRadioButton::indicator:hover {{
                border: 2px solid #CD0403;
                background-color: {bg_input_hover};
            }}
            
            QRadioButton::indicator:checked {{
                background-color: #CD0403;
                border: 2px solid #CD0403;
            }}
            
            QRadioButton::indicator:checked:hover {{
                background-color: #A30302;
                border: 2px solid #A30302;
            }}
            
            QPushButton#segment_option {{
                background-color: {"#2D2D2D" if self.tema_oscuro else "#F2F4F6"};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 7px;
                padding: 7px 8px;
                font-size: 9.5pt;
                font-weight: 700;
                outline: none;
            }}

            QPushButton#segment_option:hover {{
                background-color: {"#393939" if self.tema_oscuro else "#E8EBEE"};
                color: {text_primary};
                border: 1px solid #CD0403;
            }}

            QPushButton#segment_option:checked {{
                background-color: #FF4444;
                color: #FFFFFF;
                border: 1px solid #E22222;
            }}

            QPushButton#segment_option:checked:hover {{
                background-color: #E93636;
                color: #FFFFFF;
                border: 1px solid #CD0403;
            }}

            QPushButton#btn_print_primary {{
                background-color: #CD0403;
                color: #FFFFFF;
                border: 1px solid #F04B4A;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 11pt;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}

            QPushButton#btn_print_primary:hover {{
                background-color: #E00504;
                color: #FFFFFF;
                border: 1px solid #FF6A69;
            }}

            QPushButton#btn_print_primary:pressed {{
                background-color: #A50302;
                color: #FFFFFF;
                border: 1px solid #CD0403;
            }}

            QPushButton#btn_action_secondary {{
                background-color: {"#303846" if self.tema_oscuro else "#EEF1F4"};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 9px;
                padding: 9px 10px;
                font-size: 9.5pt;
                font-weight: 700;
            }}

            QPushButton#btn_action_secondary:hover {{
                background-color: {"#3B4657" if self.tema_oscuro else "#E2E7EC"};
                color: {text_primary};
                border: 1px solid #CD0403;
            }}

            QPushButton#btn_action_secondary:pressed {{
                background-color: {"#252C36" if self.tema_oscuro else "#D5DCE3"};
                color: {text_primary};
                border: 1px solid #A50302;
            }}

            QPushButton#btn_config_modern {{
                background-color: {"#343434" if self.tema_oscuro else "#F3F4F6"};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 9px;
                padding: 9px 12px;
                font-size: 9.5pt;
                font-weight: 650;
            }}

            QPushButton#btn_config_modern:hover {{
                background-color: {"#414141" if self.tema_oscuro else "#E6E9ED"};
                color: {text_primary};
                border: 1px solid #CD0403;
            }}

            QPushButton#btn_config_modern:pressed {{
                background-color: {"#2B2B2B" if self.tema_oscuro else "#D7DDE3"};
                color: {text_primary};
                border: 1px solid #A50302;
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
                color: #CD0403;
            }}

            QPushButton#btn_clean_link:pressed {{
                color: #8F0201;
            }}

            /* ==================== BOTONES PRIMARIOS ==================== */
            QPushButton#btn_primary {{
                background-color: #CD0403;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 11pt;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            
            QPushButton#btn_primary:hover {{
                background-color: #A50302;
            }}
            
            QPushButton#btn_primary:pressed {{
                background-color: #8F0201;
            }}
            
            QPushButton#btn_primary:disabled {{
                background-color: #E0E0E0;
                color: #9E9E9E;
            }}
            
            /* ==================== BOTONES DE ACCIÓN TÉCNICA (IMPRIMIR) ==================== */
            QPushButton#btn_success {{
                background-color: #2C3E50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 11pt;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            
            QPushButton#btn_success:hover {{
                background-color: #34495E;
            }}
            
            QPushButton#btn_success:pressed {{
                background-color: #1A252F;
            }}
            
            /* ==================== BOTONES SECUNDARIOS (OUTLINED) ==================== */
            QPushButton#btn_secondary {{
                background-color: {bg_secondary};
                color: #CD0403;
                border: 2px solid #CD0403;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 11pt;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            
            QPushButton#btn_secondary:hover {{
                background-color: #FFF5F5;
                border: 2px solid #CD0403;
                color: #CD0403;
            }}
            
            QPushButton#btn_secondary:pressed {{
                background-color: #FEE2E2;
                border: 2px solid #8F0201;
                color: #8F0201;
            }}
            
            /* ==================== BOTÓN DE CONFIGURACIÓN ==================== */
            QPushButton#btn_config {{
                background-color: #95A5A6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 11pt;
                font-weight: bold;
                letter-spacing: 0.5px;
            }}
            
            QPushButton#btn_config:hover {{
                background-color: #7F8C8D;
            }}
            
            QPushButton#btn_config:pressed {{
                background-color: #707B7C;
            }}
            
            /* ==================== BOTÓN LIMPIAR CAMPOS ==================== */
            QPushButton#btn_limpiar {{
                background-color: transparent;
                color: {"#B0B0B0" if self.tema_oscuro else "#666666"};
                border: 1px solid {"#555555" if self.tema_oscuro else "#CCCCCC"};
                border-radius: 5px;
                padding: 6px 12px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 9pt;
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
            
            /* ==================== CONTENEDOR DE VISTA PREVIA ==================== */
            QFrame#preview_container {{
                background-color: {preview_bg};
                border-radius: 12px;
                padding: 8px;
                border: none;
            }}
            
            /* Vista previa - imagen de etiqueta sin bordes ni efectos */
            QLabel#preview_image {{
                background-color: transparent;
                border: none;
                outline: none;
                padding: 0px;
            }}
            
            /* ==================== SCROLL AREA ==================== */
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
            
            /* ==================== SCROLLBAR ==================== */
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
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            
            /* ==================== TABLAS (QTableWidget) ==================== */
            QTableWidget {{
                background-color: {bg_secondary};
                alternate-background-color: {bg_container};
                color: {text_primary};
                gridline-color: {border_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                selection-background-color: #CD0403;
                selection-color: white;
            }}
            
            QTableWidget::item {{
                padding: 8px;
                border: none;
            }}
            
            QTableWidget::item:hover {{
                background-color: {bg_input_hover};
            }}
            
            QTableWidget::item:selected {{
                background-color: #CD0403;
                color: white;
            }}
            
            QHeaderView::section {{
                background-color: {bg_container};
                color: {text_primary};
                padding: 10px;
                border: none;
                border-bottom: 2px solid #CD0403;
                font-weight: bold;
                font-size: 10pt;
            }}
            
            QHeaderView::section:hover {{
                background-color: {bg_input_hover};
            }}
            
            /* ==================== DIÁLOGOS ==================== */
            QDialog {{
                background-color: {bg_secondary};
                color: {text_primary};
            }}
            
            /* ==================== HEADER ==================== */
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
            
            /* ==================== FOOTER ==================== */
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
            
            /* Botón de alternancia de tema en el footer */
            QPushButton#btn_theme_toggle {{
                background-color: {footer_button_bg};
                color: {footer_icon_color};
                border: 1px solid {footer_button_border};
                border-radius: 17px;
                padding: 6px 12px;
                font-size: 9pt;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            
            QPushButton#btn_theme_toggle:hover {{
                background-color: #CD0403;
                border: 1px solid #CD0403;
                color: #FFFFFF;
            }}
            
            QPushButton#btn_theme_toggle:pressed {{
                background-color: #A30302;
            }}
            
            /* Botón de ayuda en el footer con efecto glow */
            QPushButton#btn_help {{
                background-color: {footer_button_bg};
                border: 1px solid {footer_button_border};
                border-radius: 22px;
                padding: 5px;
            }}
            
            QPushButton#btn_help:hover {{
                background-color: #CD0403;
            }}
            
            QPushButton#btn_help:pressed {{
                background-color: #A30302;
            }}
            
            /* ==================== QMessageBox y QDialog globales ==================== */
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
            
            QMessageBox QPushButton:hover {{
                background-color: #E00504;
            }}
            
            QMessageBox QPushButton:pressed {{
                background-color: #A50302;
            }}
            
            /* Botón secundario en QMessageBox (Cancel, No, etc.) */
            QMessageBox QPushButton:last-child {{
                background-color: {bg_container};
                color: {text_primary};
                border: 1px solid {border_color};
            }}
            
            QMessageBox QPushButton:last-child:hover {{
                background-color: {bg_input_hover};
            }}
            
            QDialog {{
                background-color: {bg_secondary};
                color: {text_primary};
            }}
            
            QDialog QLabel {{
                color: {text_primary};
                background: transparent;
                border: none;
            }}
        """)
    
    def generar_imagen_etiqueta(self, escala=1, pdf_mode=True):
        """
        Genera la imagen de la etiqueta con los datos actuales (4x3 pulgadas).
        
        Crea una imagen PIL con:
        - Logo de empresa (desde HEADERS_DIR/header_etiqueta.png, máx. 15% del alto)
        - Datos del destinatario (nombre, dirección, celular)
        - Información de envío (paquetería, condición de pago y monto total)
        - Dirección de remitente (KBKA SHOP)
        
        :param escala: Factor de escala para resolución (1=96dpi, 4=384dpi para impresión).
        :type escala: float
        :param pdf_mode: Si True (default), usa dimensiones y layout compacto 4x3 pulgadas.
                         Si False, usa 6x4 pulgadas (modo legado).
        :type pdf_mode: bool
        :return: Imagen PIL de la etiqueta generada.
        :rtype: PIL.Image.Image
        """
        # Seleccionar dimensiones base y factor de escala de contenido
        if pdf_mode:
            # 4x3 pulgadas: canvas compacto, fuentes y márgenes reducidos ~35%
            base_width = self.PDF_LABEL_WIDTH   # 384px @ 96 DPI
            base_height = self.PDF_LABEL_HEIGHT  # 288px @ 96 DPI
            cs = 0.65  # content_scale: reduce fuentes y espaciados para el canvas más pequeño
        else:
            # Modo legado 6x4 pulgadas
            base_width = self.LABEL_WIDTH
            base_height = self.LABEL_HEIGHT
            cs = 1.0

        width = int(base_width * escala)
        height = int(base_height * escala)

        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)

        # ------------------------------------------------------------------
        # Fuentes escaladas: content_scale (cs) ajusta el tamaño al canvas 4x3
        # ------------------------------------------------------------------
        try:
            font_titulo    = ImageFont.truetype("segoeui.ttf", max(1, int(16 * cs * escala)))
            font_grande    = ImageFont.truetype("seguisb.ttf", max(1, int(22 * cs * escala)))  # PARA: nombre (negrita)
            font_addr      = ImageFont.truetype("segoeui.ttf", max(1, int(17 * cs * escala)))  # dirección normal
            font_addr_bold = ImageFont.truetype("seguisb.ttf", max(1, int(17 * cs * escala)))  # CP en negritas
            font_condicion = ImageFont.truetype("seguisb.ttf", max(1, int(16 * cs * escala)))  # estado de pago más grande
            font_normal    = ImageFont.truetype("segoeui.ttf", max(1, int(14 * cs * escala)))
            font_total_bold = ImageFont.truetype("seguisb.ttf", max(1, int(16 * cs * escala)))
            font_total_amount = ImageFont.truetype("segoeui.ttf", max(1, int(16 * cs * escala)))
            font_medium    = ImageFont.truetype("segoeui.ttf", max(1, int(17 * cs * escala)))  # cel y envio: mismo tamaño que dirección
            font_small     = ImageFont.truetype("segoeui.ttf", max(1, int(10 * cs * escala)))
        except:
            font_titulo    = ImageFont.load_default()
            font_grande    = ImageFont.load_default()
            font_addr      = ImageFont.load_default()
            font_addr_bold = ImageFont.load_default()
            font_condicion = ImageFont.load_default()
            font_normal    = ImageFont.load_default()
            font_total_bold = ImageFont.load_default()
            font_total_amount = ImageFont.load_default()
            font_medium    = ImageFont.load_default()
            font_small     = ImageFont.load_default()

        # Helper: divide texto en líneas que quepan dentro de max_width
        def wrap_text(text, font, max_width):
            words = text.split()
            lines, current = [], ""
            for word in words:
                test = f"{current} {word}".strip()
                w = draw.textbbox((0, 0), test, font=font)[2]
                if w <= max_width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            return lines or [text]

        # Márgenes reducidos proporcionalmente
        margin_left  = int(12 * cs * escala)
        margin_right = int(12 * cs * escala)
        margin_top   = int(10 * cs * escala)
        y_pos = margin_top

        # ========== ENCABEZADO: LOGO ==========
        try:
            logo_path = obtener_ruta_recurso(os.path.join(HEADERS_DIR, 'header_etiqueta.png'))
            if os.path.exists(logo_path):
                logo = Image.open(logo_path)
                # Logo limitado al 30% del alto total del canvas (duplicado respecto al 15% anterior)
                max_logo_h = int(height * 0.23)
                logo_h = max_logo_h
                aspect = logo.width / logo.height
                logo_w = int(logo_h * aspect)
                # Evitar que el logo supere el ancho útil
                usable_width = width - margin_left - margin_right
                if logo_w > usable_width:
                    logo_w = usable_width
                    logo_h = int(logo_w / aspect)
                logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
                img.paste(logo, (margin_left, y_pos))
                y_pos += logo_h + int(5 * cs * escala)
        except:
            pass

        # Línea separadora roja (más gruesa para mayor estructura visual)
        draw.line(
            [(margin_left, y_pos), (width - margin_right, y_pos)],
            fill=self.COLORS['primary'],
            width=max(1, int(2 * escala))
        )
        y_pos += int(14 * cs * escala)

        # ========== DATOS DEL DESTINATARIO ==========
        nombre_cliente = self.entry_nombre.text() or '[NOMBRE DEL CLIENTE]'
        usable_w  = width - margin_left - margin_right
        line_h    = int(17 * cs * escala)   # interlineado para font_addr (compacto)
        field_gap = int(3  * cs * escala)   # espacio extra entre campos (reducido para compensar fuentes más grandes)
        # Wrap del nombre por si es muy largo
        for line in wrap_text(f"PARA: {nombre_cliente}", font_grande, usable_w):
            draw.text((margin_left, y_pos), line, fill=self.COLORS['primary'], font=font_grande)
            y_pos += int(22 * cs * escala)
        y_pos += int(3 * cs * escala)

        calle = self.entry_calle.text() or '[CALLE Y NÚMERO]'
        for line in wrap_text(calle, font_addr, usable_w):
            draw.text((margin_left, y_pos), line, fill='black', font=font_addr)
            y_pos += line_h
        y_pos += field_gap

        colonia = self.combo_colonia.currentText() or '[COLONIA]'
        cp      = self.entry_cp.text() or '[CP]'
        # Dibujar colonia en normal y C.P. + valor en negrita
        prefijo_colonia = f"Col. {colonia}, "
        sufijo_cp       = f"C.P. {cp}"
        prefijo_w = draw.textbbox((0, 0), prefijo_colonia, font=font_addr)[2]
        colonia_lineas = wrap_text(prefijo_colonia + sufijo_cp, font_addr, usable_w)
        for i, line in enumerate(colonia_lineas):
            if i == 0:
                # Primera línea: prefijo normal + CP en negrita
                draw.text((margin_left, y_pos), prefijo_colonia, fill='black', font=font_addr)
                draw.text((margin_left + prefijo_w, y_pos), sufijo_cp, fill='black', font=font_addr_bold)
            else:
                draw.text((margin_left, y_pos), line, fill='black', font=font_addr)
            y_pos += line_h
        y_pos += field_gap

        ciudad = self.entry_ciudad.text() or '[CIUDAD]'
        estado = self.entry_estado.text() or '[ESTADO]'
        for line in wrap_text(f"{ciudad}, {estado}", font_addr, usable_w):
            draw.text((margin_left, y_pos), line, fill='black', font=font_addr)
            y_pos += line_h
        y_pos += field_gap

        celular = self.entry_celular.text() or '[CELULAR]'
        draw.text(
            (margin_left, y_pos),
            f"Cel: {celular}",
            fill='black',
            font=font_medium
        )
        y_pos += int(27 * cs * escala)  # mayor espacio bajo el cel antes de la línea divisora

        # Línea separadora secundaria
        draw.line(
            [(margin_left, y_pos), (width - margin_right, y_pos)],
            fill=self.COLORS['gray1'],
            width=1
        )
        y_pos += int(10 * cs * escala)  # espacio simétrico tras la línea antes de "Envío por"

        # ========== INFORMACIÓN DE ENVÍO ==========
        opcion_envio = self.opcion_envio or '[OPCIÓN DE ENVÍO]'
        draw.text(
            (margin_left, y_pos),
            f"Envío por: {opcion_envio}",
            fill='black',
            font=font_medium
        )
        y_pos += int(26 * cs * escala)  # espacio suficiente para liberar el texto antes del recuadro

        # Recuadro de condición de pago
        condicion  = self.condicion
        box_height = int(28 * cs * escala)
        box_y      = y_pos  # sin offset negativo: evita superposición con la línea anterior
        box_color  = self.COLORS['success'] if condicion == "Pagado" else self.COLORS['secondary']

        box_right = width - margin_right - int(5 * escala)
        box_width = box_right - margin_left

        draw.rectangle(
            [(margin_left, box_y), (box_right, box_y + box_height)],
            fill=None,
            outline=box_color,
        )
        condicion_text = f"  ⬤  {condicion.upper()}"  # padding izquierdo con espacios
        # Centrar texto verticalmente dentro del recuadro usando font_condicion (más grande)
        bbox = draw.textbbox((0, 0), condicion_text, font=font_condicion)
        text_h = bbox[3] - bbox[1]
        text_y = box_y + (box_height - text_h) // 2 - bbox[1]  # corregir offset interno
        draw.text(
            (margin_left + int(8 * escala), text_y),
            condicion_text,
            fill='black',
            font=font_condicion
        )

        # Monto total del pedido: TOTAL en negritas y todo el bloque
        # ligeramente más grande para facilitar su lectura al repartidor.
        total_label = "TOTAL:"
        total_amount = self.obtener_cantidad_formateada()
        total_gap = int(5 * escala)

        total_label_w = draw.textlength(
            total_label,
            font=font_total_bold,
        )
        total_amount_w = draw.textlength(
            total_amount,
            font=font_total_amount,
        )
        total_block_w = total_label_w + total_gap + total_amount_w

        # Centrar el bloque completo dentro de la mitad derecha del
        # rectángulo. Así permanece centrado aunque el monto tenga más cifras.
        total_area_left = margin_left + (box_width * 0.52)
        total_area_right = width - margin_right - int(8 * escala)
        total_area_width = total_area_right - total_area_left
        total_x = total_area_left + (
            (total_area_width - total_block_w) / 2
        )

        # Usar el centro exacto del rectángulo como ancla vertical.
        total_center_y = box_y + (box_height / 2)

        draw.text(
            (total_x, total_center_y),
            total_label,
            fill='black',
            font=font_total_bold,
            anchor="lm",
        )
        draw.text(
            (
                total_x + total_label_w + total_gap,
                total_center_y,
            ),
            total_amount,
            fill='black',
            font=font_total_amount,
            anchor="lm",
        )

        y_pos += box_height + int(8 * cs * escala)  # gap compacto tras el recuadro

        # ========== FOOTER: DIRECCIÓN REMITENTE ==========
        draw.text(
            (margin_left, y_pos),
            self.EMPRESA_DIRECCION,
            fill='#555555',  # gris medio: legible bajo luz solar/artificial
            font=font_small
        )

        return img
    
    def aplicar_esquinas_redondeadas(self, img, radio):
        """
        Aplica esquinas redondeadas a una imagen PIL.
        
        Crea una máscara alpha con bordes redondeados y la aplica a la imagen.
        Usado para dar un aspecto más profesional a la vista previa.
        
        :param img: Imagen original a la que aplicar esquinas redondeadas.
        :type img: PIL.Image.Image
        :param radio: Radio de curvatura de las esquinas en píxeles.
        :type radio: int
        :return: Imagen con esquinas redondeadas y canal alpha.
        :rtype: PIL.Image.Image
        """
        # Crear una máscara con esquinas redondeadas
        mask = Image.new('L', img.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Dibujar un rectángulo redondeado blanco en la máscara
        draw.rounded_rectangle([(0, 0), img.size], radius=radio, fill=255)
        
        # Aplicar la máscara a la imagen
        output = Image.new('RGBA', img.size, (0, 0, 0, 0))
        output.paste(img, (0, 0))
        output.putalpha(mask)
        
        return output
    
    def aplicar_borde_preview(self, img, color_borde, grosor=2, radio=16):
        """
        Agrega un borde sutil únicamente a la imagen de la vista previa.

        No modifica la lógica de impresión ni de PDF; solo mejora la
        presentación visual de la etiqueta dentro del preview.
        """
        try:
            base = img.convert("RGBA")
            ancho, alto = base.size

            canvas = Image.new(
                "RGBA",
                (ancho + grosor * 2, alto + grosor * 2),
                (0, 0, 0, 0),
            )

            draw = ImageDraw.Draw(canvas)
            draw.rounded_rectangle(
                [(0, 0), (canvas.size[0] - 1, canvas.size[1] - 1)],
                radius=radio + grosor,
                outline=color_borde,
                width=grosor,
                fill=None,
            )

            canvas.paste(base, (grosor, grosor), base)
            return canvas
        except Exception:
            return img

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
    def eventFilter(self, objeto, evento):
        """
        Reescala la etiqueta cuando cambia el tamaño del panel de vista previa.
        """
        if (
            hasattr(self, "preview_container")
            and objeto is self.preview_container
            and evento.type() == evento.Type.Resize
        ):
            QTimer.singleShot(0, self.ajustar_vista_previa)

        return super().eventFilter(objeto, evento)

    def ajustar_vista_previa(self):
        """
        Ajusta la etiqueta al mayor tamaño posible sin recortarla.

        Respeta la proporción original y deja únicamente el margen interno
        configurado en el contenedor de vista previa.
        """
        if not hasattr(self, "preview_pixmap_original"):
            return
        if self.preview_pixmap_original.isNull():
            return
        if not hasattr(self, "preview_container"):
            return

        rect = self.preview_container.contentsRect()
        margenes = self.preview_layout.contentsMargins()

        ancho_disponible = max(
            1,
            rect.width() - margenes.left() - margenes.right(),
        )
        alto_disponible = max(
            1,
            rect.height() - margenes.top() - margenes.bottom(),
        )

        pixmap_ajustado = self.preview_pixmap_original.scaled(
            ancho_disponible,
            alto_disponible,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(pixmap_ajustado)

    def actualizar_vista_previa(self):
        """
        Regenera y muestra la etiqueta en tiempo real.

        La imagen se genera con suficiente resolución y después se adapta
        automáticamente al panel derecho, sin recortarse ni requerir scroll.
        """
        try:
            # Resolución amplia para que el preview conserve nitidez incluso
            # al ocupar casi todo el panel derecho.
            scale = 2.6
            img = self.generar_imagen_etiqueta(
                escala=scale,
                pdf_mode=True,
            )

            img_redondeada = self.aplicar_esquinas_redondeadas(
                img,
                radio=max(15, int(15 * scale / 1.17)),
            )

            color_borde_preview = (
                "#555555" if self.tema_oscuro else "#000000"
            )
            img_preview = self.aplicar_borde_preview(
                img_redondeada,
                color_borde_preview,
                grosor=3,
                radio=max(15, int(15 * scale / 1.17)),
            )

            img_byte_arr = io.BytesIO()
            img_preview.save(img_byte_arr, format="PNG")
            img_byte_arr.seek(0)

            qimage = QImage.fromData(img_byte_arr.read())
            self.preview_pixmap_original = QPixmap.fromImage(qimage)

            # Esperar a que Qt termine de calcular el espacio disponible.
            QTimer.singleShot(0, self.ajustar_vista_previa)

        except Exception as e:
            print(f"Error al actualizar vista previa: {e}")
    def validar_datos(self):
        """
        Valida que todos los campos requeridos estén completos.
        
        Verifica que el usuario haya llenado:
        - Nombre del cliente
        - Calle y número
        - Código postal
        - Colonia
        - Estado
        - Ciudad
        - Número de celular
        
        :return: True si todos los campos están completos, False si falta alguno.
        :rtype: bool
        """
        if not self.entry_nombre.text().strip():
            KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese el nombre del cliente")
            return False
        if not self.entry_calle.text().strip():
            KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese la calle y número")
            return False
        if not self.entry_cp.text().strip():
            KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese el código postal")
            return False
        if not self.combo_colonia.currentText().strip():
            KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese la colonia")
            return False
        if not self.entry_estado.text().strip():
            KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese el estado")
            return False
        if not self.entry_ciudad.text().strip():
            KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese la ciudad")
            return False
        if not self.entry_celular.text().strip():
            KBKADialog.warning(self, "Datos Incompletos", "Por favor ingrese el número de celular")
            return False
        if not self.entry_cantidad.text().strip():
            KBKADialog.warning(
                self,
                "Datos Incompletos",
                "Por favor ingrese el monto total del pedido",
            )
            self.entry_cantidad.setFocus()
            return False

        try:
            cantidad = float(
                self.entry_cantidad.text().replace(",", "")
            )
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            KBKADialog.warning(
                self,
                "Monto inválido",
                "El monto total debe ser mayor que cero.",
            )
            self.entry_cantidad.setFocus()
            self.entry_cantidad.selectAll()
            return False

        # Opción de envío y Condición tienen valores por defecto.
        return True
    
    def guardar_pdf(self):
        """
        Guarda la etiqueta como archivo PDF.
        
        Genera una etiqueta de alta resolución (escala 4x = 384 DPI),
        la convierte a PDF usando ReportLab y la guarda en la ubicación
        seleccionada por el usuario.
        
        También guarda/actualiza los datos del cliente en la base de datos.
        """
        if not self.validar_datos():
            return
        
        try:
            # Solicitar ubicación de guardado
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre_archivo = f"Etiqueta_{self.entry_nombre.text().replace(' ', '_')}_{fecha}.pdf"
            
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Etiqueta",
                nombre_archivo,
                "PDF files (*.pdf)"
            )
            
            if not filepath:
                return
            
            # Generar imagen de alta calidad (4x3 pulgadas)
            img = self.generar_imagen_etiqueta(escala=4, pdf_mode=True)
            
            # Crear PDF con ReportLab (4x3 pulgadas horizontal)
            c = canvas.Canvas(filepath, pagesize=(4*inch, 3*inch))
            
            # Convertir imagen PIL a formato que ReportLab pueda usar
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            img_reader = ImageReader(img_buffer)
            
            # Dibujar imagen en PDF
            c.drawImage(img_reader, 0, 0, width=4*inch, height=3*inch)
            c.save()
            
            # Guardar datos del cliente en la base de datos (UPSERT)
            self.guardar_cliente()
            
            KBKADialog.success(
                self,
                "Guardado Exitoso",
                f"La etiqueta se ha guardado correctamente en:\n{filepath}"
            )
            
        except Exception as e:
            KBKADialog.error(self, "Error", f"Error al guardar el PDF:\n{str(e)}")
    
    def imprimir_etiqueta(self):
        """
        Imprime la etiqueta directamente en una impresora térmica.
        
        Utiliza win32print para imprimir en la impresora configurada.
        Maneja automáticamente la orientación (horizontal) y rota la imagen
        si la impresora está en modo vertical.
        
        Dimensiones objetivo: 150x100mm (6x4 pulgadas) horizontal.
        
        Requiere:
        - pywin32 instalado
        - Impresora configurada en el diálogo de configuración
        """
        # Validar datos
        if not self.validar_datos():
            return
        
        # Verificar disponibilidad de win32print
        if not WIN32_AVAILABLE:
            KBKADialog.warning(
                self,
                "Impresión No Disponible",
                "La impresión directa requiere win32print.\n\n"
                "Por favor, instale: pip install pywin32\n\n"
                "Alternativamente, use 'GUARDAR PDF' y luego imprima el archivo."
            )
            return
        
        # Obtener impresora seleccionada desde la base de datos
        nombre_impresora = self.cargar_impresora_config()
        
        if not nombre_impresora:
            KBKADialog.warning(
                self,
                "Impresora No Configurada",
                "Por favor, configure una impresora predeterminada.\n\n"
                "Use el botón '⚙️ CONFIGURAR IMPRESORA' en el panel lateral."
            )
            return
        
        try:
            # Generar imagen de alta calidad (escala 4 para mejor resolución)
            # La imagen se genera en formato 4x3 pulgadas (384x288 píxeles * 4 = 1536x1152)
            img = self.generar_imagen_etiqueta(escala=4, pdf_mode=True)
            
            # Convertir a RGB si es necesario
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Crear contexto de dispositivo de impresora
            hdc = win32ui.CreateDC()
            hdc.CreatePrinterDC(nombre_impresora)
            
            try:
                # Obtener información de la impresora
                dpi_x = hdc.GetDeviceCaps(88)  # LOGPIXELSX
                dpi_y = hdc.GetDeviceCaps(90)  # LOGPIXELSY
                printer_width = hdc.GetDeviceCaps(110)  # PHYSICALWIDTH (ancho total del papel)
                printer_height = hdc.GetDeviceCaps(111)  # PHYSICALHEIGHT (alto total del papel)
                
                # Dimensiones de la etiqueta: 4x3 pulgadas
                # En orientación horizontal: 101.6mm ancho x 76.2mm alto
                target_width_mm = 101.6  # Ancho en mm (4 pulgadas)
                target_height_mm = 76.2  # Alto en mm (3 pulgadas)
                
                # Convertir mm a pulgadas (1 pulgada = 25.4 mm)
                target_width_inch = target_width_mm / 25.4
                target_height_inch = target_height_mm / 25.4
                
                # Convertir pulgadas a píxeles de la impresora
                target_width_px = int(target_width_inch * dpi_x)
                target_height_px = int(target_height_inch * dpi_y)
                
                # Detectar si la impresora está en modo vertical (portrait)
                # Si el ancho del papel es menor que el alto, está en vertical
                is_portrait = printer_width < printer_height
                
                # Si la impresora está configurada en vertical pero queremos horizontal,
                # necesitamos rotar la imagen 90 grados
                img_to_print = img
                if is_portrait:
                    # Rotar 90 grados en sentido antihorario para que quede horizontal
                    img_to_print = img.rotate(90, expand=True)
                    # Intercambiar dimensiones objetivo
                    target_width_px, target_height_px = target_height_px, target_width_px
                
                # Giro final de 180° para que la impresión salga invertida
                # respecto a la orientación visual normal de la etiqueta.
                img_to_print = img_to_print.rotate(180, expand=True)

                # Crear DIB (Device Independent Bitmap) para la imagen
                dib = ImageWin.Dib(img_to_print)
                
                # Calcular posición centrada (opcional)
                # Para impresoras térmicas de etiquetas, generalmente se imprime desde (0,0)
                x_offset = 0
                y_offset = 0
                
                # Si hay espacio extra, centrar la imagen
                if printer_width > target_width_px:
                    x_offset = (printer_width - target_width_px) // 2
                if printer_height > target_height_px:
                    y_offset = (printer_height - target_height_px) // 2
                
                # Iniciar trabajo de impresión
                hdc.StartDoc("Etiqueta KBKA")
                hdc.StartPage()
                
                # Dibujar la imagen en el contexto de la impresora
                # dib.draw() toma: (handle, (dest_x, dest_y, dest_x2, dest_y2))
                # La imagen se estirará para ajustarse al rectángulo especificado
                dib.draw(
                    hdc.GetHandleOutput(), 
                    (x_offset, y_offset, x_offset + target_width_px, y_offset + target_height_px)
                )
                
                # Finalizar página y documento
                hdc.EndPage()
                hdc.EndDoc()
                
            finally:
                # Limpiar recursos
                hdc.DeleteDC()
            
            # Guardar datos del cliente en la base de datos (UPSERT)
            self.guardar_cliente()
            
            KBKADialog.success(
                self,
                "Impresión Enviada",
                f"La etiqueta se ha enviado correctamente a:\n{nombre_impresora}\n\n"
                f"Formato: 101.6x76.2mm (4x3 pulgadas) - Orientación horizontal\n"
                "La impresión se está procesando..."
            )
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            KBKADialog.error(
                self, 
                "Error al Imprimir", 
                f"No se pudo imprimir en '{nombre_impresora}'.\n\n"
                f"Error: {str(e)}\n\n"
                "Verifique que la impresora esté encendida, conectada\n"
                "y configurada correctamente."
            )


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
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Centro de Ayuda y Solución de Problemas")
        self.setMinimumSize(650, 500)
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
        
        # Lista para guardar referencias a los frames de problemas
        self.problema_frames = []
        
        # ==================== HEADER PREMIUM ====================
        header_frame = QFrame()
        self.header_frame = header_frame
        header_frame.setFixedHeight(65)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: none;
                border-bottom: 1px solid #EEEEEE;
            }
        """)
        
        # Aplicar efecto de sombra sutil
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(10)
        shadow_effect.setXOffset(0)
        shadow_effect.setYOffset(2)
        shadow_effect.setColor(QColor(0, 0, 0, int(255 * 0.15)))  # Negro con 15% de opacidad
        header_frame.setGraphicsEffect(shadow_effect)
        
        # Layout horizontal del header
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(12)
        
        # Espaciador izquierdo para centrar el contenido
        header_layout.addStretch()
        
        # Icono de ayuda
        icon_label = QLabel()
        # Fondo transparente para evitar que el efecto colorize tiña el fondo
        icon_label.setStyleSheet("background: transparent; border: none;")
        try:
            ayuda_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'ayuda_negra.png'))
            if os.path.exists(ayuda_icon_path):
                icon_pixmap = QPixmap(ayuda_icon_path)
                icon_pixmap = icon_pixmap.scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, 
                                                 Qt.TransformationMode.SmoothTransformation)
                icon_label.setPixmap(icon_pixmap)
            else:
                icon_label.setText("❓")
                icon_label.setStyleSheet("font-size: 24pt; background: transparent; border: none;")
        except:
            icon_label.setText("❓")
            icon_label.setStyleSheet("font-size: 24pt; background: transparent; border: none;")
        
        # Guardar referencia para aplicar el efecto de colorización más tarde
        self.icon_label = icon_label
        header_layout.addWidget(icon_label)
        
        # Título del header
        titulo_header = QLabel("Centro de Ayuda y Soporte")
        self.titulo_header = titulo_header
        titulo_header.setStyleSheet("""
            color: #2D2D2D;
            font-size: 14pt;
            font-weight: bold;
            font-family: 'Segoe UI', 'Inter', sans-serif;
        """)
        header_layout.addWidget(titulo_header)
        
        # Espaciador derecho para centrar el contenido
        header_layout.addStretch()
        
        # Agregar header al layout principal
        main_layout.addWidget(header_frame)
        
        # Área de scroll para el contenido con fondo gris claro
        scroll = QScrollArea()
        self.scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #F8F9FA;
                border: none;
            }
        """)
        
        # Widget contenedor del contenido
        content_widget = QWidget()
        self.content_widget = content_widget
        content_widget.setStyleSheet("background-color: #F8F9FA;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 30, 40, 30)
        content_layout.setSpacing(15)
        
        # === PROBLEMA 1 ===
        problema1_data = self.crear_problema_frame(
            "🖨️ La etiqueta sale en blanco o vertical",
            "Verifica que en la <b>Configuración de Impresora</b> (botón ⚙️ en el panel lateral) "
            "esté seleccionada la impresora térmica correcta.<br><br>"
            "Además, asegúrate de que en la <b>Configuración de Windows</b> → <b>Impresoras y Escáneres</b> → "
            "<b>Preferencias de Impresión</b>, el tamaño del papel esté configurado como <b>100x150mm</b> "
            "o <b>4x6 pulgadas</b> en orientación horizontal.<br><br>"
            "Si persiste el problema, reinicia la impresora y vuelve a intentar."
        )
        self.problema_frames.append(problema1_data)
        content_layout.addWidget(problema1_data['frame'])
        
        # === PROBLEMA 2 ===
        problema2_data = self.crear_problema_frame(
            "👤 No se autocompletan los datos del cliente",
            "Los datos del cliente se guardan automáticamente en la base de datos "
            "cuando presionas <b>'IMPRIMIR'</b> o <b>'GUARDAR PDF'</b>.<br><br>"
            "Si es un cliente nuevo, asegúrate de haberlo guardado al menos una vez. "
            "La próxima vez que escribas su nombre, aparecerá como sugerencia en el autocompletado.<br><br>"
            "También puedes gestionar clientes existentes usando el botón <b>'👥 GESTIONAR CLIENTES'</b>."
        )
        self.problema_frames.append(problema2_data)
        content_layout.addWidget(problema2_data['frame'])
        
        # === PROBLEMA 3 ===
        problema3_data = self.crear_problema_frame(
            "📮 El código postal no carga las colonias",
            "<b>Causa principal:</b> El archivo de base de datos SEPOMEX no se encuentra o fue movido.<br><br>"
            "Verifica que en la carpeta <b>assets/</b> exista el archivo <b>sepomex_consolidado.csv</b>.<br><br>"
            "Si el archivo está presente y el problema persiste:<br>"
            "• Verifica que el archivo no esté corrupto (debe ser un CSV válido)<br>"
            "• Asegúrate de tener permisos de lectura en la carpeta<br>"
            "• El código postal no está registrado en la base de datos<br>"
            "• Reinicia la aplicación<br><br>"
            "Si continúa fallando, ponte en contacto con Chava."
        )
        self.problema_frames.append(problema3_data)
        content_layout.addWidget(problema3_data['frame'])
        
        # === PROBLEMA 4 ===
        problema4_data = self.crear_problema_frame(
            "🔴 Error al imprimir: 'Impresora No Configurada'",
            "Este mensaje aparece cuando no has seleccionado una impresora predeterminada.<br><br>"
            "<b>Solución:</b><br>"
            "1. Haz clic en el botón <b>'⚙️ CONFIGURAR IMPRESORA'</b> en el panel lateral<br>"
            "2. Selecciona tu impresora térmica de la lista desplegable<br>"
            "3. Cierra el diálogo (la selección se guarda automáticamente)<br>"
            "4. Intenta imprimir nuevamente<br><br>"
            "Si no aparecen impresoras en la lista, verifica que:<br>"
            "• La impresora esté conectada y encendida<br>"
            "• Los drivers estén instalados correctamente en Windows<br>"
        )
        self.problema_frames.append(problema4_data)
        content_layout.addWidget(problema4_data['frame'])
        
        content_layout.addSpacing(20)
        
        # Banner de soporte premium con fondo rojo
        soporte_banner = QFrame()
        soporte_banner.setStyleSheet(f"""
            QFrame {{
                background-color: {self.parent_window.COLORS['primary']};
                border-radius: 15px;
                padding: 25px;
            }}
        """)
        soporte_layout = QVBoxLayout(soporte_banner)
        soporte_layout.setSpacing(15)
        
        # Título del banner
        soporte_titulo = QLabel("¿No pudiste resolverlo?")
        soporte_titulo.setStyleSheet("""
            color: white;
            font-size: 16pt;
            font-weight: bold;
            font-family: 'Segoe UI', sans-serif;
        """)
        soporte_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        soporte_layout.addWidget(soporte_titulo)
        
        # Mensaje cordial
        mensaje = QLabel("Contacta a Chava para apoyarte con el problema")
        mensaje.setStyleSheet("""
            color: rgba(255, 255, 255, 0.95);
            font-size: 12pt;
            font-family: 'Segoe UI', sans-serif;
        """)
        mensaje.setAlignment(Qt.AlignmentFlag.AlignCenter)
        soporte_layout.addWidget(mensaje)
        
        soporte_layout.addSpacing(10)
        
        # Contenedor del email con botón de copiar
        email_container = QHBoxLayout()
        email_container.addStretch()
        
        email_label = QLabel("📧 chavitachava2007@gmail.com")
        email_label.setStyleSheet("""
            color: white;
            font-size: 12pt;
            font-family: 'Segoe UI', monospace;
            background-color: rgba(0, 0, 0, 0.2);
            padding: 10px 15px;
            border-radius: 8px;
        """)
        email_container.addWidget(email_label)
        
        # Botón copiar correo
        btn_copiar = QPushButton("Copiar")
        btn_copiar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copiar.setFixedSize(80, 35)
        btn_copiar.clicked.connect(lambda: self.copiar_email())
        btn_copiar.setStyleSheet("""
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
        """)
        email_container.addWidget(btn_copiar)
        
        email_container.addStretch()
        soporte_layout.addLayout(email_container)
        
        # Instrucciones
        instrucciones = QLabel(
            "Incluye:<br>"
            "• Descripción detallada del problema<br>"
            "• Capturas de pantalla si es posible<br>"
            "• Mensajes de error completos"
        )
        instrucciones.setWordWrap(True)
        instrucciones.setStyleSheet("""
            color: rgba(255, 255, 255, 0.85);
            font-size: 10pt;
            font-family: 'Segoe UI', sans-serif;
            line-height: 1.6;
        """)
        instrucciones.setAlignment(Qt.AlignmentFlag.AlignCenter)
        soporte_layout.addWidget(instrucciones)
        
        content_layout.addWidget(soporte_banner)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # Botón cerrar con diseño moderno
        btn_cerrar = QPushButton("✕ Cerrar")
        self.btn_cerrar = btn_cerrar
        btn_cerrar.setMinimumHeight(50)
        btn_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cerrar.clicked.connect(self.accept)
        btn_cerrar.setStyleSheet("""
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
        """)
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
        """
        Crea una card premium para cada problema con su solución.
        
        :param titulo: Título del problema.
        :type titulo: str
        :param solucion: Descripción de la solución (puede incluir HTML).
        :type solucion: str
        :return: Diccionario con referencias a los widgets de la card.
        :rtype: dict
        """
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E8E8E8;
                border-radius: 10px;
                padding: 20px;
            }
            QFrame:hover {
                border: 1px solid #CD0403;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)
        
        # Título del problema con estilo premium
        titulo_label = QLabel(titulo)
        titulo_label.setStyleSheet(f"""
            font-size: 13pt;
            font-weight: bold;
            color: {self.parent_window.COLORS['primary']};
            font-family: 'Segoe UI', sans-serif;
            padding-bottom: 3px;
        """)
        layout.addWidget(titulo_label)
        
        # Separador sutil
        separador = QFrame()
        separador.setFixedHeight(2)
        separador.setStyleSheet("background-color: #F0F0F0; border: none;")
        layout.addWidget(separador)
        
        # Solución con texto elegante
        solucion_label = QLabel(solucion)
        solucion_label.setWordWrap(True)
        solucion_label.setTextFormat(Qt.TextFormat.RichText)
        solucion_label.setStyleSheet("""
            font-size: 10pt;
            color: #4A4A4A;
            line-height: 1.7;
            font-family: 'Segoe UI', sans-serif;
        """)
        layout.addWidget(solucion_label)
        
        # Devolver diccionario con referencias
        return {
            'frame': frame,
            'titulo': titulo_label,
            'solucion': solucion_label,
            'separador': separador
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
        # Determinar colores según el tema
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            # Modo Oscuro
            bg_main = "#121212"
            bg_header = "#1E1E1E"
            bg_content = "#1E1E1E"
            bg_card = "#2A2A2A"
            bg_card_hover = "#333333"
            text_primary = "#E0E0E0"
            text_secondary = "#B0B0B0"
            text_title = "#CD0403"  # Rojo KBKA
            border_color = "#3A3A3A"
            border_hover = "#CD0403"
            separador_color = "#3A3A3A"
            btn_cerrar_bg = "#2A2A2A"
            btn_cerrar_hover = "#333333"
            btn_cerrar_text = "#E0E0E0"
        else:
            # Modo Claro
            bg_main = "#FFFFFF"
            bg_header = "#FFFFFF"
            bg_content = "#F8F9FA"
            bg_card = "#FFFFFF"
            bg_card_hover = "#FFFFFF"
            text_primary = "#2D2D2D"
            text_secondary = "#4A4A4A"
            text_title = "#CD0403"  # Rojo KBKA
            border_color = "#E8E8E8"
            border_hover = "#CD0403"
            separador_color = "#F0F0F0"
            btn_cerrar_bg = "#F8F9FA"
            btn_cerrar_hover = "#E8E8E8"
            btn_cerrar_text = "#4A4A4A"
        
        # Actualizar header
        if hasattr(self, 'header_frame'):
            self.header_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_header};
                    border: none;
                    border-bottom: 1px solid {border_color};
                }}
            """)
        
        if hasattr(self, 'titulo_header'):
            self.titulo_header.setStyleSheet(f"""
                color: {text_primary};
                font-size: 14pt;
                font-weight: bold;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            """)
        
        # Actualizar área de scroll
        if hasattr(self, 'scroll'):
            self.scroll.setStyleSheet(f"""
                QScrollArea {{
                    background-color: {bg_content};
                    border: none;
                }}
            """)
        
        if hasattr(self, 'content_widget'):
            self.content_widget.setStyleSheet(f"background-color: {bg_content};")
        
        # Actualizar cards de problemas
        if hasattr(self, 'problema_frames'):
            for frame_data in self.problema_frames:
                frame = frame_data['frame']
                titulo_label = frame_data['titulo']
                solucion_label = frame_data['solucion']
                separador = frame_data['separador']
                
                frame.setStyleSheet(f"""
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
                """)
                
                titulo_label.setStyleSheet(f"""
                    font-size: 13pt;
                    font-weight: bold;
                    color: {text_title};
                    font-family: 'Segoe UI', sans-serif;
                    padding-bottom: 3px;
                """)
                
                solucion_label.setStyleSheet(f"""
                    font-size: 10pt;
                    color: {text_secondary};
                    line-height: 1.7;
                    font-family: 'Segoe UI', sans-serif;
                """)
                
                separador.setStyleSheet(f"background-color: {separador_color}; border: none;")
        
        # Actualizar botón cerrar
        if hasattr(self, 'btn_cerrar'):
            self.btn_cerrar.setStyleSheet(f"""
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
            """)
        
        # Aplicar efecto de colorización al icono en modo oscuro
        if hasattr(self, 'icon_label'):
            if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
                # Modo oscuro: aplicar efecto para convertir el icono negro a blanco
                efecto = QGraphicsColorizeEffect()
                efecto.setColor(QColor(255, 255, 255))  # Blanco
                efecto.setStrength(1.0)  # Fuerza máxima
                self.icon_label.setGraphicsEffect(efecto)
            else:
                # Modo claro: quitar el efecto (el icono negro es visible)
                self.icon_label.setGraphicsEffect(None)


class ConfiguracionImpresoraDialog(QDialog):
    """
    Diálogo para configurar la impresora predeterminada.
    
    Permite al usuario:
    - Ver lista de impresoras disponibles en el sistema
    - Seleccionar impresora predeterminada
    - Guardar la configuración automáticamente
    
    Usa win32print para enumerar impresoras (requiere pywin32).
    
    :param parent: Ventana principal de la aplicación.
    :type parent: EtiquetasApp
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Configuración de Impresión")
        self.setMinimumSize(450, 200)
        self.setMaximumSize(500, 250)
        self.setModal(True)
        
        self.init_ui()
    
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
        Inicializa la interfaz del diálogo de configuración de impresora.
        
        Crea:
        - Título centrado
        - ComboBox con lista de impresoras del sistema (win32print)
        - Label informativo adaptable al tema
        - Botón de cerrar
        
        La selección se guarda automáticamente en la base de datos.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Título
        titulo = QLabel("⚙️ CONFIGURACIÓN DE IMPRESIÓN")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setStyleSheet(f"""
            color: {self.parent_window.COLORS['primary']};
            font-size: 14pt;
            font-weight: bold;
            padding: 5px 0px;
        """)
        layout.addWidget(titulo)
        
        layout.addSpacing(10)
        
        # Label explicativo
        label_impresora = QLabel("Selecciona la impresora predeterminada:")
        label_impresora.setStyleSheet("font-size: 11pt; font-weight: bold;")
        layout.addWidget(label_impresora)
        
        # ComboBox de impresoras
        self.combo_impresoras = QComboBox()
        self.combo_impresoras.setPlaceholderText("Seleccione una impresora...")
        self.combo_impresoras.setMinimumHeight(40)
        
        # Cargar impresoras disponibles
        impresoras = self.parent_window.obtener_impresoras()
        if impresoras:
            self.combo_impresoras.addItems(impresoras)
            # Cargar impresora guardada
            impresora_guardada = self.parent_window.cargar_impresora_config()
            if impresora_guardada and impresora_guardada in impresoras:
                index = self.combo_impresoras.findText(impresora_guardada)
                if index >= 0:
                    self.combo_impresoras.setCurrentIndex(index)
        elif not WIN32_AVAILABLE:
            self.combo_impresoras.addItem("win32print no disponible")
            self.combo_impresoras.setEnabled(False)
        else:
            self.combo_impresoras.addItem("No hay impresoras disponibles")
            self.combo_impresoras.setEnabled(False)
        
        # Conectar señal para guardar cuando cambie la selección
        self.combo_impresoras.currentTextChanged.connect(self.on_impresora_changed)
        
        # Determinar colores según el tema del padre
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            bg_input = "#2A2A2A"
            text_color = "#E0E0E0"
            border_color = "#3A3A3A"
        else:
            bg_input = "white"
            text_color = "#212121"
            border_color = "#CCCCCC"
        
        # Aplicar estilos al combo
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
        
        # Mensaje informativo
        info_label = QLabel("💡 La impresora seleccionada se guardará automáticamente.")
        info_color = "#E0E0E0" if self.tema_oscuro else "#666666"
        info_label.setStyleSheet(f"color: {info_color}; font-size: 9pt; font-style: italic;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Botón Cerrar
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
        """
        Maneja cambios en la selección de impresora y guarda en BD.
        
        Se ejecuta automáticamente cuando el usuario selecciona
        una impresora del combo.
        
        :param nombre_impresora: Nombre de la impresora seleccionada.
        :type nombre_impresora: str
        """
        if nombre_impresora and nombre_impresora not in ["No hay impresoras disponibles", "win32print no disponible"]:
            self.parent_window.guardar_impresora_config(nombre_impresora)



class EditarClienteDialog(QDialog):
    """Ventana modal para editar y guardar los datos de un cliente."""

    def __init__(self, parent=None, datos_cliente=None):
        super().__init__(parent)
        self.parent_window = parent
        self.datos_cliente = datos_cliente or ("", "", "", "", "", "", "")
        self.nombre_original = str(self.datos_cliente[0] or "").strip()

        # Controla la carga inicial y evita repetir el mismo aviso.
        self._cargando_datos_iniciales = False
        self._ultimo_cp_invalido_alertado = None

        self.setWindowTitle("Editar cliente")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.setMaximumWidth(760)

        self._crear_interfaz()

        self._cargando_datos_iniciales = True
        try:
            self._cargar_datos()
        finally:
            self._cargando_datos_iniciales = False

        self._aplicar_estilos()

    @property
    def tema_oscuro(self):
        return bool(
            self.parent_window
            and getattr(self.parent_window, "tema_oscuro", False)
        )

    def _crear_label(self, texto):
        label = QLabel(texto)
        label.setObjectName("edit_field_label")
        return label

    def _crear_campo(self, texto, widget):
        contenedor = QWidget()
        contenedor.setObjectName("edit_transparent")
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self._crear_label(texto))
        layout.addWidget(widget)
        return contenedor

    def _crear_interfaz(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 24)
        layout.setSpacing(16)

        titulo = QLabel("✏️  EDITAR CLIENTE")
        titulo.setObjectName("edit_title")
        layout.addWidget(titulo)

        descripcion = QLabel(
            "Modifique los datos necesarios y presione Guardar cambios."
        )
        descripcion.setObjectName("edit_description")
        descripcion.setWordWrap(True)
        layout.addWidget(descripcion)

        tarjeta = QFrame()
        tarjeta.setObjectName("edit_card")
        tarjeta_layout = QVBoxLayout(tarjeta)
        tarjeta_layout.setContentsMargins(20, 18, 20, 20)
        tarjeta_layout.setSpacing(12)

        fila_nombre = QHBoxLayout()
        fila_nombre.setContentsMargins(0, 0, 0, 0)
        fila_nombre.setSpacing(12)

        self.entry_nombre_editar = QLineEdit()
        self.entry_nombre_editar.setPlaceholderText("Nombre completo")
        self.entry_nombre_editar.textChanged.connect(
            self._convertir_mayusculas
        )
        fila_nombre.addWidget(
            self._crear_campo("Nombre del cliente", self.entry_nombre_editar),
            2,
        )

        self.entry_celular_editar = QLineEdit()
        self.entry_celular_editar.setPlaceholderText("10 dígitos")
        self.entry_celular_editar.setMaxLength(10)
        self.entry_celular_editar.textChanged.connect(
            self._validar_celular
        )
        fila_nombre.addWidget(
            self._crear_campo("Número de celular", self.entry_celular_editar),
            1,
        )
        tarjeta_layout.addLayout(fila_nombre)

        self.entry_calle_editar = QLineEdit()
        self.entry_calle_editar.setPlaceholderText(
            "Calle y número exterior/interior"
        )
        self.entry_calle_editar.textChanged.connect(
            self._convertir_mayusculas
        )
        tarjeta_layout.addWidget(
            self._crear_campo("Calle y número", self.entry_calle_editar)
        )

        fila_ubicacion = QHBoxLayout()
        fila_ubicacion.setContentsMargins(0, 0, 0, 0)
        fila_ubicacion.setSpacing(12)

        self.entry_cp_editar = QLineEdit()
        self.entry_cp_editar.setPlaceholderText("5 dígitos")
        self.entry_cp_editar.setMaxLength(5)
        self.entry_cp_editar.textChanged.connect(self._buscar_por_cp)
        fila_ubicacion.addWidget(
            self._crear_campo("Código postal (CP)", self.entry_cp_editar),
            1,
        )

        self.combo_colonia_editar = QComboBox()
        self.combo_colonia_editar.setEditable(True)
        self.combo_colonia_editar.setInsertPolicy(
            QComboBox.InsertPolicy.NoInsert
        )
        self.combo_colonia_editar.setPlaceholderText("Colonia")
        fila_ubicacion.addWidget(
            self._crear_campo("Colonia", self.combo_colonia_editar),
            2,
        )
        tarjeta_layout.addLayout(fila_ubicacion)

        fila_estado = QHBoxLayout()
        fila_estado.setContentsMargins(0, 0, 0, 0)
        fila_estado.setSpacing(12)

        self.entry_estado_editar = QLineEdit()
        self.entry_estado_editar.setPlaceholderText("Estado")
        self.entry_estado_editar.textChanged.connect(
            self._convertir_mayusculas
        )
        fila_estado.addWidget(
            self._crear_campo("Estado", self.entry_estado_editar),
            1,
        )

        self.entry_ciudad_editar = QLineEdit()
        self.entry_ciudad_editar.setPlaceholderText("Ciudad / Municipio")
        self.entry_ciudad_editar.textChanged.connect(
            self._convertir_mayusculas
        )
        fila_estado.addWidget(
            self._crear_campo(
                "Ciudad / Municipio",
                self.entry_ciudad_editar,
            ),
            1,
        )
        tarjeta_layout.addLayout(fila_estado)

        layout.addWidget(tarjeta)

        botones_layout = QHBoxLayout()
        botones_layout.setContentsMargins(0, 2, 0, 0)
        botones_layout.setSpacing(10)
        botones_layout.addStretch()

        self.btn_cancelar_edicion = QPushButton("Cancelar")
        self.btn_cancelar_edicion.setObjectName("edit_cancel")
        self.btn_cancelar_edicion.setMinimumSize(125, 42)
        self.btn_cancelar_edicion.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.btn_cancelar_edicion.clicked.connect(self.reject)
        botones_layout.addWidget(self.btn_cancelar_edicion)

        self.btn_guardar_edicion = QPushButton("💾  GUARDAR CAMBIOS")
        self.btn_guardar_edicion.setObjectName("edit_save")
        self.btn_guardar_edicion.setMinimumSize(190, 42)
        self.btn_guardar_edicion.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.btn_guardar_edicion.clicked.connect(self._guardar_cambios)
        botones_layout.addWidget(self.btn_guardar_edicion)

        layout.addLayout(botones_layout)

    def _cargar_datos(self):
        nombre, celular, calle, cp, colonia, estado, municipio = (
            self.datos_cliente
        )

        self.entry_nombre_editar.setText(str(nombre or ""))
        self.entry_celular_editar.setText(str(celular or ""))
        self.entry_calle_editar.setText(str(calle or ""))
        self.entry_estado_editar.setText(str(estado or ""))
        self.entry_ciudad_editar.setText(str(municipio or ""))

        self.entry_cp_editar.blockSignals(True)
        self.entry_cp_editar.setText(str(cp or ""))
        self.entry_cp_editar.blockSignals(False)

        if cp:
            self._buscar_por_cp(str(cp))

        colonia_guardada = str(colonia or "").strip().upper()
        if colonia_guardada:
            index = self.combo_colonia_editar.findText(
                colonia_guardada,
                Qt.MatchFlag.MatchFixedString,
            )
            if index >= 0:
                self.combo_colonia_editar.setCurrentIndex(index)
            else:
                self.combo_colonia_editar.setEditText(colonia_guardada)

        if not self.entry_estado_editar.text().strip() and estado:
            self.entry_estado_editar.setText(str(estado))
        if not self.entry_ciudad_editar.text().strip() and municipio:
            self.entry_ciudad_editar.setText(str(municipio))

        self.entry_nombre_editar.setFocus()
        self.entry_nombre_editar.selectAll()

    def _convertir_mayusculas(self):
        sender = self.sender()
        if not isinstance(sender, QLineEdit):
            return

        cursor_position = sender.cursorPosition()
        texto = sender.text().upper()
        if sender.text() != texto:
            sender.blockSignals(True)
            sender.setText(texto)
            sender.setCursorPosition(cursor_position)
            sender.blockSignals(False)

    def _validar_celular(self):
        texto = self.entry_celular_editar.text()
        filtrado = "".join(filter(str.isdigit, texto))
        if texto != filtrado:
            cursor = self.entry_celular_editar.cursorPosition()
            self.entry_celular_editar.blockSignals(True)
            self.entry_celular_editar.setText(filtrado)
            self.entry_celular_editar.setCursorPosition(
                max(0, cursor - (len(texto) - len(filtrado)))
            )
            self.entry_celular_editar.blockSignals(False)

    def _buscar_por_cp(self, cp=None):
        """
        Actualiza las colonias del diálogo Editar cliente.

        Reglas:
        - Con menos de 5 dígitos, no se muestra ninguna colonia.
        - Con 5 dígitos válidos en SEPOMEX, se cargan las colonias.
        - Con 5 dígitos que no existen en SEPOMEX, se limpia todo y se
          muestra un KBKADialog de CP no encontrado.
        """
        if cp is None:
            cp = self.entry_cp_editar.text().strip()
        else:
            cp = str(cp).strip()

        # Siempre eliminar los datos correspondientes al CP anterior.
        self.entry_estado_editar.clear()
        self.entry_ciudad_editar.clear()

        self.combo_colonia_editar.blockSignals(True)
        self.combo_colonia_editar.clear()
        self.combo_colonia_editar.setCurrentIndex(-1)
        if self.combo_colonia_editar.isEditable():
            self.combo_colonia_editar.setEditText("")
        self.combo_colonia_editar.blockSignals(False)

        # Mientras no existan exactamente cinco dígitos, el combo permanece
        # vacío. No se muestra ninguna alerta mientras el usuario escribe.
        if len(cp) != 5 or not cp.isdigit():
            self.combo_colonia_editar.setPlaceholderText(
                "Ingrese un CP válido de 5 dígitos"
            )
            self._ultimo_cp_invalido_alertado = None
            return

        df_sepomex = getattr(EtiquetasApp, "df_sepomex", None)
        if df_sepomex is None:
            return

        try:
            resultados = df_sepomex[df_sepomex["d_codigo"] == cp]

            if resultados.empty:
                self.combo_colonia_editar.setPlaceholderText(
                    "No hay colonias disponibles"
                )

                if (
                    not self._cargando_datos_iniciales
                    and self._ultimo_cp_invalido_alertado != cp
                ):
                    self._ultimo_cp_invalido_alertado = cp
                    KBKADialog.info(
                        self,
                        "CP no encontrado",
                        f"No se encontró información para el CP: {cp}."
                    )
                return

            self._ultimo_cp_invalido_alertado = None

            primer_resultado = resultados.iloc[0]
            self.entry_estado_editar.setText(
                str(primer_resultado["d_estado"]).upper()
            )
            self.entry_ciudad_editar.setText(
                str(primer_resultado["D_mnpio"]).upper()
            )

            colonias = sorted(
                {
                    str(colonia).strip().upper()
                    for colonia in resultados["d_asenta"].dropna().tolist()
                    if str(colonia).strip()
                }
            )

            self.combo_colonia_editar.blockSignals(True)
            self.combo_colonia_editar.addItems(colonias)
            self.combo_colonia_editar.setCurrentIndex(-1)
            if self.combo_colonia_editar.isEditable():
                self.combo_colonia_editar.setEditText("")
            self.combo_colonia_editar.setPlaceholderText(
                "Seleccione una colonia"
            )
            self.combo_colonia_editar.blockSignals(False)

            # Al escribir manualmente un CP válido, abrir el listado para que
            # resulte evidente que debe elegirse una nueva colonia.
            if colonias and not self._cargando_datos_iniciales:
                QTimer.singleShot(
                    0,
                    self.combo_colonia_editar.showPopup,
                )

        except Exception as error:
            print(f"Error al buscar CP durante la edición: {error}")
    def _obtener_datos(self):
        return {
            "nombre": self.entry_nombre_editar.text().strip().upper(),
            "celular": self.entry_celular_editar.text().strip(),
            "calle": self.entry_calle_editar.text().strip().upper(),
            "cp": self.entry_cp_editar.text().strip(),
            "colonia": (
                self.combo_colonia_editar.currentText().strip().upper()
            ),
            "estado": self.entry_estado_editar.text().strip().upper(),
            "municipio": self.entry_ciudad_editar.text().strip().upper(),
        }

    def _validar_datos(self, datos):
        if not datos["nombre"]:
            KBKADialog.warning(
                self,
                "Dato requerido",
                "El nombre del cliente no puede quedar vacío.",
            )
            self.entry_nombre_editar.setFocus()
            return False

        if datos["celular"] and len(datos["celular"]) != 10:
            KBKADialog.warning(
                self,
                "Celular inválido",
                "El número de celular debe contener 10 dígitos.",
            )
            self.entry_celular_editar.setFocus()
            return False

        if datos["cp"] and (
            len(datos["cp"]) != 5 or not datos["cp"].isdigit()
        ):
            KBKADialog.warning(
                self,
                "Código postal inválido",
                "El código postal debe contener 5 dígitos.",
            )
            self.entry_cp_editar.setFocus()
            return False

        if datos["cp"]:
            df_sepomex = getattr(EtiquetasApp, "df_sepomex", None)
            if df_sepomex is not None:
                resultados = df_sepomex[
                    df_sepomex["d_codigo"] == datos["cp"]
                ]
                if resultados.empty:
                    KBKADialog.info(
                        self,
                        "CP no encontrado",
                        f"No se encontró información para el CP: "
                        f"{datos['cp']}."
                    )
                    self.entry_cp_editar.setFocus()
                    self.entry_cp_editar.selectAll()
                    return False

            if not datos["colonia"]:
                KBKADialog.warning(
                    self,
                    "Colonia requerida",
                    "Seleccione una colonia correspondiente al código postal.",
                )
                self.combo_colonia_editar.setFocus()
                self.combo_colonia_editar.showPopup()
                return False

        return True

    def _guardar_cambios(self):
        datos = self._obtener_datos()
        if not self._validar_datos(datos):
            return

        conn = None
        try:
            conn = sqlite3.connect(self.parent_window.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT nombre
                FROM clientes
                WHERE UPPER(nombre) = UPPER(?)
                  AND nombre <> ?
                LIMIT 1
                """,
                (datos["nombre"], self.nombre_original),
            )
            if cursor.fetchone():
                KBKADialog.warning(
                    self,
                    "Cliente existente",
                    "Ya existe otro cliente con ese nombre.",
                )
                self.entry_nombre_editar.setFocus()
                self.entry_nombre_editar.selectAll()
                return

            cursor.execute(
                """
                UPDATE clientes
                SET nombre = ?,
                    celular = ?,
                    calle = ?,
                    cp = ?,
                    colonia = ?,
                    estado = ?,
                    municipio = ?
                WHERE nombre = ?
                """,
                (
                    datos["nombre"],
                    datos["celular"],
                    datos["calle"],
                    datos["cp"],
                    datos["colonia"],
                    datos["estado"],
                    datos["municipio"],
                    self.nombre_original,
                ),
            )

            if cursor.rowcount == 0:
                conn.rollback()
                KBKADialog.error(
                    self,
                    "Cliente no encontrado",
                    "No fue posible localizar el cliente que se intentó editar.",
                )
                return

            conn.commit()
            self.nombre_original = datos["nombre"]

            KBKADialog.success(
                self,
                "Cliente actualizado",
                "Los cambios se guardaron correctamente.",
            )
            self.accept()
        except sqlite3.IntegrityError:
            if conn is not None:
                conn.rollback()
            KBKADialog.warning(
                self,
                "Cliente existente",
                "Ya existe un cliente con ese nombre.",
            )
        except Exception as error:
            if conn is not None:
                conn.rollback()
            KBKADialog.error(
                self,
                "Error al guardar",
                f"No fue posible actualizar el cliente:\n{error}",
            )
        finally:
            if conn is not None:
                conn.close()

    def _aplicar_estilos(self):
        if self.tema_oscuro:
            bg_dialog = "#1E1E1E"
            bg_card = "#292929"
            bg_input = "#303030"
            bg_hover = "#363636"
            text_primary = "#F0F0F0"
            text_secondary = "#B8B8B8"
            border = "#454545"
            cancel_bg = "#333333"
            cancel_hover = "#414141"
        else:
            bg_dialog = "#F7F8FA"
            bg_card = "#FFFFFF"
            bg_input = "#FFFFFF"
            bg_hover = "#FAFBFC"
            text_primary = "#202020"
            text_secondary = "#616A74"
            border = "#D6DADE"
            cancel_bg = "#EEF1F4"
            cancel_hover = "#E2E7EC"

        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {bg_dialog};
                color: {text_primary};
                font-family: 'Segoe UI', sans-serif;
            }}

            QWidget#edit_transparent {{
                background-color: transparent;
            }}

            QLabel#edit_title {{
                background-color: transparent;
                color: #CD0403;
                font-size: 16pt;
                font-weight: 750;
                padding: 0px;
            }}

            QLabel#edit_description {{
                background-color: transparent;
                color: {text_secondary};
                font-size: 9.5pt;
                padding: 0px 0px 4px 0px;
            }}

            QLabel#edit_field_label {{
                background-color: transparent;
                color: {text_primary};
                font-size: 9.5pt;
                font-weight: 550;
                padding: 0px;
            }}

            QFrame#edit_card {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 12px;
            }}

            QLineEdit, QComboBox {{
                background-color: {bg_input};
                color: {text_primary};
                border: 1px solid {border};
                border-radius: 8px;
                padding: 10px 12px;
                min-height: 20px;
                selection-background-color: #CD0403;
                selection-color: #FFFFFF;
            }}

            QLineEdit:hover, QComboBox:hover {{
                background-color: {bg_hover};
                border: 1px solid #B94A49;
            }}

            QLineEdit:focus, QComboBox:focus {{
                background-color: {bg_input};
                border: 2px solid #CD0403;
            }}

            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}

            QComboBox QAbstractItemView {{
                background-color: {bg_card};
                color: {text_primary};
                border: 1px solid {border};
                selection-background-color: #CD0403;
                selection-color: #FFFFFF;
                outline: none;
                padding: 5px;
            }}

            QPushButton#edit_save {{
                background-color: #CD0403;
                color: #FFFFFF;
                border: 1px solid #ED4B4A;
                border-radius: 9px;
                padding: 9px 14px;
                font-size: 10pt;
                font-weight: 700;
            }}

            QPushButton#edit_save:hover {{
                background-color: #E00504;
                border: 1px solid #FF6A69;
            }}

            QPushButton#edit_save:pressed {{
                background-color: #A50302;
            }}

            QPushButton#edit_cancel {{
                background-color: {cancel_bg};
                color: {text_primary};
                border: 1px solid {border};
                border-radius: 9px;
                padding: 9px 14px;
                font-size: 10pt;
                font-weight: 650;
            }}

            QPushButton#edit_cancel:hover {{
                background-color: {cancel_hover};
                border: 1px solid #CD0403;
            }}
            """
        )

class GestionClientesDialog(QDialog):
    """
    Diálogo para gestionar clientes de la base de datos.
    
    Muestra una interfaz premium tipo cards que permite:
    - Ver todos los clientes en tarjetas individuales
    - Buscar clientes por nombre o celular
    - Cargar un cliente guardado en el formulario principal
    - Editar clientes en una ventana independiente con guardado explícito
    - Eliminar clientes con confirmación
    - Adaptación a temas claro/oscuro con efectos hover personalizados
    
    :param parent: Ventana principal de la aplicación.
    :type parent: EtiquetasApp
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Gestión de Clientes")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        
        # Lista para mantener referencias a los botones de iconos
        self.botones_iconos = []
        
        self.init_ui()
        self.cargar_clientes()
    
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
        Inicializa la interfaz del diálogo de gestión de clientes.
        
        Crea:
        - Título premium con iconos
        - Barra de búsqueda en tiempo real
        - Área scrollable para cards de clientes
        - Botón de cerrar
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)
        
        # Título
        titulo = QLabel("👥 GESTIÓN DE CLIENTES")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setStyleSheet(f"""
            background-color: transparent;
            border: none;
            color: {self.parent_window.COLORS['primary']};
            font-size: 18pt;
            font-weight: bold;
            padding: 15px 0px;
            letter-spacing: 1px;
        """)
        layout.addWidget(titulo)
        
        # Barra de búsqueda centrada con diseño premium
        search_container = QHBoxLayout()
        search_container.addStretch()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Buscar por nombre o celular...")
        self.search_input.setFixedWidth(500)
        self.search_input.setFixedHeight(45)
        self.search_input.textChanged.connect(self.filtrar_clientes)
        
        # Determinar colores según el tema del padre
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            bg_input = "#2A2A2A"
            bg_hover = "#333333"
            border_color = "#3A3A3A"
            text_color = "#E0E0E0"
            placeholder_color = "#808080"  # Gris medio para placeholder
        else:
            bg_input = "#FAFAFA"
            bg_hover = "#FFFFFF"
            border_color = "#E0E0E0"
            text_color = "#1A1A1A"
            placeholder_color = "#999999"
        
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 12px 20px;
                border: 2px solid {border_color};
                border-radius: 22px;
                font-size: 11pt;
                background-color: {bg_input};
                color: {text_color};
            }}
            QLineEdit::placeholder {{
                color: {placeholder_color};
            }}
            QLineEdit:hover {{
                border: 2px solid #CD0403;
                background-color: {bg_hover};
            }}
            QLineEdit:focus {{
                border: 2px solid #CD0403;
                background-color: {bg_hover};
            }}
        """)
        search_container.addWidget(self.search_input)
        search_container.addStretch()
        layout.addLayout(search_container)
        
        # Scroll Area para las cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # Contenedor de cards
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setContentsMargins(5, 5, 5, 5)
        
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)
        
        # Botón Cerrar
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("btn_primary")
        btn_cerrar.setMinimumHeight(45)
        btn_cerrar.setMaximumWidth(200)
        btn_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cerrar.clicked.connect(self.accept)
        btn_cerrar.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.parent_window.COLORS['gray1']};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #6A6A6A;
            }}
            QPushButton:pressed {{
                background-color: #4A4A4A;
            }}
        """)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cerrar)
        layout.addLayout(btn_layout)
    
    def mostrar_mensaje_info(self, titulo, mensaje):
        """Muestra un mensaje de información con botón visible"""
        KBKADialog.info(self, titulo, mensaje)
    
    def mostrar_mensaje_error(self, titulo, mensaje):
        """
        Muestra un mensaje de error usando KBKADialog.
        
        :param titulo: Título del diálogo de error.
        :type titulo: str
        :param mensaje: Mensaje de error a mostrar.
        :type mensaje: str
        """
        KBKADialog.error(self, titulo, mensaje)
    
    def cargar_clientes(self):
        """
        Carga todos los clientes de la base de datos.
        
        Consulta la tabla 'clientes' y muestra las tarjetas.
        Si no hay clientes, muestra estado vacío.
        """
        try:
            conn = sqlite3.connect(self.parent_window.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT nombre, celular, cp, municipio, calle, colonia, estado FROM clientes ORDER BY nombre')
            clientes = cursor.fetchall()
            conn.close()
            
            self.clientes_data = clientes
            
            # Verificar si la lista está vacía
            if len(clientes) == 0:
                self.mostrar_estado_vacio()
            else:
                self.mostrar_clientes(clientes)
            
        except Exception as e:
            self.mostrar_mensaje_error("Error", f"Error al cargar clientes:\n{str(e)}")
    
    def mostrar_estado_vacio(self):
        """
        Muestra un estado vacío con icono y mensaje cuando no hay clientes.
        
        Usa QGraphicsOpacityEffect para suavizar el icono de advertencia.
        Se adapta al tema actual (claro/oscuro).
        """
        # Limpiar todos los elementos del layout
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Agregar stretch superior para centrar verticalmente
        self.cards_layout.addStretch()
        
        # Contenedor centrado para el estado vacío
        empty_container = QWidget()
        empty_layout = QVBoxLayout(empty_container)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(20)
        
        # Icono de advertencia grande con opacidad
        icon_label = QLabel()
        warning_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
        icon_pixmap = warning_icon.pixmap(64, 64)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Aplicar efecto de opacidad para suavizar el icono
        opacity_effect = QGraphicsOpacityEffect()
        opacity_effect.setOpacity(0.4)
        icon_label.setGraphicsEffect(opacity_effect)
        
        empty_layout.addWidget(icon_label)
        
        # Determinar color del texto según el tema
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            empty_text_color = "#A0A0A0"
        else:
            empty_text_color = "#888888"
        
        # Texto descriptivo
        text_label = QLabel("Aún no hay clientes registrados")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setStyleSheet(f"""
            background-color: transparent;
            border: none;
            font-family: 'Segoe UI', sans-serif;
            font-size: 14pt;
            color: {empty_text_color};
            font-weight: 500;
        """)
        empty_layout.addWidget(text_label)
        
        # Agregar contenedor al layout
        self.cards_layout.addWidget(empty_container)
        
        # Agregar stretch inferior para centrar verticalmente
        self.cards_layout.addStretch()
    
    def mostrar_clientes(self, clientes):
        """
        Muestra los clientes como cards premium en el scroll area.
        
        Limpia el layout anterior y crea una card por cada cliente.
        
        :param clientes: Lista de tuplas con datos de clientes.
        :type clientes: list
        """
        # Limpiar todos los elementos del layout
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Limpiar lista de botones de iconos
        self.botones_iconos.clear()
        
        # Crear una card para cada cliente
        for cliente in clientes:
            card = self.crear_card_cliente(cliente)
            self.cards_layout.addWidget(card)
        
        # Agregar stretch al final para empujar las cards hacia arriba
        self.cards_layout.addStretch()
    
    def crear_card_cliente(self, cliente):
        """
        Crea una card premium para un cliente individual.
        
        Incluye:
        - Nombre y celular con estilos adaptables al tema
        - Dirección completa
        - Botones de editar y eliminar con iconos
        - Efectos hover personalizados para modo oscuro
        
        :param cliente: Tupla con datos del cliente (nombre, celular, cp, municipio, calle, colonia, estado).
        :type cliente: tuple
        :return: Widget QFrame con la card del cliente.
        :rtype: QFrame
        """
        # Datos del cliente
        nombre, celular, cp, municipio, calle, colonia, estado = cliente
        
        # Determinar colores según el tema
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            card_bg = "#2A2A2A"
            card_border = "#3A3A3A"
            card_hover_bg = "#333333"
            nombre_color = "#F0F0F0"
            celular_color = "#B0B0B0"
            direccion_color = "#C0C0C0"
            detalles_color = "#A0A0A0"
        else:
            card_bg = "#FFFFFF"
            card_border = "#E8E8E8"
            card_hover_bg = "#FFFAFA"
            nombre_color = "#2C2C2C"
            celular_color = "#757575"
            direccion_color = "#4A4A4A"
            detalles_color = "#757575"
        
        # Frame principal de la card
        card = QFrame()
        card.setObjectName("client_card")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame#client_card {{
                background-color: {card_bg};
                border: 2px solid {card_border};
                border-radius: 12px;
                padding: 18px;
            }}
            QFrame#client_card:hover {{
                border: 2px solid #CD0403;
                background-color: {card_hover_bg};
            }}
        """)
        
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(15, 12, 15, 12)
        
        # === SECCIÓN IZQUIERDA: Nombre y Celular ===
        left_section = QVBoxLayout()
        left_section.setSpacing(5)
        
        nombre_label = QLabel(nombre or "[Sin nombre]")
        nombre_label.setStyleSheet(f"""
            background-color: transparent;
            border: none;
            font-size: 13pt;
            font-weight: bold;
            color: {nombre_color};
        """)
        left_section.addWidget(nombre_label)
        
        celular_label = QLabel(f"📱 {celular or 'Sin teléfono'}")
        celular_label.setStyleSheet(f"""
            background-color: transparent;
            border: none;
            font-size: 10pt;
            color: {celular_color};
        """)
        left_section.addWidget(celular_label)
        
        card_layout.addLayout(left_section, 2)
        
        # === SECCIÓN CENTRO: Dirección ===
        center_section = QVBoxLayout()
        center_section.setSpacing(3)
        
        calle_label = QLabel(calle or "Sin dirección")
        calle_label.setStyleSheet(f"""
            background-color: transparent;
            border: none;
            font-size: 10pt;
            color: {direccion_color};
        """)
        center_section.addWidget(calle_label)
        
        colonia_cp = f"{colonia or 'Sin colonia'}, CP {cp or 'N/A'}"
        colonia_label = QLabel(colonia_cp)
        colonia_label.setStyleSheet(f"""
            background-color: transparent;
            border: none;
            font-size: 9pt;
            color: {detalles_color};
        """)
        center_section.addWidget(colonia_label)
        
        ciudad_estado = f"{municipio or 'Sin ciudad'}, {estado or 'Sin estado'}"
        ciudad_label = QLabel(ciudad_estado)
        ciudad_label.setStyleSheet(f"""
            background-color: transparent;
            border: none;
            font-size: 9pt;
            color: {detalles_color};
        """)
        center_section.addWidget(ciudad_label)
        
        card_layout.addLayout(center_section, 3)
        
        # === SECCIÓN DERECHA: Botones de acción ===
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        
        # Colores para botones según tema
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            imprimir_border = "#3498DB"  # Azul para importar al formulario
            editar_border = "#27AE60"  # Verde profesional
            eliminar_border = "#CD0403"  # Rojo corporativo KBKA
        else:
            imprimir_border = "#3498DB"
            imprimir_hover = "#3498DB"
            editar_border = "#4CAF50"
            editar_hover = "#4CAF50"
            eliminar_border = "#F44336"
            eliminar_hover = "#F44336"
        
        # Botón Importar cliente al formulario principal (circular)
        btn_importar_cliente = QPushButton()
        btn_importar_cliente.setFixedSize(40, 40)
        btn_importar_cliente.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_importar_cliente.setToolTip(
            "Cargar los datos de este cliente en el formulario principal"
        )

        # Intentar cargar el icono personalizado importar.png
        try:
            importar_icon_path = obtener_ruta_recurso(
                os.path.join(ICONS_DIR, "importar.png")
            )
            if os.path.exists(importar_icon_path):
                btn_importar_cliente.setIcon(QIcon(importar_icon_path))
                btn_importar_cliente.setIconSize(QSize(24, 24))
            else:
                btn_importar_cliente.setText("📥")
        except Exception:
            btn_importar_cliente.setText("📥")

        if (
            hasattr(self.parent_window, "tema_oscuro")
            and self.parent_window.tema_oscuro
        ):
            btn_importar_cliente.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {imprimir_border};
                    border-radius: 20px;
                }}
                """
            )

            colorize_effect = QGraphicsColorizeEffect()
            colorize_effect.setColor(QColor("#FFFFFF"))
            colorize_effect.setStrength(1.0)
            btn_importar_cliente.setGraphicsEffect(colorize_effect)

            btn_importar_cliente.enterEvent = (
                lambda event: self._on_button_enter(
                    btn_importar_cliente,
                    imprimir_border,
                    event,
                )
            )
            btn_importar_cliente.leaveEvent = (
                lambda event: self._on_button_leave(
                    btn_importar_cliente,
                    imprimir_border,
                    event,
                )
            )
        else:
            btn_importar_cliente.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {imprimir_border};
                    border-radius: 20px;
                }}
                QPushButton:hover {{
                    background-color: {imprimir_hover};
                    border: 2px solid {imprimir_border};
                }}
                """
            )

        btn_importar_cliente.clicked.connect(
            lambda: self.cargar_cliente_en_formulario(nombre)
        )
        actions_layout.addWidget(btn_importar_cliente)
        self.botones_iconos.append(btn_importar_cliente)

        # Botón Editar (circular)
        btn_editar = QPushButton()
        btn_editar.setFixedSize(40, 40)
        btn_editar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_editar.setToolTip("Editar cliente")
        
        # Intentar cargar icono personalizado
        try:
            editar_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'editar.png'))
            if os.path.exists(editar_icon_path):
                btn_editar.setIcon(QIcon(editar_icon_path))
                btn_editar.setIconSize(QSize(24, 24))
            else:
                btn_editar.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
                btn_editar.setIconSize(QSize(20, 20))
        except:
            btn_editar.setText("✏")
        
        # Estilos según tema para botón Editar
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            # Modo oscuro: sin hover CSS (se manejará con eventos)
            btn_editar.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {editar_border};
                    border-radius: 20px;
                }}
            """)
        else:
            # Modo claro: con hover CSS
            btn_editar.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {editar_border};
                    border-radius: 20px;
                }}
                QPushButton:hover {{
                    background-color: {editar_hover};
                    border: 2px solid {editar_border};
                }}
            """)
        
        # Aplicar efecto de colorización al icono según el tema
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            colorize_effect = QGraphicsColorizeEffect()
            colorize_effect.setColor(QColor("#FFFFFF"))
            colorize_effect.setStrength(1.0)
            btn_editar.setGraphicsEffect(colorize_effect)
            
            # Conectar eventos personalizados para modo oscuro
            btn_editar.enterEvent = lambda event: self._on_button_enter(btn_editar, editar_border, event)
            btn_editar.leaveEvent = lambda event: self._on_button_leave(btn_editar, editar_border, event)
        
        btn_editar.clicked.connect(lambda: self.editar_cliente_por_nombre(nombre))
        actions_layout.addWidget(btn_editar)
        
        # Guardar referencia al botón para actualización de tema
        self.botones_iconos.append(btn_editar)
        
        # Botón Eliminar (circular)
        btn_eliminar = QPushButton()
        btn_eliminar.setFixedSize(40, 40)
        btn_eliminar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_eliminar.setToolTip("Eliminar cliente")
        
        # Intentar cargar icono personalizado
        try:
            eliminar_icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'eliminar.png'))
            if os.path.exists(eliminar_icon_path):
                btn_eliminar.setIcon(QIcon(eliminar_icon_path))
                btn_eliminar.setIconSize(QSize(24, 24))
            else:
                btn_eliminar.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
                btn_eliminar.setIconSize(QSize(20, 20))
        except:
            btn_eliminar.setText("🗑")
        
        # Estilos según tema para botón Eliminar
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            # Modo oscuro: sin hover CSS (se manejará con eventos)
            btn_eliminar.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {eliminar_border};
                    border-radius: 20px;
                }}
            """)
        else:
            # Modo claro: con hover CSS
            btn_eliminar.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {eliminar_border};
                    border-radius: 20px;
                }}
                QPushButton:hover {{
                    background-color: {eliminar_hover};
                    border: 2px solid {eliminar_border};
                }}
            """)
        
        # Aplicar efecto de colorización al icono según el tema
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            colorize_effect = QGraphicsColorizeEffect()
            colorize_effect.setColor(QColor("#FFFFFF"))
            colorize_effect.setStrength(1.0)
            btn_eliminar.setGraphicsEffect(colorize_effect)
            
            # Conectar eventos personalizados para modo oscuro
            btn_eliminar.enterEvent = lambda event: self._on_button_enter(btn_eliminar, eliminar_border, event)
            btn_eliminar.leaveEvent = lambda event: self._on_button_leave(btn_eliminar, eliminar_border, event)
        
        btn_eliminar.clicked.connect(lambda: self.borrar_cliente_por_nombre(nombre))
        actions_layout.addWidget(btn_eliminar)
        
        # Guardar referencia al botón para actualización de tema
        self.botones_iconos.append(btn_eliminar)
        
        card_layout.addLayout(actions_layout, 1)
        
        return card
    
    def _on_button_enter(self, boton, border_color, event):
        """
        Maneja el evento de entrada del mouse en botones (modo oscuro).
        
        Cambia fondo a blanco e iconos a negro con QGraphicsColorizeEffect.
        
        :param boton: Botón afectado.
        :type boton: QPushButton
        :param border_color: Color del borde del botón.
        :type border_color: str
        :param event: Evento del mouse.
        """
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            # Cambiar fondo a blanco
            boton.setStyleSheet(f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    border: 2px solid {border_color};
                    border-radius: 20px;
                }}
            """)
            
            # Cambiar icono a negro
            colorize_effect = QGraphicsColorizeEffect()
            colorize_effect.setColor(QColor("#000000"))
            colorize_effect.setStrength(1.0)
            boton.setGraphicsEffect(colorize_effect)
    
    def _on_button_leave(self, boton, border_color, event):
        """
        Maneja el evento de salida del mouse de botones (modo oscuro).
        
        Restaura fondo transparente e iconos a blanco.
        
        :param boton: Botón afectado.
        :type boton: QPushButton
        :param border_color: Color del borde del botón.
        :type border_color: str
        :param event: Evento del mouse.
        """
        if hasattr(self.parent_window, 'tema_oscuro') and self.parent_window.tema_oscuro:
            # Restaurar fondo transparente
            boton.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 2px solid {border_color};
                    border-radius: 20px;
                }}
            """)
            
            # Restaurar icono a blanco
            colorize_effect = QGraphicsColorizeEffect()
            colorize_effect.setColor(QColor("#FFFFFF"))
            colorize_effect.setStrength(1.0)
            boton.setGraphicsEffect(colorize_effect)
    
    def actualizar_iconos_tema(self):
        """
        Actualiza el color de los iconos y recarga las tarjetas según el tema actual.
        
        Reconfigura estilos de la barra de búsqueda y recarga las cards
        aplicando la lógica correcta de eventos hover para cada tema.
        """
        # Actualizar estilos del campo de búsqueda
        if hasattr(self, 'search_input') and hasattr(self.parent_window, 'tema_oscuro'):
            if self.parent_window.tema_oscuro:
                bg_input = "#2A2A2A"
                bg_hover = "#333333"
                border_color = "#3A3A3A"
                text_color = "#E0E0E0"
                placeholder_color = "#808080"
            else:
                bg_input = "#FAFAFA"
                bg_hover = "#FFFFFF"
                border_color = "#E0E0E0"
                text_color = "#1A1A1A"
                placeholder_color = "#999999"
            
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    padding: 12px 20px;
                    border: 2px solid {border_color};
                    border-radius: 22px;
                    font-size: 11pt;
                    background-color: {bg_input};
                    color: {text_color};
                }}
                QLineEdit::placeholder {{
                    color: {placeholder_color};
                }}
                QLineEdit:hover {{
                    border: 2px solid #CD0403;
                    background-color: {bg_hover};
                }}
                QLineEdit:focus {{
                    border: 2px solid #CD0403;
                    background-color: {bg_hover};
                }}
            """)
        
        # Recargar las tarjetas de clientes para aplicar la lógica correcta de eventos
        if hasattr(self, 'clientes_data'):
            if len(self.clientes_data) == 0:
                self.mostrar_estado_vacio()
            else:
                texto_busqueda = self.search_input.text().upper() if hasattr(self, 'search_input') else ""
                if texto_busqueda:
                    # Si hay texto de búsqueda, aplicar filtro
                    clientes_filtrados = [
                        cliente for cliente in self.clientes_data
                        if texto_busqueda in (cliente[0] or "").upper() or 
                           texto_busqueda in (cliente[1] or "")
                    ]
                    self.mostrar_clientes(clientes_filtrados if len(clientes_filtrados) > 0 else self.clientes_data)
                else:
                    # Sin filtro, mostrar todos
                    self.mostrar_clientes(self.clientes_data)
    
    def filtrar_clientes(self):
        """
        Filtra los clientes según el texto de búsqueda en tiempo real.
        
        Busca coincidencias en nombre (case-insensitive) y celular.
        Actualiza la visualización instantáneamente.
        """
        texto_busqueda = self.search_input.text().upper()
        
        if not texto_busqueda:
            if len(self.clientes_data) == 0:
                self.mostrar_estado_vacio()
            else:
                self.mostrar_clientes(self.clientes_data)
            return
        
        clientes_filtrados = [
            cliente for cliente in self.clientes_data
            if texto_busqueda in (cliente[0] or "").upper() or 
               texto_busqueda in (cliente[1] or "")
        ]
        
        if len(clientes_filtrados) == 0:
            self.mostrar_estado_vacio()
        else:
            self.mostrar_clientes(clientes_filtrados)
    
    def cargar_cliente_en_formulario(self, nombre):
        """
        Carga los datos del cliente seleccionado en el formulario principal.

        Después de cargar la información, cierra Gestión de Clientes para que
        el usuario pueda revisar la etiqueta y mandarla a imprimir desde el
        menú principal.
        """
        if not nombre:
            return

        conn = None
        try:
            conn = sqlite3.connect(self.parent_window.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT nombre, celular, calle, cp, colonia, estado, municipio
                FROM clientes
                WHERE nombre = ?
                """,
                (nombre,),
            )
            datos_cliente = cursor.fetchone()

            if not datos_cliente:
                self.mostrar_mensaje_error(
                    "Cliente no encontrado",
                    "No fue posible localizar los datos del cliente.",
                )
                return

            # Reutilizar la lógica existente para cargar nombre, dirección,
            # código postal, colonia, estado, municipio y vista previa.
            self.parent_window.cargar_cliente_desde_gestion(datos_cliente)

            # Cerrar Gestión de Clientes y regresar al formulario principal.
            self.accept()

            # La aplicación principal trabaja maximizada. Evitamos showNormal(),
            # porque reducía la ventana al importar un cliente.
            self.parent_window.showMaximized()
            self.parent_window.raise_()
            self.parent_window.activateWindow()

        except Exception as error:
            self.mostrar_mensaje_error(
                "Error al cargar cliente",
                f"No fue posible cargar los datos del cliente:\n{error}",
            )
        finally:
            if conn is not None:
                conn.close()
    def editar_cliente_por_nombre(self, nombre):
        """
        Abre una ventana independiente para editar al cliente seleccionado.

        El usuario modifica los datos y los guarda explícitamente mediante
        el botón Guardar cambios, sin cerrar Gestión de Clientes.
        """
        if not nombre:
            return

        try:
            conn = sqlite3.connect(self.parent_window.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT nombre, celular, calle, cp, colonia, estado, municipio
                FROM clientes
                WHERE nombre = ?
                """,
                (nombre,),
            )
            datos = cursor.fetchone()
            conn.close()

            if not datos:
                self.mostrar_mensaje_error(
                    "Cliente no encontrado",
                    "No fue posible localizar los datos del cliente.",
                )
                return

            dialogo = EditarClienteDialog(self.parent_window, datos)
            if dialogo.exec() == QDialog.DialogCode.Accepted:
                self.cargar_clientes()
                self.parent_window.actualizar_completer()
        except Exception as error:
            self.mostrar_mensaje_error(
                "Error",
                f"Error al abrir la edición del cliente:\n{error}",
            )
    def borrar_cliente_por_nombre(self, nombre):
        """
        Elimina un cliente de la base de datos con confirmación.
        
        Solicita confirmación antes de eliminar.
        Actualiza la lista y el autocompletado tras la eliminación.
        Maneja errores de base de datos bloqueada.
        
        :param nombre: Nombre del cliente a eliminar.
        :type nombre: str
        """
        if not nombre:
            return
        
        # Confirmar eliminación
        confirmado = KBKADialog.confirm(
            self,
            "Confirmar Eliminación",
            f"¿Está seguro de que desea eliminar al cliente:\n\n'{nombre}'?\n\n"
            "Esta acción no se puede deshacer."
        )
        
        if confirmado:
            conn = None
            try:
                # Conectar a la base de datos
                conn = sqlite3.connect(self.parent_window.db_path)
                cursor = conn.cursor()
                
                # Eliminar de la base de datos
                cursor.execute('DELETE FROM clientes WHERE nombre = ?', (nombre,))
                
                # Commit
                conn.commit()
                conn.close()
                conn = None
                
                # Refrescar la lista de clientes
                self.cargar_clientes()
                
                # Actualizar autocompletado de la ventana principal
                try:
                    self.parent_window.actualizar_completer()
                except Exception as comp_error:
                    print(f"Advertencia: No se pudo actualizar el autocompletado: {comp_error}")
                
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "locked" in error_msg:
                    self.mostrar_mensaje_error(
                        "Error - Base de Datos Bloqueada",
                        f"No se pudo eliminar al cliente '{nombre}'.\n\n"
                        "La base de datos está siendo utilizada por otro proceso."
                    )
                else:
                    self.mostrar_mensaje_error(
                        "Error de Base de Datos",
                        f"No se pudo eliminar al cliente '{nombre}'.\n\nError: {str(e)}"
                    )
            except Exception as e:
                self.mostrar_mensaje_error(
                    "Error al Eliminar Cliente",
                    f"Ocurrió un error al eliminar al cliente '{nombre}'.\n\n{str(e)}"
                )
            finally:
                if conn:
                    try:
                        conn.close()
                    except:
                        pass


class ModernSplashScreen(QWidget):
    """
    Pantalla de inicio ultra-premium para KBKA SHOP.
    
    Características:
    - Ventana sin bordes con fondo translúcido
    - Animaciones suaves de fade-in/fade-out
    - Barra de progreso animada
    - Efecto de escala en logo (98% a 100%)
    - Sombra profesional
    
    La ventana principal se crea después de que el splash finalice.
    """
    
    def __init__(self):
        super().__init__()
        
        # Store main window reference
        self.main_window = None
        
        # Configure window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set size (larger for better logo visibility)
        self.setFixedSize(650, 420)
        
        # Establecer icono si existe
        try:
            icon_path = obtener_ruta_recurso(os.path.join(ICONS_DIR, 'KBKA.ico'))
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except:
            pass
        
        # Center on screen
        self._center_on_screen()
        
        # Setup UI
        self._setup_ui()
        
        # Setup animations
        self._setup_animations()
        
    def _center_on_screen(self):
        """
        Centra el splash screen en la pantalla principal.
        
        Usa QApplication.primaryScreen() para obtener geometría de pantalla.
        """
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        
    def _setup_ui(self):
        """
        Configura los componentes de la interfaz del splash.
        
        Crea:
        - Frame contenedor con bordes redondeados
        - Logo desde assets/images/splash.png escalado a 500x300px
        - Barra de progreso con estilo premium (sin texto)
        - Etiqueta de estado "Cargando..."
        """
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)  # Margins for shadow
        
        # Container frame with rounded corners
        self.container = QFrame()
        self.container.setObjectName("splash_container")
        self.container.setStyleSheet("""
            #splash_container {
                background-color: #FCFCFC;
                border-radius: 20px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)
        
        # Note: Shadow effect removed to avoid conflict with opacity animation
        # The splash looks clean and modern without it
        
        # Container layout
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(40, 60, 40, 60)
        container_layout.setSpacing(30)
        
        # Add stretch to center content vertically
        container_layout.addStretch()
        
        # Logo (larger for better visibility - 70-75% of splash width)
        self.logo_label = QLabel()
        logo_path = obtener_ruta_recurso(os.path.join(IMAGES_DIR, 'splash.png'))
        
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Scale logo to 70-75% of splash width (~480px)
            scaled_pixmap = pixmap.scaled(
                500, 300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(scaled_pixmap)
        else:
            # Fallback if splash.png doesn't exist
            self.logo_label.setText("KBKA SHOP")
            self.logo_label.setStyleSheet("""
                color: #CF1312;
                font-size: 48px;
                font-weight: bold;
                font-family: 'Segoe UI', Arial, sans-serif;
            """)
        
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.logo_label)
        
        # Spacing
        container_layout.addSpacing(20)
        
        # Progress bar container
        progress_container = QWidget()
        progress_layout = QVBoxLayout(progress_container)
        progress_layout.setContentsMargins(50, 0, 50, 0)
        progress_layout.setSpacing(10)
        
        # Modern QProgressBar with perfect rounded corners
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
        
        # Status text
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
        
        # Add stretch to center content vertically
        container_layout.addStretch()
        
        main_layout.addWidget(self.container)
        
    def _setup_animations(self):
        """
        Configura todas las animaciones del splash.
        
        Crea:
        - QGraphicsOpacityEffect para fade-in (600ms, OutCubic)
        - QPropertyAnimation del progress bar (1800ms)
        - Logo scale animation de 98% a 100% (300ms, OutCubic)
        """
        # Create opacity effect for smooth premium fade-in
        self.splash_opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.splash_opacity_effect)
        self.splash_opacity_effect.setOpacity(0.0)  # Start invisible
        
        # Fade-in animation with natural easing (600ms - fast and smooth)
        self.fade_in_animation = QPropertyAnimation(self.splash_opacity_effect, b"opacity")
        self.fade_in_animation.setDuration(600)  # Short, premium fade-in
        self.fade_in_animation.setStartValue(0.0)
        self.fade_in_animation.setEndValue(1.0)
        self.fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)  # Natural easing
        
        # Logo scale-in (extremely subtle: 98% to 100% in 300ms)
        if self.logo_label.pixmap() and not self.logo_label.pixmap().isNull():
            self.original_pixmap = self.logo_label.pixmap()
            # Scale down to 98% initially (barely noticeable)
            scaled_down = self.original_pixmap.scaled(
                int(self.original_pixmap.width() * 0.98),
                int(self.original_pixmap.height() * 0.98),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(scaled_down)
        
        # Progress bar animation (0 to 100%)
        self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.progress_animation.setDuration(2000)
        self.progress_animation.setStartValue(0)
        self.progress_animation.setEndValue(100)
        self.progress_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        
        # Connect to progress animation finished signal
        self.progress_animation.finished.connect(self._on_progress_finished)
        
    def _on_progress_finished(self):
        """Called when progress animation completes - wait 1 second then show main window"""
        # Wait 1000ms (1 second) after progress completes
        QTimer.singleShot(1000, self._close_and_show_main)
        
    def show(self):
        """
        Override de show() para iniciar animaciones automáticamente.
        
        Inicia en secuencia:
        1. Fade-in del splash (600ms)
        2. Logo scale-in después de 50ms (300ms)
        3. Animación de barra de progreso (dispara _on_progress_finished al terminar)
        """
        super().show()
        
        # Start smooth fade-in (600ms - fast and premium)
        self.fade_in_animation.start()
        
        # Start subtle logo scale-in (300ms - barely noticeable)
        if hasattr(self, 'original_pixmap'):
            QTimer.singleShot(50, self._animate_logo_scale)
        
        # Start progress bar animation (will trigger _on_progress_finished when done)
        self.progress_animation.start()
        
    def _animate_logo_scale(self):
        """
        Anima el logo de 98% a 100% de escala (efecto muy sutil y rápido).
        
        Usa 6 pasos de interpolación en 300ms para un efecto suave.
        """
        if not hasattr(self, 'original_pixmap'):
            return
        
        # Fast and subtle scale animation (300ms - barely noticeable)
        steps = 6
        duration = 300  # Fast animation
        step_time = duration // steps
        
        def update_scale(step):
            if step > steps:
                return
            scale = 0.98 + (0.02 * step / steps)  # 98% to 100% (very subtle)
            scaled = self.original_pixmap.scaled(
                int(self.original_pixmap.width() * scale),
                int(self.original_pixmap.height() * scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.logo_label.setPixmap(scaled)
            
            if step < steps:
                QTimer.singleShot(step_time, lambda: update_scale(step + 1))
        
        update_scale(0)
        
    def _close_and_show_main(self):
        """
        Cierra el splash y crea/muestra la ventana principal.
        
        La ventana EtiquetasApp se crea solo DESPUÉS de que el splash termine,
        evitando problemas de inicialización y carga.
        """
        # Create main window only NOW (not before)
        self.main_window = EtiquetasApp()
        self.main_window.show()
        self.close()


def main():
    """
    Función principal de la aplicación.
    
    Inicia QApplication, muestra splash screen y ejecuta el loop de eventos.
    La ventana principal se crea automáticamente cuando termine el splash.
    """
    app = QApplication(sys.argv)
    
    # Create and show splash screen
    # Main window will be created AFTER splash finishes
    splash = ModernSplashScreen()
    splash.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
