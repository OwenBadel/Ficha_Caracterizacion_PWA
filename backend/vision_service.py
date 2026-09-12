"""
Servicio de Visión Artificial Multimodal (OCR Especializado).
Procesa las dos fotografías (Anverso y Reverso) de la Ficha de Caracterización
utilizando Google Gemini (Google GenAI) o OpenAI GPT-4o.
"""

from __future__ import annotations
import os
import json
import re
import base64
from typing import Tuple, Dict, Any, Optional
from dotenv import load_dotenv

try:
    from .schema import FichaCaracterizacion, COLUMNAS_FICHA
except (ImportError, ValueError):
    from schema import FichaCaracterizacion, COLUMNAS_FICHA

load_dotenv()

SYSTEM_PROMPT = """Eres un sistema experto en OCR y digitalización de documentos físicos oficiales de salud y caracterización ciudadana.
Tu misión es extraer la información de las 2 imágenes proporcionadas (Página 1: Anverso y Página 2: Reverso).

REGLAS OBLIGATORIAS E INVIOLABLES DE ESTANDARIZACIÓN:
1. TODO EN MAYÚSCULAS: Convierte absolutamente TODAS las respuestas (texto, nombres, selecciones, números, fechas, descripciones) a MAYÚSCULAS SIN EXCEPCIÓN. NUNCA devuelvas texto en minúsculas.
2. DETECCIÓN RIGUROSA DE CASILLAS (CHECKBOXES / OPCIONES):
   - Para las casillas de verificación marcadas con una "X", visto bueno ✔, trazo, sombreado o relleno manuscrito, extrae la opción marcada en MAYÚSCULAS ("SI" o "NO").
   - ATENCIÓN CRÍTICA A LA CASILLA 38: En "¿Has vivido o conoces algún caso cercano de embarazo adolescente?", examina con máxima atención las opciones "SI" y "NO". Si hay cualquier marca sobre o dentro del recuadro "SI", extrae "SI". Si la marca está en "NO", extrae "NO". NUNCA devuelvas cadena vacía si hay una marca visible.
   - Aplica esta misma exhaustividad a todas las casillas dicotómicas (médico, odontólogo, cigarrillo, alcohol, sustancias psicoactivas, discriminación, salud sexual, vida sexual, condón, métodos anticonceptivos, preservativos EPS, espacios de diálogo).
3. CATÁLOGO CERRADO - CAMPO 1 (NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA):
   - ÚNICAMENTE pueden existir las siguientes 4 personas autorizadas:
     * PAMELA VERGARA
     * KAREN TORRES
     * WENDY TAPIAS
     * GISEL MORENO
   Identifica la caligrafía o abreviatura y escribe EXACTAMENTE una de estas cuatro opciones.
4. CATÁLOGO CERRADO - TERRITORIO Y MUNICIPIO:
   - "TERRITORIO" solo puede ser uno de estos 4 valores:
     * MAHATES
     * TURBANA
     * TURBACO
     * BARRANCO DE LOBA
   - REGLA: "Municipio" es exactamente el mismo valor que "TERRITORIO".
5. CATÁLOGO CERRADO - TIPO DE DOCUMENTO IDENTIDAD:
   - Solo puede ser uno de los siguientes:
     * RC
     * TI
     * CC
     * PASAPORTE
     * PERMISO
   - REGLA ESTRICTA DE EDAD: Si la persona tiene menos de 18 años (Edad < 18), su tipo de documento es SIEMPRE "TI" (Tarjeta de Identidad). NUNCA coloques "CC" para menores de 18 años.
6. FORMATO ESTRICTO - GRADO ESCOLAR:
   - Debe ser el número seguido del símbolo de grado ° (ejemplos: 1°, 2°, 3°, 4°, 5°, 6°, 7°, 8°, 9°, 10°, 11°).
7. CATÁLOGO CERRADO - ZONA:
   - Solo puede ser: RURAL o URBANA.
8. CATÁLOGO CERRADO - EPS (SI TIENES):
   - Solo puede ser una de las siguientes opciones (o dejar vacío si no tiene):
     * SANITAS
     * SURA
     * SALUD TOTAL
     * MUTUAL SER
     * COOSALUD
     * NUEVA EPS
9. CATÁLOGO CERRADO - RÉGIMEN:
   - Solo puede ser: CONTRIBUTIVO, SUBSIDIADO o NINGUNO.
10. CATÁLOGO CERRADO - SEXO CON EL QUE TE IDENTIFICAS:
   - Solo puede ser: FEMENINO o MASCULINO.
11. CATÁLOGO CERRADO - IDENTIDAD DE GÉNERO:
   - Solo puede ser una de las siguientes:
     * HETEROSEXUAL
     * HOMOSEXUAL
     * BISEXUAL
     * TRANSGENERO
     * LESBIANA
12. CATÁLOGO CERRADO - POBLACIÓN O GRUPO ÉTNICO:
   - Solo puede ser una de las siguientes:
     * AFROCOLOMBIANO
     * INDÍGENA
     * PALENQUERO
     * VÍCTIMA DEL CONFLICTO
     * NO
13. CATÁLOGO CERRADO - CONDICIÓN DE DISCAPACIDAD:
   - Solo puede ser: SI o NO.
14. CONTEXTO TEMPORAL Y AÑO ACTUAL 2026 (FECHAS Y PERÍODOS):
   - Todas estas encuestas se están realizando y diligenciando en el año 2026.
   - En preguntas de fecha o período (como "¿Cuándo fue la última vez?"), los años diligenciados son 2026 (ejemplo: "MAYO 2026", "2026").
   - ATENCIÓN AL DÍGITO 6: NUNCA interpretes el número '6' manuscrito como un '0' ni cambies '2026' por '2020'. Extrae con total fidelidad "MAYO 2026".
15. CAMPO 25 (TIEMPO EMPLEADO):
   - En la pregunta "¿Qué tiempo empleas en esta actividad?", extrae el número e incluye siempre la palabra HORAS en mayúsculas (ejemplo: si escribió "2" o "2h", devuelve "2 HORAS"; si escribió "1", devuelve "1 HORA").
16. CAMPOS DE TELÉFONO Y NÚMERO DE DOCUMENTO (PEGADOS SIN ESPACIOS):
   - En "Numero de documento identidad" y "Teléfono de contacto", escribe los números completamente unidos, continuos y sin espacios, sin puntos, sin guiones ni paréntesis (ejemplos: si en la imagen se lee "1 045 678 901" o "1.045.678.901", escribe "1045678901"; si se lee "300 123 4567" o "300-123-4567", escribe "3001234567"). Aunque en la imagen física se vean separados o en casillas individuales, van pegados sin espacios.
17. CAMPOS NO RESPONDIDOS:
   - Si una casilla o pregunta no fue respondida o está en blanco, devuelve un string vacío "". NUNCA pongas null, None, o "N/A".
18. Devuelve ÚNICAMENTE un objeto JSON válido, sin bloques de texto explicativo, sin introducciones ni saludos.
19. Usa EXACTAMENTE las siguientes 43 claves JSON:
"""

PROMPT_JSON_TEMPLATE = json.dumps({col: "" for col in COLUMNAS_FICHA}, indent=2, ensure_ascii=False)

USER_PROMPT = f"""{SYSTEM_PROMPT}

ESTRUCTURA EXACTA REQUERIDA (JSON):
{PROMPT_JSON_TEMPLATE}

Analiza minuciosamente el anverso (Página 1) y reverso (Página 2) adjuntos y genera el JSON estricto.
"""


def _limpiar_bloque_json(texto: str) -> str:
    """Elimina delimitadores markdown ```json y ``` para obtener JSON puro."""
    texto = texto.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
    if match:
        return match.group(1).strip()
    if texto.startswith("{") and texto.endswith("}"):
        return texto
    start = texto.find("{")
    end = texto.rfind("}")
    if start != -1 and end != -1 and end > start:
        return texto[start:end+1]
    return texto


class VisionService:
    """Controlador de extracción multimodal para fichas físicas."""

    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.provider = os.getenv("VISION_PROVIDER", "gemini").lower()

    def extraer_datos_ficha(self, img_anverso_bytes: bytes, img_reverso_bytes: bytes,
                            mime_type_1: str = "image/jpeg",
                            mime_type_2: str = "image/jpeg") -> Dict[str, str]:
        """
        Extrae los 43 campos canónicos a partir de los bytes de las dos imágenes.
        """
        if self.provider == "openai" or (not self.gemini_api_key and self.openai_api_key):
            raw_json = self._procesar_con_openai(img_anverso_bytes, img_reverso_bytes, mime_type_1, mime_type_2)
        else:
            raw_json = self._procesar_con_gemini(img_anverso_bytes, img_reverso_bytes, mime_type_1, mime_type_2)

        # Parsear y validar con el esquema Pydantic
        limpio = _limpiar_bloque_json(raw_json)
        try:
            parsed = json.loads(limpio)
        except Exception as e:
            raise ValueError(f"La respuesta de la IA no fue un JSON válido: {e}\nRespuesta recibida: {raw_json[:300]}")

        ficha = FichaCaracterizacion.model_validate(parsed)
        return ficha.to_canonical_dict()

    def _procesar_con_gemini(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Invoca Google Gemini 2.0 / 1.5 Flash."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno.")

        # Intentar con el SDK oficial más reciente google-genai
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key)
            part_1 = types.Part.from_bytes(data=img1, mime_type=mime1)
            part_2 = types.Part.from_bytes(data=img2, mime_type=mime2)

            primary_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
            candidate_models = [primary_model, "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.7-flash"]
            models_to_try = list(dict.fromkeys(candidate_models))

            last_err = None
            for m_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=m_name,
                        contents=[USER_PROMPT, part_1, part_2],
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            response_mime_type="application/json"
                        )
                    )
                    return response.text
                except Exception as e:
                    last_err = e
                    continue

            if last_err:
                raise last_err
        except ImportError:
            # Fallback a google.generativeai legado
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.gemini_api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                generation_config={"temperature": 0.1, "response_mime_type": "application/json"}
            )
            contents = [
                USER_PROMPT,
                {"mime_type": mime1, "data": img1},
                {"mime_type": mime2, "data": img2}
            ]
            response = model.generate_content(contents)
            return response.text

    def _procesar_con_openai(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Invoca OpenAI GPT-4o."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        b64_1 = base64.b64encode(img1).decode("utf-8")
        b64_2 = base64.b64encode(img2).decode("utf-8")

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime1};base64,{b64_1}"}
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime2};base64,{b64_2}"}
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content or "{}"
