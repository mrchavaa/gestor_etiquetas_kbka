# KBKA SHOP — compilación con cx_Freeze

Este paquete contiene los tres módulos preparados para cx_Freeze:

- `main.py`
- `envios.py`
- `modelos.py`

También incluye `setup.py`, verificación automática y scripts `.bat`.

## Falta copiar tu carpeta assets

Por tamaño y porque no fue adjuntada en esta conversación, este ZIP no contiene
la carpeta `assets`. Copia la carpeta original completa junto a `main.py`.

La estructura debe quedar así:

```text
KBKA_Centro_Etiquetas_CxFreeze/
├── main.py
├── envios.py
├── modelos.py
├── setup.py
├── requirements-build.txt
├── assets/
│   ├── icons/
│   │   └── KBKA.ico
│   ├── headers/
│   │   ├── header_fondo_oscuro.png
│   │   └── header_fondo_blanco.png
│   ├── images/
│   └── db/
│       └── sepomex_consolidado.csv
└── archivos .bat
```

## Generar el instalador

1. Ejecuta `01_PREPARAR_ENTORNO.bat`.
2. Ejecuta `02_GENERAR_EXE.bat` para probar primero la aplicación.
3. Ejecuta `03_GENERAR_MSI.bat` para crear el instalador.

También puedes ejecutar `04_GENERAR_TODO.bat`.

Resultados:

- EXE: dentro de `build\exe.*`
- MSI: dentro de `dist`

## Diagnóstico

Cuando la aplicación compilada no abra o se cierre, ejecuta
`05_GENERAR_EXE_DEBUG.bat`. Ese ejecutable conserva una consola para mostrar
el error.

## Actualizaciones futuras

En `setup.py`, aumenta `APP_VERSION`, por ejemplo de `2.0.0` a `2.0.1`.
No cambies `upgrade_code`, porque identifica la misma aplicación ante Windows.

## Nota sobre cx_Freeze

cx_Freeze en Windows genera una carpeta con el EXE y sus dependencias. El MSI
instala todos esos archivos; no es un único EXE autocontenido.
