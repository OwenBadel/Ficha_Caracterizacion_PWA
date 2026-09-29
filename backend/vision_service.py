"""
Servicio de Visión Artificial Multimodal (OCR Especializado).
Procesa las dos fotografías (Anverso y Reverso) de la Ficha de Caracterización
utilizando Google Gemini (Google GenAI), OpenAI GPT-4o o OpenRouter.
"""

from __future__ import annotations
import os
import json
import re
import base64
import logging
from typing import Tuple, Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger("vision_service")

try:
    from .schema import FichaCaracterizacion, COLUMNAS_FICHA
    from .schema_test import PrePostTest, COLUMNAS_TEST
    from .participant_cache import participant_cache
except (ImportError, ValueError):
    from schema import FichaCaracterizacion, COLUMNAS_FICHA
    from schema_test import PrePostTest, COLUMNAS_TEST
    from participant_cache import participant_cache

load_dotenv()

SYSTEM_PROMPT = """Eres un sistema experto en transcripción OCR y digitalización forense de fichas físicas oficiales de caracterización ciudadana y juvenil.
Tu única misión es transcribir con EXACTITUD Y FIDELIDAD VISUAL ABSOLUTA la información de las 2 imágenes adjuntas (Página 1: Anverso y Página 2: Reverso).

======================================================================
🚨 REGLA DE ORO DE FIDELIDAD VISUAL (ESTRICTAMENTE PROHIBIDO ALUCINAR) 🚨
======================================================================
1. CERO ALUCINACIONES: Extrae EXCLUSIVAMENTE lo que esté físicamente marcado con una marca manuscrita (X, visto bueno, sombreado, cruz) o escrito a mano con tinta en el documento.
2. CASILLAS VACÍAS: Si una casilla, recuadro, línea o pregunta NO fue marcada o está en blanco, devuelve OBLIGATORIAMENTE un string vacío "". NUNCA supongas, predigas, infieras ni inventes un dato. NUNCA pongas valores predeterminados (como "NINGUNA", "NO", "HACE UN MES", "FUTBOL", "ASMA", "2026") si no hay trazos reales en esa casilla.
   🚨 ESPECIAL ATENCIÓN EN ZONA Y RÉGIMEN: Si el participante dejó en blanco la Zona (ni Rural ni Urbana) o el Régimen (ni Contributivo, ni Subsidiado, ni Ninguno), DEVUELVE OBLIGATORIAMENTE string vacío "". PROHIBIDO inventar o asumir "URBANA" o "CONTRIBUTIVO" si los recuadros están vacíos en el papel.
3. TODO EN MAYÚSCULAS: Todo el texto debe devolverse en MAYÚSCULAS sin excepción.
4. DEPENDENCIAS CONDICIONALES ESTRICTAS (PADRE - HIJO):
   Si la pregunta principal está en "NO" o vacía, la pregunta secundaria dependiente ("¿Cuál?", "Cada cuánto?", "Cuándo fue la última vez") DEBE SER OBLIGATORIAMENTE string vacío "".

======================================================================
📍 ORIENTACIÓN ESPACIAL CRÍTICA DE LAS CASILLAS (GEOMETRÍA DEL PAPEL) 📍
======================================================================

1. EN TODAS LAS PREGUNTAS DICOTÓMICAS (SI / NO):
   El diseño impreso en la ficha física ubica el recuadro [ ] A LA DERECHA de la palabra:
   
        Si [ ]   No [ ]

   ⚠️ REGLA DE LECTURA VISUAL (EXTREMA ATENCIÓN):
   * PARA MARCAR "SI": El participante coloca la marca (X, visto bueno, punto o raya) en el recuadro que está a la DERECHA de la palabra "Si":
        Si [X]   No [ ]   ===> RESPUESTA MARCADA ES "SI"
     (¡CUIDADO! Este recuadro queda en el medio entre "Si" y "No". NO lo confundas como si fuera casilla de "No"; PERTENECE AL "SI").

   * PARA MARCAR "NO": El participante coloca la marca en el recuadro que está a la DERECHA de la palabra "No":
        Si [ ]   No [X]   ===> RESPUESTA MARCADA ES "NO"

   * Aplica esta regla de recuadro a la DERECHA en todas las preguntas dicotómicas:
     - ¿Tienes alguna condición de discapacidad? (Si [ ] No [ ])
     - ¿Tienes antecedentes de alguna enfermedad personal o familiar importante? (Si [ ] No [ ])
     - ¿Has asistido al médico en el último año? (Si [ ] No [ ])
     - ¿Fuiste al odontólogo el último año? (Si [ ] No [ ])
     - ¿Consumes o has consumido cigarrillo o vapeador? (Si [ ] No [ ])
     - ¿Consumes o has consumido alcohol? (Si [ ] No [ ])
     - ¿Has consumido alguna sustancia psicoactiva? (Si [ ] No [ ])
     - ¿Has vivido situaciones de discriminación, rechazo o violencia? (Si [ ] No [ ])
     - ¿Has recibido información sobre salud sexual, ITS o métodos de prevención? (Si [ ] No [ ])
     - ¿Has iniciado tu vida sexual? (Si [ ] No [ ])
     - ¿Conoces algún método anticonceptico? (Si [ ] No [ ])
     - ¿Has vivido o conoces algún caso cercano de embarazo adolescente? (Si [ ] No [ ])
     - ¿Te han entregado preservativos en la EPS o institución de salud? (Si [ ] No [ ])
     - ¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas? (Si [ ] No [ ])

2. EN LA PREGUNTA 41 DE TEMAS DE INTERÉS ("¿Qué tema te gustaria aprender o entender mejor?"):
   AQUÍ EL DISEÑO IMPRESO ES INVERSO: El recuadro [ ] está A LA IZQUIERDA del texto:
   
        [X] VIH   [ ] SIFILIS   [ ] HEPATITIS B Y C   [ ] METODOS ANTICONCEPTIVOS ...

   * La marca [X] corresponde a la opción que tiene a su DERECHA.
   * Ejemplo: si ves marcado el recuadro que precede a "VIH" ([X] VIH), el participante seleccionó "VIH".

======================================================================
📋 MAPA ESTRUCTURAL DE LAS 43 PREGUNTAS POR HOJA FÍSICA
======================================================================

--- PÁGINA 1: ANVERSO (Preguntas 1 a 23) ---
1. "NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA": Encuestador oficial responsable. Catálogo cerrado (selecciona exactamente uno):
   * PAMELA VERGARA
   * KAREN TORRES
   * MAURICIO FORTICH
   * WENDY TAPIAS
   * GISEL MORENO
2. "TERRITORIO": Municipio oficial cabecera. Catálogo cerrado (selecciona exactamente uno):
   * MAHATES
   * TURBANA
   * TURBACO
   * BARRANCO DE LOBA
   * SAN JACINTO DEL CAUCA
   * CALAMAR
   * MORALES
   * SANTA ROSA DEL SUR
   * ARENAL
   * SOPLAVIENTO
3. "Nombre completo del participante": Nombre manuscrito legible en la hoja.
4. "Tipo de documento identidad": Catálogo cerrado: RC, TI, CC, PASAPORTE, PERMISO. (REGLA INVIOLABLE: Si la Edad es menor a 18 años, es SIEMPRE "TI").
5. "Numero de documento identidad": Dígitos continuos sin puntos, sin espacios ni guiones.
6. "Edad": Número entero manuscrito (ej: 14, 15, 16).
7. "Grado escolar": Número con símbolo de grado (ej: 8°, 9°, 10°, 11°).
8. "Teléfono de contacto": Dígitos continuos sin espacios ni guiones (ej: 3001234567). Si está en blanco, "".
9. "Dirección de residencia (barrio o vereda)": Dirección, barrio o vereda manuscrito tal como fue escrito por el encuestado (incluyendo palabras como BARRIO, VEREDA, SECTOR, CORREGIMIENTO, CALLE o abreviaturas como B/, VDA.). Ejemplos: "BARRIO EL CARMEN", "VEREDA LA FLORIDA", "SECTOR CENTRO", "CALLE PRINCIPAL". Si está en blanco, "".
10. "Municipio": Exactamente el mismo valor que "TERRITORIO".
11. "Zona": Catálogo cerrado: RURAL o URBANA. 🚨 Si ninguna casilla está marcada o está en blanco en el papel, devuelve OBLIGATORIAMENTE "". NUNCA infieras ni asumas URBANA o RURAL por defecto.
12. "EPS (si tienes)": Catálogo: NUEVA EPS, COOSALUD, MUTUAL SER, SALUD TOTAL, SURA, SANITAS, CONFAORIENTE, PROTEGER, FAMISANAR  u otra escrita en Otros. Si no tiene o está en blanco, "".
13. "Régimen": Catálogo cerrado: CONTRIBUTIVO, SUBSIDIADO o NINGUNO. 🚨 Si el participante no marcó ninguna opción o está en blanco, devuelve OBLIGATORIAMENTE "". NUNCA supongas ni inventes CONTRIBUTIVO o SUBSIDIADO.
14. "Sexo con el que te identificas": Catálogo cerrado: FEMENINO o MASCULINO.
15. "Identidad de género": Catálogo cerrado: HETEROSEXUAL, HOMOSEXUAL, BISEXUAL, TRANSGENERO, LESBIANA.
16. "¿Perteneces a alguna población o grupo étnico?": Catálogo cerrado: AFROCOLOMBIANO, INDÍGENA, PALENQUERO, VÍCTIMA DEL CONFLICTO, NO.
17. "¿Tienes alguna condición de discapacidad?": Marca en SI o NO.
18. "¿Cual?": Tipo de discapacidad manuscrita. Si en la 17 marcó NO o no hay discapacidad escrita, DEBE ser "".
19. "¿Tienes antecedentes de alguna enfermedad personal o familiar importante?": Marca en SI o NO.
20. "¿Cual?_1": Tipo de enfermedad manuscrita. Si en la 19 marcó NO o no hay enfermedad escrita, DEBE ser "".
21. "¿Has asistido al médico en el último año?": Marca en SI o NO.
22. "¿Cuándo fue la última vez?": Fecha o período de visita al médico. Si en la 21 marcó NO o no hay fecha escrita, DEBE ser "". NUNCA asumas una fecha si está en blanco.
23. "¿Fuiste al odontólogo el último año?": Marca en SI o NO.

--- PÁGINA 2: REVERSO (Preguntas 24 a 43) ---
24. "¿Qué actividades recreativas haces en tu tiempo libre?": Actividades manuscritas descritas por el participante. Si está en blanco, "".
25. "¿Qué tiempo empleas en esta actividad?": Número seguido de HORAS (ej: "2 HORAS"). Si está en blanco, "".
26. "¿Consumes o has consumido cigarrillo o vapeador?": Marca en SI o NO.
27. "Cada cuánto?": Frecuencia de consumo de cigarrillo. Si en la 26 marcó NO o está en blanco, DEBE ser "".
28. "¿Consumes o has consumido alcohol?": Marca en SI o NO.
29. "Cada cuánto?_1": Frecuencia de consumo de alcohol. Si en la 28 marcó NO o está en blanco, DEBE ser "".
30. "¿Has consumido alguna sustancia psicoactiva?": Marca en SI o NO.
31. "¿Cual?_2": Sustancia manuscrita. Si en la 30 marcó NO o está en blanco, DEBE ser "".
32. "¿Has vivido situaciones de discriminación, rechazo o violencia?": Marca en SI o NO.
33. "¿Has recibido información sobre salud sexual, ITS o métodos de prevención?": Marca en SI o NO.
34. "¿Has iniciado tu vida sexual?": Marca en SI o NO según la casilla física. Solo extrae "SI" si la casilla de SI está marcada o si en la pregunta 35 indicó uso de condón (SIEMPRE o CASI SIEMPRE). NUNCA infieras "SI" si la persona solo nombró o conoce métodos anticonceptivos en las preguntas 36 o 37.
35. "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?": Catálogo cerrado: SIEMPRE, CASI SIEMPRE o NUNCA. SOLO si en la 34 marcó SI. Si en la 34 marcó NO, DEBE ser "".
36. "¿Conoces algún método anticonceptico?": Marca en SI o NO. Si en la 37 escribió un método anticonceptivo, extrae "SI".
37. "¿Cual?_3": Método anticonceptivo manuscrito. Si el participante nombró el implante subdérmico Jadelle (o escribió YADEL, JADELLE, YADUL, barritas), extrae "YADEL". Si en la 36 marcó NO y no escribió nada, DEBE ser "".
38. "¿Has vivido o conoces algún caso cercano de embarazo adolescente?": Marca en SI o NO.
    ⚠️ REGLA CRÍTICA DE LECTURA VISUAL: El diseño impreso es: Si [ ] No [ ].
    * El recuadro para "SI" está en la mitad, a la derecha de "Si": Si [X] No [ ].
    * Si ves una marca manuscrita (X, visto bueno ✔, punto o raya) en el recuadro ENTRE "Si" y "No", la respuesta ES OBLIGATORIAMENTE "SI".
    * NO confundas el recuadro del medio como si perteneciera a "No". Solo extrae "NO" si la marca está en el recuadro final a la derecha de "No": Si [ ] No [X].
    * No te confundas con la opción de tema de interés de la pregunta 41.
39. "¿Te han entregado preservativos en la EPS o institución de salud?": Marca en SI o NO.
    ⚠️ REGLA CRÍTICA DE LECTURA VISUAL: El diseño impreso es: Si [ ] No [ ].
    * Si hay una marca en el recuadro intermedio (a la derecha de "Si": Si [X] No [ ]), extrae OBLIGATORIAMENTE "SI".
    * 🚨 ATENCIÓN A FECHA VACÍA: Si el encuestado marcó "SI" en la 39 pero dejó en blanco la pregunta 40 ("¿Cuándo fue la ultima vez?"), MANTÉN "SI" en la 39. En campo la gran mayoría no recuerda la fecha exacta. NUNCA asumas "NO" en la 39 solo porque la 40 esté vacía.
40. "¿Cuándo fue la ultima vez?": Fecha o período de entrega de preservativos en EPS. Si en la 39 marcó NO o está en blanco, DEBE ser "". NUNCA inventes fechas si no están escritas.
41. "¿Qué tema te gustaria aprender o entender mejor?": Extrae todas las opciones marcadas en el formulario, separadas OBLIGATORIAMENTE por coma y espacio (", "). Si no marcó ninguna, "".
    (Opciones posibles: VIH, SIFILIS, HEPATITIS B Y C, METODOS ANTICONCEPTIVOS, USO CORRECTO DEL PRESERVATIVO, PROYECTO DE VIDA, RESPETO POR LAS DIFERENCIAS, PREVENCION DEL EMBARAZO ADOLESCENTE, SALUD MENTAL Y RELACIONES, u Otros escritos).
42. "¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?": Marca en SI o NO.
    ⚠️ REGLA CRÍTICA DE LECTURA VISUAL: El diseño impreso es: Si [ ] No [ ].
    * El recuadro para "SI" está en la mitad, a la derecha de "Si": Si [X] No [ ].
    * Si ves una marca manuscrita (X, visto bueno ✔, punto o raya) en el recuadro ENTRE "Si" y "No", O si el participante escribió una razón, motivo o texto en la pregunta 43 ("¿Por que?"), la respuesta ES OBLIGATORIAMENTE "SI".
    * NO confundas el recuadro del medio como si perteneciera a "No".
    * Solo extrae "NO" si la marca está claramente en el recuadro final a la derecha de "No" (Si [ ] No [X]) Y la pregunta 43 está completamente vacía.
43. "¿Por que?": Motivo manuscrito por el cual le gustaría o no tener espacios de diálogo. Si está en blanco, "".

======================================================================
FORMATO DE SALIDA:
Devuelve ÚNICAMENTE un objeto JSON válido con exactamente las 43 claves canónicas sin texto explicativo adicional.
"""

PROMPT_JSON_TEMPLATE = json.dumps({col: "" for col in COLUMNAS_FICHA}, indent=2, ensure_ascii=False)

USER_PROMPT = f"""Analiza minuciosamente el anverso (Página 1) y reverso (Página 2) adjuntos.
Aplica fidelidad visual estricta y dependencias condicionales (si una casilla está vacía o su pregunta principal es NO, devuelve "").
⚠️ RECUERDA:
1. Si 'Zona' o 'Régimen' no tienen ninguna casilla marcada en el papel, déjalos OBLIGATORIAMENTE vacíos (""). Prohibido inventar o asumir "URBANA" o "CONTRIBUTIVO".
2. En preguntas dicotómicas (38 embarazo adolescente, 39 preservativos EPS, 42 espacios de diálogo), el 'SI' está entre 'Si' y 'No' (Si [X] No [ ] = SI).
3. Si en la 43 ('¿Por que?') hay justificación escrita, la 42 es categóricamente "SI".
Devuelve ÚNICAMENTE el JSON con las siguientes 43 claves canónicas:
{PROMPT_JSON_TEMPLATE}
"""

SYSTEM_PROMPT_TEST = """Eres un sistema experto en transcripción OCR y digitalización forense de evaluaciones físicas oficiales de conocimiento (Pre-Test y Post-Test de Salud Sexual y Reproductiva / ITS - Anexo 4).
Tu misión es transcribir con EXACTITUD Y FIDELIDAD VISUAL ABSOLUTA la información de la imagen adjunta (1 sola página: formato de evaluación).

======================================================================
🚨 REGLAS INVIOLABLES DE EXTRACCIÓN Y FIDELIDAD VISUAL 🚨
======================================================================
1. CERO ALUCINACIONES: Extrae ÚNICAMENTE lo que esté físicamente marcado con una marca manuscrita (X, visto bueno ✔, raya, sombreado, cruz) o escrito a mano con tinta.
2. CASILLAS VACÍAS: Si una pregunta no fue marcada o un campo está en blanco, devuelve cadena vacía "". NUNCA adivines ni inventes respuestas.
3. TODO EN MAYÚSCULAS: Todo el texto debe devolverse en MAYÚSCULAS sin excepción.
4. TIPO DE EVALUACIÓN:
   - Examina el título superior del documento:
     * Si dice "PRE-TEST PARTICIPANTES- ANEXO Nº 4" -> "PRE-TEST"
     * Si dice "POST TEST PARTICIPANTES- ANEXO Nº 4" o "POST-TEST" -> "POST-TEST"
5. DATOS DEL PARTICIPANTE:
   - NOMBRE: Nombre completo manuscrito tal como se lee.
   - EDAD: Edad en número entero (ej. 14, 15, 16).
   - MUNICIPIO: Municipio cabecera (MAHATES, TURBANA, TURBACO, BARRANCO DE LOBA, SAN JACINTO DEL CAUCA, CALAMAR, MORALES, SANTA ROSA DEL SUR, ARENAL, SOPLAVIENTO).
   - EAPB: Entidad de salud (EPS) escrita (MUTUAL SER, COOSALUD, NUEVA EPS, SALUD TOTAL, SURA, SANITAS, etc.).
6. PREGUNTAS DICOTÓMICAS (1, 2, 3, 4, 6, 7, 8, 9):
   El diseño físico tiene casillas: "Verdadero (  )    Falso (  )"
   - Si la marca manuscrita está dentro o sobre el paréntesis de Verdadero -> "VERDADERO"
   - Si la marca manuscrita está dentro o sobre el paréntesis de Falso -> "FALSO"
   - Si ninguna está marcada -> ""
7. PREGUNTA 5 ("¿Cuál de las siguientes acciones ayuda a prevenir el VIH?"):
   El diseño presenta 4 opciones con paréntesis:
   (  ) Tener información clara sobre salud sexual.
   (  ) Usar preservativo.
   (  ) Evitar compartir agujas o elementos cortopunzantes.
   (  ) Todas las anteriores.
   - Identifica cuál paréntesis contiene la marca manuscrita:
     * Si marcó "Todas las anteriores" -> "TODAS LAS ANTERIORES"
     * Si marcó "Usar preservativo" -> "USAR PRESERVATIVO"
     * Si marcó "Tener información clara sobre salud sexual" -> "TENER INFORMACIÓN CLARA SOBRE SALUD SEXUAL"
     * Si marcó "Evitar compartir agujas o elementos cortopunzantes" -> "EVITAR COMPARTIR AGUJAS O ELEMENTOS CORTOPUNZANTES"
"""

USER_PROMPT_TEST = """Analiza la fotografía adjunta correspondiente al formato físico de evaluación (Pre-Test o Post-Test Anexo 4) y genera un objeto JSON válido con las siguientes claves exactas:
{
  "TIPO DE EVALUACIÓN": "PRE-TEST o POST-TEST según el título",
  "NOMBRE": "NOMBRE COMPLETO DEL PARTICIPANTE",
  "EDAD": "EDAD",
  "MUNICIPIO": "MUNICIPIO",
  "EAPB (EPS)": "EPS O EAPB",
  "1. EL USO CORRECTO DEL PRESERVATIVO AYUDA A PREVENIR ITS COMO VIH Y SÍFILIS.": "VERDADERO o FALSO o vacío",
  "2. LAS ITS PUEDEN TRANSMITIRSE DE LA MADRE AL BEBÉ DURANTE EL EMBARAZO.": "VERDADERO o FALSO o vacío",
  "3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA.": "VERDADERO o FALSO o vacío",
  "4. LOS ANTICONCEPTIVOS ORALES PREVIENEN LAS ITS.": "VERDADERO o FALSO o vacío",
  "5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?": "Opción seleccionada o vacía",
  "6. LA PREP ES UN MEDICAMENTO QUE AYUDA A PREVENIR EL VIH EN PERSONAS CON MAYOR RIESGO DE EXPOSICIÓN.": "VERDADERO o FALSO o vacío",
  "7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B.": "VERDADERO o FALSO o vacío",
  "8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.": "VERDADERO o FALSO o vacío",
  "9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES.": "VERDADERO o FALSO o vacío"
}
Devuelve EXCLUSIVAMENTE el JSON sin bloques markdown ni comentarios.
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


def optimizar_imagen_bytes(img_bytes: bytes, max_dim: int = 3200, calidad: int = 95) -> tuple[bytes, str]:
    """
    Preserva MÁXIMA FIDELIDAD VISUAL Y RESOLUCIÓN (Ultra High Quality hasta 3200px, 95% calidad y subsampling 4:4:4).
    Garantiza que el payload a la IA mantenga nitidez fotográfica absoluta para que los modelos
    (Qwen2.5-VL 72B, Gemini 2.5 Flash) puedan leer con precisión forense números continuos (teléfonos, cédulas),
    trazos tenues de bolígrafo y casillas de verificación sin artefactos de compresión.
    """
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes))
        w, h = img.size

        # Si la imagen ya es JPEG de alta calidad (<= 3200px) y peso manejable (<= 10MB), no recompilar
        if max(w, h) <= max_dim and len(img_bytes) <= 10 * 1024 * 1024 and getattr(img, 'format', '') == 'JPEG':
            return img_bytes, "image/jpeg"

        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        # subsampling=0 (4:4:4) previene el difuminado cromático en trazos finos de bolígrafo
        img.save(out_buf, format="JPEG", quality=calidad, subsampling=0, optimize=True)
        return out_buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning(f"No se pudo procesar imagen con PIL ({e}), utilizando bytes originales.")
        return img_bytes, "image/jpeg"


class VisionService:
    """Controlador de extracción multimodal para fichas físicas."""

    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.provider = os.getenv("VISION_PROVIDER", "gemini").lower()

    def _optimizar_imagen(self, img_bytes: bytes, mime_type: str = "image/jpeg") -> tuple[bytes, str]:
        """Helper para compatibilidad con optimización de imágenes."""
        return optimizar_imagen_bytes(img_bytes)

    def extraer_datos_ficha(self, img_anverso_bytes: bytes, img_reverso_bytes: bytes,
                            mime_type_1: str = "image/jpeg",
                            mime_type_2: str = "image/jpeg") -> Dict[str, str]:
        """
        Extrae los 43 campos canónicos a partir de los bytes de las dos imágenes.
        """
        img1_opt, mime1_opt = optimizar_imagen_bytes(img_anverso_bytes)
        img2_opt, mime2_opt = optimizar_imagen_bytes(img_reverso_bytes)
        logger.info(f"Imágenes optimizadas para IA: Anverso={len(img1_opt)/1024:.1f}KB, Reverso={len(img2_opt)/1024:.1f}KB")

        raw_json = None
        if self.provider == "openai" or (not self.gemini_api_key and self.openai_api_key):
            raw_json = self._procesar_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
        elif self.provider == "openrouter" or (not self.gemini_api_key and self.openrouter_api_key):
            raw_json = self._procesar_con_openrouter(img1_opt, img2_opt, mime1_opt, mime2_opt)
        else:
            try:
                raw_json = self._procesar_con_gemini(img1_opt, img2_opt, mime1_opt, mime2_opt)
            except Exception as e:
                if self.openai_api_key:
                    logger.warning(f"Gemini reportó error ({e}). Activando fallback a OpenAI...")
                    raw_json = self._procesar_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
                elif self.openrouter_api_key:
                    logger.warning(f"Gemini reportó error ({e}). Activando fallback a OpenRouter...")
                    raw_json = self._procesar_con_openrouter(img1_opt, img2_opt, mime1_opt, mime2_opt)
                else:
                    raise

        limpio = _limpiar_bloque_json(raw_json)
        try:
            parsed = json.loads(limpio)
        except Exception as e:
            raise ValueError(f"La respuesta de la IA no fue un JSON válido: {e}\nRespuesta recibida: {raw_json[:300]}")

        ficha = FichaCaracterizacion.model_validate(parsed)
        return ficha.to_canonical_dict()

    def _procesar_con_gemini(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Invoca Google Gemini con temperatura 0.0 determinista para evitar alucinaciones."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno.")

        try:
            import time
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key)
            part_1 = types.Part.from_bytes(data=img1, mime_type=mime1)
            part_2 = types.Part.from_bytes(data=img2, mime_type=mime2)

            primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            candidate_models = [
                primary_model,
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-flash-latest"
            ]
            models_to_try = list(dict.fromkeys(candidate_models))
            prompt_completo = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT}"

            last_err = None
            for m_name in models_to_try:
                try:
                    logger.info(f"Enviando fotos a Gemini con modelo '{m_name}' (temperature=0.0)...")
                    response = client.models.generate_content(
                        model=m_name,
                        contents=[prompt_completo, part_1, part_2],
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json"
                        )
                    )
                    if response and response.text:
                        return response.text
                except Exception as e:
                    last_err = e
                    logger.warning(f"Modelo '{m_name}' reportó fallo: {e}. Probando siguiente modelo...")
                    time.sleep(1.0)
                    continue

            if last_err:
                raise last_err
        except ImportError:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.gemini_api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
            )
            prompt_completo = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT}"
            contents = [
                prompt_completo,
                {"mime_type": mime1, "data": img1},
                {"mime_type": mime2, "data": img2}
            ]
            response = model.generate_content(contents)
            return response.text

    def _procesar_con_openai(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Invoca OpenAI GPT-4o con temperatura 0.0 determinista."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada en las variables de entorno.")

        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        b64_1 = base64.b64encode(img1).decode("utf-8")
        b64_2 = base64.b64encode(img2).decode("utf-8")

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.0,
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

    def _procesar_con_openrouter(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Invoca OpenRouter API con temperatura 0.0 determinista y cascada de modelos."""
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY no está configurada en las variables de entorno.")

        import httpx
        from openai import OpenAI
        http_client = httpx.Client(verify=False, timeout=150.0)
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key,
            http_client=http_client
        )
        b64_1 = base64.b64encode(img1).decode("utf-8")
        b64_2 = base64.b64encode(img2).decode("utf-8")

        primary_model = os.getenv("OPENROUTER_MODEL", "qwen/qwen2.5-vl-72b-instruct").strip()
        candidate_models = [
            primary_model,
            "qwen/qwen2.5-vl-72b-instruct",
            "google/gemini-2.5-flash",
            "openai/gpt-4o-mini"
        ]
        models_to_try = list(dict.fromkeys(candidate_models))

        last_err = None
        for model_name in models_to_try:
            try:
                logger.info(f"Enviando fotos a OpenRouter con modelo '{model_name}' (temperature=0.0)...")
                response = client.chat.completions.create(
                    model=model_name,
                    temperature=0.0,
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
                if response and response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
            except Exception as e:
                last_err = e
                logger.warning(f"Fallo en OpenRouter con modelo '{model_name}': {e}. Probando siguiente modelo...")
                continue

        if last_err:
            raise last_err
        return "{}"

    # -------------------------------------------------------------
    # MÉTODOS ESPECIALIZADOS PARA PRE-TEST Y POST-TEST (1 SOLA FOTO)
    # -------------------------------------------------------------
    def extraer_datos_test(
        self,
        img_bytes: bytes,
        mime_type: str = "image/jpeg",
        tipo_evaluacion_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extrae datos de 1 sola fotografía correspondiente al Pre-Test o Post-Test.
        Reconcilia automáticamente con participant_cache si existe coincidencia previa.
        """
        img_opt, mime_opt = optimizar_imagen_bytes(img_bytes)
        logger.info(f"Imagen del test optimizada para IA: {len(img_opt)/1024:.1f}KB ({mime_opt})")
        raw_json = "{}"

        if self.provider == "openrouter":
            try:
                raw_json = self._procesar_test_con_openrouter(img_opt, mime_opt)
            except Exception as e:
                logger.warning(f"OpenRouter reportó error en test ({e}). Activando fallback a Gemini...")
                if self.gemini_api_key:
                    raw_json = self._procesar_test_con_gemini(img_opt, mime_opt)
                elif self.openai_api_key:
                    raw_json = self._procesar_test_con_openai(img_opt, mime_opt)
                else:
                    raise
        elif self.provider == "openai":
            try:
                raw_json = self._procesar_test_con_openai(img_opt, mime_opt)
            except Exception as e:
                logger.warning(f"OpenAI reportó error en test ({e}). Activando fallback...")
                if self.gemini_api_key:
                    raw_json = self._procesar_test_con_gemini(img_opt, mime_opt)
                elif self.openrouter_api_key:
                    raw_json = self._procesar_test_con_openrouter(img_opt, mime_opt)
                else:
                    raise
        else:
            try:
                raw_json = self._procesar_test_con_gemini(img_opt, mime_opt)
            except Exception as e:
                logger.warning(f"Gemini reportó error en test ({e}). Activando fallback...")
                if self.openai_api_key:
                    raw_json = self._procesar_test_con_openai(img_opt, mime_opt)
                elif self.openrouter_api_key:
                    raw_json = self._procesar_test_con_openrouter(img_opt, mime_opt)
                else:
                    raise

        limpio = _limpiar_bloque_json(raw_json)
        try:
            parsed = json.loads(limpio)
        except Exception as e:
            raise ValueError(f"La respuesta de la IA para el test no fue un JSON válido: {e}\nRespuesta: {raw_json[:300]}")

        # Aplicar override manual de tipo de evaluación si fue seleccionado en UI
        if tipo_evaluacion_override and tipo_evaluacion_override.upper() in ["PRE-TEST", "POST-TEST"]:
            parsed["TIPO DE EVALUACIÓN"] = tipo_evaluacion_override.upper()

        test_obj = PrePostTest.model_validate(parsed)
        datos = test_obj.to_canonical_dict()

        # Reconciliar con base de datos de participantes si está cargada
        nombre_extraido = datos.get("NOMBRE", "")
        municipio_extraido = datos.get("MUNICIPIO", "")
        coincidencia = participant_cache.buscar_coincidencia(nombre_extraido, municipio_extraido)
        if coincidencia:
            logger.info(f"Reconciliando test de '{nombre_extraido}' con participante registrado: '{coincidencia['nombre']}'")
            datos["NOMBRE"] = coincidencia["nombre"]
            if not datos.get("EDAD") and coincidencia.get("edad"):
                datos["EDAD"] = coincidencia["edad"]
            if not datos.get("MUNICIPIO") and coincidencia.get("municipio"):
                datos["MUNICIPIO"] = coincidencia["municipio"]
            if not datos.get("EAPB (EPS)") and coincidencia.get("eapb"):
                datos["EAPB (EPS)"] = coincidencia["eapb"]

        return datos

    def _procesar_test_con_openrouter(self, img: bytes, mime: str) -> str:
        """Invoca OpenRouter API para procesar la hoja de evaluación del test."""
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY no está configurada.")

        import httpx
        from openai import OpenAI
        http_client = httpx.Client(verify=False, timeout=60.0)
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key,
            http_client=http_client
        )
        b64 = base64.b64encode(img).decode("utf-8")
        primary_model = os.getenv("OPENROUTER_MODEL", "qwen/qwen2.5-vl-72b-instruct").strip()
        candidate_models = [
            primary_model,
            "google/gemini-2.5-flash",
            "openai/gpt-4o-mini",
            "qwen/qwen2.5-vl-72b-instruct"
        ]
        models_to_try = list(dict.fromkeys(candidate_models))

        last_err = None
        for model_name in models_to_try:
            try:
                logger.info(f"Enviando test a OpenRouter con modelo '{model_name}'...")
                response = client.chat.completions.create(
                    model=model_name,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    messages=[
                        {
                            "role": "system",
                            "content": SYSTEM_PROMPT_TEST
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": USER_PROMPT_TEST},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                                }
                            ]
                        }
                    ]
                )
                if response and response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
            except Exception as e:
                last_err = e
                logger.warning(f"Fallo en OpenRouter (test) con '{model_name}': {e}. Probando siguiente...")
                continue

        if last_err:
            raise last_err
        return "{}"

    def _procesar_test_con_gemini(self, img: bytes, mime: str) -> str:
        """Invoca Google Gemini para procesar la hoja de evaluación del test."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurada.")

        try:
            import time
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.gemini_api_key)
            part = types.Part.from_bytes(data=img, mime_type=mime)

            primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            candidate_models = [
                primary_model,
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash"
            ]
            models_to_try = list(dict.fromkeys(candidate_models))
            prompt_completo = f"{SYSTEM_PROMPT_TEST}\n\n{USER_PROMPT_TEST}"

            last_err = None
            for m_name in models_to_try:
                try:
                    logger.info(f"Enviando test a Gemini con modelo '{m_name}'...")
                    response = client.models.generate_content(
                        model=m_name,
                        contents=[prompt_completo, part],
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json"
                        )
                    )
                    if response and response.text:
                        return response.text
                except Exception as e:
                    last_err = e
                    logger.warning(f"Modelo '{m_name}' reportó fallo en test: {e}. Probando siguiente...")
                    time.sleep(1.0)
                    continue

            if last_err:
                raise last_err
        except ImportError:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.gemini_api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = legacy_genai.GenerativeModel(
                model_name=model_name,
                generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
            )
            prompt_completo = f"{SYSTEM_PROMPT_TEST}\n\n{USER_PROMPT_TEST}"
            contents = [
                prompt_completo,
                {"mime_type": mime, "data": img}
            ]
            response = model.generate_content(contents)
            return response.text
        return "{}"

    def _procesar_test_con_openai(self, img: bytes, mime: str) -> str:
        """Invoca OpenAI GPT-4o para procesar la hoja de evaluación del test."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada.")

        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        b64 = base64.b64encode(img).decode("utf-8")

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT_TEST
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT_TEST},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"}
                        }
                    ]
                }
            ]
        )
        return response.choices[0].message.content or "{}"
