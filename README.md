# 📱 PROJ-006: Digitalizador Móvil de Fichas de Caracterización (PWA + IA Visión + Google Sheets)

Aplicación Web Progresiva (**PWA Mobile-First**) diseñada para digitalizar en campo "Fichas de Caracterización" físicas mediante dos fotografías (Anverso y Reverso), extraer 43 variables con IA de Visión (Gemini 2.0/1.5 Flash o GPT-4o) con normalización estricta a **MAYÚSCULAS**, e insertar automáticamente cada registro como una fila ordenada en **Google Sheets**.

---

## 🌟 Características Principales

* 📱 **Mobile-First & PWA:** Diseñada para navegador de celular y configurable como app nativa ("Añadir a pantalla de inicio"). Carga ultrarrápida y soporte offline mediante Service Worker.
* 📸 **Captura Guiada en 2 Pasos:** Disparador gigante que activa la cámara del celular (`capture="environment"`). Guía al encuestador: *Foto 1 (Anverso)* ➔ *Foto 2 (Reverso)*. Permite previsualizar y repetir cualquier foto si sale borrosa.
* ⚡ **Modo Inmediato:** Envía automáticamente ambas fotos a la IA y sube los datos a Google Sheets al instante.
* 📦 **Modo Cola (Offline-First / Batch):** Almacena las fotos y encuestas localmente en el dispositivo (**IndexedDB**). Cuenta las encuestas pendientes, permite revisarlas en un drawer visual y sincronizarlas todas juntas al volver a tener buena conexión ("🚀 Sincronizar Todas Ahora").
* 🧠 **IA de Visión Multimodal (OCR Estricto):** Convierte todo a mayúsculas, interpreta checkboxes marcados con "X", deja campos vacíos como `""` y retorna exactamente las 43 columnas requeridas.
* 📊 **Google Sheets API v4 Automatizado:** Inserta directamente en la hoja de cálculo usando Service Account oficial (o Webhook de Google Apps Script), creando los encabezados automáticamente si la hoja está vacía.

---

## 📂 Estructura del Proyecto

```text
PROJ_006_Ficha_Caracterizacion_PWA/
├── AGENTS.md                   # Directiva maestra del proyecto en la Fábrica
├── README.md                   # Esta guía completa
├── requirements.txt            # Dependencias Python
├── .env.example                # Plantilla de variables de entorno
├── .env                        # Variables locales configuradas
├── backend/
│   ├── __init__.py
│   ├── schema.py               # Modelo Pydantic y 43 columnas canónicas
│   ├── vision_service.py       # Extracción con Gemini / OpenAI GPT-4o
│   ├── sheets_service.py       # Inserción en Google Sheets con Service Account
│   └── main.py                 # Servidor FastAPI y entrega de la PWA estática
└── frontend/
    ├── index.html              # Interfaz de usuario Mobile-First
    ├── manifest.json           # Manifiesto PWA para instalación
    ├── sw.js                   # Service Worker para funcionamiento offline
    ├── css/
    │   └── styles.css          # Diseño Dark Glassmorphism, micro-animaciones
    └── js/
        ├── db.js               # Persistencia local con IndexedDB (cola offline)
        └── app.js              # Lógica de interfaz, cámara y sincronización
```

---

## ⚙️ Guía de Configuración Paso a Paso

### 1. Requisitos Previos e Instalación

1. Asegúrate de tener Python 3.10 o superior instalado.
2. Abre una terminal en la carpeta del proyecto y crea un entorno virtual (opcional pero recomendado):
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   ```
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

---

### 2. Configurar la IA de Visión (Google Gemini u OpenAI)

La app viene preconfigurada para usar **Google Gemini 2.0 Flash / 1.5 Flash** (rápido, económico y con excelente precisión para tablas y casillas en español).

En el archivo `.env`:
```env
VISION_PROVIDER=gemini
GEMINI_API_KEY=tu_clave_de_google_ai_studio
GEMINI_MODEL=gemini-2.0-flash
```

*(Si deseas usar OpenAI, coloca `VISION_PROVIDER=openai`, `OPENAI_API_KEY=tu_clave` y `OPENAI_MODEL=gpt-4o`).*

---

### 3. Configurar Google Sheets (Método Oficial: Service Account)

Este es el método recomendado para producción:

1. **Crear Proyecto en Google Cloud:**
   * Ve a [Google Cloud Console](https://console.cloud.google.com/).
   * Crea un nuevo proyecto (ej. `Ficha-Digital-Salud`).

2. **Habilitar APIs:**
   * En el menú lateral, ve a **APIs y Servicios** > **Biblioteca**.
   * Busca y **Habilita** las dos siguientes APIs:
     1. **Google Sheets API**
     2. **Google Drive API**

3. **Crear Cuenta de Servicio (Service Account):**
   * Ve a **APIs y Servicios** > **Credenciales**.
   * Haz clic en **Crear Credenciales** > **Cuenta de servicio**.
   * Asigna un nombre (ej. `sheets-writer`) y haz clic en **Crear y Continuar**.
   * En el rol, selecciona **Editor** (o Básico > Editor). Finaliza el asistente.

4. **Descargar la Llave JSON:**
   * En la lista de Cuentas de Servicio, haz clic en la cuenta que acabas de crear.
   * Ve a la pestaña **Claves** (Keys) > **Agregar clave** > **Crear clave nueva**.
   * Selecciona formato **JSON** y descárgala.
   * Renombra ese archivo como `credentials.json` y colócalo en la raíz de `PROJ_006_Ficha_Caracterizacion_PWA/credentials.json`.

5. **Compartir tu Google Sheet con la Cuenta de Servicio:**
   * Abre tu hoja de cálculo en Google Sheets (o crea una nueva).
   * Haz clic en el botón verde **Compartir** (Share) en la esquina superior derecha.
   * Pega el correo electrónico de la cuenta de servicio (ejemplo: `sheets-writer@tu-proyecto.iam.gserviceaccount.com`).
   * Asígnale permisos de **Editor** y guarda.

6. **Configurar el ID en el `.env`:**
   * Mira la URL de tu hoja de cálculo:
     `https://docs.google.com/spreadsheets/d/1BxiMVs0XRrE...tu_id_aqui...4Q/edit`
   * Copia esa cadena de caracteres y ponla en tu `.env`:
     ```env
     GOOGLE_SHEET_ID=1BxiMVs0XRrE...tu_id_aqui...4Q
     GOOGLE_SHEET_TAB=Respuestas
     GOOGLE_APPLICATION_CREDENTIALS=credentials.json
     ```

---

### 4. (Alternativa) Webhook con Google Apps Script

Si prefieres no crear una Service Account de Google Cloud, puedes usar un script Webhook:

1. En tu Google Sheet, ve a **Extensiones** > **Apps Script**.
2. Pega el siguiente código:
   ```javascript
   function doPost(e) {
     var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
     var data = JSON.parse(e.postData.contents);
     
     if (sheet.getLastRow() === 0 && data.headers) {
       sheet.appendRow(data.headers);
     }
     if (data.row) {
       sheet.appendRow(data.row);
     }
     return ContentService.createTextOutput(JSON.stringify({status: "ok"}))
       .setMimeType(ContentService.MimeType.JSON);
   }
   ```
3. Haz clic en **Implementar** > **Nueva implementación** > Tipo: **Aplicación web**.
4. En *"Quién tiene acceso"*, selecciona **Cualquier usuario (Anyone)**.
5. Copia la URL de la aplicación web y ponla en `.env`:
   ```env
   GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
   ```

---

## 🚀 Cómo Ejecutar y Usar la Aplicación

### 1. Iniciar el Servidor
Ejecuta en tu terminal:
```bash
python backend/main.py
```
O directamente con Uvicorn:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

El servidor arrancará en `http://localhost:8000`.

### 2. Abrir desde el Celular
1. Asegúrate de que tu celular y tu computadora estén conectados a la **misma red Wi-Fi**.
2. En tu PC, abre una terminal y escribe `ipconfig` para conocer tu dirección IPv4 (por ejemplo, `192.168.1.45`).
3. Abre Chrome o Safari en tu celular y entra a:
   `http://192.168.1.45:8000`
4. En el menú del navegador, selecciona **"Agregar a la pantalla principal"** o **"Instalar aplicación"** para disfrutar de la experiencia PWA a pantalla completa sin barra de navegación.

---

## 📋 Lista de las 43 Columnas Extraídas

Cada fila insertada en Google Sheets contiene exactamente en este orden:

| # | Nombre de Columna |
|---|-------------------|
| 1 | `NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA` |
| 2 | `TERRITORIO` |
| 3 | `Nombre completo del participante` |
| 4 | `Tipo de documento identidad` |
| 5 | `Numero de documento identidad` |
| 6 | `Edad` |
| 7 | `Grado escolar` |
| 8 | `Teléfono de contacto` |
| 9 | `Dirección de residencia (barrio o vereda)` |
| 10 | `Municipio` |
| 11 | `Zona` |
| 12 | `EPS (si tienes)` |
| 13 | `Régimen` |
| 14 | `Sexo con el que te identificas` |
| 15 | `Identidad de género` |
| 16 | `¿Perteneces a alguna población o grupo étnico?` |
| 17 | `¿Tienes alguna condición de discapacidad?` |
| 18 | `¿Cual?` |
| 19 | `¿Tienes antecedentes de alguna enfermedad personal o familiar importante?` |
| 20 | `¿Cual?_1` |
| 21 | `¿Has asistido al médico en el último año?` |
| 22 | `¿Cuándo fue la última vez?` |
| 23 | `¿Fuiste al odontólogo el último año?` |
| 24 | `¿Qué actividades recreativas haces en tu tiempo libre?` |
| 25 | `¿Qué tiempo empleas en esta actividad?` |
| 26 | `¿Consumes o has consumido cigarrillo o vapeador?` |
| 27 | `Cada cuánto?` |
| 28 | `¿Consumes o has consumido alcohol?` |
| 29 | `Cada cuánto?_1` |
| 30 | `¿Has consumido alguna sustancia psicoactiva?` |
| 31 | `¿Cual?_2` |
| 32 | `¿Has vivido situaciones de discriminación, rechazo o violencia?` |
| 33 | `¿Has recibido información sobre salud sexual, ITS o métodos de prevención?` |
| 34 | `¿Has iniciado tu vida sexual?` |
| 35 | `Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?` |
| 36 | `¿Conoces algún método anticonceptico?` |
| 37 | `¿Cual?_3` |
| 38 | `¿Has vivido o conoces algún caso cercano de embarazo adolescente?` |
| 39 | `¿Te han entregado preservativos en la EPS o institución de salud?` |
| 40 | `¿Cuándo fue la ultima vez?` |
| 41 | `¿Qué tema te gustaria aprender o entender mejor?` |
| 42 | `¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?` |
| 43 | `¿Por que?` |
