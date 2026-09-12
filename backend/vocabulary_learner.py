"""
vocabulary_learner.py — Módulo de Vocabulario Adaptativo y Guía de Coincidencias (Fuzzy Matching)
Digitalizador de Fichas de Caracterización (PROJ-006 - Lemon Fábrica)

Permite que el sistema aprenda términos frecuentes y respuestas de formularios anteriores
para todas las columnas de texto abierto, actuando como guía de coincidencia para auto-corregir
caligrafía dudosa, ilegible o con variaciones fonéticas/ortográficas (ej. 'YADUL', 'YADOL' -> 'YADEL' en anticonceptivos).
"""

from __future__ import annotations
import os
import json
import re
import difflib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("vocabulary_learner")

CURRENT_DIR = Path(__file__).resolve().parent
CACHE_FILE = CURRENT_DIR / "vocabulario_cache.json"

# Todas las columnas de texto libre o semi-abierto aptas para aprendizaje y guía de coincidencia
# (Se excluyen estrictamente identificaciones únicas como nombre del participante, ID y teléfono)
COLUMNAS_APRENDIZAJE: List[str] = [
    "¿Cual?_3",                                               # Método anticonceptivo (ej. YADEL / JADELLE)
    "¿Qué actividades recreativas haces en tu tiempo libre?", # Actividades de ocio
    "Dirección de residencia (barrio o vereda)",             # Barrios y sectores locales
    "¿Cual?_2",                                               # Sustancias psicoactivas
    "¿Cual?_1",                                               # Enfermedades importantes
    "¿Cual?",                                                 # Tipo de discapacidad
    "Cada cuánto?",                                           # Frecuencia consumo cigarrillo
    "Cada cuánto?_1",                                         # Frecuencia consumo alcohol
    "¿Cuándo fue la última vez?",                             # Consulta médica
    "¿Cuándo fue la ultima vez?",                             # Entrega preservativos
    "¿Qué tema te gustaria aprender o entender mejor?",       # Temas de interés
    "¿Por que?"                                               # Motivo de diálogo
]

# Semilla inicial enriquecida con términos y respuestas reales frecuentes
SEMILLA_INICIAL: Dict[str, Dict[str, int]] = {
    "¿Cual?_3": {
        "YADEL": 80,
        "JADELLE": 60,
        "CONDON": 60,
        "CONDÓN": 60,
        "PASTILLAS": 50,
        "INYECCION": 45,
        "INYECCIÓN": 45,
        "IMPLANTE": 40,
        "PRESERVATIVO": 35,
        "T DE COBRE": 25,
        "DIU": 25,
        "PARCHE": 20,
        "POMADA": 15,
        "RITMO": 15
    },
    "¿Qué actividades recreativas haces en tu tiempo libre?": {
        "FUTBOL": 50,
        "FÚTBOL": 50,
        "MICROFUTBOL": 30,
        "VOLEIBOL": 25,
        "BALONCESTO": 25,
        "BAILAR": 25,
        "LEER": 20,
        "DIBUJAR": 20,
        "ESCUCHAR MUSICA": 25,
        "JUGAR": 20,
        "VIDEOJUEGOS": 20,
        "CAMINAR": 15,
        "PATINAJE": 15
    },
    "Dirección de residencia (barrio o vereda)": {
        "CENTRO": 35,
        "SAN RAFAEL": 30,
        "EL RETIRO": 25,
        "LA FLORIDA": 25,
        "SAN JOSE": 20,
        "BUENOS AIRES": 20,
        "EL CARMEN": 20,
        "VILLA NUEVA": 15,
        "LA CONCEPCION": 15
    },
    "¿Cual?_2": {
        "MARIHUANA": 50,
        "TUSI": 35,
        "COCAINA": 25,
        "ALCOHOL": 25,
        "CIGARRILLO": 20,
        "NINGUNA": 30
    },
    "¿Cual?_1": {
        "ASMA": 50,
        "DIABETES": 40,
        "HIPERTENSION": 40,
        "HIPERTENSIÓN": 40,
        "CANCER": 20,
        "ALERGIA": 20,
        "CARDIOPATIA": 15,
        "NINGUNA": 30
    },
    "¿Cual?": {
        "FISICA": 40,
        "FÍSICA": 40,
        "VISUAL": 35,
        "AUDITIVA": 30,
        "COGNITIVA": 30,
        "MOTORA": 25,
        "PSICOSOCIAL": 20
    },
    "Cada cuánto?": {
        "DIARIO": 40,
        "SEMANAL": 35,
        "FINES DE SEMANA": 30,
        "OCASIONAL": 25,
        "NUNCA": 25
    },
    "Cada cuánto?_1": {
        "FINES DE SEMANA": 45,
        "SEMANAL": 35,
        "MENSUAL": 30,
        "EN FIESTAS": 25,
        "OCASIONAL": 25,
        "NUNCA": 20
    },
    "¿Cuándo fue la última vez?": {
        "HACE UN MES": 40,
        "HACE TRES MESES": 35,
        "HACE SEIS MESES": 35,
        "HACE UN AÑO": 30,
        "MAYO 2026": 25,
        "ESTE AÑO": 20
    },
    "¿Cuándo fue la ultima vez?": {
        "HACE UN MES": 40,
        "HACE TRES MESES": 35,
        "HACE SEIS MESES": 35,
        "MAYO 2026": 25,
        "NUNCA": 30
    },
    "¿Qué tema te gustaria aprender o entender mejor?": {
        "VIH": 60,
        "SIFILIS": 60,
        "SÍFILIS": 60,
        "HEPATITIS B Y C": 60,
        "METODOS ANTICONCEPTIVOS": 60,
        "MÉTODOS ANTICONCEPTIVOS": 60,
        "USO CORRECTO DEL PRESERVATIVO": 60,
        "PROYECTO DE VIDA": 60,
        "RESPETO POR LAS DIFERENCIAS": 60,
        "PREVENCION DEL EMBARAZO ADOLESCENTE": 60,
        "PREVENCIÓN DEL EMBARAZO ADOLESCENTE": 60,
        "SALUD MENTAL Y RELACIONES": 60,
        "SALUD SEXUAL": 50,
        "AUTOESTIMA": 40
    },
    "¿Por que?": {
        "PARA APRENDER MAS": 45,
        "ES IMPORTANTE": 40,
        "PARA PREVENIR": 35,
        "RESOLVER DUDAS": 30,
        "ORIENTACION": 25,
        "CUIDAR MI SALUD": 25
    }
}


class VocabularyLearner:
    """Gestiona el aprendizaje dinámico y la corrección difusa de términos por columna."""

    def __init__(self, cache_path: Path = CACHE_FILE):
        self.cache_path = cache_path
        self.vocabulario: Dict[str, Dict[str, int]] = {}
        self._cargar_cache()

    def _cargar_cache(self):
        """Carga el vocabulario persistido o inicializa/fusiona con la semilla base."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cargado = json.load(f)
                self.vocabulario = cargado
            except Exception as e:
                logger.warning(f"No se pudo leer {self.cache_path}: {e}. Usando semilla inicial.")
                self.vocabulario = json.loads(json.dumps(SEMILLA_INICIAL))
        else:
            self.vocabulario = json.loads(json.dumps(SEMILLA_INICIAL))

        # Asegurar que todas las columnas de la semilla existan y estén enriquecidas
        actualizado = False
        for col, terminos_semilla in SEMILLA_INICIAL.items():
            if col not in self.vocabulario:
                self.vocabulario[col] = {}
                actualizado = True
            for termino, peso in terminos_semilla.items():
                if termino not in self.vocabulario[col]:
                    self.vocabulario[col][termino] = peso
                    actualizado = True

        # Limpiar si YADEL estaba erróneamente en dirección de residencia
        if "Dirección de residencia (barrio o vereda)" in self.vocabulario:
            if "YADEL" in self.vocabulario["Dirección de residencia (barrio o vereda)"]:
                del self.vocabulario["Dirección de residencia (barrio o vereda)"]["YADEL"]
                actualizado = True

        # Garantizar que YADEL esté presente en ¿Cual?_3
        if "¿Cual?_3" not in self.vocabulario:
            self.vocabulario["¿Cual?_3"] = {}
        if self.vocabulario["¿Cual?_3"].get("YADEL", 0) < 80:
            self.vocabulario["¿Cual?_3"]["YADEL"] = 80
            actualizado = True

        if actualizado or not self.cache_path.exists():
            self._guardar_cache()

    def _guardar_cache(self):
        """Persiste el vocabulario en disco de forma atómica."""
        try:
            temp_path = self.cache_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.vocabulario, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.cache_path)
        except Exception as e:
            logger.error(f"Error al guardar vocabulario en {self.cache_path}: {e}")

    def obtener_terminos_frecuentes(self, columna: str, limite: int = 15) -> List[str]:
        """Devuelve los términos más frecuentes de una columna específica."""
        terminos = self.vocabulario.get(columna, {})
        if not terminos:
            return []
        ordenados = sorted(terminos.items(), key=lambda item: item[1], reverse=True)
        return [t[0] for t in ordenados[:limite]]

    def generar_resumen_guia_todas_columnas(self, limite_por_columna: int = 6) -> str:
        """
        Construye un resumen estructurado de respuestas frecuentes para todas las columnas de texto.
        Sirve como guía de contexto en el prompt para que el modelo de IA resuelva dudas de caligrafía.
        """
        lineas = []
        nombres_amigables = {
            "¿Cual?_3": "Método anticonceptivo (¿Cual?_3)",
            "¿Qué actividades recreativas haces en tu tiempo libre?": "Actividades recreativas / ocio",
            "Dirección de residencia (barrio o vereda)": "Dirección / Barrio / Vereda",
            "¿Cual?_2": "Sustancias psicoactivas (¿Cual?_2)",
            "¿Cual?_1": "Enfermedades importantes (¿Cual?_1)",
            "¿Cual?": "Tipo de discapacidad (¿Cual?)",
            "Cada cuánto?": "Frecuencia cigarrillo (Cada cuánto?)",
            "Cada cuánto?_1": "Frecuencia alcohol (Cada cuánto?_1)",
            "¿Cuándo fue la última vez?": "Última vez médico",
            "¿Cuándo fue la ultima vez?": "Última vez preservativos",
            "¿Qué tema te gustaria aprender o entender mejor?": "Temas de interés",
            "¿Por que?": "Razón de espacios de diálogo (¿Por qué?)"
        }

        for col in COLUMNAS_APRENDIZAJE:
            frecuentes = self.obtener_terminos_frecuentes(col, limite=limite_por_columna)
            if frecuentes:
                nombre = nombres_amigables.get(col, col)
                # Destacar YADEL en anticonceptivos
                if col == "¿Cual?_3":
                    lineas.append(f"    * {nombre}: YADEL (implante Jadelle / barritas en brazo), {', '.join([f for f in frecuentes if f != 'YADEL'])}")
                else:
                    lineas.append(f"    * {nombre}: {', '.join(frecuentes)}")

        return "\n".join(lineas)

    def corregir_valor(self, columna: str, valor: Optional[Any], umbral_similitud: float = 0.74) -> str:
        """
        Aplica corrección difusa (Fuzzy Matching) sobre el valor extraído
        comparándolo con los términos aprendidos de la columna correspondiente.
        """
        if not valor:
            return ""
        s = str(valor).strip().upper()
        if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED"]:
            return ""

        # Si la columna no está habilitada para aprendizaje, devolver sin alteración
        if columna not in COLUMNAS_APRENDIZAJE:
            return s

        # Regla especial para método anticonceptivo: YADEL / JADELLE
        if columna == "¿Cual?_3":
            # Normalizar caracteres y buscar variaciones de Jadelle/Yadel
            s_clean = re.sub(r"[^A-Z]", "", s)
            if s_clean in ["YADEL", "YADUL", "YADOL", "YADELL", "YADELLE", "JADEL", "JADUL", "JADOL", "JADELL", "JADELLE", "YADIL", "YADLE"]:
                logger.info(f"Corrección directa de anticonceptivo Jadelle: '{s}' -> 'YADEL'")
                return "YADEL"

        dict_col = self.vocabulario.get(columna, {})
        if not dict_col:
            return s

        # 1. Si coincide exactamente con un término conocido
        if s in dict_col:
            return s

        # 2. Coincidencia difusa de la frase completa
        terminos_conocidos = list(dict_col.keys())
        terminos_conocidos.sort(key=lambda k: dict_col[k], reverse=True)

        mejor_match = None
        mejor_score = 0.0

        for t in terminos_conocidos:
            score = difflib.SequenceMatcher(None, s, t).ratio()
            if score > mejor_score:
                mejor_score = score
                mejor_match = t

        if mejor_match and mejor_score >= umbral_similitud:
            logger.info(f"Fuzzy Match detectado en '{columna}': '{s}' -> '{mejor_match}' (score: {mejor_score:.2f})")
            return mejor_match

        # 3. Coincidencia difusa por tokens individuales
        palabras = re.findall(r"\b[A-ZÁÉÍÓÚÑ0-9]+\b", s)
        hubo_reemplazo = False
        resultado_tokens = []

        prefijos_comunes = {"BARRIO", "VEREDA", "SECTOR", "CALLE", "CRA", "CARRERA", "URB", "URBANIZACION", "EN", "EL", "LA", "LOS", "LAS", "DE"}

        for palabra in palabras:
            if palabra in prefijos_comunes or len(palabra) < 4:
                resultado_tokens.append(palabra)
                continue

            token_match = None
            token_score = 0.0

            for t in terminos_conocidos:
                if " " not in t and len(t) >= 4:
                    sc = difflib.SequenceMatcher(None, palabra, t).ratio()
                    if sc > token_score and sc >= 0.72:
                        token_score = sc
                        token_match = t

            if token_match:
                logger.info(f"Fuzzy Token Match en '{columna}': '{palabra}' -> '{token_match}' (score: {token_score:.2f})")
                resultado_tokens.append(token_match)
                hubo_reemplazo = True
            else:
                resultado_tokens.append(palabra)

        if hubo_reemplazo:
            return " ".join(resultado_tokens)

        return s

    def aprender_fila(self, fila_data: Dict[str, Any] | List[str], columnas_referencia: Optional[List[str]] = None):
        """
        Registra una fila confirmada en el vocabulario histórico, incrementando las frecuencias.
        """
        if isinstance(fila_data, list):
            from .schema import COLUMNAS_FICHA
            cols = columnas_referencia or COLUMNAS_FICHA
            dict_data = dict(zip(cols, fila_data))
        elif isinstance(fila_data, dict):
            dict_data = fila_data
        else:
            return

        cambios = False
        for col in COLUMNAS_APRENDIZAJE:
            val = dict_data.get(col)
            if not val:
                continue
            s = str(val).strip().upper()
            if not s or s in ["NONE", "NULL", "N/A", "UNDEFINED", "NO"]:
                continue

            if len(s) > 50:
                continue

            if col not in self.vocabulario:
                self.vocabulario[col] = {}

            actual = self.vocabulario[col].get(s, 0)
            self.vocabulario[col][s] = actual + 1
            cambios = True

        if cambios:
            self._guardar_cache()


# Instancia singleton para todo el backend
vocabulary_learner = VocabularyLearner()
