"""
Servidor API REST FastAPI para el Digitalizador de Fichas de Caracterización.
Expone endpoints de procesamiento con Visión Artificial y subida a Google Sheets,
además de servir la aplicación PWA frontend en modo Mobile-First.
"""

from __future__ import annotations
import os
import sys
import json
import logging
import asyncio
import hashlib
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from starlette.concurrency import run_in_threadpool
import uvicorn
from dotenv import load_dotenv

try:
    from .schema import FichaCaracterizacion, COLUMNAS_FICHA, ENCABEZADOS_FICHA_SHEETS
    from .schema_test import PrePostTest, COLUMNAS_TEST, ENCABEZADOS_TEST_SHEETS
    from .schema_anexo17 import PrePostTestAnexo17, COLUMNAS_ANEXO17, ENCABEZADOS_ANEXO17_SHEETS
    from .vision_service import VisionService
    from .sheets_service import GoogleSheetsService
    from .vocabulary_learner import vocabulary_learner
    from .participant_cache import participant_cache
except (ImportError, ValueError):
    backend_dir = Path(__file__).resolve().parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from schema import FichaCaracterizacion, COLUMNAS_FICHA, ENCABEZADOS_FICHA_SHEETS
    from schema_test import PrePostTest, COLUMNAS_TEST, ENCABEZADOS_TEST_SHEETS
    from schema_anexo17 import PrePostTestAnexo17, COLUMNAS_ANEXO17, ENCABEZADOS_ANEXO17_SHEETS
    from vision_service import VisionService
    from sheets_service import GoogleSheetsService
    from vocabulary_learner import vocabulary_learner
    from participant_cache import participant_cache

# Configurar logging y paths
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main_api")

PROJECT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"
PENDIENTES_FILE = PROJECT_DIR / "backend" / "pendientes_sincronizacion.json"
IDEMPOTENCIA_FILE = PROJECT_DIR / "backend" / "idempotencia_cache.json"


def guardar_pendiente_local(tipo: str, fila: list, error: str):
    """Guarda una fila en contingencia local si Google Sheets tiene timeout."""
    try:
        data = []
        if PENDIENTES_FILE.exists():
            try:
                data = json.loads(PENDIENTES_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = []
        data.append({
            "timestamp": datetime.now().isoformat(),
            "tipo": tipo,
            "fila": fila,
            "error": error
        })
        PENDIENTES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Registro ({tipo}) salvaguardado en contingencia local: {PENDIENTES_FILE}")
    except Exception as e:
        logger.error(f"Error guardando pendiente local: {e}")


# =========================================================================
# CONTROL DE CONCURRENCIA MULTI-DISPOSITIVO & DEDUPLICACIÓN
# Garantiza que múltiples teléfonos mandando a cola simultáneamente se encolen
# ordenadamente sin colapsar cuotas de Gemini ni saturar Google Sheets.
# =========================================================================
GEMINI_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(2)  # Máximo 2 llamadas de visión simultáneas
SHEETS_WRITE_SEMAPHORE = asyncio.Semaphore(1)        # Escritura estrictamente serializada y atómica

IDEMPOTENCY_CACHE: Dict[str, Dict[str, Any]] = {}
IDEMPOTENCY_CACHE_MAX = 3000
ACTIVE_TASKS: Dict[str, asyncio.Event] = {}
ACTIVE_RESULTS: Dict[str, Dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()


def cargar_idempotencia_disco():
    """Carga el historial de idempotencia persistido en disco al iniciar el servidor."""
    global IDEMPOTENCY_CACHE
    if IDEMPOTENCIA_FILE.exists():
        try:
            data = json.loads(IDEMPOTENCIA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                with _CACHE_LOCK:
                    IDEMPOTENCY_CACHE.update(data)
                logger.info(f"Caché de idempotencia cargado desde disco: {len(IDEMPOTENCY_CACHE)} entradas.")
        except Exception as e:
            logger.warning(f"Error cargando idempotencia desde disco: {e}")


def guardar_idempotencia_disco():
    """Persiste en disco el historial de idempotencia para sobrevivir a reinicios."""
    try:
        with _CACHE_LOCK:
            copia = dict(list(IDEMPOTENCY_CACHE.items())[-IDEMPOTENCY_CACHE_MAX:])
        IDEMPOTENCIA_FILE.write_text(json.dumps(copia, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Error guardando idempotencia en disco: {e}")


# Cargar inmediatamente en tiempo de importación
cargar_idempotencia_disco()

load_dotenv(PROJECT_DIR / ".env")

app = FastAPI(
    title="Digitalizador de Fichas de Caracterización y Tests PWA",
    description="Backend de extracción multimodal con IA de Visión para Fichas y Pre/Post Tests, y sincronización en Google Sheets.",
    version="2.0.0"
)

# Permitir CORS amplio para dispositivos móviles y PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar servicios
vision_service = VisionService()
sheets_service = GoogleSheetsService()


@app.on_event("startup")
async def startup_event():
    """Inicialización desatendida y verificación de estado."""
    auto_sync = os.getenv("AUTO_SYNC_ON_STARTUP", "false").lower() == "true"
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if auto_sync and sheet_id:
        try:
            logger.info(f"Auto-sincronizando PATRON MAESTRO desde Google Sheet ID: {sheet_id}...")
            total = participant_cache.sincronizar_desde_google_sheets(sheet_id)
            logger.info(f"PATRON MAESTRO cargado en arranque: {total} registros.")
        except Exception as e:
            logger.warning(f"No se pudo sincronizar automáticamente con Google Sheets al arrancar: {e}")

    # Verificar si existe archivo local patron_maestro en el proyecto
    for candidata in [
        PROJECT_DIR / "patron_maestro.xlsx",
        PROJECT_DIR / "patron_maestro.csv",
        PROJECT_DIR / "backend" / "patron_maestro.xlsx",
        PROJECT_DIR / "backend" / "patron_maestro.csv",
    ]:
        if candidata.exists() and participant_cache.contar() == 0:
            try:
                cargados = participant_cache.sincronizar_desde_archivo_local(candidata)
                logger.info(f"PATRON MAESTRO cargado desde archivo local '{candidata.name}': {cargados} registros.")
                break
            except Exception as e:
                logger.warning(f"Error cargando archivo local '{candidata.name}': {e}")


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health_check() -> Dict[str, Any]:
    """Verifica el estado del sistema, motor Google Gemini y conexión a Google Sheets."""
    gemini_ok = bool(vision_service.gemini_api_key)
    openai_ok = bool(vision_service.openai_api_key)
    sheets_ok = bool(sheets_service._gspread_client or sheets_service.webhook_url or sheets_service.webhook_url_tests)

    return {
        "status": "online",
        "service": "Ficha Caracterización, Pre/Post Test Anexo 4 & Anexo 17 OCR",
        "vision_provider": vision_service.provider,
        "gemini_configured": gemini_ok,
        "openai_configured": openai_ok,
        "sheets_configured": sheets_ok,
        "sheets_method": "gspread_api" if sheets_service._gspread_client else ("webhook" if sheets_service.webhook_url else "none"),
        "columnas_ficha_count": len(COLUMNAS_FICHA),
        "columnas_test_count": len(COLUMNAS_TEST),
        "columnas_anexo17_count": len(COLUMNAS_ANEXO17),
        "patron_maestro_participantes": participant_cache.contar()
    }


# =====================================================================
# ENDPOINTS PARA PATRÓN MAESTRO Y COINCIDENCIA JARO-WINKLER
# =====================================================================

@app.get("/api/participants/summary")
def get_participants_summary() -> Dict[str, Any]:
    """Retorna el conteo y resumen territorial del Patrón Maestro."""
    return {
        "status": "online",
        "total": participant_cache.contar(),
        "data": participant_cache.obtener_resumen(limit=50)
    }


@app.post("/api/participants/sync-master")
async def sync_master_pattern(
    sheet_id: Optional[str] = Form(None),
    tab_name: Optional[str] = Form("PATRON MAESTRO"),
    file: Optional[UploadFile] = File(None)
) -> Dict[str, Any]:
    """
    Sincroniza la base canónica del PATRÓN MAESTRO.
    Permite subir un archivo Excel/CSV o proporcionar un Google Sheet ID.
    """
    try:
        total_cargados = 0

        # Caso 1: Archivo subido directamente
        if file and file.filename:
            contenido = await file.read()
            sufijo = Path(file.filename).suffix.lower()
            if sufijo == ".csv":
                total_cargados = participant_cache.sincronizar_desde_csv_texto(contenido.decode("utf-8", errors="replace"))
            elif sufijo in [".xlsx", ".xls"]:
                # Guardar temporalmente para parsear con pandas
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=sufijo, delete=False) as tmp:
                    tmp.write(contenido)
                    tmp_path = Path(tmp.name)
                try:
                    total_cargados = participant_cache.sincronizar_desde_archivo_local(tmp_path)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()
            else:
                raise HTTPException(status_code=400, detail="Formato de archivo no soportado. Debe ser .csv o .xlsx")

        # Caso 2: Google Sheet ID
        else:
            id_hoja = (sheet_id or os.getenv("GOOGLE_SHEET_ID", "")).strip()
            if not id_hoja:
                # Intentar buscar archivo local por defecto
                encontrado = False
                for c in [PROJECT_DIR / "patron_maestro.xlsx", PROJECT_DIR / "patron_maestro.csv"]:
                    if c.exists():
                        total_cargados = participant_cache.sincronizar_desde_archivo_local(c)
                        encontrado = True
                        break
                if not encontrado:
                    raise HTTPException(
                        status_code=400,
                        detail="Debe proporcionar un 'sheet_id' de Google Sheets o subir un archivo Excel/CSV."
                    )
            else:
                total_cargados = await run_in_threadpool(
                    participant_cache.sincronizar_desde_google_sheets,
                    sheet_id=id_hoja,
                    tab_name=tab_name or "PATRON MAESTRO"
                )

        return {
            "success": True,
            "message": f"PATRÓN MAESTRO sincronizado exitosamente con {total_cargados} registros.",
            "total_participantes": participant_cache.contar()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sincronizando PATRON MAESTRO: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error sincronizando PATRON MAESTRO: {str(e)}")


@app.post("/api/participants/test-match")
def test_participant_match(payload: Dict[str, str]) -> Dict[str, Any]:
    """Prueba la reconciliación Jaro-Winkler tokenizada para un nombre y municipio dado."""
    nombre = payload.get("nombre", "")
    municipio = payload.get("municipio", "")
    coincidencia = participant_cache.buscar_coincidencia(nombre, municipio)
    if coincidencia:
        return {
            "match_found": True,
            "query": {"nombre": nombre, "municipio": municipio},
            "reconciliado": coincidencia
        }
    return {
        "match_found": False,
        "query": {"nombre": nombre, "municipio": municipio},
        "message": "No se encontró coincidencia que supere el umbral Jaro-Winkler."
    }



@app.get("/api/columns")
def get_columns() -> Dict[str, Any]:
    """Retorna la lista exacta y ordenada de las 43 columnas y encabezados para Google Sheets."""
    return {
        "total": len(COLUMNAS_FICHA),
        "columns": COLUMNAS_FICHA,
        "headers_sheets": ENCABEZADOS_FICHA_SHEETS
    }


@app.get("/api/vocabulary")
def get_vocabulary() -> Dict[str, Any]:
    """Retorna el catálogo de términos y barrios aprendidos por el sistema."""
    return {
        "status": "online",
        "total_columns": len(vocabulary_learner.vocabulario),
        "vocabulary": vocabulary_learner.vocabulario
    }


@app.get("/api/columns-test")
def get_columns_test() -> Dict[str, Any]:
    """Retorna la lista ordenada de columnas para Pre-Test y Post-Test (Anexo 4)."""
    return {
        "total": len(COLUMNAS_TEST),
        "columns": COLUMNAS_TEST,
        "headers_sheets": ENCABEZADOS_TEST_SHEETS
    }


@app.get("/api/columns-anexo17")
def get_columns_anexo17() -> Dict[str, Any]:
    """Retorna la lista ordenada de columnas para Pre-Test y Post-Test (Anexo 17 Pellízcate)."""
    return {
        "total": len(COLUMNAS_ANEXO17),
        "columns": COLUMNAS_ANEXO17,
        "headers_sheets": ENCABEZADOS_ANEXO17_SHEETS
    }


@app.get("/api/participants")
def get_participants() -> Dict[str, Any]:
    """Retorna el resumen de participantes cargados en caché."""
    return {
        "status": "online",
        **participant_cache.obtener_resumen()
    }


def resolver_mime_imagen(f: Optional[UploadFile], fallback: str = "image/jpeg") -> str:
    """
    Resuelve el tipo MIME real de una imagen, tolerando blobs de IndexedDB
    que los navegadores móviles envían como 'application/octet-stream' o vacíos.
    """
    if not f:
        return fallback
    mime = (getattr(f, "content_type", None) or "").lower().strip()
    if mime.startswith("image/"):
        return mime
    fname = (getattr(f, "filename", None) or "").lower().strip()
    if fname.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif fname.endswith(".png"):
        return "image/png"
    elif fname.endswith(".webp"):
        return "image/webp"
    return fallback


async def _tarea_subida_sheets(
    tipo: str,
    fila: list,
    tipo_evaluacion: Optional[str] = None,
    client_keys: Optional[list] = None
):
    """Sube la fila a Google Sheets en segundo plano bajo el semáforo atómico."""
    try:
        async with SHEETS_WRITE_SEMAPHORE:
            if tipo == "ficha":
                res = await run_in_threadpool(sheets_service.insertar_encuesta, fila)
            elif tipo == "test":
                res = await run_in_threadpool(sheets_service.insertar_test, fila, tipo_evaluacion)
            elif tipo == "anexo17":
                res = await run_in_threadpool(sheets_service.insertar_anexo17, fila, tipo_evaluacion)
            else:
                res = {"success": False, "error": f"Tipo de registro desconocido: {tipo}"}

        logger.info(f"Subida asíncrona a Google Sheets ({tipo}) completada exitosamente: {res}")
        if client_keys:
            with _CACHE_LOCK:
                for ck in client_keys:
                    if ck and ck in IDEMPOTENCY_CACHE:
                        IDEMPOTENCY_CACHE[ck]["sheets_result"] = res
                        if res.get("deduplicated"):
                            IDEMPOTENCY_CACHE[ck]["deduplicated"] = True
            guardar_idempotencia_disco()

    except Exception as e:
        logger.error(f"Error en subida diferida a Google Sheets ({tipo}): {e}")
        guardar_pendiente_local(tipo, fila, str(e))


@app.post("/api/process-survey")
async def process_survey(
    background_tasks: BackgroundTasks,
    foto_anverso: UploadFile = File(..., description="Fotografía Página 1 (Anverso)"),
    foto_reverso: UploadFile = File(..., description="Fotografía Página 2 (Reverso)"),
    modo: Optional[str] = Form("inmediato", description="Modo de sincronización ('inmediato' o 'batch')"),
    client_item_id: Optional[str] = Form(None, description="Identificador único del registro en el cliente (idempotencia)")
) -> Dict[str, Any]:
    """
    Recibe las dos fotos obligatorias de la ficha, realiza extracción OCR multimodal con IA
    y registra la fila resultante en Google Sheets con control de concurrencia y deduplicación.
    """
    # 0. Verificación inmediata de Idempotencia previa en memoria / disco
    if client_item_id and client_item_id in IDEMPOTENCY_CACHE:
        cached = dict(IDEMPOTENCY_CACHE[client_item_id])
        cached["deduplicated"] = True
        cached["message"] = f"Ficha ya procesada previamente ({cached.get('participante', '')}). Deduplicado por idempotencia de dispositivo."
        logger.info(f"Idempotencia detectada para ficha client_item_id={client_item_id}. Retornando caché.")
        return cached

    mime1 = resolver_mime_imagen(foto_anverso, "image/jpeg")
    mime2 = resolver_mime_imagen(foto_reverso, "image/jpeg")

    try:
        anverso_bytes = await foto_anverso.read()
        reverso_bytes = await foto_reverso.read()

        if len(anverso_bytes) == 0 or len(reverso_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una o ambas imágenes están vacías (0 bytes)."
            )

        # 1. Clave secundaria por Hash SHA-256 de las imágenes (cero duplicación física)
        hash_img = hashlib.sha256(anverso_bytes + reverso_bytes).hexdigest()
        hash_key = f"hash_ficha_{hash_img}"

        if hash_key in IDEMPOTENCY_CACHE:
            cached = dict(IDEMPOTENCY_CACHE[hash_key])
            cached["deduplicated"] = True
            cached["message"] = f"Ficha ya procesada previamente ({cached.get('participante', '')}). Deduplicado por hash de imagen."
            logger.info(f"Idempotencia detectada por hash_key={hash_key}. Retornando resultado sin re-procesar.")
            if client_item_id:
                with _CACHE_LOCK:
                    IDEMPOTENCY_CACHE[client_item_id] = cached
                guardar_idempotencia_disco()
            return cached

        primary_key = client_item_id or hash_key

        # 2. Control de concurrencia en vuelo (evitar doble llamada mientras se procesa)
        if primary_key in ACTIVE_TASKS:
            logger.info(f"Petición concurrente detectada para '{primary_key}'. Esperando a la tarea en vuelo...")
            event = ACTIVE_TASKS[primary_key]
            await event.wait()
            cached = ACTIVE_RESULTS.get(primary_key) or IDEMPOTENCY_CACHE.get(primary_key)
            if cached:
                cached_copy = dict(cached)
                cached_copy["deduplicated"] = True
                cached_copy["message"] = "Registro procesado concurrentemente. Deduplicado por idempotencia en vuelo."
                return cached_copy

        active_event = asyncio.Event()
        ACTIVE_TASKS[primary_key] = active_event
        if hash_key != primary_key:
            ACTIVE_TASKS[hash_key] = active_event

        try:
            logger.info(f"Procesando encuesta en modo '{modo}' (Client ID={client_item_id}, Hash={hash_img[:10]}...).")

            # 3. Extracción con IA de Visión bajo semáforo
            logger.info("Encolando extracción multimodal de Ficha con IA (Semaphore)...")
            async with GEMINI_CONCURRENCY_SEMAPHORE:
                datos_dict = await run_in_threadpool(
                    vision_service.extraer_datos_ficha,
                    img_anverso_bytes=anverso_bytes,
                    img_reverso_bytes=reverso_bytes,
                    mime_type_1=mime1,
                    mime_type_2=mime2
                )

            ficha = FichaCaracterizacion.model_validate(datos_dict)
            fila_ordenada = [str(x or "").strip().upper() for x in ficha.to_ordered_row()]

            logger.info(
                f"Fila extraída con IA -> Participante='{fila_ordenada[2]}', "
                f"Doc='{fila_ordenada[4]}', Municipio='{fila_ordenada[9]}'"
            )

            # 4. Aprendizaje continuo
            try:
                await run_in_threadpool(vocabulary_learner.aprender_fila, fila_ordenada)
                await run_in_threadpool(
                    participant_cache.aprender_participante,
                    nombre=fila_ordenada[2],
                    edad=fila_ordenada[5],
                    municipio=fila_ordenada[9],
                    eapb=fila_ordenada[11],
                    documento=fila_ordenada[4]
                )
            except Exception as e:
                logger.warning(f"Aviso en aprendizaje continuo de ficha: {e}")

            # 5. Desacoplamiento de Google Sheets
            sheets_result = None
            if modo == "sincrono":
                async with SHEETS_WRITE_SEMAPHORE:
                    sheets_result = await run_in_threadpool(sheets_service.insertar_encuesta, fila_ordenada)
            else:
                guardar_pendiente_local("ficha_en_cola", fila_ordenada, "Encolado para subida asíncrona")
                background_tasks.add_task(
                    _tarea_subida_sheets,
                    tipo="ficha",
                    fila=fila_ordenada,
                    tipo_evaluacion=None,
                    client_keys=[client_item_id, hash_key]
                )
                sheets_result = {
                    "success": True,
                    "status": "en_cola_background",
                    "message": "Ficha procesada y validada exitosamente por IA. Sincronizando con Google Sheets en segundo plano."
                }

            is_dedup = bool(sheets_result and sheets_result.get("deduplicated", False))
            msg_final = sheets_result.get("message") if (sheets_result and is_dedup) else "Ficha de caracterización procesada exitosamente."

            response_payload = {
                "success": True,
                "deduplicated": is_dedup,
                "message": msg_final,
                "participante": fila_ordenada[2] or "SIN NOMBRE",
                "documento": fila_ordenada[4] or "SIN DOCUMENTO",
                "sheets_result": sheets_result,
                "datos_extraidos": ficha.to_canonical_dict()
            }

            with _CACHE_LOCK:
                if client_item_id:
                    IDEMPOTENCY_CACHE[client_item_id] = response_payload
                IDEMPOTENCY_CACHE[hash_key] = response_payload
                ACTIVE_RESULTS[primary_key] = response_payload
            guardar_idempotencia_disco()

            return response_payload

        finally:
            active_event.set()
            ACTIVE_TASKS.pop(primary_key, None)
            if hash_key != primary_key:
                ACTIVE_TASKS.pop(hash_key, None)
            ACTIVE_RESULTS.pop(primary_key, None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando encuesta: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": str(e),
                "detail": "Ocurrió un error durante el procesamiento con IA o la escritura en Google Sheets."
            }
        )


@app.post("/api/process-test")
async def process_test(
    background_tasks: BackgroundTasks,
    foto_test: UploadFile = File(..., description="Fotografía Hoja Única del Test (Pre o Post)"),
    tipo_evaluacion: Optional[str] = Form(None, description="Override opcional ('PRE-TEST', 'POST-TEST' o None para autodetección)"),
    modo: Optional[str] = Form("inmediato", description="Modo de sincronización ('inmediato' o 'batch')"),
    client_item_id: Optional[str] = Form(None, description="Identificador único del registro en el cliente (idempotencia)")
) -> Dict[str, Any]:
    """
    Recibe la fotografía única del Pre-Test o Post-Test (Anexo 4),
    realiza extracción OCR multimodal con IA (con reconciliación de participantes)
    y registra la fila resultante en Google Sheets con control de concurrencia y deduplicación atómica.
    """
    # 0. Verificación inmediata de Idempotencia previa en memoria / disco
    if client_item_id and client_item_id in IDEMPOTENCY_CACHE:
        cached = dict(IDEMPOTENCY_CACHE[client_item_id])
        cached["deduplicated"] = True
        cached["message"] = f"Test ya procesado previamente ({cached.get('participante', '')}). Deduplicado por idempotencia de dispositivo."
        logger.info(f"Idempotencia detectada para test client_item_id={client_item_id}. Retornando caché.")
        return cached

    mime = resolver_mime_imagen(foto_test, "image/jpeg")

    try:
        test_bytes = await foto_test.read()
        if len(test_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen del test está vacía (0 bytes)."
            )

        # 1. Clave secundaria por Hash SHA-256
        hash_img = hashlib.sha256(test_bytes).hexdigest()
        hash_key = f"hash_test_{hash_img}"

        if hash_key in IDEMPOTENCY_CACHE:
            cached = dict(IDEMPOTENCY_CACHE[hash_key])
            cached["deduplicated"] = True
            cached["message"] = f"Test ya procesado previamente ({cached.get('participante', '')}). Deduplicado por hash de imagen."
            logger.info(f"Idempotencia detectada por hash_key={hash_key}. Retornando resultado sin re-procesar.")
            if client_item_id:
                with _CACHE_LOCK:
                    IDEMPOTENCY_CACHE[client_item_id] = cached
                guardar_idempotencia_disco()
            return cached

        primary_key = client_item_id or hash_key

        # 2. Control de concurrencia en vuelo
        if primary_key in ACTIVE_TASKS:
            logger.info(f"Petición concurrente detectada para test '{primary_key}'. Esperando a la tarea en vuelo...")
            event = ACTIVE_TASKS[primary_key]
            await event.wait()
            cached = ACTIVE_RESULTS.get(primary_key) or IDEMPOTENCY_CACHE.get(primary_key)
            if cached:
                cached_copy = dict(cached)
                cached_copy["deduplicated"] = True
                cached_copy["message"] = "Test procesado concurrentemente. Deduplicado por idempotencia en vuelo."
                return cached_copy

        active_event = asyncio.Event()
        ACTIVE_TASKS[primary_key] = active_event
        if hash_key != primary_key:
            ACTIVE_TASKS[hash_key] = active_event

        try:
            logger.info(f"Procesando test en modo '{modo}' (Client ID={client_item_id}, Override={tipo_evaluacion}).")

            # 3. Extracción con IA de Visión bajo semáforo
            logger.info("Encolando extracción con IA para Pre/Post Test Anexo 4 (Semaphore)...")
            async with GEMINI_CONCURRENCY_SEMAPHORE:
                datos_dict = await run_in_threadpool(
                    vision_service.extraer_datos_test,
                    img_bytes=test_bytes,
                    mime_type=mime,
                    tipo_evaluacion_override=tipo_evaluacion
                )

            test_obj = PrePostTest.model_validate(datos_dict)
            fila_ordenada = [str(x or "").strip().upper() for x in test_obj.to_ordered_row()]

            logger.info(
                f"Test extraído con IA -> Tipo='{test_obj.tipo_evaluacion}', "
                f"Participante='{test_obj.nombre}', "
                f"Municipio='{test_obj.municipio}'"
            )

            # 4. Auto-aprendizaje continuo en base de participantes
            try:
                if test_obj.nombre and len(test_obj.nombre) >= 4:
                    await run_in_threadpool(
                        participant_cache.aprender_participante,
                        nombre=test_obj.nombre,
                        edad=test_obj.edad or "",
                        municipio=test_obj.municipio or "",
                        eapb=test_obj.eps or "",
                        documento=""
                    )
            except Exception as e:
                logger.warning(f"No se pudo registrar participante de test en caché: {e}")

            # 5. Desacoplamiento de Google Sheets
            sheets_result = None
            if modo == "sincrono":
                async with SHEETS_WRITE_SEMAPHORE:
                    sheets_result = await run_in_threadpool(
                        sheets_service.insertar_test,
                        valores_ordenados=fila_ordenada,
                        tipo_evaluacion=test_obj.tipo_evaluacion
                    )
            else:
                guardar_pendiente_local(f"test_{test_obj.tipo_evaluacion.lower()}", fila_ordenada, "Encolado para subida asíncrona")
                background_tasks.add_task(
                    _tarea_subida_sheets,
                    tipo="test",
                    fila=fila_ordenada,
                    tipo_evaluacion=test_obj.tipo_evaluacion,
                    client_keys=[client_item_id, hash_key]
                )
                sheets_result = {
                    "success": True,
                    "status": "en_cola_background",
                    "message": f"{test_obj.tipo_evaluacion} validado exitosamente. Sincronizando con Google Sheets en segundo plano."
                }

            is_dedup = bool(sheets_result and sheets_result.get("deduplicated", False))
            msg_final = sheets_result.get("message") if (sheets_result and is_dedup) else f"{test_obj.tipo_evaluacion} procesado y registrado exitosamente en Google Sheets."

            response_payload = {
                "success": True,
                "deduplicated": is_dedup,
                "message": msg_final,
                "tipo_evaluacion": test_obj.tipo_evaluacion,
                "participante": test_obj.nombre or "SIN NOMBRE",
                "municipio": test_obj.municipio or "SIN MUNICIPIO",
                "sheets_result": sheets_result,
                "datos_extraidos": test_obj.to_canonical_dict()
            }

            with _CACHE_LOCK:
                if client_item_id:
                    IDEMPOTENCY_CACHE[client_item_id] = response_payload
                IDEMPOTENCY_CACHE[hash_key] = response_payload
                ACTIVE_RESULTS[primary_key] = response_payload
            guardar_idempotencia_disco()

            return response_payload

        finally:
            active_event.set()
            ACTIVE_TASKS.pop(primary_key, None)
            if hash_key != primary_key:
                ACTIVE_TASKS.pop(hash_key, None)
            ACTIVE_RESULTS.pop(primary_key, None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando test: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": str(e),
                "detail": "Ocurrió un error durante el procesamiento del test o la escritura en Google Sheets."
            }
        )


@app.post("/api/process-anexo17")
async def process_anexo17(
    background_tasks: BackgroundTasks,
    foto_anverso: Optional[UploadFile] = File(None, description="Fotografía Página 1 del Anexo 17 (Datos y preguntas 1 a 5)"),
    foto_reverso: Optional[UploadFile] = File(None, description="Fotografía Página 2 del Anexo 17 (Preguntas 6 a 10)"),
    foto_test: Optional[UploadFile] = File(None, description="Compatibilidad con foto única"),
    tipo_evaluacion: Optional[str] = Form(None, description="Override opcional ('PRE-TEST', 'POST-TEST' o None para autodetección)"),
    modo: Optional[str] = Form("inmediato", description="Modo de sincronización ('inmediato' o 'batch')"),
    client_item_id: Optional[str] = Form(None, description="Identificador único del registro en el cliente (idempotencia)")
) -> Dict[str, Any]:
    """
    Recibe las dos fotografías (Página 1 y Página 2) del Pre-Test o Post-Test (Anexo 17 Pellízcate con Generación B+),
    realiza extracción OCR multimodal con IA (con reconciliación de participantes Jaro-Winkler)
    y registra la fila resultante en Google Sheets con control de concurrencia y deduplicación atómica.
    """
    # 0. Verificación de Idempotencia en memoria (por client_item_id de dispositivo)
    if client_item_id and client_item_id in IDEMPOTENCY_CACHE:
        cached = dict(IDEMPOTENCY_CACHE[client_item_id])
        cached["deduplicated"] = True
        cached["message"] = f"Registro ya procesado previamente ({cached.get('participante', '')}). Deduplicado por idempotencia de dispositivo."
        logger.info(f"Idempotencia detectada para client_item_id={client_item_id}. Retornando caché sin duplicar.")
        return cached

    f1 = foto_anverso or foto_test
    if not f1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere al menos la fotografía de la Página 1 (foto_anverso o foto_test)."
        )

    mime1 = resolver_mime_imagen(f1, "image/jpeg")

    try:
        bytes1 = await f1.read()
        if len(bytes1) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen de la Página 1 está vacía (0 bytes)."
            )

        bytes2 = None
        mime2 = None
        if foto_reverso:
            mime2 = resolver_mime_imagen(foto_reverso, "image/jpeg")
            bytes2 = await foto_reverso.read()
            if len(bytes2) == 0:
                bytes2 = None
                mime2 = None

        # 1. Clave secundaria por Hash SHA-256
        hash_img = hashlib.sha256(bytes1 + (bytes2 or b"")).hexdigest()
        hash_key = f"hash_anexo17_{hash_img}"

        if hash_key in IDEMPOTENCY_CACHE:
            cached = dict(IDEMPOTENCY_CACHE[hash_key])
            cached["deduplicated"] = True
            cached["message"] = f"Anexo 17 ya procesado previamente ({cached.get('participante', '')}). Deduplicado por hash de imagen."
            logger.info(f"Idempotencia detectada por hash_key={hash_key}. Retornando resultado sin re-procesar.")
            if client_item_id:
                with _CACHE_LOCK:
                    IDEMPOTENCY_CACHE[client_item_id] = cached
                guardar_idempotencia_disco()
            return cached

        primary_key = client_item_id or hash_key

        # 2. Control de concurrencia en vuelo
        if primary_key in ACTIVE_TASKS:
            logger.info(f"Petición concurrente detectada para anexo 17 '{primary_key}'. Esperando a la tarea en vuelo...")
            event = ACTIVE_TASKS[primary_key]
            await event.wait()
            cached = ACTIVE_RESULTS.get(primary_key) or IDEMPOTENCY_CACHE.get(primary_key)
            if cached:
                cached_copy = dict(cached)
                cached_copy["deduplicated"] = True
                cached_copy["message"] = "Anexo 17 procesado concurrentemente. Deduplicado por idempotencia en vuelo."
                return cached_copy

        active_event = asyncio.Event()
        ACTIVE_TASKS[primary_key] = active_event
        if hash_key != primary_key:
            ACTIVE_TASKS[hash_key] = active_event

        try:
            logger.info(
                f"Procesando Anexo 17 en modo '{modo}' (Client ID={client_item_id}). "
                f"Pág 1={f1.filename} ({len(bytes1)/1024:.1f}KB), "
                f"Pág 2={'Sí (' + str(len(bytes2)/1024) + 'KB)' if bytes2 else 'No'}, "
                f"Override={tipo_evaluacion}"
            )

            # 3. Extracción con IA de Visión bajo semáforo de concurrencia
            logger.info("Encolando extracción con IA para Pre/Post Test Anexo 17 (Semaphore)...")
            async with GEMINI_CONCURRENCY_SEMAPHORE:
                datos_dict = await run_in_threadpool(
                    vision_service.extraer_datos_anexo17,
                    img_anverso_bytes=bytes1,
                    img_reverso_bytes=bytes2,
                    mime_type_1=mime1,
                    mime_type_2=mime2,
                    tipo_evaluacion_override=tipo_evaluacion
                )

            test_obj = PrePostTestAnexo17.model_validate(datos_dict)
            fila_ordenada = [str(x or "").strip().upper() for x in test_obj.to_ordered_row()]

            logger.info(
                f"Anexo 17 extraído con IA -> Tipo='{test_obj.tipo_evaluacion}', "
                f"Participante='{test_obj.nombre}', "
                f"Municipio='{test_obj.municipio}', "
                f"Fecha='{test_obj.fecha}'"
            )

            # 4. Auto-aprendizaje continuo en base de participantes
            try:
                if test_obj.nombre and len(test_obj.nombre) >= 4:
                    await run_in_threadpool(
                        participant_cache.aprender_participante,
                        nombre=test_obj.nombre,
                        edad=test_obj.edad or "",
                        municipio=test_obj.municipio or "SANTA CATALINA",
                        eapb="",
                        documento=""
                    )
            except Exception as e:
                logger.warning(f"No se pudo registrar participante de Anexo 17 en caché: {e}")

            # 5. Desacoplamiento de Google Sheets
            sheets_result = None
            if modo == "sincrono":
                async with SHEETS_WRITE_SEMAPHORE:
                    sheets_result = await run_in_threadpool(
                        sheets_service.insertar_anexo17,
                        valores_ordenados=fila_ordenada,
                        tipo_evaluacion=test_obj.tipo_evaluacion
                    )
            else:
                guardar_pendiente_local(f"anexo17_{test_obj.tipo_evaluacion.lower()}", fila_ordenada, "Encolado para subida asíncrona")
                background_tasks.add_task(
                    _tarea_subida_sheets,
                    tipo="anexo17",
                    fila=fila_ordenada,
                    tipo_evaluacion=test_obj.tipo_evaluacion,
                    client_keys=[client_item_id, hash_key]
                )
                sheets_result = {
                    "success": True,
                    "status": "en_cola_background",
                    "message": f"Anexo 17 ({test_obj.tipo_evaluacion}) validado exitosamente. Sincronizando con Google Sheets en segundo plano."
                }

            is_dedup = bool(sheets_result and sheets_result.get("deduplicated", False))
            msg_final = sheets_result.get("message") if (sheets_result and is_dedup) else f"Anexo 17 ({test_obj.tipo_evaluacion}) procesado y registrado exitosamente."

            response_payload = {
                "success": True,
                "deduplicated": is_dedup,
                "message": msg_final,
                "tipo_evaluacion": test_obj.tipo_evaluacion,
                "participante": test_obj.nombre or "SIN NOMBRE",
                "municipio": test_obj.municipio or "SIN MUNICIPIO",
                "fecha": test_obj.fecha or "",
                "sheets_result": sheets_result,
                "datos_extraidos": test_obj.to_canonical_dict()
            }

            with _CACHE_LOCK:
                if client_item_id:
                    IDEMPOTENCY_CACHE[client_item_id] = response_payload
                IDEMPOTENCY_CACHE[hash_key] = response_payload
                ACTIVE_RESULTS[primary_key] = response_payload
            guardar_idempotencia_disco()

            return response_payload

        finally:
            active_event.set()
            ACTIVE_TASKS.pop(primary_key, None)
            if hash_key != primary_key:
                ACTIVE_TASKS.pop(hash_key, None)
            ACTIVE_RESULTS.pop(primary_key, None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando Anexo 17: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": str(e),
                "detail": "Ocurrió un error durante el procesamiento del Anexo 17 o la escritura en Google Sheets."
            }
        )


# =====================================================================
# ENDPOINTS DE PATRÓN MAESTRO Y CACHÉ DE PARTICIPANTES (JARO-WINKLER)
# =====================================================================

@app.get("/api/participants/stats")
async def get_participant_stats():
    """Retorna la cantidad de participantes y municipios en la memoria viva Jaro-Winkler."""
    try:
        resumen = await run_in_threadpool(participant_cache.obtener_resumen)
        return {"success": True, "stats": resumen}
    except Exception as e:
        logger.error(f"Error consultando estadísticas de participantes: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/participants/sync-sheet")
async def sync_participants_from_sheet(sheet_id: Optional[str] = Form(None)):
    """
    Descarga y sincroniza la pestaña 'PATRON MAESTRO' de Google Sheets.
    Si sheet_id no se proporciona, usa el GOOGLE_SHEET_ID configurado en el entorno.
    """
    target_id = sheet_id or os.getenv("GOOGLE_SHEET_ID")
    if not target_id:
        raise HTTPException(
            status_code=400,
            detail="No se proporcionó un ID ni URL de Google Sheets y GOOGLE_SHEET_ID no está configurado en .env."
        )

    try:
        total = await run_in_threadpool(
            participant_cache.sincronizar_desde_google_sheets,
            sheet_id=target_id,
            tab_name="PATRON MAESTRO"
        )
        resumen = await run_in_threadpool(participant_cache.obtener_resumen)
        return {
            "success": True,
            "message": f"Sincronización exitosa: {total} participantes registrados en la memoria de la IA.",
            "total_cargados": total,
            "stats": resumen
        }
    except Exception as e:
        logger.error(f"Error sincronizando PATRON MAESTRO desde Google Sheets: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "detail": "Error al conectar con Google Sheets. Asegúrese de que la hoja tenga permisos de lectura y la pestaña se llame 'PATRON MAESTRO'."
            }
        )


@app.post("/api/participants/upload-file")
async def upload_participants_file(file: UploadFile = File(...)):
    """Sube un archivo Excel (.xlsx/.xls) o CSV con el Patrón Maestro para ingestarlo."""
    try:
        import tempfile
        ext = Path(file.filename or "").suffix.lower()
        if ext not in [".xlsx", ".xls", ".csv"]:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de archivo '{ext}' no soportado. Debe ser .xlsx o .csv."
            )

        contenido = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(contenido)
            tmp_path = Path(tmp.name)

        try:
            total = await run_in_threadpool(
                participant_cache.sincronizar_desde_archivo_local,
                ruta_archivo=tmp_path
            )
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        resumen = await run_in_threadpool(participant_cache.obtener_resumen)
        return {
            "success": True,
            "message": f"Archivo ingestatado con éxito: {total} participantes incorporados a la memoria.",
            "total_cargados": total,
            "stats": resumen
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando archivo de participantes: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/participants/clear")
async def clear_participants():
    """Vacía por completo la memoria de participantes para reiniciar a 0."""
    try:
        await run_in_threadpool(participant_cache.limpiar)
        resumen = await run_in_threadpool(participant_cache.obtener_resumen)
        return {
            "success": True,
            "message": "Memoria de participantes vaciada a 0 registros.",
            "total": 0,
            "stats": resumen
        }
    except Exception as e:
        logger.error(f"Error vaciando memoria de participantes: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/api/pending-sync")
async def get_pending_sync_count():
    """Retorna la cantidad de registros en cola de contingencia local."""
    if not PENDIENTES_FILE.exists():
        return {"total_pendientes": 0, "pendientes": []}
    try:
        data = json.loads(PENDIENTES_FILE.read_text(encoding="utf-8"))
        return {"total_pendientes": len(data), "pendientes": data}
    except Exception:
        return {"total_pendientes": 0, "pendientes": []}


@app.post("/api/sync-pending")
async def sync_pending_records():
    """Reintenta la inserción en Google Sheets de todos los registros encolados por timeout."""
    if not PENDIENTES_FILE.exists():
        return {"success": True, "total_sincronizados": 0, "message": "No hay registros en cola."}
    try:
        data = json.loads(PENDIENTES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"success": True, "total_sincronizados": 0, "message": "Cola vacía o inválida."}

    if not data:
        return {"success": True, "total_sincronizados": 0, "message": "No hay registros en cola."}

    exitosos = []
    fallidos = []

    for item in data:
        tipo = item.get("tipo", "ficha")
        fila = item.get("fila", [])
        try:
            if "anexo17" in str(tipo).lower():
                # La fila guardada para Anexo 17 contiene 16 columnas con timestamp o 15 valores
                vals = fila[1:] if len(fila) == 16 else fila
                await run_in_threadpool(sheets_service.insertar_anexo17, valores_ordenados=vals, tipo_evaluacion=tipo)
            elif tipo in ["PRE-TEST", "POST-TEST", "pre_test", "post_test"]:
                # La fila guardada para test contiene: [timestamp, tipo, nombre, ...] (15 columnas)
                # insertar_test espera los 14 valores ordenados sin timestamp (lo agrega automáticamente)
                vals = fila[1:] if len(fila) == 15 else fila
                await run_in_threadpool(sheets_service.insertar_test, valores_ordenados=vals, tipo_evaluacion=tipo)
            else:
                # insertar_encuesta espera los 43 valores sin timestamp
                vals = fila[1:] if len(fila) == 44 else fila
                await run_in_threadpool(sheets_service.insertar_encuesta, valores_ordenados=vals)
            exitosos.append(item)
        except Exception as e:
            item["error"] = str(e)
            fallidos.append(item)

    PENDIENTES_FILE.write_text(json.dumps(fallidos, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "success": True,
        "total_sincronizados": len(exitosos),
        "total_restantes": len(fallidos),
        "message": f"Sincronizados {len(exitosos)} registros exitosamente en Google Sheets."
    }


# Servir Frontend PWA estático
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.api_route("/", methods=["GET", "HEAD"])
    def serve_pwa_index():
        return FileResponse(
            FRONTEND_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )

    @app.api_route("/manifest.json", methods=["GET", "HEAD"])
    def serve_manifest():
        return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/manifest+json")

    @app.api_route("/sw.js", methods=["GET", "HEAD"])
    def serve_sw():
        return FileResponse(
            FRONTEND_DIR / "sw.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        )


def obtener_ip_local() -> str:
    """Detecta la dirección IP local en la red Wi-Fi/LAN."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    local_ip = obtener_ip_local()
    print(f"\n=======================================================")
    print(f"  DIGITALIZADOR DE FICHAS PWA — OWEN BADEL HOOKER")
    print(f"=======================================================")
    print(f"  - Desde tu PC:      http://localhost:{port}")
    print(f"  - Desde tu Celular: http://{local_ip}:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host=host, port=port)
