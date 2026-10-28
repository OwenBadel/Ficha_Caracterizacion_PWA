"""
Servicio de Visión Artificial Multimodal (OCR Especializado y Forense).
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.

Procesa las fotografías físicas de Fichas de Caracterización y Evaluaciones Pre/Post Test
utilizando modelos de visión multimodal de alta precisión mediante Google Gemini (gemini-2.5-flash),
con control de tasa inteligente (Rate Limiter), reconciliación Jaro-Winkler contra el Patrón Maestro,
y fallback opcional a OpenAI si está configurado.
"""

from __future__ import annotations
import os
import json
import re
import base64
import logging
import time
import random
import threading
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logger = logging.getLogger("vision_service")

try:
    from .schema import FichaCaracterizacion, COLUMNAS_FICHA, normalizar_territorio, normalizar_eps
    from .schema_test import PrePostTest
    from .schema_anexo17 import PrePostTestAnexo17, normalizar_municipio as normalizar_municipio_anexo17
    from .participant_cache import participant_cache
except (ImportError, ValueError):
    from schema import FichaCaracterizacion, COLUMNAS_FICHA, normalizar_territorio, normalizar_eps
    from schema_test import PrePostTest
    from schema_anexo17 import PrePostTestAnexo17, normalizar_municipio as normalizar_municipio_anexo17
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

PROMPT_JSON_TEMPLATE = json.dumps({f"c{i}": col for i, col in enumerate(COLUMNAS_FICHA, 1)}, indent=2, ensure_ascii=False)

USER_PROMPT = f"""Analiza minuciosamente el anverso (Página 1) y reverso (Página 2) adjuntos.
Aplica fidelidad visual estricta y dependencias condicionales (si una casilla está vacía o su pregunta principal es NO, devuelve "").
Devuelve ÚNICAMENTE un objeto JSON ultracompacto con las 43 claves indexadas ("c1" a "c43") correspondientes a cada columna:
{PROMPT_JSON_TEMPLATE}
"""


def deserializar_json_ficha(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Estandariza respuestas de Gemini mapeando claves indexadas ('c1' a 'c43')
    o claves canónicas completas hacia el diccionario de 43 columnas canónicas.
    """
    resultado = {}
    for i, col in enumerate(COLUMNAS_FICHA, 1):
        clave_idx = f"c{i}"
        if clave_idx in parsed:
            resultado[col] = parsed[clave_idx]
        elif col in parsed:
            resultado[col] = parsed[col]
        else:
            val = None
            for pk, pv in parsed.items():
                if pk.strip().lower() == col.strip().lower():
                    val = pv
                    break
            resultado[col] = val if val is not None else ""

    for k, v in parsed.items():
        if not (k.startswith("c") and k[1:].isdigit()) and k not in resultado:
            resultado[k] = v

    return resultado

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

   🚨 REGLA CARDINAL: CERO SESGO MÉDICO O JUICIO CIENTÍFICO 🚨
   - Esto es una evaluación educativa (Pre-Test). Los participantes tienen dudas, mitos y responden erróneamente por desinformación.
   - ESTRICTAMENTE PROHIBIDO responder según lo que sea médicamente correcto. Tu único trabajo es observar la tinta física del papel.
   - Si el participante marcó "FALSO" en una afirmación que científicamente es verdadera (como en la pregunta 8: 'La sífilis tiene tratamiento y puede prevenirse', o en la pregunta 7: 'Existe vacuna para prevenir la Hepatitis B'), DEBES TRANSCRIBIR OBLIGATORIAMENTE "FALSO".
   - Jamás pongas "VERDADERO" por lógica médica si la 'X' está en el lado de "Falso".
   
   GEOMETRÍA FÍSICA DE LAS CASILLAS:
   - La opción 'Verdadero (  )' está SIEMPRE a la IZQUIERDA.
   - La opción 'Falso (  )' está SIEMPRE a la DERECHA.
   - El participante marca con una 'X', cruz (+), visto bueno (✔), punto, tilde o tachón de bolígrafo.
   - Si la marca está en el paréntesis o sobre la opción de la DERECHA ('Falso') -> extrae estrictamente "FALSO".
   - Si la marca está en el paréntesis o sobre la opción de la IZQUIERDA ('Verdadero') -> extrae estrictamente "VERDADERO".
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
  "8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.": "VERDADERO o FALSO (observa estrictamente la casilla marcada con X, CERO sesgo médico)",
  "9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES.": "VERDADERO o FALSO o vacío"
}
Devuelve EXCLUSIVAMENTE el JSON sin bloques markdown ni comentarios.
"""

# ======================================================================
# PROMPTS CANÓNICOS DE FORENSE OCR (ANEXO 17 PELLÍZCATE CON GENERACIÓN B+)
# ======================================================================

SYSTEM_PROMPT_ANEXO17 = """Eres un sistema experto en transcripción OCR y digitalización forense de evaluaciones físicas de conocimiento (Pre-Test y Post-Test del Anexo 17: "Pellízcate con Generación B+").
Tu única misión es transcribir con EXACTITUD Y FIDELIDAD VISUAL ABSOLUTA la información de las imágenes adjuntas correspondientes a las hojas físicas de la evaluación.

======================================================================
🚨 ESTRUCTURA FÍSICA EN 2 PÁGINAS (2 HOJAS POR EVALUACIÓN) 🚨
======================================================================
1. La evaluación física consta de dos páginas (o 2 imágenes adjuntas):
   - PÁGINA 1 (Anverso): Encabezado ("PRE-TEST" o "POST-TEST"), datos manuscritos del participante (Nombre, Municipio, Fecha, Edad) y las Preguntas 1 a 5.
   - PÁGINA 2 (Reverso): Preguntas 6 a 10.
2. Consolida toda la información de ambas páginas en un ÚNICO objeto JSON con los 15 campos exactos.

======================================================================
🚨 REGLA DE ORO DE FIDELIDAD VISUAL (ESTRICTAMENTE PROHIBIDO ALUCINAR) 🚨
======================================================================
1. CERO ALUCINACIONES: Extrae EXCLUSIVAMENTE lo que esté físicamente marcado con una marca manuscrita (X, visto bueno, sombreado, cruz) o escrito a mano con tinta en el documento.
2. CASILLAS VACÍAS: Si una pregunta NO fue marcada o está en blanco, devuelve OBLIGATORIAMENTE un string vacío "". NUNCA adivines ni supongas una respuesta si el participante la dejó sin contestar.
3. TODO EN MAYÚSCULAS: Todo el texto debe devolverse en MAYÚSCULAS sin excepción.
4. TIPO DE EVALUACIÓN:
   - Inspecciona el encabezado superior de la Página 1:
     * Si contiene "PRE-TEST" o "PRE TEST" -> "PRE-TEST"
     * Si contiene "POS-TEST", "POS TEST" o "POST-TEST" -> "POST-TEST"
5. DATOS DEL PARTICIPANTE:
   - Nombre: Lee el texto manuscrito en "Nombre: __________________________".
   - Municipio: Lee el texto manuscrito en "Municipio: __________________________" (frecuentemente "SANTA CATALINA", "TURBANA" u otro municipio del departamento de Bolívar). Devuélvelo transcrito con fidelidad en MAYÚSCULAS. Si no está legible o está en blanco, devuelve "SANTA CATALINA".
   - Fecha: Lee la fecha manuscrita en "Fecha: ___________________________". Estandariza obligatoriamente a formato numérico DD/MM/AAAA (por ejemplo: si dice "14 de septiembre de 2026", "14 septiembre 2026", "14-sep-26" o cualquier nombre de mes, estandarízalo siempre con el mes en números: "14/09/2026"; si solo viene mes y año, "09/2026").
   - Edad: Lee los dígitos manuscritos en "Edad: _______".
6. PREGUNTAS DE OPCIÓN MÚLTIPLE (1 A 10):
   Cada una de las 10 preguntas ofrece 3 opciones (a, b, c).
   Identifica cuál de las opciones tiene la marca con una 'X', cruz o visto bueno:
   - Pregunta 1: "¿Qué es un proyecto de vida?"
     Opciones: a (Un plan sobre lo que quiero lograr en el futuro), b (Una tarea del colegio), c (Un juego entre amigos).
   - Pregunta 2: "Si alguien quiere tocar tu cuerpo y tú no deseas, ¿qué puedes hacer?"
     Opciones: a (Quedarte callado), b (Decir “no”, alejarte y buscar ayuda), c (Aceptar para evitar problemas).
   - Pregunta 3: "¿Cuál ayuda a prevenir un embarazo y las infecciones de transmisión sexual?"
     Opciones: a (El uso correcto del condón), b (Compartir información personal), c (Tomar cualquier medicamento).
   - Pregunta 4: "¿Qué debes hacer si sufres bullying o ciberacoso?"
     Opciones: a (Responder con violencia), b (Guardarlo en secreto), c (Contárselo a un adulto de confianza y pedir ayuda).
   - Pregunta 5: "¿Cuál es una forma saludable de manejar una emoción difícil?"
     Opciones: a (Hablar con alguien de confianza), b (Lastimarse o lastimar a otra persona), c (Ignorar siempre lo que se siente).
   - Pregunta 6: "Si un amigo dice que no quiere seguir viviendo, ¿qué debes hacer?"
     Opciones: a (Pensar que está bromeando), b (Escucharlo y buscar inmediatamente la ayuda de un adulto), c (Dejarlo solo para que se calme).
   - Pregunta 7: "¿Qué significa comunicarse de manera asertiva?"
     Opciones: a (Expresar lo que pienso y siento con respeto), b (Gritar para que me escuchen), c (Quedarme callado, aunque algo me moleste).
   - Pregunta 8: "¿Qué es una red de apoyo?"
     Opciones: a (Personas e instituciones que pueden orientarnos y ayudarnos), b (Un grupo de redes sociales), c (Personas que deciden todo por nosotros).
   - Pregunta 9: "¿Cuál de estas situaciones puede afectar los derechos de un adolescente?"
     Opciones: a (Estudiar y participar en actividades culturales), b (Ser obligado a trabajar o vincularse a un grupo armado), c (Recibir orientación de su familia).
   - Pregunta 10: "Antes de tomar una decisión importante, lo mejor es:"
     Opciones: a (Pensar en las consecuencias y pedir orientación), b (Hacer lo que digan los demás), c (Actuar sin pensar).

   Para cada pregunta, devuelve la letra y texto canónico (ej: "A. UN PLAN SOBRE LO QUE QUIERO LOGRAR EN EL FUTURO", "B. DECIR “NO”, ALEJARTE Y BUSCAR AYUDA", etc.) o simplemente la letra marcada ("A", "B", "C"). Si ninguna opción está marcada, devuelve "".
"""

USER_PROMPT_ANEXO17 = """Analiza las fotografías adjuntas correspondientes al formato físico de evaluación (Página 1 y Página 2 del Anexo 17 Pellízcate con Generación B+) y genera un objeto JSON válido con las siguientes claves exactas:
{
  "TIPO DE EVALUACIÓN": "PRE-TEST o POST-TEST según el título/encabezado",
  "NOMBRE": "NOMBRE COMPLETO MANUSCRITO",
  "MUNICIPIO": "SANTA CATALINA o TURBANA según texto manuscrito o asignado",
  "FECHA": "FECHA MANUSCRITA ESTANDARIZADA NUMÉRICA (DD/MM/AAAA) o vacía",
  "EDAD": "EDAD EN DÍGITOS o vacía",
  "1. ¿QUÉ ES UN PROYECTO DE VIDA?": "Opción seleccionada (A, B, C o texto) o vacía",
  "2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?": "Opción seleccionada (A, B, C o texto) o vacía",
  "3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?": "Opción seleccionada (A, B, C o texto) o vacía",
  "4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?": "Opción seleccionada (A, B, C o texto) o vacía",
  "5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?": "Opción seleccionada (A, B, C o texto) o vacía",
  "6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?": "Opción seleccionada (A, B, C o texto) o vacía",
  "7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?": "Opción seleccionada (A, B, C o texto) o vacía",
  "8. ¿QUÉ ES UNA RED DE APOYO?": "Opción seleccionada (A, B, C o texto) o vacía",
  "9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?": "Opción seleccionada (A, B, C o texto) o vacía",
  "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:": "Opción seleccionada (A, B, C o texto) o vacía"
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


def optimizar_imagen_bytes(
    img_bytes: bytes,
    max_dim: int = 1600,
    calidad: int = 90,
    auto_rotar: bool = True
) -> tuple[bytes, str]:
    """
    Optimiza la imagen manteniendo alta resolución y nitidez para el modelo de visión.
    Si auto_rotar es False y la imagen ya viene optimizada desde el frontend
    en formato JPEG con dimensiones adecuadas (<= max_dim), retorna los bytes directamente
    evitando la doble compresión JPEG y preservando la nitidez de los trazos manuscritos.
    """
    if not img_bytes:
        return img_bytes, "image/jpeg"

    # Si no requiere auto_rotar, verificar si ya es JPEG y cumple dimensiones sin recompresión
    if not auto_rotar:
        try:
            from PIL import Image
            import io
            with Image.open(io.BytesIO(img_bytes)) as probe:
                if probe.format == "JPEG" and max(probe.width, probe.height) <= max_dim:
                    return img_bytes, "image/jpeg"
        except Exception:
            pass

    try:
        from PIL import Image, ImageOps
        import io

        img = Image.open(io.BytesIO(img_bytes))
        img = ImageOps.exif_transpose(img)

        # Rotar a vertical si el ancho supera el alto únicamente si auto_rotar está activo
        if auto_rotar and img.width > img.height:
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
# CONTROLADOR DE RANGO DE VELOCIDAD THREAD-SAFE (RATE LIMITER)
# ======================================================================

class PipelineRateLimiter:
    """Controlador thread-safe de intervalo mínimo entre llamadas a Gemini API."""
    def __init__(self, min_interval_seconds: float = 2.0):
        self.min_interval = min_interval_seconds
        self._last_call_timestamp = 0.0
        self._lock = threading.Lock()

    def esperar_turno(self) -> float:
        with self._lock:
            ahora = time.time()
            transcurrido = ahora - self._last_call_timestamp
            if transcurrido < self.min_interval:
                tiempo_espera = self.min_interval - transcurrido
                logger.info(
                    f"PipelineRateLimiter: espaciando llamada a Gemini API "
                    f"({tiempo_espera:.2f}s para respetar límite de {self.min_interval:.1f}s)..."
                )
                time.sleep(tiempo_espera)
                esperado = tiempo_espera
            else:
                esperado = 0.0

            self._last_call_timestamp = time.time()
            return esperado

    def reset(self):
        with self._lock:
            self._last_call_timestamp = 0.0

pipeline_rate_limiter = PipelineRateLimiter(
    min_interval_seconds=float(os.getenv("GEMINI_MIN_INTERVAL_SECONDS", "2.0"))
)


def _es_error_transitorio(error: Exception) -> bool:
    """
    Identifica si el error de la API es transitorio (503 Service Unavailable,
    429 Rate Limit / ResourceExhausted, 500/502/504 o timeouts) para aplicar Exponential Backoff.
    """
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if code in (503, 429, 500, 502, 504):
        return True
    err_str = str(error).lower()
    return any(term in err_str for term in [
        "503", "unavailable", "overloaded",
        "429", "resource_exhausted", "quota", "rate limit",
        "500", "internal error", "502", "504", "gateway",
        "timeout", "timed out", "connection", "disconnected", "reset by peer"
    ])


# ======================================================================
# CLASE PRINCIPAL: VISION SERVICE (GOOGLE GEMINI DE ALTA PRECISIÓN)
# ======================================================================

class VisionService:
    """Controlador de extracción multimodal forense para fichas físicas y tests."""

    def __init__(self, rate_limiter: Optional[PipelineRateLimiter] = None):
        self.provider = os.getenv("VISION_PROVIDER", "gemini").lower().strip()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.rate_limiter = rate_limiter or pipeline_rate_limiter
        self._gemini_client = None
        self._openai_client = None
        self._init_clients()

        logger.info(
            f"VisionService inicializado -> Proveedor: '{self.provider}', "
            f"Gemini configurado: {bool(self.gemini_api_key)}, "
            f"OpenAI configurado: {bool(self.openai_api_key)}"
        )

    def _init_clients(self):
        """Inicializa los clientes HTTP persistentes para reutilizar pools de conexiones TLS."""
        if self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception:
                self._gemini_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception:
                self._openai_client = None

    def _get_gemini_client(self):
        """Retorna el cliente persistente de Gemini o lo instancia de forma lazy."""
        if not self._gemini_client and self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception:
                self._gemini_client = None
        return self._gemini_client

    def _get_openai_client(self):
        """Retorna el cliente persistente de OpenAI o lo instancia de forma lazy."""
        if not self._openai_client and self.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception:
                self._openai_client = None
        return self._openai_client

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
        mime_type_2: str = "image/jpeg",
        auto_rotar: bool = True
    ) -> Dict[str, str]:
        """
        Extrae los 43 campos canónicos a partir de las fotografías del Anverso y Reverso.
        Aprende automáticamente los datos del participante en el caché local.
        """
        img1_opt, mime1_opt = optimizar_imagen_bytes(img_anverso_bytes, auto_rotar=auto_rotar)
        img2_opt, mime2_opt = optimizar_imagen_bytes(img_reverso_bytes, auto_rotar=auto_rotar)
        logger.info(
            f"Imágenes de Ficha optimizadas: Anverso={len(img1_opt)/1024:.1f}KB, "
            f"Reverso={len(img2_opt)/1024:.1f}KB"
        )

        raw_json = None
        if self.provider == "gemini" or (self.provider != "openai" and self.gemini_api_key):
            try:
                raw_json = self._procesar_con_gemini(img1_opt, img2_opt, mime1_opt, mime2_opt)
            except Exception as e:
                if self.openai_api_key:
                    logger.warning(f"Gemini reportó error ({e}). Activando fallback a OpenAI...")
                    raw_json = self._procesar_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
                else:
                    raise
        elif self.provider == "openai" or self.openai_api_key:
            raw_json = self._procesar_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
        else:
            raise ValueError(
                "No hay proveedor de visión configurado. Configure GEMINI_API_KEY en su archivo .env."
            )

        limpio = _limpiar_bloque_json(raw_json)
        try:
            parsed = json.loads(limpio)
        except Exception as e:
            raise ValueError(f"La respuesta de la IA no fue un JSON válido: {e}\nRespuesta recibida: {raw_json[:300]}")

        parsed_estandarizado = deserializar_json_ficha(parsed)
        ficha = FichaCaracterizacion.model_validate(parsed_estandarizado)
        datos_canonicos = ficha.to_canonical_dict()

        # Reconciliación con Patrón Maestro (Jaro-Winkler) para homogeneizar caligrafía
        nombre_extraido = datos_canonicos.get("Nombre completo del participante", "")
        municipio_extraido = datos_canonicos.get("Municipio", "") or datos_canonicos.get("TERRITORIO", "")
        coincidencia = participant_cache.buscar_coincidencia(nombre_extraido, municipio_extraido)
        if coincidencia:
            score = coincidencia.get("score", 1.0)
            logger.info(
                f"Reconciliando Ficha: '{nombre_extraido}' -> '{coincidencia['nombre']}' "
                f"(Score Jaro-Winkler: {score:.3f}). Estandarizando datos del participante."
            )
            datos_canonicos["Nombre completo del participante"] = coincidencia["nombre"]
            if coincidencia.get("edad") and not datos_canonicos.get("Edad"):
                datos_canonicos["Edad"] = coincidencia["edad"]
            if coincidencia.get("municipio"):
                datos_canonicos["Municipio"] = normalizar_territorio(coincidencia["municipio"])
            if coincidencia.get("eapb") and not datos_canonicos.get("EPS (si tienes)"):
                datos_canonicos["EPS (si tienes)"] = normalizar_eps(coincidencia["eapb"])
            if coincidencia.get("documento") and not datos_canonicos.get("Numero de documento identidad"):
                datos_canonicos["Numero de documento identidad"] = coincidencia["documento"]

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

    # -----------------------------------------------------------------
    # EXTRACCIÓN DE PRE-TEST Y POST-TEST (1 SOLA FOTOGRAFÍA)
    # -----------------------------------------------------------------

    def extraer_datos_test(
        self,
        img_bytes: bytes,
        mime_type: str = "image/jpeg",
        tipo_evaluacion_override: Optional[str] = None,
        auto_rotar: bool = True
    ) -> Dict[str, Any]:
        """
        Extrae datos de 1 fotografía correspondiente a Pre-Test o Post-Test.
        Reconcilia automáticamente con el PATRÓN MAESTRO y el caché de participantes
        mediante Jaro-Winkler tokenizado para garantizar coincidencia del 100% en:
        NOMBRE, EDAD, MUNICIPIO y EPS (EAPB).
        """
        img_opt, mime_opt = optimizar_imagen_bytes(img_bytes, auto_rotar=auto_rotar)
        logger.info(f"Imagen de Test optimizada: {len(img_opt)/1024:.1f}KB ({mime_opt})")

        raw_json = None
        if self.provider == "gemini" or (self.provider != "openai" and self.gemini_api_key):
            try:
                raw_json = self._procesar_test_con_gemini(img_opt, mime_opt)
            except Exception as e:
                if self.openai_api_key:
                    logger.warning(f"Gemini reportó error en test ({e}). Activando fallback a OpenAI...")
                    raw_json = self._procesar_test_con_openai(img_opt, mime_opt)
                else:
                    raise
        elif self.provider == "openai" or self.openai_api_key:
            raw_json = self._procesar_test_con_openai(img_opt, mime_opt)
        else:
            raise ValueError(
                "No hay proveedor de visión configurado. Configure GEMINI_API_KEY en su archivo .env."
            )

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
                datos["MUNICIPIO"] = normalizar_territorio(coincidencia["municipio"])
            if coincidencia.get("eapb"):
                datos["EAPB (EPS)"] = normalizar_eps(coincidencia["eapb"])

        return datos

    # -----------------------------------------------------------------
    # EXTRACCIÓN DE PRE-TEST Y POST-TEST (ANEXO 17 PELLÍZCATE)
    # -----------------------------------------------------------------

    def extraer_datos_anexo17(
        self,
        img_anverso_bytes: bytes,
        img_reverso_bytes: Optional[bytes] = None,
        mime_type_1: str = "image/jpeg",
        mime_type_2: Optional[str] = None,
        tipo_evaluacion_override: Optional[str] = None,
        municipio_override: Optional[str] = None,
        auto_rotar: bool = True
    ) -> Dict[str, Any]:
        """
        Extrae datos de 1 o 2 fotografías correspondientes a Pre-Test o Post-Test (Anexo 17 Pellízcate con Generación B+).
        - Página 1: Encabezado, Nombre, Municipio (Santa Catalina o Turbana u otro), Fecha, Edad y Preguntas 1 a 5.
        - Página 2 (Reverso): Preguntas 6 a 10.
        Reconcilia automáticamente con el PATRÓN MAESTRO y el caché de participantes
        mediante Jaro-Winkler tokenizado para garantizar coincidencia del 100% en:
        NOMBRE, EDAD y MUNICIPIO.
        """
        img1_opt, mime1_opt = optimizar_imagen_bytes(img_anverso_bytes, auto_rotar=auto_rotar)
        img2_opt, mime2_opt = None, None
        if img_reverso_bytes and len(img_reverso_bytes) > 0:
            img2_opt, mime2_opt = optimizar_imagen_bytes(img_reverso_bytes, auto_rotar=auto_rotar)
            logger.info(f"Imágenes Anexo 17 optimizadas: Pág 1={len(img1_opt)/1024:.1f}KB, Pág 2={len(img2_opt)/1024:.1f}KB")
        else:
            logger.info(f"Imagen única Anexo 17 optimizada: {len(img1_opt)/1024:.1f}KB ({mime1_opt})")

        raw_json = None
        if self.provider == "gemini" or (self.provider != "openai" and self.gemini_api_key):
            try:
                raw_json = self._procesar_anexo17_con_gemini(img1_opt, img2_opt, mime1_opt, mime2_opt)
            except Exception as e:
                if self.openai_api_key:
                    logger.warning(f"Gemini reportó error en Anexo 17 ({e}). Activando fallback a OpenAI...")
                    raw_json = self._procesar_anexo17_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
                else:
                    raise
        elif self.provider == "openai" or self.openai_api_key:
            raw_json = self._procesar_anexo17_con_openai(img1_opt, img2_opt, mime1_opt, mime2_opt)
        else:
            raise ValueError(
                "No hay proveedor de visión configurado. Configure GEMINI_API_KEY en su archivo .env."
            )

        limpio = _limpiar_bloque_json(raw_json)
        try:
            parsed = json.loads(limpio)
        except Exception as e:
            raise ValueError(f"La respuesta de la IA para Anexo 17 no fue un JSON válido: {e}\nRespuesta: {raw_json[:300]}")

        # Aplicar override manual si fue seleccionado explícitamente en el frontend
        if tipo_evaluacion_override and tipo_evaluacion_override.upper() in ["PRE-TEST", "POST-TEST"]:
            parsed["TIPO DE EVALUACIÓN"] = tipo_evaluacion_override.upper()

        if municipio_override and municipio_override.strip():
            parsed["MUNICIPIO"] = normalizar_municipio_anexo17(municipio_override.strip())

        test_obj = PrePostTestAnexo17.model_validate(parsed)
        datos = test_obj.to_canonical_dict()

        if municipio_override and municipio_override.strip():
            datos["MUNICIPIO"] = normalizar_municipio_anexo17(municipio_override.strip())

        # ==============================================================
        # RECONCILIACIÓN ESTRICTA CON PATRÓN MAESTRO (JARO-WINKLER)
        # ==============================================================
        nombre_extraido = datos.get("NOMBRE", "")
        municipio_extraido = datos.get("MUNICIPIO", "")
        coincidencia = participant_cache.buscar_coincidencia(nombre_extraido, municipio_extraido)

        if coincidencia:
            score = coincidencia.get("score", 1.0)
            logger.info(
                f"Reconciliando Anexo 17: '{nombre_extraido}' -> '{coincidencia['nombre']}' "
                f"(Score Jaro-Winkler: {score:.3f}). Estandarizando Nombre, Edad y Municipio."
            )
            datos["NOMBRE"] = coincidencia["nombre"]
            if coincidencia.get("edad"):
                datos["EDAD"] = coincidencia["edad"]
            if coincidencia.get("municipio") and not (municipio_override and municipio_override.strip()):
                datos["MUNICIPIO"] = normalizar_municipio_anexo17(coincidencia["municipio"])

        return datos

    # -----------------------------------------------------------------
    # MÉTODOS DE EXTRACCIÓN CON GOOGLE GEMINI (ALTA PRECISIÓN VISUAL)
    # -----------------------------------------------------------------

    def _invocar_gemini_con_backoff(
        self,
        client: Any,
        contents: list,
        models_to_try: list[str],
        config: Any,
        descripcion: str = "Documento",
        max_reintentos_por_modelo: int = 2,
        base_delay: float = 2.0
    ) -> str:
        """
        Ejecuta la inferencia en Google Gemini aplicando Exponential Backoff con Jitter
        ante errores transitorios (503 Service Unavailable, 429 Rate Limit, timeouts).
        Previene colapsos en cadena y sobrecarga evitando cambiar de modelo precipitadamente.
        """
        last_err = None
        for m_name in models_to_try:
            for intento in range(max_reintentos_por_modelo + 1):
                try:
                    self.rate_limiter.esperar_turno()
                    intento_str = f" (intento {intento + 1}/{max_reintentos_por_modelo + 1})" if intento > 0 else ""
                    logger.info(f"Enviando {descripcion} a Gemini con modelo '{m_name}'{intento_str}...")

                    response = client.models.generate_content(
                        model=m_name,
                        contents=contents,
                        config=config
                    )
                    if response and response.text:
                        return response.text
                except Exception as e:
                    last_err = e
                    es_transitorio = _es_error_transitorio(e)

                    if es_transitorio and intento < max_reintentos_por_modelo:
                        # Exponential Backoff con Jitter aleatorio (0.5s a 1.5s)
                        jitter = random.uniform(0.5, 1.5)
                        espera = (base_delay * (2 ** intento)) + jitter
                        logger.warning(
                            f"Gemini [{m_name}] reportó error transitorio ({e}). "
                            f"Aplicando Exponential Backoff con Jitter: esperando {espera:.2f}s antes de reintentar..."
                        )
                        time.sleep(espera)
                        continue
                    else:
                        logger.warning(
                            f"Gemini [{m_name}] falló tras intento {intento + 1}: {e}. "
                            f"{'Conmutando al siguiente modelo candidato...' if m_name != models_to_try[-1] else 'Agotados modelos candidatos.'}"
                        )
                        break

        if last_err:
            raise last_err
        return "{}"

    def _invocar_legacy_gemini_con_backoff(
        self,
        legacy_genai: Any,
        contents: list,
        models_to_try: list[str],
        descripcion: str = "Documento",
        max_reintentos_por_modelo: int = 2,
        base_delay: float = 2.0
    ) -> str:
        """Fallback con Exponential Backoff y Jitter para la librería legacy google.generativeai."""
        last_err = None
        for m_name in models_to_try:
            for intento in range(max_reintentos_por_modelo + 1):
                try:
                    self.rate_limiter.esperar_turno()
                    model = legacy_genai.GenerativeModel(
                        model_name=m_name,
                        generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
                    )
                    intento_str = f" (intento {intento + 1}/{max_reintentos_por_modelo + 1})" if intento > 0 else ""
                    logger.info(f"Enviando {descripcion} a Legacy Gemini con modelo '{m_name}'{intento_str}...")
                    response = model.generate_content(contents)
                    if response and response.text:
                        return response.text
                except Exception as e:
                    last_err = e
                    es_transitorio = _es_error_transitorio(e)
                    if es_transitorio and intento < max_reintentos_por_modelo:
                        jitter = random.uniform(0.5, 1.5)
                        espera = (base_delay * (2 ** intento)) + jitter
                        logger.warning(
                            f"Legacy Gemini [{m_name}] error transitorio ({e}). "
                            f"Reintentando en {espera:.2f}s..."
                        )
                        time.sleep(espera)
                        continue
                    else:
                        logger.warning(f"Legacy Gemini [{m_name}] falló: {e}. Conmutando...")
                        break

        if last_err:
            raise last_err
        return "{}"

    def _procesar_con_gemini(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Invoca Google Gemini con temperatura 0.0 determinista para digitalizar la ficha."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurada en las variables de entorno.")

        primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        candidate_models = [
            primary_model,
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite"
        ]
        models_to_try = list(dict.fromkeys(candidate_models))

        try:
            from google import genai
            from google.genai import types

            client = self._get_gemini_client()
            if not client:
                client = genai.Client(api_key=self.gemini_api_key)
            part_1 = types.Part.from_bytes(data=img1, mime_type=mime1)
            part_2 = types.Part.from_bytes(data=img2, mime_type=mime2)
            prompt_completo = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT}"
            contents = [prompt_completo, part_1, part_2]
            config = types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )

            return self._invocar_gemini_con_backoff(
                client=client,
                contents=contents,
                models_to_try=models_to_try,
                config=config,
                descripcion="Ficha de Caracterización"
            )

        except ImportError:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.gemini_api_key)
            prompt_completo = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT}"
            contents = [
                prompt_completo,
                {"mime_type": mime1, "data": img1},
                {"mime_type": mime2, "data": img2}
            ]
            return self._invocar_legacy_gemini_con_backoff(
                legacy_genai=legacy_genai,
                contents=contents,
                models_to_try=models_to_try,
                descripcion="Ficha de Caracterización"
            )

    def _procesar_test_con_gemini(self, img: bytes, mime: str) -> str:
        """Invoca Google Gemini para procesar la evaluación física del test con 100% fidelidad visual."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurada.")

        primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        candidate_models = [
            primary_model,
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite"
        ]
        models_to_try = list(dict.fromkeys(candidate_models))

        try:
            from google import genai
            from google.genai import types

            client = self._get_gemini_client()
            if not client:
                client = genai.Client(api_key=self.gemini_api_key)
            part = types.Part.from_bytes(data=img, mime_type=mime)
            prompt_completo = f"{SYSTEM_PROMPT_TEST}\n\n{USER_PROMPT_TEST}"
            contents = [prompt_completo, part]
            config = types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )

            return self._invocar_gemini_con_backoff(
                client=client,
                contents=contents,
                models_to_try=models_to_try,
                config=config,
                descripcion="Pre/Post Test"
            )

        except ImportError:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.gemini_api_key)
            prompt_completo = f"{SYSTEM_PROMPT_TEST}\n\n{USER_PROMPT_TEST}"
            contents = [
                prompt_completo,
                {"mime_type": mime, "data": img}
            ]
            return self._invocar_legacy_gemini_con_backoff(
                legacy_genai=legacy_genai,
                contents=contents,
                models_to_try=models_to_try,
                descripcion="Pre/Post Test"
            )

    def _procesar_anexo17_con_gemini(
        self,
        img1: bytes,
        img2: Optional[bytes] = None,
        mime1: str = "image/jpeg",
        mime2: Optional[str] = None
    ) -> str:
        """Invoca Google Gemini para procesar la evaluación física de Anexo 17 (1 o 2 páginas) con 100% fidelidad visual."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY no está configurada.")

        primary_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        candidate_models = [
            primary_model,
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite"
        ]
        models_to_try = list(dict.fromkeys(candidate_models))

        try:
            from google import genai
            from google.genai import types

            client = self._get_gemini_client()
            if not client:
                client = genai.Client(api_key=self.gemini_api_key)
            part_1 = types.Part.from_bytes(data=img1, mime_type=mime1)
            prompt_completo = f"{SYSTEM_PROMPT_ANEXO17}\n\n{USER_PROMPT_ANEXO17}"
            contents = [prompt_completo, part_1]
            if img2 and len(img2) > 0:
                part_2 = types.Part.from_bytes(data=img2, mime_type=mime2 or "image/jpeg")
                contents.append(part_2)

            config = types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )

            return self._invocar_gemini_con_backoff(
                client=client,
                contents=contents,
                models_to_try=models_to_try,
                config=config,
                descripcion="Pre/Post Test Anexo 17 (2 Páginas)" if img2 else "Pre/Post Test Anexo 17"
            )

        except ImportError:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=self.gemini_api_key)
            prompt_completo = f"{SYSTEM_PROMPT_ANEXO17}\n\n{USER_PROMPT_ANEXO17}"
            contents = [
                prompt_completo,
                {"mime_type": mime1, "data": img1}
            ]
            if img2 and len(img2) > 0:
                contents.append({"mime_type": mime2 or "image/jpeg", "data": img2})

            return self._invocar_legacy_gemini_con_backoff(
                legacy_genai=legacy_genai,
                contents=contents,
                models_to_try=models_to_try,
                descripcion="Pre/Post Test Anexo 17 (2 Páginas)" if img2 else "Pre/Post Test Anexo 17"
            )

    # -----------------------------------------------------------------
    # MÉTODOS DE FALLBACK SECUNDARIO (OPENAI SI TIENE API KEY)
    # -----------------------------------------------------------------

    def _procesar_con_openai(self, img1: bytes, img2: bytes, mime1: str, mime2: str) -> str:
        """Fallback opcional con OpenAI si está configurado en el entorno."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada para fallback.")

        client = self._get_openai_client()
        if not client:
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

        client = self._get_openai_client()
        if not client:
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

    def _procesar_anexo17_con_openai(
        self,
        img1: bytes,
        img2: Optional[bytes] = None,
        mime1: str = "image/jpeg",
        mime2: Optional[str] = None
    ) -> str:
        """Fallback opcional de OpenAI para Anexo 17 (1 o 2 imágenes)."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY no está configurada para fallback.")

        client = self._get_openai_client()
        if not client:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_api_key)

        b64_1 = base64.b64encode(img1).decode("utf-8")
        user_content = [
            {"type": "text", "text": USER_PROMPT_ANEXO17},
            {"type": "image_url", "image_url": {"url": f"data:{mime1};base64,{b64_1}"}}
        ]
        if img2 and len(img2) > 0:
            b64_2 = base64.b64encode(img2).decode("utf-8")
            user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime2 or 'image/jpeg'};base64,{b64_2}"}})

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ANEXO17},
                {"role": "user", "content": user_content}
            ]
        )
        return response.choices[0].message.content or "{}"

