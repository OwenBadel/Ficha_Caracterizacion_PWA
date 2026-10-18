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


# Variaciones fonéticas comunes de nombres de pila en campo colombiano
EQUIVALENCIAS_NOMBRES: Dict[str, str] = {
    "MAIKOL": "MICHAEL",
    "MAYCOL": "MICHAEL",
    "MAICOL": "MICHAEL",
    "MICHEL": "MICHAEL",
    "MICOL": "MICHAEL",
    "YEISON": "JEYSON",
    "JEISON": "JEYSON",
    "YEYSON": "JEYSON",
    "BRAYAN": "BRYAN",
    "BRAIAN": "BRYAN",
    "BRIAN": "BRYAN",
    "JONATAN": "JONATHAN",
    "YONATAN": "JONATHAN",
    "DUBAN": "DUVAN",
    "ESTID": "STEVEN",
    "ESTIVEN": "STEVEN",
    "STIVEN": "STEVEN",
    "DEIBID": "DAVID",
    "DAYANA": "DAIANA",
    "YULIETH": "JULIETH",
    "YULI": "JULIE",
    "KATERIN": "KATHERINE",
    "CATERIN": "KATHERINE",
    "MAYRA": "MAIRA"
}


def similitud_nombre_pila(t1: str, t2: str) -> float:
    """Calcula similitud de primer nombre integrando equivalencias fonéticas regionales."""
    if t1 == t2:
        return 1.0
    c1 = EQUIVALENCIAS_NOMBRES.get(t1, t1)
    c2 = EQUIVALENCIAS_NOMBRES.get(t2, t2)
    if c1 == c2:
        return 1.0
    return jaro_winkler_similarity(t1, t2)


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

    # Inversión de nombre/apellido (ej. "PEREZ MICHAEL" vs "MICHAEL PEREZ")
    if len(tokens1) >= 2 and len(tokens2) >= 2:
        if (
            similitud_nombre_pila(tokens1[0], tokens2[-1]) >= 0.82
            and jaro_winkler_similarity(tokens1[-1], tokens2[0]) >= 0.82
        ):
            tokens1 = list(reversed(tokens1))

    # 1. Validación estricta de primer nombre (nombre de pila)
    if len(tokens1) >= 1 and len(tokens2) >= 1:
        sim_primer = similitud_nombre_pila(tokens1[0], tokens2[0])
        if sim_primer < 0.82:
            return 0.0

    # 2. Validación estricta de apellidos (últimos tokens)
    # El último token de la cadena más corta debe coincidir con al menos un token de apellido (índice >= 1)
    if len(tokens1) >= 2 and len(tokens2) >= 2:
        corta = tokens1 if len(tokens1) <= len(tokens2) else tokens2
        larga = tokens2 if len(tokens1) <= len(tokens2) else tokens1
        ultimo_corta = corta[-1]
        max_sim_apellido = max(jaro_winkler_similarity(ultimo_corta, t_larga) for t_larga in larga[1:])
        if max_sim_apellido < 0.82:
            return 0.0

    # 3. Validación de apellidos discordantes en nombres de 3 o más palabras:
    # Evita que 'MARIA JOSE PEREZ' se cruce con 'MARIA JOSE GOMEZ'
    if len(tokens1) >= 3 and len(tokens2) >= 3:
        for t1 in tokens1[1:]:
            max_t1_en_t2 = max(jaro_winkler_similarity(t1, t2) for t2 in tokens2[1:])
            if max_t1_en_t2 < 0.70:
                return 0.0

    # Cobertura cruzada simétrica de tokens con soporte de equivalencias
    def match_token(t_a, t_b):
        return similitud_nombre_pila(t_a, t_b)

    score_1_to_2 = sum(max(match_token(t1, t2) for t2 in tokens2) for t1 in tokens1) / len(tokens1)
    score_2_to_1 = sum(max(match_token(t2, t1) for t1 in tokens1) for t2 in tokens2) / len(tokens2)

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
        self.indice_por_nombre: Dict[str, List[Dict[str, str]]] = {}
        self._lock = threading.Lock()
        self.cargar()

    def _generar_clave(self, nom: str, doc: str = "", muni: str = "") -> str:
        """Genera una clave compuesta única para evitar colisiones entre homónimos."""
        doc_limpio = limpiar_texto(doc)
        mun_limpio = limpiar_texto(muni)
        if doc_limpio:
            return f"{nom}|{doc_limpio}"
        if mun_limpio:
            return f"{nom}|{mun_limpio}"
        return nom

    def _reconstruir_indice_nombres_locked(self):
        """Reconstruye el índice secundario por nombre para consultas O(1) de homónimos."""
        self.indice_por_nombre = {}
        for k, v in self.participantes.items():
            nom = v.get("nombre") or k.split("|")[0]
            nom = limpiar_texto(nom)
            if nom:
                self.indice_por_nombre.setdefault(nom, []).append(v)

    def cargar(self):
        """Carga la base de participantes desde el archivo JSON local y reconstruye el índice."""
        with self._lock:
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        self.participantes = json.load(f)
                    self._reconstruir_indice_nombres_locked()
                    logger.info(f"Caché de participantes cargado: {len(self.participantes)} registros.")
                except Exception as e:
                    logger.warning(f"Error cargando caché de participantes: {e}")
                    self.participantes = {}
                    self.indice_por_nombre = {}
            else:
                self.participantes = {}
                self.indice_por_nombre = {}

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
            self.indice_por_nombre = {}
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
        """Agrega o actualiza un participante en la base usando clave compuesta."""
        nom = limpiar_texto(nombre)
        if not nom or len(nom) < 4:
            return

        muni = limpiar_texto(municipio)
        if muni:
            muni = normalizar_territorio(muni)
        eps_norm = limpiar_texto(eapb)
        if eps_norm:
            eps_norm = normalizar_eps(eps_norm)
        doc_norm = limpiar_texto(documento)

        item = {
            "nombre": nom,
            "edad": limpiar_texto(edad),
            "municipio": muni,
            "eapb": eps_norm,
            "documento": doc_norm
        }

        clave = self._generar_clave(nom, doc_norm, muni)

        with self._lock:
            self.participantes[clave] = item
            lista = self.indice_por_nombre.setdefault(nom, [])
            idx_existente = next(
                (i for i, x in enumerate(lista) if (doc_norm and x.get("documento") == doc_norm) or (not doc_norm and x.get("municipio") == muni)),
                None
            )
            if idx_existente is not None:
                lista[idx_existente] = item
            else:
                lista.append(item)

        if guardar_inmediato:
            self.guardar()

    def aprender_lote(self, registros: List[Dict[str, str]]) -> int:
        """Incorpora un lote de registros maestros con claves compuestas y persiste a disco."""
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
                doc_norm = limpiar_texto(r.get("documento"))

                item = {
                    "nombre": nom,
                    "edad": limpiar_texto(r.get("edad")),
                    "municipio": muni,
                    "eapb": eps_norm,
                    "documento": doc_norm
                }
                clave = self._generar_clave(nom, doc_norm, muni)
                self.participantes[clave] = item

                lista = self.indice_por_nombre.setdefault(nom, [])
                idx_existente = next(
                    (i for i, x in enumerate(lista) if (doc_norm and x.get("documento") == doc_norm) or (not doc_norm and x.get("municipio") == muni)),
                    None
                )
                if idx_existente is not None:
                    lista[idx_existente] = item
                else:
                    lista.append(item)

                insertados += 1

        self.guardar()
        logger.info(f"Ingesta de lote completada: {insertados} participantes actualizados/agregados.")
        return insertados

    def buscar_coincidencia(self, nombre_raw: str, municipio_hint: str = "") -> Optional[Dict[str, str]]:
        """
        Busca un participante coincidente mediante coincidencia exacta (con desempate por municipio)
        o Jaro-Winkler tokenizado con bonificación territorial reducida a 0.03 (desactivada en Santa Catalina).
        """
        nom_busqueda = limpiar_texto(nombre_raw)
        if not nom_busqueda or len(nom_busqueda) < 4:
            return None

        mun_hint_limpio = limpiar_texto(municipio_hint)
        if mun_hint_limpio:
            try:
                mun_norm = normalizar_territorio(mun_hint_limpio)
                if mun_norm:
                    mun_hint_limpio = mun_norm
            except Exception:
                pass

        with self._lock:
            # 1. Coincidencia exacta directa (O(1)) resolviendo homónimos por municipio
            if nom_busqueda in self.indice_por_nombre:
                candidatos = self.indice_por_nombre[nom_busqueda]
                if len(candidatos) == 1:
                    res = dict(candidatos[0])
                    res["score"] = 1.0
                    return res
                elif len(candidatos) > 1:
                    if mun_hint_limpio:
                        for c in candidatos:
                            if c.get("municipio") == mun_hint_limpio:
                                res = dict(c)
                                res["score"] = 1.0
                                return res
                    # Si no coincide o no hay hint, devolver el primer candidato
                    res = dict(candidatos[0])
                    res["score"] = 1.0
                    return res

            items_copia = list(self.participantes.values())

        # 2. Coincidencia difusa con Jaro-Winkler Tokenizado
        mejor_match = None
        mejor_score = 0.0

        for data in items_copia:
            score = token_jaro_winkler_similarity(nom_busqueda, data.get("nombre", ""))

            # Bonificación territorial reducida a 0.03 y desactivada en SANTA CATALINA
            if mun_hint_limpio and data.get("municipio") == mun_hint_limpio:
                if mun_hint_limpio != "SANTA CATALINA":
                    score += 0.03

            if score > mejor_score:
                mejor_score = score
                mejor_match = data

        # Umbral canónico: 0.78
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
