"""
Esquema Canónico de Datos: Pre-Test y Post-Test (Anexo 4 SSR ITS)
Define la estructura exacta de 14 campos (+ Marca temporal), validación Pydantic v2
y estandarización a MAYÚSCULAS con catálogos canónicos de municipios y EPS.
"""

from __future__ import annotations
import re
import difflib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

# Importar catálogos canónicos ya definidos en schema.py
try:
    from .schema import TERRITORIOS_VALIDOS, EPS_VALIDAS
except (ImportError, ValueError):
    try:
        from schema import TERRITORIOS_VALIDOS, EPS_VALIDAS
    except ImportError:
        from backend.schema import TERRITORIOS_VALIDOS, EPS_VALIDAS


# -------------------------------------------------------------
# 14 COLUMNAS CANÓNICAS DE DATOS (+ 1 MARCA TEMPORAL EN HOJA)
# -------------------------------------------------------------
COLUMNAS_TEST: List[str] = [
    "TIPO DE EVALUACIÓN",
    "NOMBRE",
    "EDAD",
    "MUNICIPIO",
    "EAPB (EPS)",
    "1. EL USO CORRECTO DEL PRESERVATIVO AYUDA A PREVENIR ITS COMO VIH Y SÍFILIS.",
    "2. LAS ITS PUEDEN TRANSMITIRSE DE LA MADRE AL BEBÉ DURANTE EL EMBARAZO.",
    "3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA.",
    "4. LOS ANTICONCEPTIVOS ORALES PREVIENEN LAS ITS.",
    "5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?",
    "6. LA PREP ES UN MEDICAMENTO QUE AYUDA A PREVENIR EL VIH EN PERSONAS CON MAYOR RIESGO DE EXPOSICIÓN.",
    "7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B.",
    "8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.",
    "9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES."
]

# Encabezados completos tal como se escriben en la fila 1 de Google Sheets
ENCABEZADOS_TEST_SHEETS: List[str] = ["Marca temporal"] + COLUMNAS_TEST

# Opciones válidas para preguntas dicotómicas
VALORES_DICOTOMICOS_TEST: List[str] = ["VERDADERO", "FALSO"]

# Opciones válidas para la pregunta 5
OPCIONES_PREGUNTA_5: List[str] = [
    "TODAS LAS ANTERIORES",
    "USAR PRESERVATIVO",
    "TENER INFORMACIÓN CLARA SOBRE SALUD SEXUAL",
    "EVITAR COMPARTIR AGUJAS O ELEMENTOS CORTOPUNZANTES"
]

TIPOS_EVALUACION_VALIDOS: List[str] = ["PRE-TEST", "POST-TEST"]


def normalizar_texto_base(val: Any) -> str:
    """Limpia caracteres de control y convierte a mayúsculas."""
    if val is None:
        return ""
    texto = str(val).strip().upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def normalizar_dicotomica(val: Any) -> str:
    """Normaliza respuestas de Verdadero / Falso."""
    txt = normalizar_texto_base(val)
    if not txt:
        return ""
    if txt in ["VERDADERO", "V", "VERDAD", "TRUE", "SI", "SÍ", "CIERTO"]:
        return "VERDADERO"
    if txt in ["FALSO", "F", "FALSE", "NO", "INCORRECTO"]:
        return "FALSO"
    # Si viene con similitud
    coincidencias = difflib.get_close_matches(txt, ["VERDADERO", "FALSO"], n=1, cutoff=0.6)
    if coincidencias:
        return coincidencias[0]
    return txt


def normalizar_pregunta_5(val: Any) -> str:
    """Normaliza la respuesta de la pregunta 5 (opciones múltiples / única)."""
    txt = normalizar_texto_base(val)
    if not txt:
        return ""
    
    # Comprobar "TODAS LAS ANTERIORES"
    if "TODAS" in txt or "ANTERIORES" in txt:
        return "TODAS LAS ANTERIORES"
    
    # Comprobar "USAR PRESERVATIVO"
    if "PRESERVATIVO" in txt or "CONDON" in txt or "CONDÓN" in txt:
        return "USAR PRESERVATIVO"
        
    # Comprobar "INFORMACION" / "SALUD SEXUAL"
    if "INFORMACION" in txt or "INFORMACIÓN" in txt or "SEXUAL" in txt:
        return "TENER INFORMACIÓN CLARA SOBRE SALUD SEXUAL"
        
    # Comprobar "AGUJAS" / "CORTOPUNZANTES"
    if "AGUJA" in txt or "CORTOPUNZANTE" in txt or "ELEMENTOS" in txt:
        return "EVITAR COMPARTIR AGUJAS O ELEMENTOS CORTOPUNZANTES"
        
    coincidencias = difflib.get_close_matches(txt, OPCIONES_PREGUNTA_5, n=1, cutoff=0.55)
    if coincidencias:
        return coincidencias[0]
        
    return txt


def normalizar_municipio(val: Any) -> str:
    """Asigna el municipio a uno de los 10 territorios canónicos de la Gobernación."""
    txt = normalizar_texto_base(val)
    if not txt:
        return ""
    if txt in TERRITORIOS_VALIDOS:
        return txt
    coincidencias = difflib.get_close_matches(txt, TERRITORIOS_VALIDOS, n=1, cutoff=0.5)
    if coincidencias:
        return coincidencias[0]
    return txt


def normalizar_eps(val: Any) -> str:
    """Asigna la EAPB/EPS a una del catálogo oficial o preserva nombre válido."""
    txt = normalizar_texto_base(val)
    if not txt:
        return ""
    if txt in EPS_VALIDAS:
        return txt
    coincidencias = difflib.get_close_matches(txt, EPS_VALIDAS, n=1, cutoff=0.65)
    if coincidencias:
        return coincidencias[0]
    return txt


class PrePostTest(BaseModel):
    """
    Modelo Pydantic v2 para el Anexo 4 (Pre-Test y Post-Test de Conocimiento SSR/ITS).
    Garantiza 14 campos estrictamente formateados en mayúsculas para la sincronización con Google Sheets.
    """
    tipo_evaluacion: str = Field(..., alias="TIPO DE EVALUACIÓN", description="PRE-TEST o POST-TEST")
    nombre: str = Field(..., alias="NOMBRE", description="Nombre completo manuscrito del participante")
    edad: str = Field(..., alias="EDAD", description="Edad en dígitos")
    municipio: str = Field(..., alias="MUNICIPIO", description="Uno de los 10 municipios priorizados")
    eapb: str = Field("", alias="EAPB (EPS)", description="Entidad administradora de salud (EPS)")

    # 9 Preguntas de conocimiento
    pregunta_1: str = Field("", alias="1. EL USO CORRECTO DEL PRESERVATIVO AYUDA A PREVENIR ITS COMO VIH Y SÍFILIS.")
    pregunta_2: str = Field("", alias="2. LAS ITS PUEDEN TRANSMITIRSE DE LA MADRE AL BEBÉ DURANTE EL EMBARAZO.")
    pregunta_3: str = Field("", alias="3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA.")
    pregunta_4: str = Field("", alias="4. LOS ANTICONCEPTIVOS ORALES PREVIENEN LAS ITS.")
    pregunta_5: str = Field("", alias="5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?")
    pregunta_6: str = Field("", alias="6. LA PREP ES UN MEDICAMENTO QUE AYUDA A PREVENIR EL VIH EN PERSONAS CON MAYOR RIESGO DE EXPOSICIÓN.")
    pregunta_7: str = Field("", alias="7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B.")
    pregunta_8: str = Field("", alias="8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.")
    pregunta_9: str = Field("", alias="9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES.")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }

    @model_validator(mode="before")
    @classmethod
    def normalizar_campos(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Unificar claves flexibles recibidas desde la IA
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
        raw_tipo = buscar_valor("TIPO DE EVALUACIÓN", "TIPO_EVALUACION", "TIPO DE EVALUACION", "EVALUACION")
        tipo_str = normalizar_texto_base(raw_tipo)
        if "POST" in tipo_str:
            tipo_final = "POST-TEST"
        elif "PRE" in tipo_str:
            tipo_final = "PRE-TEST"
        else:
            tipo_final = "PRE-TEST"

        # 2. Nombre
        raw_nombre = buscar_valor("NOMBRE", "NOMBRE COMPLETO", "NOMBRE DEL PARTICIPANTE")
        nombre_final = normalizar_texto_base(raw_nombre)

        # 3. Edad
        raw_edad = buscar_valor("EDAD")
        edad_digits = re.sub(r"\D", "", str(raw_edad or ""))
        edad_final = edad_digits if edad_digits else normalizar_texto_base(raw_edad)

        # 4. Municipio
        raw_mun = buscar_valor("MUNICIPIO", "TERRITORIO")
        mun_final = normalizar_municipio(raw_mun)

        # 5. EAPB (EPS)
        raw_eapb = buscar_valor("EAPB (EPS)", "EAPB", "EPS")
        eapb_final = normalizar_eps(raw_eapb)

        # Preguntas 1 a 9
        p1 = normalizar_dicotomica(buscar_valor("1. EL USO CORRECTO DEL PRESERVATIVO", "PREGUNTA_1", "1", "1."))
        p2 = normalizar_dicotomica(buscar_valor("2. LAS ITS PUEDEN TRANSMITIRSE", "PREGUNTA_2", "2", "2."))
        p3 = normalizar_dicotomica(buscar_valor("3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA", "PREGUNTA_3", "3", "3."))
        p4 = normalizar_dicotomica(buscar_valor("4. LOS ANTICONCEPTIVOS ORALES PREVIENEN", "PREGUNTA_4", "4", "4."))
        p5 = normalizar_pregunta_5(buscar_valor("5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?", "PREGUNTA_5", "5", "5."))
        p6 = normalizar_dicotomica(buscar_valor("6. LA PREP ES UN MEDICAMENTO", "PREGUNTA_6", "6", "6."))
        p7 = normalizar_dicotomica(buscar_valor("7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B", "PREGUNTA_7", "7", "7."))
        p8 = normalizar_dicotomica(buscar_valor("8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE", "PREGUNTA_8", "8", "8."))
        p9 = normalizar_dicotomica(buscar_valor("9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN", "PREGUNTA_9", "9", "9."))

        return {
            "TIPO DE EVALUACIÓN": tipo_final,
            "NOMBRE": nombre_final,
            "EDAD": edad_final,
            "MUNICIPIO": mun_final,
            "EAPB (EPS)": eapb_final,
            "1. EL USO CORRECTO DEL PRESERVATIVO AYUDA A PREVENIR ITS COMO VIH Y SÍFILIS.": p1,
            "2. LAS ITS PUEDEN TRANSMITIRSE DE LA MADRE AL BEBÉ DURANTE EL EMBARAZO.": p2,
            "3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA.": p3,
            "4. LOS ANTICONCEPTIVOS ORALES PREVIENEN LAS ITS.": p4,
            "5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?": p5,
            "6. LA PREP ES UN MEDICAMENTO QUE AYUDA A PREVENIR EL VIH EN PERSONAS CON MAYOR RIESGO DE EXPOSICIÓN.": p6,
            "7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B.": p7,
            "8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.": p8,
            "9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES.": p9,
        }

    def to_ordered_row(self) -> List[str]:
        """
        Retorna la lista de 14 valores ordenados según COLUMNAS_TEST
        para inserción directa en Google Sheets.
        """
        canonical = self.to_canonical_dict()
        return [canonical.get(col, "") for col in COLUMNAS_TEST]

    def to_canonical_dict(self) -> Dict[str, str]:
        """Retorna un diccionario con las 14 claves oficiales en mayúsculas."""
        return {
            "TIPO DE EVALUACIÓN": self.tipo_evaluacion,
            "NOMBRE": self.nombre,
            "EDAD": self.edad,
            "MUNICIPIO": self.municipio,
            "EAPB (EPS)": self.eapb,
            "1. EL USO CORRECTO DEL PRESERVATIVO AYUDA A PREVENIR ITS COMO VIH Y SÍFILIS.": self.pregunta_1,
            "2. LAS ITS PUEDEN TRANSMITIRSE DE LA MADRE AL BEBÉ DURANTE EL EMBARAZO.": self.pregunta_2,
            "3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA.": self.pregunta_3,
            "4. LOS ANTICONCEPTIVOS ORALES PREVIENEN LAS ITS.": self.pregunta_4,
            "5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?": self.pregunta_5,
            "6. LA PREP ES UN MEDICAMENTO QUE AYUDA A PREVENIR EL VIH EN PERSONAS CON MAYOR RIESGO DE EXPOSICIÓN.": self.pregunta_6,
            "7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B.": self.pregunta_7,
            "8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.": self.pregunta_8,
            "9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES.": self.pregunta_9,
        }
