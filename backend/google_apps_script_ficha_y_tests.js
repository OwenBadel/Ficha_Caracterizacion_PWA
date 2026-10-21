/**
 * ============================================================================
 * GOOGLE APPS SCRIPT — WEBHOOK RECEPTOR DE FICHA (ANEXO 10) Y PRE/POST TEST (ANEXO 4)
 * PROYECTO: PROJ-006 Digitalizador Móvil de Fichas y Tests PWA
 * AUTORÍA: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect
 * ============================================================================
 * 
 * INSTRUCCIONES DE INSTALACIÓN EN TU GOOGLE SHEET PRINCIPAL:
 * 1. Abre tu Google Sheet conectado para Fichas y Anexo 4.
 * 2. En el menú superior, haz clic en: Extensiones -> Apps Script.
 * 3. Borra todo el código que aparezca en el editor (Código.gs).
 * 4. Pega TODO este código completo.
 * 5. Haz clic en el icono de Guardar (disquete).
 * 6. Haz clic en el botón azul superior "Implementar" -> "Nueva implementación".
 * 7. En el icono de engranaje (⚙️ Seleccionar tipo), elige: "Aplicación web".
 * 8. Configura los siguientes campos:
 *    - Descripción: Webhook Fichas y Anexo 4 PWA
 *    - Ejecutar como: "Yo" (tu cuenta de correo)
 *    - Quién tiene acceso: "Cualquier usuario" (Anyone)  <--- ¡MUY IMPORTANTE!
 * 9. Haz clic en "Implementar" y autoriza los permisos si te los solicita.
 * 10. Copia la "URL de la aplicación web" generada (termina en /exec) y pégala
 *     en el archivo .env de tu proyecto como:
 *     GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/.../exec
 * ============================================================================
 */

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    // Esperar hasta 30 segundos por el lock para sincronizaciones concurrentes
    lock.waitLock(30000);
  } catch (lockError) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "Servidor ocupado. Bloqueo de concurrencia activo (LockService timeout 30s). Reintenta en breves segundos."
    })).setMimeType(ContentService.MimeType.JSON);
  }

  try {
    let payload;
    if (e.postData && e.postData.contents) {
      payload = JSON.parse(e.postData.contents);
    } else if (e.parameter) {
      payload = e.parameter;
    } else {
      throw new Error("Petición vacía sin cuerpo JSON ni parámetros POST.");
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const tabDestino = payload.tab || payload.sheet_name || payload.hoja || "Respuestas de formulario 1";
    const tipoRegistro = String(payload.tipo || "ficha").toLowerCase();

    // Obtener la pestaña de destino
    let sheet = ss.getSheetByName(tabDestino);
    if (!sheet) {
      sheet = ss.insertSheet(tabDestino);
      if (payload.headers && Array.isArray(payload.headers)) {
        sheet.appendRow(payload.headers);
        SpreadsheetApp.flush();
      }
    }

    // Extraer fila de datos
    let fila = payload.row;
    if (!fila || !Array.isArray(fila)) {
      if (payload.data && typeof payload.data === "object") {
        if (payload.headers && Array.isArray(payload.headers)) {
          fila = payload.headers.map(function(h) { return payload.data[h] || ""; });
        } else {
          fila = Object.values(payload.data);
        }
      } else {
        throw new Error("No se encontró el array 'row' ni el objeto 'data' en el payload.");
      }
    }

    // Asegurar que la primera columna tenga Marca temporal si viene vacía
    if (!fila[0] || fila[0] === "") {
      fila[0] = Utilities.formatDate(new Date(), "America/Bogota", "dd/MM/yyyy HH:mm:ss");
    }

    const lastRow = sheet.getLastRow();

    // =========================================================================
    // DEDUPLICACIÓN MULTI-DISPOSITIVO ATÓMICA
    // =========================================================================
    if (lastRow > 1) {
      // 1. MÓDULO FICHA (ANEXO 10): Deduplicación por Documento y por Nombre
      if (tipoRegistro === "ficha") {
        // En Ficha con Marca temporal: Columna 6 = Documento, Columna 4 = Nombre
        const colDocIdx = 6;
        const colNomIdx = 4;
        const docCandidato = normalizarDocParaComparar(payload.documento || (fila.length >= colDocIdx ? fila[colDocIdx - 1] : ""));
        const nomCandidato = normalizarTextoParaComparar(payload.nombre || (fila.length >= colNomIdx ? fila[colNomIdx - 1] : ""));

        // Deduplicación por Documento
        if (docCandidato && docCandidato !== "SINDOCUMENTO" && docCandidato !== "0") {
          const rangoDocs = sheet.getRange(2, colDocIdx, lastRow - 1, 1).getValues();
          for (let i = 0; i < rangoDocs.length; i++) {
            const docExistente = normalizarDocParaComparar(rangoDocs[i][0]);
            if (docExistente === docCandidato) {
              return ContentService.createTextOutput(JSON.stringify({
                status: "success",
                deduplicated: true,
                message: "Ficha con documento '" + (fila[colDocIdx - 1] || docCandidato) + "' ya existe en Google Sheets (" + tabDestino + "). Deduplicado exitosamente.",
                tab: tabDestino,
                row_index: i + 2,
                documento: docCandidato
              })).setMimeType(ContentService.MimeType.JSON);
            }
          }
        }

        // Deduplicación por Nombre Completo (ÚNICAMENTE si no tiene documento de identidad válido, permitiendo homónimos reales)
        if ((!docCandidato || docCandidato === "SINDOCUMENTO" || docCandidato === "0") && nomCandidato && nomCandidato !== "SINNOMBRE") {
          const rangoNoms = sheet.getRange(2, colNomIdx, lastRow - 1, 1).getValues();
          for (let i = 0; i < rangoNoms.length; i++) {
            const nomExistente = normalizarTextoParaComparar(rangoNoms[i][0]);
            if (nomExistente === nomCandidato) {
              return ContentService.createTextOutput(JSON.stringify({
                status: "success",
                deduplicated: true,
                message: "Ficha para '" + (fila[colNomIdx - 1] || nomCandidato) + "' ya existe en Google Sheets (" + tabDestino + "). Deduplicado exitosamente.",
                tab: tabDestino,
                row_index: i + 2,
                participante: nomCandidato
              })).setMimeType(ContentService.MimeType.JSON);
            }
          }
        }

      // 2. MÓDULO ANEXO 4 (PRE/POST TEST) Y ANEXO 17: Deduplicación por Nombre en Pestaña
      } else if (tipoRegistro.indexOf("test") !== -1 || tipoRegistro.indexOf("anexo") !== -1) {
        // En Test: Columna 3 = Nombre del participante
        const colNomTest = 3;
        const nomCandidato = normalizarTextoParaComparar(payload.nombre || payload.participante || (fila.length >= colNomTest ? fila[colNomTest - 1] : ""));

        if (nomCandidato && nomCandidato !== "SINNOMBRE") {
          const rangoNoms = sheet.getRange(2, colNomTest, lastRow - 1, 1).getValues();
          for (let i = 0; i < rangoNoms.length; i++) {
            const nomExistente = normalizarTextoParaComparar(rangoNoms[i][0]);
            if (nomExistente === nomCandidato) {
              return ContentService.createTextOutput(JSON.stringify({
                status: "success",
                deduplicated: true,
                message: "Test para '" + (fila[colNomTest - 1] || nomCandidato) + "' ya existe en Google Sheets (" + tabDestino + "). Deduplicado exitosamente.",
                tab: tabDestino,
                row_index: i + 2,
                participante: nomCandidato
              })).setMimeType(ContentService.MimeType.JSON);
            }
          }
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
      row_index: sheet.getLastRow()
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

function normalizarTextoParaComparar(texto) {
  if (!texto) return "";
  return String(texto)
    .trim()
    .toUpperCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Z0-9]/g, "");
}

function normalizarDocParaComparar(doc) {
  if (!doc) return "";
  return String(doc)
    .trim()
    .toUpperCase()
    .replace(/[^0-9A-Z]/g, "");
}
