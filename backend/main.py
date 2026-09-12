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
import uvicorn
from dotenv import load_dotenv

try:
    from .schema import FichaCaracterizacion, COLUMNAS_FICHA
    from .vision_service import VisionService
    from .sheets_service import GoogleSheetsService
except (ImportError, ValueError):
    backend_dir = Path(__file__).resolve().parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    from schema import FichaCaracterizacion, COLUMNAS_FICHA
    from vision_service import VisionService
    from sheets_service import GoogleSheetsService

# Configurar logging y paths
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("main_api")

PROJECT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"

load_dotenv(PROJECT_DIR / ".env")

app = FastAPI(
    title="Digitalizador de Fichas de Caracterización PWA",
    description="Backend de extracción multimodal con IA de Visión y sincronización automática en Google Sheets.",
    version="1.0.0"
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


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    """Verifica el estado del sistema, proveedores de IA y conexión a Google Sheets."""
    gemini_ok = bool(vision_service.gemini_api_key)
    openai_ok = bool(vision_service.openai_api_key)
    sheets_ok = bool(sheets_service._gspread_client or sheets_service.webhook_url)

    return {
        "status": "online",
        "service": "Ficha Caracterización OCR & Sheets",
        "vision_provider": vision_service.provider,
        "gemini_configured": gemini_ok,
        "openai_configured": openai_ok,
        "sheets_configured": sheets_ok,
        "sheets_method": "gspread_api" if sheets_service._gspread_client else ("webhook" if sheets_service.webhook_url else "none"),
        "columnas_count": len(COLUMNAS_FICHA)
    }


@app.get("/api/columns")
def get_columns() -> Dict[str, Any]:
    """Retorna la lista exacta y ordenada de las 43 columnas."""
    return {
        "total": len(COLUMNAS_FICHA),
        "columns": COLUMNAS_FICHA
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

        # 1. Extracción con IA de Visión
        logger.info("Iniciando extracción multimodal con IA...")
        datos_dict = vision_service.extraer_datos_ficha(
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

        # 2. Inserción en Google Sheets
        logger.info("Enviando fila estructurada a Google Sheets...")
        sheets_result = sheets_service.insertar_encuesta(fila_ordenada)

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


# Servir Frontend PWA estático
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_pwa_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/manifest.json")
    def serve_manifest():
        return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/manifest+json")

    @app.get("/sw.js")
    def serve_sw():
        return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")


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
    print(f"  LEMON FABRICA - DIGITALIZADOR DE FICHAS PWA")
    print(f"=======================================================")
    print(f"  - Desde tu PC:      http://localhost:{port}")
    print(f"  - Desde tu Celular: http://{local_ip}:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host=host, port=port)
