# 📱 PROJ-006: Digitalizador Móvil de Fichas de Caracterización (PWA + Google Gemini + Google Sheets)
**Autoría y Diseño:** Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.

Aplicación Web Progresiva (**PWA Mobile-First**) diseñada para digitalizar en campo "Fichas de Caracterización" físicas y evaluaciones "Pre/Post Test (Anexo 4)" mediante fotografías asistidas, extraer variables con IA de Visión de Alta Fidelidad (**Google Gemini `gemini-2.5-flash`** con Rate Limiter de seguridad) con normalización estricta a **MAYÚSCULAS**, auto-orientación vertical inteligente de capturas, reconciliación fonética/caligráfica con **Jaro-Winkler** contra el **PATRÓN MAESTRO**, e inserción automática de cada registro como fila ordenada en **Google Sheets**.

---

## 🌟 Características Principales

* 📱 **Mobile-First & PWA:** Diseñada para navegador de celular y configurable como app nativa ("Añadir a pantalla de inicio"). Carga ultrarrápida y soporte offline mediante Service Worker.
* 🧠 **IA de Visión de Alta Precisión (Google Gemini):** Extracción OCR multimodal de máxima fidelidad con `gemini-2.5-flash` y limitador de tasa (`PipelineRateLimiter`) para evitar cuellos de botella y saturación HTTP 429.
* 🎯 **Algoritmo Jaro-Winkler con Bonificación Territorial:** Reconcilia nombres escritos a mano con variaciones ortográficas ("MAIKOL PEREZ" -> "MICHAEL STEVEN PEREZ", inversión de apellidos, etc.) comparándolos con el **PATRÓN MAESTRO** de los 10 municipios. Estandariza de forma automática e instantánea: **Nombre del participante, Edad, Municipio y EPS**.
* 📋 **Ingesta del PATRÓN MAESTRO:** Sincronización automática directa desde la pestaña `PATRON MAESTRO` de Google Sheets o mediante archivo local (`.xlsx` o `.csv`).
* 📸 **Captura Guiada y Auto-Orientación Vertical:** Disparador ergonómico con corrección inteligente de orientación: si una foto es tomada en horizontal, se transforma automáticamente a vertical con nitidez fotográfica y botones de rotación manual.
* 📝 **Arquitectura Multimódulo Tripartita (Fichas, Anexo 4 y Anexo 17):**
  1. **Ficha de Caracterización:** Captura dual (Anverso y Reverso), 43 variables normalizadas.
  2. **Anexo 4 (SSR ITS):** Hoja única, 9 preguntas dicotómicas y selección de prevención, enrutamiento a `PRE-TEST` y `POST-TEST`.
  3. **Anexo 17 (Pellízcate con Generación B+):** Hoja única, 10 preguntas de opción múltiple (a, b, c) de proyecto de vida y derechos, enrutamiento a `PRE-TEST` y `POST-TEST` con Google Sheets independiente.
* ⚡ **Modo Inmediato:** Envía automáticamente las fotos al motor de visión y sube los datos a Google Sheets al instante.
* 📦 **Modo Cola (Offline-First / Batch):** Almacena las fotos y encuestas localmente en el dispositivo (**IndexedDB**), permitiendo continuar capturando y sincronizar todo en lote al recuperar conexión.
* 📊 **Google Sheets API v4 Automatizado:** Inserta directamente en la hoja de cálculo usando Webhook oficial de Google Apps Script con tiempo de espera extendido (65s) y cola de contingencia local.

---

## 📂 Estructura del Proyecto

```text
PROJ_006_Ficha_Caracterizacion_PWA/
├── AGENTS.md                   # Directiva maestra del proyecto
├── README.md                   # Esta documentación completa
├── requirements.txt            # Dependencias Python
├── INICIAR_APP.bat             # Lanzador interactivo directo con detección de Python
├── .env.example                # Plantilla de variables de entorno
├── .env                        # Variables locales configuradas
├── backend/
│   ├── __init__.py
│   ├── schema.py               # Modelo Pydantic y 43 columnas canónicas de la Ficha
│   ├── schema_test.py          # Modelo Pydantic para Pre-Test / Post-Test (Anexo 4 SSR ITS)
│   ├── schema_anexo17.py       # Modelo Pydantic para Anexo 17 (Pellízcate con Generación B+)
│   ├── participant_cache.py    # Memoria viva, Jaro-Winkler tokenizado y Patrón Maestro
│   ├── vision_service.py       # Extracción multimodal con Google Gemini y Rate Limiter
│   ├── sheets_service.py       # Inserción en Google Sheets vía Webhook Apps Script
│   └── main.py                 # Servidor FastAPI y entrega de la PWA estática
├── frontend/
│   ├── index.html              # Interfaz de usuario Mobile-First (Selector tripartito)
│   ├── manifest.json           # Manifiesto PWA para instalación
│   ├── sw.js                   # Service Worker para funcionamiento offline
│   ├── css/
│   │   └── styles.css          # Diseño Dark Glassmorphism, ergonomía táctil (≥44px)
│   └── js/
│       ├── db.js               # Persistencia local con IndexedDB (cola offline multimódulo)
│       └── app.js              # Lógica de interfaz, cámara, auto-orientación y sincronización
└── tests/                      # Suite de pruebas automatizadas (31 tests verdes)
    ├── run_all_tests.py        # Ejecutor maestro de pruebas
    ├── test_schema.py          # Pruebas de validación de Ficha
    ├── test_test_schema.py     # Pruebas de Anexo 4 y Patrón Maestro
    ├── test_anexo17_schema.py  # Pruebas de Anexo 17 (Pellízcate)
    ├── test_image_orientation.py # Pruebas de rotación y visión
    └── test_audit_fixes.py     # Pruebas de robustez y concurrencia
```

---

## ⚙️ Guía de Configuración y Uso

### 1. Variables de Entorno (`.env`)

En el archivo `.env` en la raíz del proyecto:
```env
# Proveedor de Visión OCR de Alta Precisión (Google Gemini)
VISION_PROVIDER=gemini
GEMINI_API_KEY=tu_gemini_api_key_aqui
GEMINI_MODEL=gemini-2.5-flash
GEMINI_MIN_INTERVAL_SECONDS=2.0

# Patrón Maestro (Google Sheets)
# Pega aquí el ID de tu hoja de cálculo (lo que está entre /d/ y /edit en la URL)
GOOGLE_SHEET_ID=tu_google_sheet_id_aqui
GOOGLE_SHEET_TAB_PATRON_MAESTRO=PATRON MAESTRO

# Google Sheets Webhooks
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
GOOGLE_APPS_SCRIPT_URL_TESTS=https://script.google.com/macros/s/.../exec
GOOGLE_SHEET_TAB=Respuestas
GOOGLE_SHEET_TAB_TESTS=Pre_Post_Test
```

### 2. Estructura de Columnas de `PATRON MAESTRO`

El sistema lee las columnas de la pestaña `PATRON MAESTRO` automáticamente:
1. Marca temporal
2. NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA
3. TERRITORIO (Municipio)
4. **Nombre completo del participante** *(Mapeado a Nombre)*
5. Tipo de documento identidad
6. **Numero de documento identidad** *(Mapeado a Documento)*
7. **Edad** *(Mapeado a Edad)*
8. Grado escolar
9. Teléfono de contacto
10. Dirección de residencia (barrio o vereda)
11. **Municipio** *(Mapeado a Municipio)*
12. Zona
13. **EPS (si tienes)** *(Mapeado a EPS / EAPB)*

### 3. Iniciar la Aplicación

Simplemente haz doble clic en `INICIAR_APP.bat`.
El script:
1. Detecta automáticamente la instalación de Python en el sistema.
2. Inicia el servidor FastAPI en el puerto `8000`.
3. Muestra la URL para abrir en tu PC (`http://localhost:8000`) y en tu Celular en la misma red Wi-Fi (`http://192.168.x.x:8000`).

---

## 🧪 Pruebas Unitarias

Para ejecutar toda la suite de pruebas automatizadas:
```bash
python tests/run_all_tests.py
```
Todas las 24 pruebas (orientación vertical, modelo Google Gemini, esquema Pydantic, reconciliación Jaro-Winkler, ruteo de pestañas y concurrencia) están verificadas en verde.
