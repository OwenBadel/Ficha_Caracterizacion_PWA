"""
Servicio de Visión Artificial Multimodal (OCR Especializado y Forense).
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.

Procesa las fotografías físicas de Fichas de Caracterización y Evaluaciones Pre/Post Test
utilizando modelos de visión multimodal en local mediante Ollama (Qwen3-VL / MiniCPM-V)
acelerados por hardware NVIDIA GPU, con fallback opcional a OpenAI si está configurado.
Garantiza cero dependencias de servicios externos sujetos a cuotas o bloqueos concurrentes.
"""

from __future__ import annotations
import os
import json
import re
import base64
import logging
import time
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

# ======================================================================
# PROMPTS CANÓNICOS DE FORENSE OCR (FICHA DE CARACTERIZACIÓN)
# ======================================================================

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
   Si la pregunta principal está en "NO" o vacía, la pregunta secundaria dependiente ("¿Cuál?", "¿Cada cuánto?", "¿Cuándo fue la última vez?") DEBE SER OBLIGATORIAMENTE string vacío "".

======================================================================
📍 ORIENTACIÓN ESPACIAL CRÍTICA DE LAS CASILLAS (GEOMETRÍA DEL PAPEL) 📍
======================================================================

1. EN TODAS LAS PREGUNTAS DICOTÓMICAS (SI / NO):
   El diseño impreso en la ficha física ubica el recuadro [ ] A LA DERECHA de la palabra:
   
        Si [ ]   No [ ]

   ⚠️ REGLA DE LECTURA VISUAL:
   * PARA MARCAR "SI": El participante coloca la marca en el recuadro que está a la DERECHA de "Si":
        Si [X]   No [ ]   ===> RESPUESTA MARCADA ES "SI"
     (¡CUIDADO! Este recuadro queda en el medio entre "Si" y "No". NO lo confundas como si fuera de "No"; PERTENECE AL "SI").

   * PARA MARCAR "NO": El participante coloca la marca en el recuadro que está a la DERECHA de "No":
        Si [ ]   No [X]   ===> RESPUESTA MARCADA ES "NO"

2. EN LA PREGUNTA 41 DE TEMAS DE INTERÉS:
   AQUÍ EL DISEÑO IMPRESO ES INVERSO: El recuadro [ ] está A LA IZQUIERDA del texto:
        [X] VIH   [ ] SIFILIS   [ ] HEPATITIS B Y C   [ ] METODOS ANTICONCEPTIVOS ...

======================================================================
📋 MAPA ESTRUCTURAL DE LAS 43 PREGUNTAS
======================================================================
--- PÁGINA 1: ANVERSO (Preguntas 1 a 23) ---
1. "NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA": Encuestador oficial responsable.
2. "TERRITORIO": Municipio oficial cabecera.
3. "Nombre completo del participante": Nombre manuscrito legible en la hoja.
4. "Tipo de documento identidad": RC, TI, CC, PASAPORTE, PERMISO.
5. "Numero de documento identidad": Dígitos continuos sin puntos, ni espacios.
6. "Edad": Número entero manuscrito.
7. "Grado escolar": Número con símbolo de grado (ej: 8°, 9°, 10°, 11°).
8. "Teléfono de contacto": Dígitos continuos (ej: 3001234567). Si está en blanco, "".
9. "Dirección de residencia (barrio o vereda)": Dirección o barrio tal como fue escrito.
10. "Municipio": Mismo valor que "TERRITORIO".
11. "Zona": RURAL o URBANA. Si está en blanco, "".
12. "EPS (si tienes)": Entidad de salud. Si está en blanco, "".
13. "Régimen": CONTRIBUTIVO, SUBSIDIADO o NINGUNO. Si está en blanco, "".
14. "Sexo con el que te identificas": FEMENINO o MASCULINO.
15. "Identidad de género": HETEROSEXUAL, HOMOSEXUAL, BISEXUAL, TRANSGENERO, LESBIANA.
16. "¿Perteneces a alguna población o grupo étnico?": AFROCOLOMBIANO, INDÍGENA, PALENQUERO, VÍCTIMA DEL CONFLICTO, NO.
17. "¿Tienes alguna condición de discapacidad?": SI o NO.
18. "¿Cual?": Tipo de discapacidad si la 17 es SI.
19. "¿Tienes antecedentes de alguna enfermedad personal o familiar importante?": SI o NO.
20. "¿Cual?_1": Tipo de enfermedad si la 19 es SI.
21. "¿Has asistido al médico en el último año?": SI o NO.
22. "¿Cuándo fue la última vez?": Fecha si la 21 es SI.
23. "¿Fuiste al odontólogo el último año?": SI o NO.

--- PÁGINA 2: REVERSO (Preguntas 24 a 43) ---
24. "¿Qué actividades recreativas haces en tu tiempo libre?": Actividades manuscritas.
25. "¿Qué tiempo empleas en esta actividad?": Horas (ej: "2 HORAS").
26. "¿Consumes o has consumido cigarrillo o vapeador?": SI o NO.
27. "Cada cuánto?": Frecuencia si la 26 es SI.
28. "¿Consumes o has consumido alcohol?": SI o NO.
29. "Cada cuánto?_1": Frecuencia si la 28 es SI.
30. "¿Has consumido alguna sustancia psicoactiva?": SI o NO.
31. "¿Cual?_2": Sustancia si la 30 es SI.
32. "¿Has vivido situaciones de discriminación, rechazo o violencia?": SI o NO.
33. "¿Has recibido información sobre salud sexual, ITS o métodos de prevención?": SI o NO.
34. "¿Has iniciado tu vida sexual?": SI o NO.
35. "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?": SIEMPRE, CASI SIEMPRE o NUNCA si la 34 es SI.
36. "¿Conoces algún método anticonceptico?": SI o NO.
37. "¿Cual?_3": Método si la 36 es SI (si es implante/jadelle extraer "YADEL").
38. "¿Has vivido o conoces algún caso cercano de embarazo adolescente?": SI o NO (Si [X] No [ ] = SI).
39. "¿Te han entregado preservativos en la EPS o institución de salud?": SI o NO (Si [X] No [ ] = SI).
40. "¿Cuándo fue la ultima vez?": Fecha si la 39 es SI.
41. "¿Qué tema te gustaria aprender o entender mejor?": Opciones marcadas separadas por coma y espacio.
42. "¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?": SI o NO (Si [X] No [ ] = SI, o si la 43 tiene texto escrito = SI).
43. "¿Por que?": Motivo manuscrito.
"""

PROMPT_JSON_TEMPLATE = json.dumps({col: "" for col in COLUMNAS_FICHA}, indent=2, ensure_ascii=False)

USER_PROMPT = f"""Analiza minuciosamente el anverso (Página 1) y reverso (Página 2) adjuntos.
Aplica fidelidad visual estricta y dependencias condicionales (si una casilla está vacía o su pregunta principal es NO, devuelve "").
Devuelve ÚNICAMENTE un objeto JSON válido con las siguientes 43 claves canónicas:
{PROMPT_JSON_TEMPLATE}
"""

# ======================================================================
# PROMPTS CANÓNICOS DE EVALUACIONES PRE-TEST Y POST-TEST (ANEXO 4)
# ======================================================================

SYSTEM_PROMPT_TEST = """Eres un sistema forense de alta precisión especializado en la transcripción OCR de evaluaciones físicas de salud sexual y reproductiva (Pre-Test y Post-Test de Salud Sexual y Reproductiva / ITS - Anexo 4).
Tu misión es inspeccionar minuciosamente los trazos de tinta manuscrita en el papel físico.

======================================================================
🚨 REGLAS ESTRICTAS DE FIDELIDAD VISUAL Y CERO ALUCINACIÓN 🚨
======================================================================

1. CERO TEXTO IMPRESO EN CAMPOS MANUSCRITOS:
   - "TIPO DE EVALUACIÓN": Revisa el título superior:
     * Si dice "PRE-TEST PARTICIPANTES- ANEXO Nº 4" -> "PRE-TEST"
     * Si dice "POST TEST PARTICIPANTES- ANEXO Nº 4" o "POST-TEST" -> "POST-TEST"
   - "NOMBRE": Extrae ÚNICAMENTE el nombre y apellidos escritos a mano con bolígrafo al lado de "NOMBRE:".
   - "EDAD": Extrae únicamente los dígitos de la edad escrita a mano (ej: 14, 15, 16).
   - "MUNICIPIO": Extrae el municipio manuscrito (MAHATES, TURBANA, TURBACO, BARRANCO DE LOBA, SAN JACINTO DEL CAUCA, CALAMAR, MORALES, SANTA ROSA DEL SUR, ARENAL, SOPLAVIENTO).
   - "EAPB (EPS)": Extrae ÚNICAMENTE la entidad de salud manuscrita (ej: MUTUAL SER, COOSALUD, NUEVA EPS, SURA, SANITAS, SALUD TOTAL, etc.).
     🚨 REGLA VITAL EN EAPB: Si el participante NO escribió nada en la línea de EAPB (está vacía o en blanco), DEVUELVE OBLIGATORIAMENTE string vacío "".
     ESTRICTAMENTE PROHIBIDO copiar o extraer la frase impresa de abajo que dice 'Marque con una X dependiendo de la afirmación:' o cualquier otro texto instructivo del formulario. Si no hay EPS manuscrita, devuelve "".

2. DETECCIÓN DE MARCAS EN PREGUNTAS DICOTÓMICAS (1, 2, 3, 4, 6, 7, 8, 9):
   Cada una de estas preguntas tiene debajo dos opciones con paréntesis:
        Verdadero (  )    Falso (  )
   
   - La opción 'Verdadero' está a la IZQUIERDA.
   - La opción 'Falso' está a la DERECHA.
   - El participante marca con una 'X', un visto bueno (✔), un punto, cruz o raya de bolígrafo.
   - Si la marca manuscrita está dentro del paréntesis de Verdadero, o marcando/tachando la palabra Verdadero -> extrae "VERDADERO".
   - Si la marca manuscrita está dentro del paréntesis de Falso, o marcando/tachando la palabra Falso -> extrae "FALSO".
   - Si ninguna opción tiene trazos manuscritos de tinta -> devuelve "".

3. PREGUNTA 5 ("¿Cuál de las siguientes acciones ayuda a prevenir el VIH?"):
   Tiene 4 opciones en lista vertical, cada una con un paréntesis (  ) a la IZQUIERDA del texto:
        (  ) Tener información clara sobre salud sexual.
        (  ) Usar preservativo.
        (  ) Evitar compartir agujas o elementos cortopunzantes.
        (  ) Todas las anteriores.
   
   - Examina cuál de los 4 paréntesis de la izquierda tiene la marca manuscrita (X, ✔, punto, raya):
     * Si la marca está en la primera opción -> "TENER INFORMACIÓN CLARA SOBRE SALUD SEXUAL"
     * Si la marca está en la segunda opción -> "USAR PRESERVATIVO"
     * Si la marca está en la tercera opción -> "EVITAR COMPARTIR AGUJAS O ELEMENTOS CORTOPUNZANTES"
     * Si la marca está en la cuarta opción -> "TODAS LAS ANTERIORES"
     * Si no hay ninguna marca -> ""
"""

USER_PROMPT_TEST = """Analiza la fotografía adjunta correspondiente al formato físico de evaluación (Pre-Test o Post-Test Anexo 4) y genera un objeto JSON válido con las siguientes claves exactas:
{
  "TIPO DE EVALUACIÓN": "PRE-TEST o POST-TEST según el título",
  "NOMBRE": "NOMBRE COMPLETO DEL PARTICIPANTE",
  "EDAD": "EDAD",
  "MUNICIPIO": "MUNICIPIO",
  "EAPB (EPS)": "EPS MANUSCRITA o vacía (NUNCA el texto impreso 'Marque con una X...')",
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


def _reparar_json_truncado(texto: str) -> str:
    """Si el JSON fue cortado a mitad de una clave o valor, lo auto-cierra para recuperar lo extraído."""
    texto = texto.strip()
    if not texto.startswith("{"):
        start = texto.find("{")
        if start != -1:
            texto = texto[start:]
        else:
            return texto
    if texto.endswith("}"):
        return texto

    lineas = texto.splitlines()
    lineas_limpias = []
    for l in lineas:
        if l.count('"') % 2 != 0:
            break
        lineas_limpias.append(l)

    texto_reparado = "\n".join(lineas_limpias).rstrip()
    if texto_reparado.endswith(","):
        texto_reparado = texto_reparado[:-1]
    if not texto_reparado.endswith("}"):
        texto_reparado += "\n}"
    return texto_reparado


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
        return texto[start:end + 1]
    return _reparar_json_truncado(texto)


def optimizar_imagen_bytes(img_bytes: bytes, max_dim: int = 1400, calidad: int = 90) -> tuple[bytes, str]:
    """
    Optimiza la imagen manteniendo alta resolución y nitidez para el modelo de visión (1400px).
    Garantiza orientación vertical si fue capturada rotada.
    """
    try:
        from PIL import Image, ImageOps
        import io

        img = Image.open(io.BytesIO(img_bytes))
        img = ImageOps.exif_transpose(img)

        # Rotar a vertical si el ancho supera el alto
        if img.width > img.height:
            img = img.rotate(270, expand=True)

        # Redimensionar suavemente si excede max_dim
        if max(img.width, img.height) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        if img.mode != "RGB":
            img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=calidad, optimize=True)
        return buffer.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning(f"No se pudo procesar imagen con PIL ({e}), utilizando bytes originales.")
        return img_bytes, "image/jpeg"


# ======================================================================
# CLASE PRINCIPAL: VISION SERVICE (OLLAMA GPU SOBERANO)
# ======================================================================

class VisionService:
    """Controlador de extracción multimodal forense para fichas físicas y tests."""

    def __init__(self):
        self.provider = os.getenv("VISION_PROVIDER", "ollama").lower().strip()
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3-vl").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

        logger.info(
            f"VisionService inicializado -> Proveedor: '{self.provider}', "
            f"Modelo Ollama: '{self.ollama_model}', Endpoint: '{self.ollama_base_url}'"
        )

    def _optimizar_imagen(self, img_bytes: bytes, mime_type: str = "image/jpeg") -> tuple[bytes, str]:
        return optimizar_imagen_bytes(img_bytes)

    # -----------------------------------------------------------------
    # EXTRACCIÓN DE FICHAS DE CARACTERIZACIÓN (2 IMÁGENES)
    # -----------------------------------------------------------------

    def extraer_datos_ficha(
        self,
        img_anverso_bytes: bytes,
        img_reverso_bytes: bytes,
        mime_type_1: str = "image/jpeg",
        mime_type_2: str = "image/jpeg"
    ) -> Dict[str, str]:
        """
        Extrae los 43 campos canónicos a partir de las fotografías del Anverso y Reverso.
        Aprende automáticamente los datos del participante en el caché local.
        """
        img1_opt, mime1_opt = optimizar_imagen_bytes(img_anverso_bytes)
        img2_opt, mime2_opt = optimizar_imagen_bytes(img_reverso_bytes)
        logger.info(
            f"Imágenes de Ficha optimizadas: Anverso={len(img1_opt)/1024:.1f}KB, "
            f"Reverso={len(img2_opt)/1024:.1f}KB"
        )

        raw_json = None
        if self.provider == "openai" or (self.provider != "ollama" and self.openai_api_key):
            raw_json = self._procesar_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
        else:
            try:
                raw_json = self._procesar_con_ollama(img1_opt, img2_opt, mime1_opt, mime2_opt)
            except Exception as e:
                if self.openai_api_key:
                    logger.warning(f"Ollama reportó error ({e}). Activando fallback a OpenAI...")
                    raw_json = self._procesar_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
                else:
                    raise

        limpio = _limpiar_bloque_json(raw_json)
        try:
            parsed = json.loads(limpio)
        except Exception as e:
            raise ValueError(f"La respuesta de la IA no fue un JSON válido: {e}\nRespuesta recibida: {raw_json[:300]}")

        ficha = FichaCaracterizacion.model_validate(parsed)
        datos_canonicos = ficha.to_canonical_dict()

        # Auto-aprendizaje en el caché de participantes (memoria viva de la fábrica)
        nom = datos_canonicos.get("Nombre completo del participante", "")
        if nom and len(nom) >= 4:
            participant_cache.aprender_participante(
                nombre=nom,
                edad=datos_canonicos.get("Edad", ""),
                municipio=datos_canonicos.get("Municipio", "") or datos_canonicos.get("TERRITORIO", ""),
                eapb=datos_canonicos.get("EPS (si tienes)", ""),
                documento=datos_canonicos.get("Numero de documento identidad", "")
            )

        return datos_canonicos

    def _procesar_con_ollama(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Invoca la API local de Ollama con formato JSON estricto y temperatura 0.0."""
        import httpx
        b64_1 = base64.b64encode(img1).decode("utf-8")
        b64_2 = base64.b64encode(img2).decode("utf-8")

        prompt_completo = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT}"
        payload = {
            "model": self.ollama_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_completo,
                    "images": [b64_1, b64_2]
                }
            ],
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_ctx": 16384,
                "num_predict": 4096
            },
            "stream": False
        }

        endpoint = f"{self.ollama_base_url}/api/chat"
        logger.info(f"Enviando fotos de Ficha a Ollama ({self.ollama_model}) en {endpoint}...")

        # Intentar con modelo primario y fallback si es necesario
        modelos_a_probar = [self.ollama_model, "qwen3-vl", "minicpm-v"]
        modelos_unicos = list(dict.fromkeys(modelos_a_probar))
        ultimo_error = None

        with httpx.Client(timeout=180.0) as client:
            for mod in modelos_unicos:
                try:
                    payload["model"] = mod
                    resp = client.post(endpoint, json=payload)
                    if resp.status_code == 200:
                        contenido = resp.json().get("message", {}).get("content", "{}")
                        if contenido and contenido.strip():
                            return contenido
                    else:
                        logger.warning(f"Ollama con modelo '{mod}' retornó HTTP {resp.status_code}: {resp.text}")
                except Exception as ex:
                    ultimo_error = ex
                    logger.warning(f"Error invocando modelo '{mod}' en Ollama: {ex}. Probando siguiente...")

        if ultimo_error:
            raise ultimo_error
        raise RuntimeError("Ollama no pudo generar una respuesta válida para la ficha.")

    # -----------------------------------------------------------------
    # EXTRACCIÓN DE PRE-TEST Y POST-TEST (1 SOLA FOTOGRAFÍA)
    # -----------------------------------------------------------------

    def extraer_datos_test(
        self,
        img_bytes: bytes,
        mime_type: str = "image/jpeg",
        tipo_evaluacion_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extrae datos de 1 fotografía correspondiente a Pre-Test o Post-Test.
        Reconcilia automáticamente con el PATRÓN MAESTRO y el caché de participantes
        mediante Jaro-Winkler tokenizado para garantizar coincidencia del 100% en:
        NOMBRE, EDAD, MUNICIPIO y EPS (EAPB).
        """
        img_opt, mime_opt = optimizar_imagen_bytes(img_bytes)
        logger.info(f"Imagen de Test optimizada: {len(img_opt)/1024:.1f}KB ({mime_opt})")

        raw_json = None
        if self.provider == "openai" or (self.provider != "ollama" and self.openai_api_key):
            raw_json = self._procesar_test_con_openai(img_opt, mime_opt)
        else:
            try:
                raw_json = self._procesar_test_con_ollama(img_opt, mime_opt)
            except Exception as e:
                if self.openai_api_key:
                    logger.warning(f"Ollama reportó error en test ({e}). Activando fallback a OpenAI...")
                    raw_json = self._procesar_test_con_openai(img_opt, mime_opt)
                else:
                    raise

        limpio = _limpiar_bloque_json(raw_json)
        try:
            parsed = json.loads(limpio)
        except Exception as e:
            raise ValueError(f"La respuesta de la IA para el test no fue un JSON válido: {e}\nRespuesta: {raw_json[:300]}")

        # Aplicar override manual si fue seleccionado explícitamente en el frontend
        if tipo_evaluacion_override and tipo_evaluacion_override.upper() in ["PRE-TEST", "POST-TEST"]:
            parsed["TIPO DE EVALUACIÓN"] = tipo_evaluacion_override.upper()

        test_obj = PrePostTest.model_validate(parsed)
        datos = test_obj.to_canonical_dict()

        # ==============================================================
        # RECONCILIACIÓN ESTRICTA CON PATRÓN MAESTRO (JARO-WINKLER)
        # ==============================================================
        nombre_extraido = datos.get("NOMBRE", "")
        municipio_extraido = datos.get("MUNICIPIO", "")
        coincidencia = participant_cache.buscar_coincidencia(nombre_extraido, municipio_extraido)

        if coincidencia:
            score = coincidencia.get("score", 1.0)
            logger.info(
                f"Reconciliando test: '{nombre_extraido}' -> '{coincidencia['nombre']}' "
                f"(Score Jaro-Winkler: {score:.3f}). Estandarizando Nombre, Edad, EPS y Municipio."
            )
            # Sobrescribir exactamente las columnas compartidas con el Patrón Maestro
            datos["NOMBRE"] = coincidencia["nombre"]
            if coincidencia.get("edad"):
                datos["EDAD"] = coincidencia["edad"]
            if coincidencia.get("municipio"):
                datos["MUNICIPIO"] = coincidencia["municipio"]
            if coincidencia.get("eapb"):
                datos["EAPB (EPS)"] = coincidencia["eapb"]

        return datos

    def _procesar_test_con_ollama(self, img: bytes, mime: str) -> str:
        """Invoca Ollama local para procesar la evaluación física del test."""
        import httpx
        b64 = base64.b64encode(img).decode("utf-8")

        prompt_completo = f"{SYSTEM_PROMPT_TEST}\n\n{USER_PROMPT_TEST}"
        payload = {
            "model": self.ollama_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_completo,
                    "images": [b64]
                }
            ],
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_ctx": 6144,
                "num_predict": 2500
            },
            "stream": False
        }

        endpoint = f"{self.ollama_base_url}/api/chat"
        logger.info(f"Enviando test a Ollama ({self.ollama_model}) en {endpoint}...")

        modelos_a_probar = [self.ollama_model, "qwen3-vl", "minicpm-v"]
        modelos_unicos = list(dict.fromkeys(modelos_a_probar))
        ultimo_error = None

        with httpx.Client(timeout=180.0) as client:
            for mod in modelos_unicos:
                try:
                    payload["model"] = mod
                    resp = client.post(endpoint, json=payload)
                    if resp.status_code == 200:
                        msg = resp.json().get("message", {})
                        contenido = msg.get("content", "")
                        # Si content viene vacío porque el modelo razonador puso el JSON en thinking
                        if not contenido or not contenido.strip():
                            thinking = msg.get("thinking", "")
                            if thinking and "{" in thinking and "}" in thinking:
                                match = re.search(r"(\{.*\})", thinking, re.DOTALL)
                                if match:
                                    contenido = match.group(1)
                        if contenido and contenido.strip():
                            return contenido
                    else:
                        logger.warning(f"Ollama test con modelo '{mod}' retornó HTTP {resp.status_code}: {resp.text}")
                except Exception as ex:
                    ultimo_error = ex
                    logger.warning(f"Error en Ollama test con modelo '{mod}': {ex}. Probando siguiente...")

        if ultimo_error:
            raise ultimo_error
        raise RuntimeError("Ollama no pudo generar una respuesta válida para el test.")

    # -----------------------------------------------------------------
    # MÉTODOS DE FALLBACK SECUNDARIO (OPENAI SI TIENE API KEY)
    # -----------------------------------------------------------------

    def _procesar_con_openai(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Fallback opcional con OpenAI si está configurado en el entorno."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada para fallback.")

        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        b64_1 = base64.b64encode(img1).decode("utf-8")
        b64_2 = base64.b64encode(img2).decode("utf-8")

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:{mime1};base64,{b64_1}"}},
                        {"type": "image_url", "image_url": {"url": f"data:{mime2};base64,{b64_2}"}}
                    ]
                }
            ]
        )
        return response.choices[0].message.content or "{}"

    def _procesar_test_con_openai(self, img: bytes, mime: str) -> str:
        """Fallback opcional de OpenAI para test."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada para fallback.")

        from openai import OpenAI
        client = OpenAI(api_key=self.openai_api_key)
        b64 = base64.b64encode(img).decode("utf-8")

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TEST},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": USER_PROMPT_TEST},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                    ]
                }
            ]
        )
        return response.choices[0].message.content or "{}"
