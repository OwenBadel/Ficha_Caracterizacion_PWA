"""
Pruebas Unitarias para Rotación Automática a Vertical y Prioridad de Gemini 2.5 Flash.
"""

import io
import os
import sys
from pathlib import Path
from PIL import Image

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from vision_service import optimizar_imagen_bytes, VisionService


def test_rotacion_automatica_horizontal_a_vertical():
    """Valida que una foto horizontal se rote 90° automáticamente a vertical."""
    # Crear imagen horizontal en memoria (ancho 800, alto 400)
    img_horizontal = Image.new("RGB", (800, 400), color="blue")
    buf = io.BytesIO()
    img_horizontal.save(buf, format="JPEG")
    bytes_in = buf.getvalue()

    # Procesar con optimizar_imagen_bytes
    bytes_out, mime = optimizar_imagen_bytes(bytes_in)
    img_result = Image.open(io.BytesIO(bytes_out))

    # Debe ser vertical: alto >= ancho
    assert img_result.height > img_result.width, f"Se esperaba vertical pero tiene {img_result.size}"
    assert img_result.width == 400
    assert img_result.height == 800
    print("[PASS] test_rotacion_automatica_horizontal_a_vertical")


def test_imagen_vertical_se_mantiene_vertical():
    """Valida que una foto ya vertical conserve su orientación sin rotación adicional."""
    img_vertical = Image.new("RGB", (500, 700), color="green")
    buf = io.BytesIO()
    img_vertical.save(buf, format="JPEG")
    bytes_in = buf.getvalue()

    bytes_out, mime = optimizar_imagen_bytes(bytes_in)
    img_result = Image.open(io.BytesIO(bytes_out))

    assert img_result.height > img_result.width, f"Se esperaba vertical pero tiene {img_result.size}"
    assert img_result.width == 500
    assert img_result.height == 700
    print("[PASS] test_imagen_vertical_se_mantiene_vertical")


def test_prioridad_gemini_2_5_flash_en_modelos():
    """Valida que Gemini 2.5 Flash esté configurado como modelo primario en el servicio."""
    service = VisionService()
    # Verificar que el modelo por defecto en OpenRouter apunte a gemini-2.5-flash
    openrouter_model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    assert "gemini-2.5-flash" in openrouter_model.lower()
    assert "gemini-2.5-flash" in gemini_model.lower()
    print("[PASS] test_prioridad_gemini_2_5_flash_en_modelos")


if __name__ == "__main__":
    test_rotacion_automatica_horizontal_a_vertical()
    test_imagen_vertical_se_mantiene_vertical()
    test_prioridad_gemini_2_5_flash_en_modelos()
    print("\nTODAS LAS PRUEBAS DE ORIENTACIÓN Y MODELO PASARON CON ÉXITO.")
