/**
 * ============================================================================
 * GOOGLE APPS SCRIPT — WEBHOOK RECEPTOR DE ANEXO 17 (PELLÍZCATE)
 * PROYECTO: PROJ-006 Digitalizador Móvil de Fichas y Tests PWA
 * AUTORÍA: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect
 * ============================================================================
 * 
 * INSTRUCCIONES DE INSTALACIÓN EN TU GOOGLE SHEET:
 * 1. Abre tu Google Sheet creado para el Anexo 17.
 * 2. En el menú superior, haz clic en: Extensiones -> Apps Script.
 * 3. Borra todo el código que aparezca en el editor (Código.gs).
 * 4. Pega TODO este código completo.
 * 5. Haz clic en el icono de Guardar (disquete).
 * 6. Haz clic en el botón azul superior "Implementar" -> "Nueva implementación".
 * 7. En el icono de engranaje (⚙️ Seleccionar tipo), elige: "Aplicación web".
 * 8. Configura los siguientes campos:
 *    - Descripción: Webhook Anexo 17 PWA
 *    - Ejecutar como: "Yo" (tu cuenta de correo)
 *    - Quién tiene acceso: "Cualquier usuario" (Anyone)  <--- ¡MUY IMPORTANTE!
 * 9. Haz clic en "Implementar" y autoriza los permisos si te los solicita.
 * 10. Copia la "URL de la aplicación web" generada (termina en /exec) y pégala
 *     en el archivo .env de tu proyecto como:
 *     GOOGLE_APPS_SCRIPT_URL_ANEXO17=https://script.google.com/macros/s/.../exec
 * ============================================================================
 */

// 16 Encabezados canónicos de Google Sheets para Anexo 17
const ENCABEZADOS_ANEXO17 = [
  "Marca temporal",
  "TIPO DE EVALUACIÓN",
  "NOMBRE",
  "MUNICIPIO",
  "FECHA",
  "EDAD",
  "1. ¿QUÉ ES UN PROYECTO DE VIDA?",
  "2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?",
  "3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?",
  "4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?",
  "5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?",
  "6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?",
  "7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?",
  "8. ¿QUÉ ES UNA RED DE APOYO?",
  "9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?",
  "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:"
];

/**
 * Receptor HTTP POST: Invocado por FastAPI en modo inmediato o por la cola batch de la PWA.
 */
function doPost(e) {
  const lock = LockService.getScriptLock();
  // Esperar hasta 30 segundos por concurrencia para evitar colisiones de filas
  try {
    lock.waitLock(30000);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "Bloqueo por concurrencia. El servidor de Google Sheets está ocupado."
    })).setMimeType(ContentService.MimeType.JSON);
  }

  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "No se recibieron datos en el cuerpo POST."
      })).setMimeType(ContentService.MimeType.JSON);
    }

    const payload = JSON.parse(e.postData.contents);
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // Determinar pestaña destino: 'PRE-TEST' o 'POST-TEST'
    let tabDestino = (payload.tab || payload.sheet_name || payload.hoja || "PRE-TEST").trim().toUpperCase();
    if (tabDestino.indexOf("POST") !== -1 || tabDestino.indexOf("POS") !== -1) {
      tabDestino = "POST-TEST";
    } else {
      tabDestino = "PRE-TEST";
    }

    // Obtener o auto-crear la pestaña si aún no existe
    let sheet = ss.getSheetByName(tabDestino);
    if (!sheet) {
      sheet = ss.insertSheet(tabDestino);
      inicializarPestana(sheet);
    } else if (sheet.getLastRow() === 0) {
      inicializarPestana(sheet);
    }

    // Extraer fila de datos
    let fila = payload.row;
    if (!fila || !Array.isArray(fila)) {
      if (payload.data && typeof payload.data === "object") {
        fila = ENCABEZADOS_ANEXO17.map(function(h) {
          return payload.data[h] || "";
        });
      } else {
        throw new Error("No se encontró el array 'row' ni el objeto 'data' en el payload.");
      }
    }

    // Asegurar que la primera columna tenga Marca temporal si viene vacía
    if (!fila[0] || fila[0] === "") {
      fila[0] = Utilities.formatDate(new Date(), "America/Bogota", "dd/MM/yyyy HH:mm:ss");
    }

    // =========================================================================
    // DEDUPLICACIÓN MULTI-DISPOSITIVO ATÓMICA
    // Si varios dispositivos sincronizan la misma persona o hay reintentos de red,
    // se conserva el primer registro y se evita crear filas repetidas en la hoja.
    // =========================================================================
    const lastRow = sheet.getLastRow();
    const nombreCandidato = normalizarTextoParaComparar(fila[2]);

    if (lastRow > 1 && nombreCandidato !== "" && nombreCandidato !== "SIN NOMBRE") {
      // Columna 3 (C) es el NOMBRE del participante
      const rangoNombres = sheet.getRange(2, 3, lastRow - 1, 1).getValues();
      for (let i = 0; i < rangoNombres.length; i++) {
        const nombreExistente = normalizarTextoParaComparar(rangoNombres[i][0]);
        if (nombreExistente === nombreCandidato) {
          const filaExistenteIndex = i + 2;
          return ContentService.createTextOutput(JSON.stringify({
            status: "success",
            deduplicated: true,
            message: "Registro ya existente en Google Sheets para '" + fila[2] + "' (" + tabDestino + "). Deduplicado exitosamente.",
            tab: tabDestino,
            row_index: filaExistenteIndex,
            participante: fila[2] || ""
          })).setMimeType(ContentService.MimeType.JSON);
        }
      }
    }

    // Insertar la fila al final de la pestaña si no existía
    sheet.appendRow(fila);
    SpreadsheetApp.flush();

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      deduplicated: false,
      message: "Registro insertado exitosamente en Google Sheets (" + tabDestino + ")",
      tab: tabDestino,
      row_index: sheet.getLastRow(),
      participante: fila[2] || ""
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString(),
      stack: error.stack
    })).setMimeType(ContentService.MimeType.JSON);

  } finally {
    lock.releaseLock();
  }
}

/**
 * Normaliza cadenas de texto para comparaciones robustas e insensibles a tildes o puntuación.
 */
function normalizarTextoParaComparar(txt) {
  if (!txt) return "";
  var s = txt.toString().trim().toUpperCase();
  s = s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  s = s.replace(/[^A-Z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
  return s;
}

/**
 * Receptor HTTP GET: Permite validar que el webhook está en línea desde el navegador.
 */
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "online",
    modulo: "Anexo 17 — Pellízcate con Generación B+",
    municipio_objetivo: "SANTA CATALINA",
    pestanas_soportadas: ["PRE-TEST", "POST-TEST"],
    deduplicacion_atomica: true,
    total_columnas: ENCABEZADOS_ANEXO17.length,
    fecha_servidor: Utilities.formatDate(new Date(), "America/Bogota", "dd/MM/yyyy HH:mm:ss")
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Inicializa una pestaña con los 16 encabezados oficiales, diseño corporativo e inmovilización.
 */
function inicializarPestana(sheet) {
  sheet.getRange(1, 1, 1, ENCABEZADOS_ANEXO17.length).setValues([ENCABEZADOS_ANEXO17]);
  
  // Estilo editorial: Fondo Púrpura Corporativo, texto blanco negrita
  const headerRange = sheet.getRange(1, 1, 1, ENCABEZADOS_ANEXO17.length);
  headerRange.setBackground("#581c87"); // Púrpura oscuro elegante
  headerRange.setFontColor("#ffffff");
  headerRange.setFontWeight("bold");
  headerRange.setFontFamily("Arial");
  headerRange.setFontSize(10);
  headerRange.setHorizontalAlignment("center");
  headerRange.setVerticalAlignment("middle");
  headerRange.setWrap(true);
  
  sheet.setRowHeight(1, 45);
  sheet.setFrozenRows(1);
}

/**
 * Función de prueba manual para ejecutar dentro del editor de Apps Script.
 * Haz clic en "Ejecutar" para verificar que las pestañas PRE-TEST y POST-TEST se crean con éxito.
 */
function probarInsercionManual() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Probar PRE-TEST
  let sheetPre = ss.getSheetByName("PRE-TEST");
  if (!sheetPre) {
    sheetPre = ss.insertSheet("PRE-TEST");
  }
  inicializarPestana(sheetPre);

  // 2. Probar POST-TEST
  let sheetPost = ss.getSheetByName("POST-TEST");
  if (!sheetPost) {
    sheetPost = ss.insertSheet("POST-TEST");
  }
  inicializarPestana(sheetPost);

  Logger.log("¡Prueba exitosa! Pestañas PRE-TEST y POST-TEST inicializadas con los 16 encabezados.");
}
