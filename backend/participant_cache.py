"""
Módulo de Memoria y Coincidencia Difusa de Participantes (Caché Offline y Patrón Maestro).
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.

Permite reutilizar la base de datos de participantes digitalizados y el PATRÓN MAESTRO,
reconciliando nombres, edad, municipio y EPS mediante similitud Jaro-Winkler tokenizada
con bonificación territorial para corregir errores tipográficos o caligráficos
al escanear los Pre-Test y Post-Test sin requerir intervención manual ni consumo de tokens.
"""

from __future__ import annotations
import os
import csv
import io
import json
import logging
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
from schema import normalizar_territorio, normalizar_eps

logger = logging.getLogger("participant_cache")

CACHE_FILE_DEFAULT = Path(__file__).resolve().parent / "participantes_cache.json"


def limpiar_texto(val: Any) -> str:
    """Normaliza cadenas de texto a mayúsculas, sin espacios redundantes ni acentos desordenados."""
    if val is None:
        return ""
    texto = str(val).strip().upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto


# =====================================================================
# ALGORITMO JARO-WINKLER PURO (MATEMÁTICA FORENSE DE CADENAS)
# =====================================================================

def jaro_similarity(s1: str, s2: str) -> float:
    """
    Calcula el coeficiente de similitud de Jaro entre dos cadenas en el rango [0.0, 1.0].
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j]:
                continue
            if s1[i] == s2[j]:
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

    if matches == 0:
        return 0.0

    # Contar transposiciones
    k = 0
    transpositions = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    transpositions //= 2

    return (
        (matches / len1) +
        (matches / len2) +
        ((matches - transpositions) / matches)
    ) / 3.0


def jaro_winkler_similarity(s1: str, s2: str, prefix_weight: float = 0.1) -> float:
    """
    Calcula la similitud Jaro-Winkler dando peso adicional a prefijos idénticos (hasta 4 chars).
    """
    j_sim = jaro_similarity(s1, s2)
    if j_sim < 0.7:
        return j_sim

    prefix_len = 0
    max_prefix = min(4, min(len(s1), len(s2)))
    for i in range(max_prefix):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break

    return j_sim + (prefix_len * prefix_weight * (1.0 - j_sim))


def token_jaro_winkler_similarity(s1: str, s2: str) -> float:
    """
    Calcula la similitud Jaro-Winkler a nivel de tokens (palabras individuales).
    Permite casar 'MAIKOL PEREZ' con 'MICHAEL STEVEN PEREZ' o nombres con orden invertido.
    """
    s1_clean = limpiar_texto(s1)
    s2_clean = limpiar_texto(s2)

    if not s1_clean or not s2_clean:
        return 0.0
    if s1_clean == s2_clean:
        return 1.0

    global_jw = jaro_winkler_similarity(s1_clean, s2_clean)

    tokens1 = [t for t in s1_clean.split() if len(t) >= 2]
    tokens2 = [t for t in s2_clean.split() if len(t) >= 2]

    if not tokens1 or not tokens2:
        return global_jw

    # Cobertura cruzada simétrica de tokens
    score_1_to_2 = sum(max(jaro_winkler_similarity(t1, t2) for t2 in tokens2) for t1 in tokens1) / len(tokens1)
    score_2_to_1 = sum(max(jaro_winkler_similarity(t2, t1) for t1 in tokens1) for t2 in tokens2) / len(tokens2)

    token_score = (score_1_to_2 + score_2_to_1) / 2.0
    return max(global_jw, token_score)


# =====================================================================
# GESTOR DEL PATRÓN MAESTRO Y CACHÉ DE PARTICIPANTES
# =====================================================================

class ParticipantCache:
    """Gestiona el catálogo de participantes y resuelve reconciliaciones deterministas thread-safe."""

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_file = cache_file or CACHE_FILE_DEFAULT
        self.participantes: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()
        self.cargar()

    def cargar(self):
        """Carga la base de participantes desde el archivo JSON local."""
        with self._lock:
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        self.participantes = json.load(f)
                    logger.info(f"Caché de participantes cargado: {len(self.participantes)} registros.")
                except Exception as e:
                    logger.warning(f"Error cargando caché de participantes: {e}")
                    self.participantes = {}
            else:
                self.participantes = {}

    def guardar(self):
        """Guarda la base de participantes a disco de manera atómica con archivo temporal."""
        with self._lock:
            try:
                temp_file = self.cache_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self.participantes, f, ensure_ascii=False, indent=2)
                temp_file.replace(self.cache_file)
            except Exception as e:
                logger.error(f"Error guardando caché de participantes: {e}")

    def limpiar(self):
        """Vacía por completo la base de participantes en memoria y en disco."""
        with self._lock:
            self.participantes = {}
        self.guardar()
        logger.info("Memoria viva de participantes reiniciada a 0 registros.")

    def aprender_participante(
        self,
        nombre: str,
        edad: str = "",
        municipio: str = "",
        eapb: str = "",
        documento: str = "",
        guardar_inmediato: bool = True
    ):
        """Agrega o actualiza un participante en la base."""
        nom = limpiar_texto(nombre)
        if not nom or len(nom) < 4:
            return

        muni = limpiar_texto(municipio)
        if muni:
            muni = normalizar_territorio(muni)
        eps_norm = limpiar_texto(eapb)
        if eps_norm:
            eps_norm = normalizar_eps(eps_norm)

        item = {
            "nombre": nom,
            "edad": limpiar_texto(edad),
            "municipio": muni,
            "eapb": eps_norm,
            "documento": limpiar_texto(documento)
        }

        with self._lock:
            self.participantes[nom] = item

        if guardar_inmediato:
            self.guardar()

    def aprender_lote(self, registros: List[Dict[str, str]]) -> int:
        """Incorpora un lote de registros maestros y persiste a disco."""
        insertados = 0
        with self._lock:
            for r in registros:
                nom = limpiar_texto(r.get("nombre"))
                if not nom or len(nom) < 4:
                    continue
                muni = limpiar_texto(r.get("municipio"))
                if muni:
                    muni = normalizar_territorio(muni)
                eps_norm = limpiar_texto(r.get("eapb"))
                if eps_norm:
                    eps_norm = normalizar_eps(eps_norm)

                self.participantes[nom] = {
                    "nombre": nom,
                    "edad": limpiar_texto(r.get("edad")),
                    "municipio": muni,
                    "eapb": eps_norm,
                    "documento": limpiar_texto(r.get("documento"))
                }
                insertados += 1

        self.guardar()
        logger.info(f"Ingesta de lote completada: {insertados} participantes actualizados/agregados.")
        return insertados

    def buscar_coincidencia(self, nombre_raw: str, municipio_hint: str = "") -> Optional[Dict[str, str]]:
        """
        Busca un participante coincidente mediante Jaro-Winkler tokenizado y bonificación territorial.
        Retorna el registro canónico si la similitud supera el umbral (0.78, o 0.72 si coincide municipio).
        """
        nom_busqueda = limpiar_texto(nombre_raw)
        if not nom_busqueda or len(nom_busqueda) < 4:
            return None

        with self._lock:
            # 1. Coincidencia exacta directa (O(1))
            if nom_busqueda in self.participantes:
                res = dict(self.participantes[nom_busqueda])
                res["score"] = 1.0
                return res
            items_copia = list(self.participantes.items())

        # 2. Coincidencia difusa con Jaro-Winkler Tokenizado
        mejor_match = None
        mejor_score = 0.0
        mun_hint_limpio = limpiar_texto(municipio_hint)

        for clave_nom, data in items_copia:
            score = token_jaro_winkler_similarity(nom_busqueda, clave_nom)

            # Bonificación territorial si el municipio concuerda
            if mun_hint_limpio and data.get("municipio") == mun_hint_limpio:
                score += 0.08

            if score > mejor_score:
                mejor_score = score
                mejor_match = data

        # Umbral canónico: 0.78 (equivalente a 0.70 base + 0.08 si el municipio concuerda)
        umbral = 0.78
        if mejor_score >= umbral and mejor_match:
            logger.info(
                f"Reconciliación Jaro-Winkler: '{nom_busqueda}' -> '{mejor_match['nombre']}' "
                f"(Score: {mejor_score:.3f}, Municipio: {mejor_match.get('municipio', 'N/A')})"
            )
            resultado = dict(mejor_match)
            resultado["score"] = round(mejor_score, 3)
            return resultado

        return None

    # =================================================================
    # INGESTA DEL PATRÓN MAESTRO (GOOGLE SHEETS Y ARCHIVOS LOCALES)
    # =================================================================

    def sincronizar_desde_csv_texto(self, contenido_csv: str) -> int:
        """
        Parsea el contenido CSV del PATRÓN MAESTRO mapeando las columnas definidas:
        Col 0: Marca temporal
        Col 1: NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA
        Col 2: TERRITORIO
        Col 3: Nombre completo del participante (NOMBRE)
        Col 4: Tipo de documento
        Col 5: Numero de documento (DOCUMENTO)
        Col 6: Edad (EDAD)
        Col 7: Grado escolar
        Col 8: Teléfono
        Col 9: Dirección
        Col 10: Municipio (MUNICIPIO)
        Col 11: Zona
        Col 12: EPS (si tienes) (EAPB)
        """
        if not contenido_csv.strip():
            return 0

        # Detectar delimitador analizando la primera línea
        primera_linea = contenido_csv.split("\n", 1)[0]
        delimitador = ","
        if ";" in primera_linea and primera_linea.count(";") > primera_linea.count(","):
            delimitador = ";"
        elif "\t" in primera_linea and primera_linea.count("\t") > primera_linea.count(","):
            delimitador = "\t"

        reader = csv.reader(io.StringIO(contenido_csv), delimiter=delimitador)
        filas = list(reader)
        if not filas:
            return 0

        # Inspeccionar encabezados para mapeo flexible
        header = [limpiar_texto(c) for c in filas[0]]
        idx_nombre = -1
        idx_edad = -1
        idx_municipio = -1
        idx_eps = -1
        idx_doc = -1

        for i, col in enumerate(header):
            if "PARTICIPANTE" in col or ("NOMBRE" in col and "DILIGENCIA" not in col):
                if idx_nombre == -1:
                    idx_nombre = i
            elif "EDAD" in col:
                idx_edad = i
            elif "EPS" in col or "EAPB" in col:
                idx_eps = i
            elif "MUNICIPIO" in col:
                idx_municipio = i
            elif "TERRITORIO" in col and idx_municipio == -1:
                idx_municipio = i
            elif "NUMERO DE DOCUMENTO" in col or ("DOCUMENTO" in col and "TIPO" not in col):
                idx_doc = i

        # Fallback a posiciones ordinales según especificación si no se identificaron por nombre
        if len(header) <= 5:
            # Estructura simplificada de 4 columnas: [Nombre, Edad, Municipio, EPS]
            if idx_nombre == -1:
                idx_nombre = 0
            if idx_edad == -1:
                idx_edad = 1
            if idx_municipio == -1:
                idx_municipio = 2
            if idx_eps == -1:
                idx_eps = 3
        else:
            # Estructura completa de 13 columnas del formulario
            if idx_nombre == -1:
                idx_nombre = 3
            if idx_doc == -1:
                idx_doc = 5
            if idx_edad == -1:
                idx_edad = 6
            if idx_municipio == -1:
                idx_municipio = 10 if len(header) > 10 else 2
            if idx_eps == -1:
                idx_eps = 12 if len(header) > 12 else -1

        registros: List[Dict[str, str]] = []
        for fila in filas[1:]:
            if not fila or len(fila) <= idx_nombre:
                continue

            nombre = fila[idx_nombre].strip()
            if not nombre or len(nombre) < 3:
                continue

            edad = fila[idx_edad].strip() if 0 <= idx_edad < len(fila) else ""
            municipio = fila[idx_municipio].strip() if 0 <= idx_municipio < len(fila) else ""
            if not municipio and 0 <= 2 < len(fila) and len(header) > 5:
                municipio = fila[2].strip()  # Fallback a TERRITORIO en formulario completo
            eps = fila[idx_eps].strip() if 0 <= idx_eps < len(fila) else ""
            doc = fila[idx_doc].strip() if 0 <= idx_doc < len(fila) else ""

            registros.append({
                "nombre": nombre,
                "edad": edad,
                "municipio": municipio,
                "eapb": eps,
                "documento": doc
            })

        return self.aprender_lote(registros)

    def sincronizar_desde_google_sheets(self, sheet_id: str, tab_name: str = "PATRON MAESTRO") -> int:
        """
        Descarga automáticamente la pestaña 'PATRON MAESTRO' de Google Sheets vía exportación CSV.
        Soporta tanto el ID directo como la URL completa del navegador.
        Requiere que la hoja tenga permisos de lectura con enlace.
        """
        cadena = str(sheet_id or "").strip()
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", cadena)
        id_limpio = match.group(1) if match else cadena

        tab_encoded = urllib.parse.quote(tab_name)
        url = f"https://docs.google.com/spreadsheets/d/{id_limpio}/gviz/tq?tqx=out:csv&sheet={tab_encoded}"
        logger.info(f"Descargando PATRÓN MAESTRO desde Google Sheets: {url}")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            csv_text = resp.read().decode("utf-8")

        total = self.sincronizar_desde_csv_texto(csv_text)
        logger.info(f"Sincronización con Google Sheets completada: {total} participantes cargados.")
        return total

    def sincronizar_desde_archivo_local(self, ruta_archivo: Path | str) -> int:
        """Carga el PATRÓN MAESTRO desde un archivo local (.csv o .xlsx)."""
        ruta = Path(ruta_archivo)
        if not ruta.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

        if ruta.suffix.lower() == ".csv":
            with open(ruta, "r", encoding="utf-8", errors="replace") as f:
                return self.sincronizar_desde_csv_texto(f.read())
        elif ruta.suffix.lower() in [".xlsx", ".xls"]:
            import pandas as pd
            df = pd.read_excel(ruta, sheet_name=None)
            # Buscar hoja PATRON MAESTRO o usar la primera
            hoja = None
            for nombre_hoja in df.keys():
                if "PATRON" in nombre_hoja.upper() or "MAESTRO" in nombre_hoja.upper():
                    hoja = df[nombre_hoja]
                    break
            if hoja is None:
                hoja = next(iter(df.values()))

            csv_buffer = io.StringIO()
            hoja.to_csv(csv_buffer, index=False)
            return self.sincronizar_desde_csv_texto(csv_buffer.getvalue())
        else:
            raise ValueError(f"Formato no soportado: {ruta.suffix}. Use .csv o .xlsx")

    def contar(self) -> int:
        with self._lock:
            return len(self.participantes)

    def obtener_resumen(self, limit: int = 50) -> Dict[str, Any]:
        """Retorna resumen y muestra de participantes cargados."""
        with self._lock:
            municipios = {}
            for p in self.participantes.values():
                m = p.get("municipio") or "SIN MUNICIPIO"
                municipios[m] = municipios.get(m, 0) + 1

            total = len(self.participantes)
            muestra = list(self.participantes.values())[:limit]

        return {
            "total": total,
            "por_municipio": municipios,
            "muestra": muestra
        }


# Instancia singleton accesible globalmente
participant_cache = ParticipantCache()
