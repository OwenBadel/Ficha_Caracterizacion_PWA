"""
Servidor API REST FastAPI para el Digitalizador de Fichas de Caracterización.
Expone endpoints de procesamiento con Visión Artificial y subida a Google Sheets,
además de servir la aplicación PWA frontend en modo Mobile-First.
"""

from __future__ import annotations
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from starlette.concurrency import run_in_threadpool
import uvicorn
from dotenv import load_dotenv

try:
    from .schema import FichaCaracterizacion, COLUMNAS_FICHA
    from .schema_test import PrePostTest, COLUMNAS_TEST, ENCABEZADOS_TEST_SHEETS
    from .vision_service import VisionService
    from .sheets_service import GoogleSheetsService
    from .vocabulary_learner import vocabulary_learner
    from .participant_cache import participant_cache
except (ImportError, ValueError):
    backend_dir = Path(__file__).resolve().parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from schema import FichaCaracterizacion, COLUMNAS_FICHA
    from schema_test import PrePostTest, COLUMNAS_TEST, ENCABEZADOS_TEST_SHEETS
    from vision_service import VisionService
    from sheets_service import GoogleSheetsService
    from vocabulary_learner import vocabulary_learner
    from participant_cache import participant_cache

# Configurar logging y paths
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main_api")

PROJECT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

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
    """Inicialización desatendida y sincronización del Patrón Maestro."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if sheet_id:
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
    """Verifica el estado del sistema, motor Ollama GPU, y conexión a Google Sheets."""
    openai_ok = bool(vision_service.openai_api_key)
    sheets_ok = bool(sheets_service._gspread_client or sheets_service.webhook_url or sheets_service.webhook_url_tests)

    # Comprobar si Ollama responde localmente
    ollama_ok = False
    try:
        import urllib.request
        req = urllib.request.Request(f"{vision_service.ollama_base_url}/api/tags", headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            ollama_ok = (resp.status == 200)
    except Exception:
        ollama_ok = False

    return {
        "status": "online",
        "service": "Ficha Caracterización & Pre/Post Test OCR (Soberano)",
        "vision_provider": vision_service.provider,
        "ollama_model": vision_service.ollama_model,
        "ollama_online": ollama_ok,
        "openai_configured": openai_ok,
        "sheets_configured": sheets_ok,
        "sheets_method": "gspread_api" if sheets_service._gspread_client else ("webhook" if sheets_service.webhook_url else "none"),
        "columnas_ficha_count": len(COLUMNAS_FICHA),
        "columnas_test_count": len(COLUMNAS_TEST),
        "patron_maestro_participantes": participant_cache.contar()
    }


# =====================================================================
# ENDPOINTS PARA PATRÓN MAESTRO Y COINCIDENCIA JARO-WINKLER
# =====================================================================

@app.get("/api/participants")
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
    """Retorna la lista exacta y ordenada de las 43 columnas."""
    return {
        "total": len(COLUMNAS_FICHA),
        "columns": COLUMNAS_FICHA
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


@app.get("/api/participants")
def get_participants() -> Dict[str, Any]:
    """Retorna el resumen de participantes cargados en caché."""
    return {
        "status": "online",
        **participant_cache.obtener_resumen()
    }


@app.post("/api/process-survey")
async def process_survey(
    foto_anverso: UploadFile = File(..., description="Fotografía Página 1 (Anverso)"),
    foto_reverso: UploadFile = File(..., description="Fotografía Página 2 (Reverso)"),
    modo: Optional[str] = Form("inmediato", description="Modo de sincronización ('inmediato' o 'batch')")
) -> Dict[str, Any]:
    """
    Recibe las dos fotos obligatorias de la ficha, realiza extracción OCR multimodal con IA
    y registra la fila resultante en Google Sheets.
    """
    logger.info(f"Procesando encuesta en modo '{modo}'. Archivo 1: {foto_anverso.filename}, Archivo 2: {foto_reverso.filename}")

    # Validar tipos de archivo
    mime1 = foto_anverso.content_type or "image/jpeg"
    mime2 = foto_reverso.content_type or "image/jpeg"

    if not mime1.startswith("image/") or not mime2.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ambos archivos deben ser imágenes válidas (JPEG, PNG, WebP, etc.)."
        )

    try:
        anverso_bytes = await foto_anverso.read()
        reverso_bytes = await foto_reverso.read()

        if len(anverso_bytes) == 0 or len(reverso_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Una o ambas imágenes están vacías (0 bytes)."
            )

        # 1. Extracción con IA de Visión (Offloaded a threadpool para proteger el event loop)
        logger.info("Iniciando extracción multimodal con IA...")
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
            f"Col 22 (Última vez)='{fila_ordenada[21]}', "
            f"Col 25 (Tiempo)='{fila_ordenada[24]}', "
            f"Col 38 (Embarazo adolescente)='{fila_ordenada[37]}', "
            f"Col 43 (Por qué)='{fila_ordenada[42]}'"
        )

        # 2. Inserción en Google Sheets (Offloaded a threadpool)
        logger.info("Enviando fila estructurada a Google Sheets...")
        sheets_result = await run_in_threadpool(sheets_service.insertar_encuesta, fila_ordenada)

        # 3. Aprendizaje continuo de vocabulario para futuras coincidencias difusas
        try:
            await run_in_threadpool(vocabulary_learner.aprender_fila, fila_ordenada)
            logger.info("Vocabulario adaptativo actualizado a partir de la nueva ficha procesada.")
        except Exception as e:
            logger.warning(f"No se pudo actualizar vocabulario adaptativo: {e}")

        # 4. Aprendizaje continuo en base de participantes
        try:
            await run_in_threadpool(
                participant_cache.aprender_participante,
                nombre=fila_ordenada[2],
                edad=fila_ordenada[5],
                municipio=fila_ordenada[9],
                eapb=fila_ordenada[11],
                documento=fila_ordenada[4]
            )
            logger.info(f"Participante registrado en caché: {fila_ordenada[2]}")
        except Exception as e:
            logger.warning(f"No se pudo registrar participante en caché: {e}")

        return {
            "success": True,
            "message": "Ficha de caracterización procesada y registrada exitosamente en Google Sheets.",
            "participante": fila_ordenada[2] or "SIN NOMBRE",
            "documento": fila_ordenada[4] or "SIN DOCUMENTO",
            "sheets_result": sheets_result,
            "datos_extraidos": ficha.to_canonical_dict()
        }

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
    foto_test: UploadFile = File(..., description="Fotografía Hoja Única del Test (Pre o Post)"),
    tipo_evaluacion: Optional[str] = Form(None, description="Override opcional ('PRE-TEST', 'POST-TEST' o None para autodetección)"),
    modo: Optional[str] = Form("inmediato", description="Modo de sincronización ('inmediato' o 'batch')")
) -> Dict[str, Any]:
    """
    Recibe la fotografía única del Pre-Test o Post-Test (Anexo 4),
    realiza extracción OCR multimodal con IA (con reconciliación de participantes)
    y registra la fila resultante en Google Sheets.
    """
    logger.info(f"Procesando test en modo '{modo}'. Archivo: {foto_test.filename}, Override: {tipo_evaluacion}")

    mime = foto_test.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser una imagen válida (JPEG, PNG, WebP)."
        )

    try:
        test_bytes = await foto_test.read()
        if len(test_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen del test está vacía (0 bytes)."
            )

        # 1. Extracción con IA de Visión (Offloaded a threadpool para proteger event loop)
        logger.info("Iniciando extracción con IA para Pre/Post Test...")
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
            f"Municipio='{test_obj.municipio}', "
            f"P5='{test_obj.pregunta_5}'"
        )

        # 2. Inserción en Google Sheets (Offloaded a threadpool)
        logger.info(f"Enviando fila de test estructurada a Google Sheets (Pestaña: '{test_obj.tipo_evaluacion}')...")
        sheets_result = await run_in_threadpool(
            sheets_service.insertar_test,
            valores_ordenados=fila_ordenada,
            tipo_evaluacion=test_obj.tipo_evaluacion
        )

        return {
            "success": True,
            "message": f"{test_obj.tipo_evaluacion} procesado y registrado exitosamente en Google Sheets.",
            "tipo_evaluacion": test_obj.tipo_evaluacion,
            "participante": test_obj.nombre or "SIN NOMBRE",
            "municipio": test_obj.municipio or "SIN MUNICIPIO",
            "sheets_result": sheets_result,
            "datos_extraidos": test_obj.to_canonical_dict()
        }

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
