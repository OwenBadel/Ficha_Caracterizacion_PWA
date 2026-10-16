"""
Esquema Canónico de Datos: Pre-Test y Post-Test (Anexo 17 — Pellízcate con Generación B+)
Define la estructura exacta de 15 campos (+ Marca temporal en Google Sheets),
validación Pydantic v2 y estandarización a MAYÚSCULAS con catálogos canónicos.
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.
"""

from __future__ import annotations
import re
import difflib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

# Importar catálogos canónicos ya definidos en schema.py
try:
    from .schema import TERRITORIOS_VALIDOS, normalizar_territorio
except (ImportError, ValueError):
    try:
        from schema import TERRITORIOS_VALIDOS, normalizar_territorio
    except ImportError:
        from backend.schema import TERRITORIOS_VALIDOS, normalizar_territorio


# -------------------------------------------------------------
# 15 COLUMNAS CANÓNICAS DE DATOS (+ 1 MARCA TEMPORAL EN HOJA)
# -------------------------------------------------------------
COLUMNAS_ANEXO17: List[str] = [
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
]

# Encabezados completos tal como se escriben en la fila 1 de Google Sheets
ENCABEZADOS_ANEXO17_SHEETS: List[str] = ["Marca temporal"] + COLUMNAS_ANEXO17

# Opciones canónicas completas por pregunta (Prefijadas con letra mayúscula para orden y legibilidad)
OPCIONES_CANONICAS_ANEXO17: Dict[int, Dict[str, str]] = {
    1: {
        "A": "A. UN PLAN SOBRE LO QUE QUIERO LOGRAR EN EL FUTURO",
        "B": "B. UNA TAREA DEL COLEGIO",
        "C": "C. UN JUEGO ENTRE AMIGOS"
    },
    2: {
        "A": "A. QUEDARTE CALLADO",
        "B": "B. DECIR “NO”, ALEJARTE Y BUSCAR AYUDA",
        "C": "C. ACEPTAR PARA EVITAR PROBLEMAS"
    },
    3: {
        "A": "A. EL USO CORRECTO DEL CONDÓN",
        "B": "B. COMPARTIR INFORMACIÓN PERSONAL",
        "C": "C. TOMAR CUALQUIER MEDICAMENTO"
    },
    4: {
        "A": "A. RESPONDER CON VIOLENCIA",
        "B": "B. GUARDARLO EN SECRETO",
        "C": "C. CONTÁRSELO A UN ADULTO DE CONFIANZA Y PEDIR AYUDA"
    },
    5: {
        "A": "A. HABLAR CON ALGUIEN DE CONFIANZA",
        "B": "B. LASTIMARSE O LASTIMAR A OTRA PERSONA",
        "C": "C. IGNORAR SIEMPRE LO QUE SE SIENTE"
    },
    6: {
        "A": "A. PENSAR QUE ESTÁ BROMEANDO",
        "B": "B. ESCUCHARLO Y BUSCAR INMEDIATAMENTE LA AYUDA DE UN ADULTO",
        "C": "C. DEJARLO SOLO PARA QUE SE CALME"
    },
    7: {
        "A": "A. EXPRESAR LO QUE PIENSO Y SIENTO CON RESPETO",
        "B": "B. GRITAR PARA QUE ME ESCUCHEN",
        "C": "C. QUEDARME CALLADO, AUNQUE ALGO ME MOLESTE"
    },
    8: {
        "A": "A. PERSONAS E INSTITUCIONES QUE PUEDEN ORIENTARNOS Y AYUDARNOS",
        "B": "B. UN GRUPO DE REDES SOCIALES",
        "C": "C. PERSONAS QUE DECIDEN TODO POR NOSOTROS"
    },
    9: {
        "A": "A. ESTUDIAR Y PARTICIPAR EN ACTIVIDADES CULTURALES",
        "B": "B. SER OBLIGADO A TRABAJAR O VINCULARSE A UN GRUPO ARMADO",
        "C": "C. RECIBIR ORIENTACIÓN DE SU FAMILIA"
    },
    10: {
        "A": "A. PENSAR EN LAS CONSECUENCIAS Y PEDIR ORIENTACIÓN",
        "B": "B. HACER LO QUE DIGAN LOS DEMÁS",
        "C": "C. ACTUAR SIN PENSAR"
    }
}

TIPOS_EVALUACION_VALIDOS: List[str] = ["PRE-TEST", "POST-TEST"]


def normalizar_texto_base(val: Any) -> str:
    """Limpia caracteres de control y convierte a mayúsculas."""
    if val is None:
        return ""
    texto = str(val).strip().upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def normalizar_municipio(val: Any) -> str:
    """
    Asigna el municipio a uno de los territorios canónicos autorizados o su variante oficial.
    Por directiva del proyecto, las evaluaciones del Anexo 17 corresponden a EL CARMEN DE BOLIVAR.
    """
    txt = normalizar_texto_base(val)
    if not txt:
        return "EL CARMEN DE BOLIVAR"
    if "CARMEN" in txt:
        return "EL CARMEN DE BOLIVAR"
    res = normalizar_territorio(txt)
    if res in TERRITORIOS_VALIDOS:
        return res
    if txt in TERRITORIOS_VALIDOS:
        return txt
    coincidencias = difflib.get_close_matches(txt, TERRITORIOS_VALIDOS, n=1, cutoff=0.6)
    if coincidencias:
        return coincidencias[0]
    return res if res else "EL CARMEN DE BOLIVAR"


def normalizar_fecha(val: Any) -> str:
    """Estandariza formatos de fecha manuscrita a DD/MM/AAAA si contiene dígitos válidos."""
    txt = normalizar_texto_base(val)
    if not txt:
        return ""
    # Buscar patrones tipo 14/10/2026 o 14-10-2026
    m = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})", txt)
    if m:
        dia, mes, anio = m.group(1), m.group(2), m.group(3)
        if len(dia) == 1:
            dia = f"0{dia}"
        if len(mes) == 1:
            mes = f"0{mes}"
        if len(anio) == 2:
            anio = f"20{anio}"
        return f"{dia}/{mes}/{anio}"
    return txt


def normalizar_opcion_anexo17(num_pregunta: int, val: Any) -> str:
    """
    Normaliza la respuesta de una pregunta de opción múltiple (a, b, c).
    Acepta tanto la letra ("A", "B", "C") como fragmentos del texto o la opción completa.
    Retorna la opción canónica formateada (ej. "A. UN PLAN SOBRE LO QUE QUIERO LOGRAR EN EL FUTURO")
    o cadena vacía "" si no hubo marca.
    """
    txt = normalizar_texto_base(val)
    if not txt:
        return ""

    opciones = OPCIONES_CANONICAS_ANEXO17.get(num_pregunta, {})
    if not opciones:
        return txt

    # 1. Comprobación exacta o prefijada por letra
    m_letra = re.match(r"^(?:OPCIÓN|OPCION)?\s*([ABC])\b", txt)
    if m_letra:
        letra = m_letra.group(1)
        if letra in opciones:
            return opciones[letra]

    # Letra simple aislada
    if txt in ["A", "B", "C"]:
        return opciones[txt]

    # 2. Búsqueda por palabras clave específicas de cada opción
    if num_pregunta == 1:
        if "PLAN" in txt or "FUTURO" in txt or "LOGRAR" in txt:
            return opciones["A"]
        if "COLEGIO" in txt or "TAREA" in txt:
            return opciones["B"]
        if "JUEGO" in txt or "AMIGOS" in txt:
            return opciones["C"]

    elif num_pregunta == 2:
        if "CALLADO" in txt or "QUEDARTE" in txt:
            return opciones["A"]
        if "DECIR NO" in txt or "ALEJARTE" in txt or "BUSCAR AYUDA" in txt or "NO" in txt:
            return opciones["B"]
        if "ACEPTAR" in txt or "PROBLEMAS" in txt:
            return opciones["C"]

    elif num_pregunta == 3:
        if "CONDON" in txt or "CONDÓN" in txt or "PRESERVATIVO" in txt:
            return opciones["A"]
        if "PERSONAL" in txt or "COMPARTIR" in txt:
            return opciones["B"]
        if "MEDICAMENTO" in txt or "TOMAR" in txt:
            return opciones["C"]

    elif num_pregunta == 4:
        if "VIOLENCIA" in txt or "RESPONDER" in txt:
            return opciones["A"]
        if "SECRETO" in txt or "GUARDARLO" in txt:
            return opciones["B"]
        if "ADULTO" in txt or "CONFIANZA" in txt or "CONTÁRSELO" in txt or "CONTARSELO" in txt or "PEDIR AYUDA" in txt:
            return opciones["C"]

    elif num_pregunta == 5:
        if "HABLAR" in txt or "ALGUIEN" in txt or "CONFIANZA" in txt:
            return opciones["A"]
        if "LASTIMARSE" in txt or "LASTIMAR" in txt:
            return opciones["B"]
        if "IGNORAR" in txt or "SIENTE" in txt:
            return opciones["C"]

    elif num_pregunta == 6:
        if "BROMEANDO" in txt or "PENSAR" in txt:
            return opciones["A"]
        if "ESCUCHARLO" in txt or "ADULTO" in txt or "INMEDIATAMENTE" in txt or "BUSCAR" in txt:
            return opciones["B"]
        if "SOLO" in txt or "CALME" in txt or "DEJARLO" in txt:
            return opciones["C"]

    elif num_pregunta == 7:
        if "RESPETO" in txt or "PIENSO" in txt or "SIENTO" in txt or "EXPRESAR" in txt:
            return opciones["A"]
        if "GRITAR" in txt or "ESCUCHEN" in txt:
            return opciones["B"]
        if "CALLADO" in txt or "MOLESTE" in txt:
            return opciones["C"]

    elif num_pregunta == 8:
        if "INSTITUCIONES" in txt or "ORIENTARNOS" in txt or "AYUDARNOS" in txt or "PERSONAS E" in txt:
            return opciones["A"]
        if "REDES" in txt or "SOCIALES" in txt:
            return opciones["B"]
        if "DECIDEN TODO" in txt or "POR NOSOTROS" in txt:
            return opciones["C"]

    elif num_pregunta == 9:
        if "ESTUDIAR" in txt or "ACTIVIDADES" in txt or "CULTURALES" in txt:
            return opciones["A"]
        if "OBLIGADO" in txt or "TRABAJAR" in txt or "ARMADO" in txt or "GRUPO" in txt:
            return opciones["B"]
        if "FAMILIA" in txt or "ORIENTACIÓN" in txt or "ORIENTACION" in txt:
            return opciones["C"]

    elif num_pregunta == 10:
        if "CONSECUENCIAS" in txt or "PENSAR" in txt or "ORIENTACIÓN" in txt or "ORIENTACION" in txt:
            return opciones["A"]
        if "DIGAN" in txt or "DEMÁS" in txt or "DEMAS" in txt:
            return opciones["B"]
        if "SIN PENSAR" in txt or "ACTUAR" in txt:
            return opciones["C"]

    # 3. Fallback mediante similitud difusa (difflib)
    valores_posibles = list(opciones.values())
    coincidencias = difflib.get_close_matches(txt, valores_posibles, n=1, cutoff=0.45)
    if coincidencias:
        return coincidencias[0]

    return txt


class PrePostTestAnexo17(BaseModel):
    """
    Modelo Pydantic v2 para el Anexo 17 (Pre-Test y Post-Test Pellízcate con Generación B+).
    Garantiza 15 campos estrictamente formateados en mayúsculas para inserción en Google Sheets.
    """
    tipo_evaluacion: str = Field(..., alias="TIPO DE EVALUACIÓN", description="PRE-TEST o POST-TEST")
    nombre: str = Field(..., alias="NOMBRE", description="Nombre manuscrito legible del participante")
    municipio: str = Field(..., alias="MUNICIPIO", description="Municipio cabecera oficial")
    fecha: str = Field("", alias="FECHA", description="Fecha de aplicación de la evaluación")
    edad: str = Field(..., alias="EDAD", description="Edad en dígitos")

    # 10 Preguntas de opción múltiple
    pregunta_1: str = Field("", alias="1. ¿QUÉ ES UN PROYECTO DE VIDA?")
    pregunta_2: str = Field("", alias="2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?")
    pregunta_3: str = Field("", alias="3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?")
    pregunta_4: str = Field("", alias="4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?")
    pregunta_5: str = Field("", alias="5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?")
    pregunta_6: str = Field("", alias="6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?")
    pregunta_7: str = Field("", alias="7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?")
    pregunta_8: str = Field("", alias="8. ¿QUÉ ES UNA RED DE APOYO?")
    pregunta_9: str = Field("", alias="9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?")
    pregunta_10: str = Field("", alias="10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }

    @model_validator(mode="before")
    @classmethod
    def normalizar_campos(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        dict_norm = {}
        for k, v in data.items():
            k_upper = normalizar_texto_base(k)
            dict_norm[k_upper] = v

        def buscar_valor(*posibles_claves: str) -> Any:
            for p in posibles_claves:
                p_norm = normalizar_texto_base(p)
                if p_norm in dict_norm:
                    return dict_norm[p_norm]
                for k, v in dict_norm.items():
                    if p_norm in k or k in p_norm:
                        return v
            return ""

        # 1. Tipo de Evaluación
        raw_tipo = buscar_valor("TIPO DE EVALUACIÓN", "TIPO_EVALUACION", "TIPO DE EVALUACION", "EVALUACION", "MOMENTO")
        tipo_str = normalizar_texto_base(raw_tipo)
        if "POST" in tipo_str or "POS" in tipo_str:
            tipo_final = "POST-TEST"
        elif "PRE" in tipo_str:
            tipo_final = "PRE-TEST"
        else:
            tipo_final = "PRE-TEST"

        # 2. Nombre
        raw_nombre = buscar_valor("NOMBRE", "NOMBRE COMPLETO", "NOMBRE DEL PARTICIPANTE", "ESTUDIANTE")
        nombre_final = normalizar_texto_base(raw_nombre)

        # 3. Municipio
        raw_mun = buscar_valor("MUNICIPIO", "TERRITORIO", "CIUDAD")
        mun_final = normalizar_municipio(raw_mun)

        # 4. Fecha
        raw_fecha = buscar_valor("FECHA", "FECHA DE EVALUACIÓN", "FECHA_EVALUACION")
        fecha_final = normalizar_fecha(raw_fecha)

        # 5. Edad
        raw_edad = buscar_valor("EDAD")
        edad_digits = re.sub(r"\D", "", str(raw_edad or ""))
        edad_final = edad_digits if edad_digits else normalizar_texto_base(raw_edad)

        # Preguntas 1 a 10
        p1 = normalizar_opcion_anexo17(1, buscar_valor("1. ¿QUÉ ES UN PROYECTO DE VIDA?", "PROYECTO DE VIDA", "PREGUNTA_1", "1", "1."))
        p2 = normalizar_opcion_anexo17(2, buscar_valor("2. SI ALGUIEN QUIERE TOCAR TU CUERPO", "TOCAR TU CUERPO", "PREGUNTA_2", "2", "2."))
        p3 = normalizar_opcion_anexo17(3, buscar_valor("3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO", "PREVENIR UN EMBARAZO", "PREGUNTA_3", "3", "3."))
        p4 = normalizar_opcion_anexo17(4, buscar_valor("4. ¿QUÉ DEBES HACER SI SUFRES BULLYING", "BULLYING", "CIBERACOSO", "PREGUNTA_4", "4", "4."))
        p5 = normalizar_opcion_anexo17(5, buscar_valor("5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR", "EMOCIÓN DIFÍCIL", "EMOCION DIFICIL", "PREGUNTA_5", "5", "5."))
        p6 = normalizar_opcion_anexo17(6, buscar_valor("6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO", "NO QUIERE SEGUIR VIVIENDO", "PREGUNTA_6", "6", "6."))
        p7 = normalizar_opcion_anexo17(7, buscar_valor("7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?", "COMUNICARSE DE MANERA ASERTIVA", "PREGUNTA_7", "7", "7."))
        p8 = normalizar_opcion_anexo17(8, buscar_valor("8. ¿QUÉ ES UNA RED DE APOYO?", "RED DE APOYO", "PREGUNTA_8", "8", "8."))
        p9 = normalizar_opcion_anexo17(9, buscar_valor("9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS", "DERECHOS DE UN ADOLESCENTE", "PREGUNTA_9", "9", "9."))
        p10 = normalizar_opcion_anexo17(10, buscar_valor("10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE", "DECISIÓN IMPORTANTE", "DECISION IMPORTANTE", "PREGUNTA_10", "10", "10."))

        return {
            "TIPO DE EVALUACIÓN": tipo_final,
            "NOMBRE": nombre_final,
            "MUNICIPIO": mun_final,
            "FECHA": fecha_final,
            "EDAD": edad_final,
            "1. ¿QUÉ ES UN PROYECTO DE VIDA?": p1,
            "2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?": p2,
            "3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?": p3,
            "4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?": p4,
            "5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?": p5,
            "6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?": p6,
            "7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?": p7,
            "8. ¿QUÉ ES UNA RED DE APOYO?": p8,
            "9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?": p9,
            "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:": p10,
        }

    def to_ordered_row(self) -> List[str]:
        """
        Retorna la lista de 15 valores ordenados según COLUMNAS_ANEXO17
        para inserción directa en Google Sheets.
        """
        canonical = self.to_canonical_dict()
        return [canonical.get(col, "") for col in COLUMNAS_ANEXO17]

    def to_canonical_dict(self) -> Dict[str, str]:
        """Retorna un diccionario con las 15 claves oficiales en mayúsculas."""
        return {
            "TIPO DE EVALUACIÓN": self.tipo_evaluacion,
            "NOMBRE": self.nombre,
            "MUNICIPIO": self.municipio,
            "FECHA": self.fecha,
            "EDAD": self.edad,
            "1. ¿QUÉ ES UN PROYECTO DE VIDA?": self.pregunta_1,
            "2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?": self.pregunta_2,
            "3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?": self.pregunta_3,
            "4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?": self.pregunta_4,
            "5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?": self.pregunta_5,
            "6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?": self.pregunta_6,
            "7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?": self.pregunta_7,
            "8. ¿QUÉ ES UNA RED DE APOYO?": self.pregunta_8,
            "9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?": self.pregunta_9,
            "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:": self.pregunta_10,
        }
