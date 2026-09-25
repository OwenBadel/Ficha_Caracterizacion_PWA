"""
Esquema Canónico de Datos: Ficha de Caracterización
Define la estructura exacta de 43 campos, el orden para Google Sheets y normalización a mayúsculas.
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

try:
    from .vocabulary_learner import vocabulary_learner, COLUMNAS_APRENDIZAJE
except (ImportError, ValueError):
    try:
        from vocabulary_learner import vocabulary_learner, COLUMNAS_APRENDIZAJE
    except ImportError:
        from backend.vocabulary_learner import vocabulary_learner, COLUMNAS_APRENDIZAJE


COLUMNAS_FICHA: List[str] = [
    "NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA",
    "TERRITORIO",
    "Nombre completo del participante",
    "Tipo de documento identidad",
    "Numero de documento identidad",
    "Edad",
    "Grado escolar",
    "Teléfono de contacto",
    "Dirección de residencia (barrio o vereda)",
    "Municipio",
    "Zona",
    "EPS (si tienes)",
    "Régimen",
    "Sexo con el que te identificas",
    "Identidad de género",
    "¿Perteneces a alguna población o grupo étnico?",
    "¿Tienes alguna condición de discapacidad?",
    "¿Cual?",
    "¿Tienes antecedentes de alguna enfermedad personal o familiar importante?",
    "¿Cual?_1",
    "¿Has asistido al médico en el último año?",
    "¿Cuándo fue la última vez?",
    "¿Fuiste al odontólogo el último año?",
    "¿Qué actividades recreativas haces en tu tiempo libre?",
    "¿Qué tiempo empleas en esta actividad?",
    "¿Consumes o has consumido cigarrillo o vapeador?",
    "Cada cuánto?",
    "¿Consumes o has consumido alcohol?",
    "Cada cuánto?_1",
    "¿Has consumido alguna sustancia psicoactiva?",
    "¿Cual?_2",
    "¿Has vivido situaciones de discriminación, rechazo o violencia?",
    "¿Has recibido información sobre salud sexual, ITS o métodos de prevención?",
    "¿Has iniciado tu vida sexual?",
    "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?",
    "¿Conoces algún método anticonceptico?",
    "¿Cual?_3",
    "¿Has vivido o conoces algún caso cercano de embarazo adolescente?",
    "¿Te han entregado preservativos en la EPS o institución de salud?",
    "¿Cuándo fue la ultima vez?",
    "¿Qué tema te gustaria aprender o entender mejor?",
    "¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?",
    "¿Por que?"
]


# -------------------------------------------------------------
# CATÁLOGOS CANÓNICOS DE ESTANDARIZACIÓN
# -------------------------------------------------------------
ENCUESTADORES_VALIDOS: List[str] = [
    "PAMELA VERGARA",
    "KAREN TORRES",
    "MAURICIO FORTICH",
    "WENDY TAPIAS",
    "GISEL MORENO"
]

TERRITORIOS_VALIDOS: List[str] = [
    "MAHATES",
    "TURBANA",
    "TURBACO",
    "BARRANCO DE LOBA",
    "SAN JACINTO DEL CAUCA",
    "CALAMAR",
    "MORALES",
    "SANTA ROSA DEL SUR",
    "ARENAL",
    "SOPLAVIENTO"
]

TIPOS_DOCUMENTO_VALIDOS: List[str] = [
    "RC",
    "TI",
    "CC",
    "PASAPORTE",
    "PERMISO"
]

ZONAS_VALIDAS: List[str] = [
    "RURAL",
    "URBANA"
]

EPS_VALIDAS: List[str] = [
    "SANITAS",
    "SURA",
    "SALUD TOTAL",
    "MUTUAL SER",
    "COOSALUD",
    "NUEVA EPS",
    "CONFAORIENTE",
    "PROTEGER",
    "FAMISANAR"
]

REGIMENES_VALIDOS: List[str] = [
    "CONTRIBUTIVO",
    "SUBSIDIADO",
    "NINGUNO"
]

SEXOS_VALIDOS: List[str] = [
    "FEMENINO",
    "MASCULINO"
]

IDENTIDADES_GENERO_VALIDAS: List[str] = [
    "HETEROSEXUAL",
    "HOMOSEXUAL",
    "BISEXUAL",
    "TRANSGENERO",
    "LESBIANA"
]

ETNIAS_VALIDAS: List[str] = [
    "AFROCOLOMBIANO",
    "INDÍGENA",
    "PALENQUERO",
    "VÍCTIMA DEL CONFLICTO",
    "NO"
]

DISCAPACIDADES_VALIDAS: List[str] = [
    "SI",
    "NO"
]

TEMAS_INTERES_CANONICOS: List[str] = [
    "VIH",
    "SIFILIS",
    "HEPATITIS B Y C",
    "METODOS ANTICONCEPTIVOS",
    "USO CORRECTO DEL PRESERVATIVO",
    "PROYECTO DE VIDA",
    "RESPETO POR LAS DIFERENCIAS",
    "PREVENCION DEL EMBARAZO ADOLESCENTE",
    "SALUD MENTAL Y RELACIONES"
]


# -------------------------------------------------------------
# FUNCIONES DE NORMALIZACIÓN POR CAMPO
# -------------------------------------------------------------
def normalizar_valor_mayusculas(val: Optional[Any]) -> str:
    """Convierte cualquier valor a mayúsculas limpio de espacios extra."""
    if val is None:
        return ""
    val_str = str(val).strip()
    if val_str.lower() in ["none", "null", "n/a", "undefined"]:
        return ""
    return val_str.upper()


def normalizar_quien_diligencia(val: Optional[Any]) -> str:
    """Normaliza el campo 'NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA'."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    for persona in ENCUESTADORES_VALIDOS:
        if s == persona:
            return persona
    s_clean = re.sub(r"[^A-Z\s]", "", s)
    if "PAMELA" in s_clean or "VERGARA" in s_clean:
        return "PAMELA VERGARA"
    if "KAREN" in s_clean or "TORRES" in s_clean:
        return "KAREN TORRES"
    if "WENDY" in s_clean or "TAPIAS" in s_clean:
        return "WENDY TAPIAS"
    if "MAURICIO" in s_clean or "FORTICH" in s_clean:
        return "MAURICIO FORTICH"
    if "GISEL" in s_clean or "GISELLE" in s_clean or "MORENO" in s_clean or "GISELE" in s_clean:
        return "GISEL MORENO"
    return s


def normalizar_territorio(val: Optional[Any]) -> str:
    """Normaliza Territorio y Municipio a los municipios autorizados:
    MAHATES, TURBANA, TURBACO, BARRANCO DE LOBA, SAN JACINTO DEL CAUCA,
    CALAMAR, MORALES, SANTA ROSA DEL SUR, ARENAL, SOPLAVIENTO.
    """
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    for t in TERRITORIOS_VALIDOS:
        if s == t:
            return t
    if "MAHATE" in s:
        return "MAHATES"
    if "TURBANA" in s:
        return "TURBANA"
    if "TURBACO" in s:
        return "TURBACO"
    if "BARRANCO" in s or "LOBA" in s:
        return "BARRANCO DE LOBA"
    if "SAN JACINTO" in s or "JACINTO" in s or ("SAN" in s and "CAUCA" in s):
        return "SAN JACINTO DEL CAUCA"
    if "CALAMAR" in s:
        return "CALAMAR"
    if "MORALE" in s:
        return "MORALES"
    if "SANTA ROSA" in s or "ROSA DEL SUR" in s or "STA ROSA" in s or "STA. ROSA" in s:
        return "SANTA ROSA DEL SUR"
    if "ARENAL" in s:
        return "ARENAL"
    if "SOPLAVIENTO" in s or "SOPLA VIENTO" in s or "SOPLA" in s:
        return "SOPLAVIENTO"
    return s


def normalizar_tipo_documento(val: Optional[Any]) -> str:
    """Normaliza Tipo de documento a: RC, TI, CC, PASAPORTE, PERMISO."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    for td in TIPOS_DOCUMENTO_VALIDOS:
        if s == td:
            return td
    s_clean = re.sub(r"[^A-Z]", "", s)
    if s_clean in ["CC", "CEDULA", "CEDULADECIUDADANIA"]:
        return "CC"
    if s_clean in ["TI", "TARJETA", "TARJETADEIDENTIDAD"]:
        return "TI"
    if s_clean in ["RC", "REGISTRO", "REGISTROCIVIL"]:
        return "RC"
    if "PASAPORTE" in s_clean:
        return "PASAPORTE"
    if "PERMISO" in s_clean or s_clean in ["PPT", "PEP"]:
        return "PERMISO"
    return s


def normalizar_tipo_documento_segun_edad(val: Optional[Any], edad: Optional[Any]) -> str:
    """Normaliza el tipo de documento según la edad del participante.
    Regla de negocio: Si tiene menos de 18 años (< 18), el documento es TI,
    a menos que presente un documento de extranjería explícito (PASAPORTE o PERMISO).
    Si marcó CC, RC o quedó vacío, se estandariza automáticamente a TI.
    """
    td = normalizar_tipo_documento(val)
    if edad is not None:
        m = re.search(r"\b(\d+)\b", str(edad))
        if m:
            try:
                edad_num = int(m.group(1))
                if 0 < edad_num < 18:
                    if td not in ["PASAPORTE", "PERMISO"]:
                        return "TI"
            except ValueError:
                pass
    return td


def normalizar_grado_escolar(val: Optional[Any]) -> str:
    """Normaliza el grado escolar al formato: el numero y ° (ej. 6°, 10°)."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    m = re.search(r"(\d+)", s)
    if m:
        return f"{m.group(1)}°"
    text_grades = {
        "PRIMERO": "1°", "SEGUNDO": "2°", "TERCERO": "3°", "CUARTO": "4°", "QUINTO": "5°",
        "SEXTO": "6°", "SEPTIMO": "7°", "SÉPTIMO": "7°", "OCTAVO": "8°", "NOVENO": "9°",
        "DECIMO": "10°", "DÉCIMO": "10°", "ONCE": "11°", "DUODECIMO": "12°"
    }
    for k, v in text_grades.items():
        if k in s:
            return v
    return s


def normalizar_zona(val: Optional[Any]) -> str:
    """Normaliza Zona a: RURAL o URBANA."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    if "RURAL" in s:
        return "RURAL"
    if "URBAN" in s:
        return "URBANA"
    return s


def normalizar_eps(val: Optional[Any]) -> str:
    """Normaliza EPS a una de las 6 autorizadas o string vacío si no tiene."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED", "NO TIENE", "NO", "NINGUNA", "SIN EPS", "PARTICULAR"]:
        return ""
    for eps in EPS_VALIDAS:
        if s == eps:
            return eps
    if "SANITAS" in s:
        return "SANITAS"
    if "SURA" in s:
        return "SURA"
    if "SALUD" in s and "TOTAL" in s:
        return "SALUD TOTAL"
    if "MUTUAL" in s:
        return "MUTUAL SER"
    if "COOSALUD" in s or "COO SALUD" in s:
        return "COOSALUD"
    if "NUEVA" in s:
        return "NUEVA EPS"
    if "CONFAORIENTE" in s or "CONFA ORIENTE" in s:
        return "CONFAORIENTE"
    if "PROTEGER" in s:
        return "PROTEGER"
    return s


def normalizar_regimen(val: Optional[Any]) -> str:
    """Normaliza Régimen a: CONTRIBUTIVO, SUBSIDIADO o NINGUNO."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    if "CONTRIBUT" in s:
        return "CONTRIBUTIVO"
    if "SUBSIDI" in s:
        return "SUBSIDIADO"
    if "NINGUN" in s or s in ["NO", "NO TIENE", "NINGUNO", "NINGUNA"]:
        return "NINGUNO"
    return s


def normalizar_sexo(val: Optional[Any]) -> str:
    """Normaliza Sexo a: FEMENINO o MASCULINO."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    if "FEM" in s or s in ["F", "MUJER"]:
        return "FEMENINO"
    if "MASC" in s or s in ["M", "HOMBRE"]:
        return "MASCULINO"
    return s


def normalizar_identidad_genero(val: Optional[Any]) -> str:
    """Normaliza Identidad de género a: HETEROSEXUAL, HOMOSEXUAL, BISEXUAL, TRANSGENERO, LESBIANA."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    for idg in IDENTIDADES_GENERO_VALIDAS:
        if s == idg:
            return idg
    if "HETERO" in s:
        return "HETEROSEXUAL"
    if "HOMO" in s or "GAY" in s:
        return "HOMOSEXUAL"
    if "BISEX" in s:
        return "BISEXUAL"
    if "TRANS" in s:
        return "TRANSGENERO"
    if "LESBI" in s:
        return "LESBIANA"
    return s


def normalizar_etnia(val: Optional[Any]) -> str:
    """Normaliza Etnia a: AFROCOLOMBIANO, INDÍGENA, PALENQUERO, VÍCTIMA DEL CONFLICTO, NO."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    for et in ETNIAS_VALIDAS:
        if s == et:
            return et
    if "AFRO" in s or "NEGRO" in s:
        return "AFROCOLOMBIANO"
    if "INDIGENA" in s or "INDÍGENA" in s:
        return "INDÍGENA"
    if "PALENQU" in s:
        return "PALENQUERO"
    if "VICTIMA" in s or "VÍCTIMA" in s or "CONFLICTO" in s:
        return "VÍCTIMA DEL CONFLICTO"
    if s in ["NO", "NINGUNO", "NINGUNA", "NINGUN"]:
        return "NO"
    return s


def normalizar_si_no(val: Optional[Any]) -> str:
    """Normaliza casillas dicotómicas a SI o NO."""
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    if s in ["SI", "SÍ", "X", "TRUE", "1"]:
        return "SI"
    if s in ["NO", "FALSE", "0"]:
        return "NO"
    return s


USOS_CONDON_VALIDOS: List[str] = [
    "SIEMPRE",
    "CASI SIEMPRE",
    "NUNCA"
]

def normalizar_uso_condon(val: Optional[Any]) -> str:
    """Normaliza la columna 35 ('Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?').
    Opciones de la ficha física: SIEMPRE, CASI SIEMPRE, NUNCA.
    """
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    for u in USOS_CONDON_VALIDOS:
        if s == u:
            return u
    if "CASI" in s or "A VECES" in s:
        return "CASI SIEMPRE"
    if "SIEMPRE" in s or s in ["SI", "SÍ"]:
        return "SIEMPRE"
    if "NUNCA" in s or s in ["NO", "JAMAS", "JAMÁS"]:
        return "NUNCA"
    return s


# Lista exacta de columnas dicotómicas (SI / NO) de la ficha de caracterización
COLUMNAS_DICOTOMICAS_SI_NO: List[str] = [
    "¿Tienes alguna condición de discapacidad?",
    "¿Tienes antecedentes de alguna enfermedad personal o familiar importante?",
    "¿Has asistido al médico en el último año?",
    "¿Fuiste al odontólogo el último año?",
    "¿Consumes o has consumido cigarrillo o vapeador?",
    "¿Consumes o has consumido alcohol?",
    "¿Has consumido alguna sustancia psicoactiva?",
    "¿Has vivido situaciones de discriminación, rechazo o violencia?",
    "¿Has recibido información sobre salud sexual, ITS o métodos de prevención?",
    "¿Has iniciado tu vida sexual?",
    "¿Conoces algún método anticonceptico?",
    "¿Has vivido o conoces algún caso cercano de embarazo adolescente?",
    "¿Te han entregado preservativos en la EPS o institución de salud?",
    "¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?"
]


def normalizar_tiempo_horas(val: Optional[Any]) -> str:
    """Para la columna 25 ('¿Qué tiempo empleas en esta actividad?'):
    Asegura que cualquier número o texto lleve la palabra 'HORAS'.
    Ejemplo: '2' -> '2 HORAS', '1' -> '1 HORA', '2H' -> '2 HORAS'.
    """
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    if "HORA" in s or "MINUTO" in s or "DIA" in s or "SEMANA" in s:
        return s
    m = re.match(r"^(\d+(?:[\.,]\d+)?)\s*H?$", s)
    if m:
        num = m.group(1)
        return f"{num} HORA" if num == "1" else f"{num} HORAS"
    if re.search(r"\d", s):
        return f"{s} HORAS"
    return f"{s} HORAS"


def normalizar_fecha_periodo(val: Optional[Any]) -> str:
    """Normaliza campos de fecha/período como '¿Cuándo fue la última vez?'.
    1. Asegura MAYÚSCULAS.
    2. Si el OCR confundió el trazo manuscrito de '2026' con '2020', corrige automáticamente a '2026'.
    """
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    s = re.sub(r"\b2020\b", "2026", s)
    s = re.sub(r"\b202O\b", "2026", s)
    return s


def normalizar_direccion(val: Optional[Any]) -> str:
    """Normaliza la columna 9 ('Dirección de residencia (barrio o vereda)').
    1. Asegura MAYÚSCULAS y espacios limpios.
    2. Estandariza prefijos y abreviaturas frecuentes territoriales:
       - 'B/', 'B.', 'BRR.', 'BRR ', 'BR.' -> 'BARRIO '
       - 'VDA.', 'VDA/', 'VDA ' -> 'VEREDA '
       - 'CORR.', 'CORREG.' -> 'CORREGIMIENTO '
    3. Limpia redundancias como 'RESIDENCIA EN EL BARRIO', 'RESIDENCIA BARRIO', 'RESIDENCIA:'
    """
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED", "NO TIENE", "NO APLICA"]:
        return ""

    # Limpiar prefijos de 'RESIDENCIA' redundantes
    s = re.sub(r"^RESIDENCIA\s+EN\s+(?:EL\s+)?BARRIO\b", "BARRIO", s)
    s = re.sub(r"^RESIDENCIA\s+EN\s+(?:LA\s+)?VEREDA\b", "VEREDA", s)
    s = re.sub(r"^RESIDENCIA\s+BARRIO\b", "BARRIO", s)
    s = re.sub(r"^RESIDENCIA\s*:\s*", "", s)

    # Estandarizar abreviaturas de BARRIO
    s = re.sub(r"^(?:B\/\s*|B\.\s*|BRR\.\s*|BRR\s+|BR\.\s*)", "BARRIO ", s)

    # Estandarizar abreviaturas de VEREDA
    s = re.sub(r"^(?:VDA\.\s*|VDA\/\s*|VDA\s+)", "VEREDA ", s)

    # Estandarizar abreviaturas de CORREGIMIENTO
    s = re.sub(r"^(?:CORR\.\s*|CORREG\.\s*|CORR\s+)", "CORREGIMIENTO ", s)

    # Normalizar espacios intermedios
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalizar_sin_espacios(val: Optional[Any]) -> str:
    """Para campos numéricos o de identificación (Teléfono, Documento de identidad):
    Elimina todos los espacios, puntos, comas, guiones, paréntesis y caracteres separadores,
    dejando el valor completamente unido y continuo sin espacios.
    Ejemplo: '1 045 678 901' -> '1045678901', '300 123 4567' -> '3001234567'.
    """
    if not val:
        return ""
    s = str(val).strip().upper()
    if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
        return ""
    return re.sub(r"[\s\.\,\-\(\)\_]+", "", s)


def normalizar_temas_interes(val: Any) -> str:
    """
    Normaliza las opciones seleccionadas en '¿Qué tema te gustaria aprender o entender mejor?'.
    Garantiza que múltiples opciones queden separadas estrictamente por coma y espacio (', ').
    Ejemplo: 'VIH; SIFILIS' -> 'VIH, SIFILIS'.
             ['VIH', 'METODOS ANTICONCEPTIVOS'] -> 'VIH, METODOS ANTICONCEPTIVOS'.
    """
    if not val:
        return ""

    elementos: List[str] = []

    # 1. Si es lista de Python
    if isinstance(val, (list, tuple, set)):
        for item in val:
            item_str = str(item).strip()
            if item_str:
                elementos.append(item_str)
    else:
        texto = str(val).strip()
        if not texto or texto.lower() in ["none", "null", "n/a", "undefined"]:
            return ""

        # Si vino como string JSON o representación de lista: "['VIH', 'SIFILIS']"
        if (texto.startswith("[") and texto.endswith("]")) or (texto.startswith("(") and texto.endswith(")")):
            try:
                parsed = json.loads(texto)
                if isinstance(parsed, list):
                    return normalizar_temas_interes(parsed)
            except Exception:
                texto = texto.strip("[]()\"' ")

        # Si ya contiene delimitadores explícitos (coma, punto y coma, salto de línea, pipe, slash, guion largo)
        if any(d in texto for d in [",", ";", "\n", "\r", "|"]) or " - " in texto or " / " in texto:
            partes = re.split(r"[,;\n\r|]+|\s+-\s+|\s+/\s+", texto)
            for p in partes:
                p_clean = p.strip()
                if p_clean:
                    elementos.append(p_clean)
        else:
            # Si vino todo junto sin comas o como texto continuo
            texto_upper = texto.upper()
            encontrados = []
            temas_ordenados = sorted(TEMAS_INTERES_CANONICOS, key=len, reverse=True)
            for tema in temas_ordenados:
                tema_regex = r"\b" + re.escape(tema) + r"\b"
                if re.search(tema_regex, texto_upper):
                    encontrados.append(tema)
                    texto_upper = re.sub(tema_regex, " ", texto_upper)

            texto_restante = re.sub(r"\s+", " ", texto_upper).strip()
            if len(encontrados) > 1:
                encontrados.sort(key=lambda t: texto.upper().find(t))
                if texto_restante and len(texto_restante) > 2:
                    encontrados.append(texto_restante)
                elementos = encontrados
            else:
                elementos = [texto]

    # 2. Normalizar cada elemento contra el catálogo canónico (removiendo tildes y espacios duplicados)
    resultado_final: List[str] = []
    tildes = {"Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U"}

    for el in elementos:
        el_clean = str(el).strip().upper()
        for a, b in tildes.items():
            el_clean = el_clean.replace(a, b)
        el_clean = re.sub(r"\s+", " ", el_clean).strip()
        if not el_clean:
            continue

        # Mapear a canónico
        canonico = None
        for tema in TEMAS_INTERES_CANONICOS:
            if el_clean == tema:
                canonico = tema
                break

        if not canonico:
            if el_clean in ["SIFILIS", "SÍFILIS"]:
                canonico = "SIFILIS"
            elif "EMBARAZO ADOLESCENTE" in el_clean:
                canonico = "PREVENCION DEL EMBARAZO ADOLESCENTE"
            elif "USO" in el_clean and "PRESERVATIVO" in el_clean:
                canonico = "USO CORRECTO DEL PRESERVATIVO"
            elif "METODOS ANTICONCEPTIVOS" in el_clean or "METODO ANTICONCEPTIVO" in el_clean:
                canonico = "METODOS ANTICONCEPTIVOS"
            elif "SALUD MENTAL" in el_clean:
                canonico = "SALUD MENTAL Y RELACIONES"
            elif "RESPETO" in el_clean and "DIFERENCIA" in el_clean:
                canonico = "RESPETO POR LAS DIFERENCIAS"
            elif "HEPATITIS" in el_clean:
                canonico = "HEPATITIS B Y C"
            elif "PROYECTO DE VIDA" in el_clean:
                canonico = "PROYECTO DE VIDA"

        final_val = canonico if canonico else el_clean
        if final_val and final_val not in resultado_final:
            resultado_final.append(final_val)

    return ", ".join(resultado_final)


def normalizar_campo_por_columna(col: str, val: Any) -> str:
    """Aplica la normalización correspondiente según el nombre canónico de la columna."""
    col_l = col.lower()

    # Columna 41: Temas de interés (puede ser lista o string, múltiples opciones separadas por coma)
    if col == "¿Qué tema te gustaria aprender o entender mejor?" or "tema te gustaria" in col_l or "tema te gustaría" in col_l or "aprender o entender" in col_l:
        return normalizar_temas_interes(val)

    v = normalizar_valor_mayusculas(val)
    if not v:
        return ""

    # 1. Casillas dicotómicas estrictas (SI / NO) prioritarias
    # (Evita que columnas como '¿Te han entregado preservativos en la EPS...' se confundan con la pregunta de EPS)
    if col in COLUMNAS_DICOTOMICAS_SI_NO:
        return normalizar_si_no(v)

    # 2. Casillas con catálogos cerrados específicos
    if col == "NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA" or "quien diligencia" in col_l:
        return normalizar_quien_diligencia(v)
    if col == "TERRITORIO" or col_l == "territorio":
        return normalizar_territorio(v)
    if col == "Municipio" or col_l == "municipio":
        return normalizar_territorio(v)
    if col == "Tipo de documento identidad" or col_l in ["tipo de documento", "tipo de documento identidad"]:
        return normalizar_tipo_documento(v)
    if col == "Numero de documento identidad" or "documento identidad" in col_l or "numero de documento" in col_l:
        return normalizar_sin_espacios(v)
    if col == "Teléfono de contacto" or "telefono" in col_l or "teléfono" in col_l:
        return normalizar_sin_espacios(v)
    if col == "Grado escolar" or "grado escolar" in col_l:
        return normalizar_grado_escolar(v)
    if col == "Zona" or col_l in ["zona", "zona rural o urbana"]:
        return normalizar_zona(v)
    if col == "EPS (si tienes)" or col_l in ["eps", "eps (si tienes)"]:
        return normalizar_eps(v)
    if col == "Régimen" or col_l in ["régimen", "regimen"]:
        return normalizar_regimen(v)
    if col == "Sexo con el que te identificas" or "sexo con el que" in col_l:
        return normalizar_sexo(v)
    if col == "Identidad de género" or "identidad de g" in col_l:
        return normalizar_identidad_genero(v)
    if col == "¿Perteneces a alguna población o grupo étnico?" or "grupo étnico" in col_l or "grupo etnico" in col_l:
        return normalizar_etnia(v)
    if "usas condón o preservativo" in col_l or "usas condon" in col_l:
        return normalizar_uso_condon(v)
    if col == "¿Qué tiempo empleas en esta actividad?" or "tiempo empleas" in col_l:
        return normalizar_tiempo_horas(v)
    if col == "Dirección de residencia (barrio o vereda)" or "direccion" in col_l or "dirección" in col_l or "barrio o vereda" in col_l:
        v = normalizar_direccion(v)
    if "cuándo fue la" in col_l or "cuando fue la" in col_l:
        v = normalizar_fecha_periodo(v)

    # Corrección difusa de vocabulario adaptativo para columnas abiertas aprendidas
    if col in COLUMNAS_APRENDIZAJE:
        v = vocabulary_learner.corregir_valor(col, v)

    return v


def canonicalizar_clave_columna(k: str) -> str:
    """Mapea claves con variaciones de tildes, espacios o redacción a la columna canónica exacta de COLUMNAS_FICHA."""
    if not k:
        return ""
    if k in COLUMNAS_FICHA:
        return k
    k_strip = str(k).strip()
    if k_strip in COLUMNAS_FICHA:
        return k_strip

    # Limpieza para comparación fonética/estructural
    k_clean = re.sub(r"[^\w\s]", "", k_strip.lower())
    k_clean = re.sub(r"\s+", " ", k_clean).strip()
    tildes = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for a, b in tildes.items():
        k_clean = k_clean.replace(a, b)

    # Desambiguación explícita Columna 40 vs 22 (Cuándo fue la última vez) ANTES del matching ciego:
    # La Columna 22 es "¿Cuándo fue la última vez?" (médico, con tilde)
    # La Columna 40 es "¿Cuándo fue la ultima vez?" (preservativos EPS, sin tilde)
    if "cuando fue" in k_clean or "ultima vez" in k_clean:
        if any(w in k_clean for w in ["preservativo", "condon", "eps", "salud", "metodo"]) or any(w in k_strip for w in ["_1", "40"]):
            return "¿Cuándo fue la ultima vez?"
        if any(w in k_clean for w in ["medico", "doctor", "cita", "consulta", "medica"]) or "22" in k_strip:
            return "¿Cuándo fue la última vez?"
        if "última" in k_strip:
            return "¿Cuándo fue la última vez?"
        if "ultima" in k_strip:
            return "¿Cuándo fue la ultima vez?"

    # 1. Búsqueda directa sin tildes contra COLUMNAS_FICHA
    # (Evitamos "cuando fue la ultima vez" porque colisiona 22 con 40 y ya fue tratada arriba)
    if k_clean != "cuando fue la ultima vez":
        for col in COLUMNAS_FICHA:
            col_clean = re.sub(r"[^\w\s]", "", col.lower())
            col_clean = re.sub(r"\s+", " ", col_clean).strip()
            for a, b in tildes.items():
                col_clean = col_clean.replace(a, b)
            if k_clean == col_clean:
                return col

    # 2. Casilla 39 (Preservativos en EPS o institución de salud)
    if ("entregado" in k_clean or "entrega" in k_clean or "recibido" in k_clean) and \
       ("preservativo" in k_clean or "condon" in k_clean) and \
       ("eps" in k_clean or "salud" in k_clean or "institucion" in k_clean):
        return "¿Te han entregado preservativos en la EPS o institución de salud?"
    if ("preservativos en la eps" in k_clean or "preservativo en la eps" in k_clean or "condon en la eps" in k_clean or "condones en la eps" in k_clean):
        return "¿Te han entregado preservativos en la EPS o institución de salud?"

    # Casilla 38 (Embarazo adolescente)
    if "embarazo" in k_clean and ("adolescente" in k_clean or "adolescentes" in k_clean or "cercano" in k_clean or "caso" in k_clean):
        return "¿Has vivido o conoces algún caso cercano de embarazo adolescente?"

    # Casilla 33 (Prevención ITS / Salud sexual)
    if ("prevencion de its" in k_clean or "salud sexual its" in k_clean or "informacion sobre salud sexual" in k_clean) and "embarazo" not in k_clean:
        return "¿Has recibido información sobre salud sexual, ITS o métodos de prevención?"

    # Casilla 34 (¿Has iniciado tu vida sexual?)
    if any(t in k_clean for t in ["vida sexual", "iniciado tu vida", "iniciado vida", "iniciaste vida sexual", "inicio vida sexual", "iniciaste tu vida sexual"]) or \
       (("iniciado" in k_clean or "empezado" in k_clean or "inicio" in k_clean or "iniciaste" in k_clean or "comenzado" in k_clean) and ("sexual" in k_clean or "relacion" in k_clean)):
        return "¿Has iniciado tu vida sexual?"

    # Casilla 35 (Uso de condón en relaciones sexuales)
    if any(t in k_clean for t in ["usas condon", "usas preservativo", "condon o preservativo", "preservativo en tus relaciones", "condon en tus relaciones", "si respondiste si", "uso de condon", "uso de preservativo"]) and not any(t in k_clean for t in ["iniciado", "empezado", "inicio vida"]):
        return "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?"
    if "relaciones sexuales" in k_clean and ("condon" in k_clean or "preservativo" in k_clean):
        return "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?"

    # Casilla 37 (Cuál método anticonceptivo - Campo abierto para el nombre del método)
    if (any(w in k_clean for w in ["cual", "que metodo", "nombre metodo", "especifique metodo", "cual metodo", "tipo de metodo"]) and any(w in k_clean for w in ["anticoncepti", "metodo", "3"])) or \
       ("3" in k_strip and ("cual" in k_clean or "metodo" in k_clean)):
        return "¿Cual?_3"

    # Casilla 36 (Conoce algún método anticonceptivo - Pregunta dicotómica SI/NO)
    if (any(w in k_clean for w in ["conoce", "conoces", "conozca", "sabe"]) and any(w in k_clean for w in ["metodo", "anticoncepti"])) or \
       ("metodo anticoncepti" in k_clean and not any(w in k_clean for w in ["cual", "que", "nombre", "tipo", "especifique", "3"])) or \
       ("conoces algun metodo" in k_clean):
        return "¿Conoces algún método anticonceptico?"

    # Casilla 41 (Temas de interés / aprender o entender mejor)
    if any(t in k_clean for t in ["tema te gustaria", "temas te gustaria", "aprender o entender", "temas de interes", "tema de interes", "tema a aprender", "temas interes", "gustaria aprender"]):
        return "¿Qué tema te gustaria aprender o entender mejor?"

    # Casilla 42 (Espacios de diálogo en institución educativa)
    if any(t in k_clean for t in ["espacios para dialogar", "espacios de dialogo", "dialogar de estos temas", "mas espacios", "institucion educativa se hicieran mas espacios", "espacios en tu institucion", "espacios educativos"]):
        return "¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?"

    # Casilla 43 (¿Por que?)
    if k_clean in ["por que", "porque", "por que razon", "motivo", "razon", "por que_1", "porque_1"] or \
       ("por que" in k_clean and not any(t in k_clean for t in ["asistio", "odontologo", "actividad", "fuma", "alcohol", "sustancia"])):
        return "¿Por que?"

    return k_strip


def aplicar_reglas_coherencia(data: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica reglas transversales de fidelidad, coherencia lógica y dependencias entre casillas (cols 1 a 43)."""
    res = dict(data)

    # 1. Regla de negocio: El municipio es el mismo que el territorio
    terr = res.get("TERRITORIO") or res.get("territorio") or res.get("Municipio") or res.get("municipio")
    if terr:
        terr_norm = normalizar_territorio(terr)
        res["TERRITORIO"] = terr_norm
        res["territorio"] = terr_norm
        res["Municipio"] = terr_norm
        res["municipio"] = terr_norm

    # 2. Regla de negocio: Si tiene menos de 18 años, el tipo de documento es TI
    edad_val = res.get("Edad") or res.get("edad")
    td_val = res.get("Tipo de documento identidad") or res.get("tipo_documento")
    td_norm = normalizar_tipo_documento_segun_edad(td_val, edad_val)
    if td_norm:
        res["Tipo de documento identidad"] = td_norm
        res["tipo_documento"] = td_norm

    # 3. Fidelidad Discapacidad (Cols 17 y 18):
    # Si no tiene condición de discapacidad, la casilla ¿Cual? debe estar vacía.
    discapacidad = res.get("¿Tienes alguna condición de discapacidad?", "")
    cual_discapacidad = res.get("¿Cual?", "")
    if discapacidad == "NO":
        res["¿Cual?"] = ""
        res["cual_discapacidad"] = ""
    elif cual_discapacidad and cual_discapacidad not in ["", "NO", "NINGUNA", "NINGUNO", "N/A"]:
        res["¿Tienes alguna condición de discapacidad?"] = "SI"
        res["discapacidad"] = "SI"

    # 4. Fidelidad Enfermedades importantes (Cols 19 y 20):
    # Si no tiene antecedentes de enfermedad, la casilla ¿Cual?_1 debe estar vacía.
    enfermedad = res.get("¿Tienes antecedentes de alguna enfermedad personal o familiar importante?", "")
    cual_enfermedad = res.get("¿Cual?_1", "")
    if enfermedad == "NO":
        res["¿Cual?_1"] = ""
        res["cual_enfermedad"] = ""
    elif cual_enfermedad and cual_enfermedad not in ["", "NO", "NINGUNA", "NINGUNO", "N/A"]:
        res["¿Tienes antecedentes de alguna enfermedad personal o familiar importante?"] = "SI"
        res["antecedentes_enfermedad"] = "SI"

    # 5. Fidelidad Médico (Cols 21 y 22):
    # Si no asistió al médico en el último año, ¿Cuándo fue la última vez? debe estar vacío.
    asistio_medico = res.get("¿Has asistido al médico en el último año?", "")
    cuando_medico = res.get("¿Cuándo fue la última vez?", "")
    if asistio_medico == "NO":
        res["¿Cuándo fue la última vez?"] = ""
        res["cuando_medico"] = ""
    elif cuando_medico and cuando_medico not in ["", "NINGUNA", "NO", "N/A", "NINGUNO"]:
        res["¿Has asistido al médico en el último año?"] = "SI"
        res["asistio_medico"] = "SI"

    # 6. Fidelidad Cigarrillo o Vapeador (Cols 26 y 27):
    # Si no consume cigarrillo, la frecuencia Cada cuánto? debe estar vacía.
    cigarrillo = res.get("¿Consumes o has consumido cigarrillo o vapeador?", "")
    cada_cuanto_fuma = res.get("Cada cuánto?", "")
    if cigarrillo == "NO":
        res["Cada cuánto?"] = ""
        res["cada_cuanto_fuma"] = ""
    elif cada_cuanto_fuma and cada_cuanto_fuma not in ["", "NO", "NUNCA", "NINGUNO", "N/A"]:
        res["¿Consumes o has consumido cigarrillo o vapeador?"] = "SI"
        res["cigarrillo_vapeador"] = "SI"

    # 7. Fidelidad Consumo de Alcohol (Cols 28 y 29):
    # Si no consume alcohol, la frecuencia Cada cuánto?_1 debe estar vacía.
    alcohol = res.get("¿Consumes o has consumido alcohol?", "")
    cada_cuanto_alcohol = res.get("Cada cuánto?_1", "")
    if alcohol == "NO":
        res["Cada cuánto?_1"] = ""
        res["cada_cuanto_alcohol"] = ""
    elif cada_cuanto_alcohol and cada_cuanto_alcohol not in ["", "NO", "NUNCA", "NINGUNO", "N/A"]:
        res["¿Consumes o has consumido alcohol?"] = "SI"
        res["consume_alcohol"] = "SI"

    # 8. Fidelidad Sustancias Psicoactivas (Cols 30 y 31):
    # Si no ha consumido sustancias, la casilla ¿Cual?_2 debe estar vacía.
    sustancia = res.get("¿Has consumido alguna sustancia psicoactiva?", "")
    cual_sustancia = res.get("¿Cual?_2", "")
    if sustancia == "NO":
        res["¿Cual?_2"] = ""
        res["cual_sustancia"] = ""
    elif cual_sustancia and cual_sustancia not in ["", "NO", "NINGUNA", "NINGUNO", "N/A"]:
        res["¿Has consumido alguna sustancia psicoactiva?"] = "SI"
        res["sustancia_psicoactiva"] = "SI"

    # 9. Coherencia Vida Sexual y Condón (Cols 34 y 35):
    # a) Si respondió explícitamente uso de condón (SIEMPRE o CASI SIEMPRE en relaciones sexuales):
    #    Confirma categóricamente que SÍ ha iniciado vida sexual -> Col 34 = SI.
    #    NOTA: Conocer o nombrar un método anticonceptivo en Col 37 (¿Cual?_3) NO implica haber iniciado
    #    vida sexual (es conocimiento teórico/educación), por lo que NUNCA debe forzar Col 34 = SI.
    condon_val = res.get("Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?", "")
    iniciado_sexual = res.get("¿Has iniciado tu vida sexual?", "")

    if condon_val in ["SIEMPRE", "CASI SIEMPRE"]:
        res["¿Has iniciado tu vida sexual?"] = "SI"
        res["iniciado_vida_sexual"] = "SI"
        iniciado_sexual = "SI"

    # b) Si la persona explícitamente marcó NO en Col 34 (no ha iniciado vida sexual):
    #    Por fidelidad a la pregunta ('Si respondiste Si...'), la casilla 35 DEBE SER VACÍA.
    if iniciado_sexual == "NO":
        res["Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?"] = ""
        res["usa_condon"] = ""

    # 10. Coherencia Conocimiento de Métodos Anticonceptivos (Cols 36 y 37):
    # a) Si el participante escribió un método anticonceptivo real en Col 37 (¿Cual?_3) -> Col 36 = SI.
    conoce_metodo = res.get("¿Conoces algún método anticonceptico?", "")
    metodo_val = res.get("¿Cual?_3", "")
    if metodo_val and metodo_val not in ["", "NO", "NINGUNO", "NINGUNA", "N/A", "NO CONOCE", "NO SE"]:
        res["¿Conoces algún método anticonceptico?"] = "SI"
        res["conoce_anticonceptivo"] = "SI"
    elif conoce_metodo == "NO":
        # b) Si marcó NO en conocer algún método, no puede haber método en Col 37.
        res["¿Cual?_3"] = ""
        res["cual_anticonceptivo"] = ""

    # 11. Fidelidad y Coherencia Preservativos EPS (Cols 39 y 40):
    # a) Si en Col 39 respondió NO -> la fecha de Col 40 DEBE SER VACÍA.
    entregado_pres = res.get("¿Te han entregado preservativos en la EPS o institución de salud?", "")
    cuando_pres = res.get("¿Cuándo fue la ultima vez?", "")
    if entregado_pres == "NO":
        res["¿Cuándo fue la ultima vez?"] = ""
        res["cuando_preservativos"] = ""
    elif cuando_pres and cuando_pres not in ["", "NINGUNA", "NO", "N/A", "NINGUNO"]:
        # b) Si hay una fecha o período de entrega en Col 40 -> Col 39 = SI.
        res["¿Te han entregado preservativos en la EPS o institución de salud?"] = "SI"
        res["entregado_preservativos"] = "SI"

    # 12. Coherencia Espacios de Diálogo en Institución Educativa (Cols 42 y 43):
    # Si el participante escribió un motivo o justificación en Col 43 ('¿Por que?'),
    # esto confirma categóricamente que SÍ desea espacios de diálogo -> Col 42 = SI.
    # Corrige además el error óptico donde la IA confunde la casilla física Si [X] No [ ] con NO a pesar de haber escrito.
    por_que = res.get("¿Por que?", "") or res.get("por_que", "")
    if por_que and str(por_que).strip().upper() not in ["", "NO", "NINGUNO", "NINGUNA", "N/A", "NO SE", "NO SABE"]:
        res["¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?"] = "SI"
        res["espacios_dialogo"] = "SI"

    return res


class FichaCaracterizacion(BaseModel):
    """Modelo estructurado con las 43 variables de la ficha física."""
    quien_diligencia: str = Field(default="", alias="NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA")
    territorio: str = Field(default="", alias="TERRITORIO")
    nombre_participante: str = Field(default="", alias="Nombre completo del participante")
    tipo_documento: str = Field(default="", alias="Tipo de documento identidad")
    numero_documento: str = Field(default="", alias="Numero de documento identidad")
    edad: str = Field(default="", alias="Edad")
    grado_escolar: str = Field(default="", alias="Grado escolar")
    telefono: str = Field(default="", alias="Teléfono de contacto")
    direccion: str = Field(default="", alias="Dirección de residencia (barrio o vereda)")
    municipio: str = Field(default="", alias="Municipio")
    zona: str = Field(default="", alias="Zona")
    eps: str = Field(default="", alias="EPS (si tienes)")
    regimen: str = Field(default="", alias="Régimen")
    sexo: str = Field(default="", alias="Sexo con el que te identificas")
    identidad_genero: str = Field(default="", alias="Identidad de género")
    etnia: str = Field(default="", alias="¿Perteneces a alguna población o grupo étnico?")
    discapacidad: str = Field(default="", alias="¿Tienes alguna condición de discapacidad?")
    cual_discapacidad: str = Field(default="", alias="¿Cual?")
    antecedentes_enfermedad: str = Field(default="", alias="¿Tienes antecedentes de alguna enfermedad personal o familiar importante?")
    cual_enfermedad: str = Field(default="", alias="¿Cual?_1")
    asistio_medico: str = Field(default="", alias="¿Has asistido al médico en el último año?")
    cuando_medico: str = Field(default="", alias="¿Cuándo fue la última vez?")
    odontologo: str = Field(default="", alias="¿Fuiste al odontólogo el último año?")
    actividades_recreativas: str = Field(default="", alias="¿Qué actividades recreativas haces en tu tiempo libre?")
    tiempo_actividad: str = Field(default="", alias="¿Qué tiempo empleas en esta actividad?")
    cigarrillo_vapeador: str = Field(default="", alias="¿Consumes o has consumido cigarrillo o vapeador?")
    cada_cuanto_fuma: str = Field(default="", alias="Cada cuánto?")
    consume_alcohol: str = Field(default="", alias="¿Consumes o has consumido alcohol?")
    cada_cuanto_alcohol: str = Field(default="", alias="Cada cuánto?_1")
    sustancia_psicoactiva: str = Field(default="", alias="¿Has consumido alguna sustancia psicoactiva?")
    cual_sustancia: str = Field(default="", alias="¿Cual?_2")
    discriminacion_violencia: str = Field(default="", alias="¿Has vivido situaciones de discriminación, rechazo o violencia?")
    info_its_sexual: str = Field(default="", alias="¿Has recibido información sobre salud sexual, ITS o métodos de prevención?")
    iniciado_vida_sexual: str = Field(default="", alias="¿Has iniciado tu vida sexual?")
    usa_condon: str = Field(default="", alias="Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?")
    conoce_anticonceptivo: str = Field(default="", alias="¿Conoces algún método anticonceptico?")
    cual_anticonceptivo: str = Field(default="", alias="¿Cual?_3")
    embarazo_adolescente: str = Field(default="", alias="¿Has vivido o conoces algún caso cercano de embarazo adolescente?")
    entregado_preservativos: str = Field(default="", alias="¿Te han entregado preservativos en la EPS o institución de salud?")
    cuando_preservativos: str = Field(default="", alias="¿Cuándo fue la ultima vez?")
    tema_aprender: str = Field(default="", alias="¿Qué tema te gustaria aprender o entender mejor?")
    espacios_dialogo: str = Field(default="", alias="¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?")
    por_que: str = Field(default="", alias="¿Por que?")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore"
    }

    @model_validator(mode="before")
    @classmethod
    def convertir_todo_a_mayusculas(cls, data: Any) -> Any:
        if isinstance(data, dict):
            normalizado = {}
            for k, v in data.items():
                clave_canonica = canonicalizar_clave_columna(k)
                normalizado[clave_canonica] = normalizar_campo_por_columna(clave_canonica, v)

            # Aplicar reglas de coherencia lógica y dependencias
            normalizado = aplicar_reglas_coherencia(normalizado)
            return normalizado
        return data

    def to_ordered_row(self) -> List[str]:
        """Convierte los valores a una lista ordenada de strings para Google Sheets asegurando MAYÚSCULAS y estandarización."""
        dump = self.model_dump(by_alias=True)
        dump = aplicar_reglas_coherencia(dump)
        terr = normalizar_territorio(dump.get("TERRITORIO") or dump.get("Municipio", ""))
        tipo_doc = normalizar_tipo_documento_segun_edad(
            dump.get("Tipo de documento identidad", ""),
            dump.get("Edad", "")
        )

        fila = []
        for col in COLUMNAS_FICHA:
            if col in ["Municipio", "TERRITORIO"] and terr:
                val = terr
            elif col == "Tipo de documento identidad":
                val = tipo_doc
            else:
                val = normalizar_campo_por_columna(col, dump.get(col, ""))
            fila.append(val)
        return fila

    def to_canonical_dict(self) -> Dict[str, str]:
        """Devuelve un diccionario exacto con las 43 claves en mayúsculas y estandarizadas."""
        dump = self.model_dump(by_alias=True)
        dump = aplicar_reglas_coherencia(dump)
        terr = normalizar_territorio(dump.get("TERRITORIO") or dump.get("Municipio", ""))
        tipo_doc = normalizar_tipo_documento_segun_edad(
            dump.get("Tipo de documento identidad", ""),
            dump.get("Edad", "")
        )

        res = {}
        for col in COLUMNAS_FICHA:
            if col in ["Municipio", "TERRITORIO"] and terr:
                val = terr
            elif col == "Tipo de documento identidad":
                val = tipo_doc
            else:
                val = normalizar_campo_por_columna(col, dump.get(col, ""))
            res[col] = val
        return res
