"""
Módulo de Memoria y Coincidencia Difusa de Participantes (Caché Offline).
Permite reutilizar la base de datos de participantes ya digitalizados en las Fichas de Caracterización,
reconciliando nombres, edad, municipio y EPS mediante similitud difusa (Levenshtein/Difflib)
para evitar errores tipográficos o caligráficos al escanear los Pre-Test y Post-Test.
"""

from __future__ import annotations
import os
import io
import csv
import json
import logging
import difflib
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("participant_cache")

CACHE_FILE_DEFAULT = Path(__file__).resolve().parent / "participantes_cache.json"


def limpiar_texto(val: Any) -> str:
    if val is None:
        return ""
    texto = str(val).strip().upper()
    texto = re.sub(r"\s+", " ", texto)
    return texto


class ParticipantCache:
    """Gestiona el catálogo de participantes y resuelve coincidencias difusas."""

    def __init__(self, cache_file: Optional[Path] = None):
        self.cache_file = cache_file or CACHE_FILE_DEFAULT
        self.participantes: Dict[str, Dict[str, str]] = {}
        self.cargar()

    def cargar(self):
        """Carga la base de participantes desde el archivo JSON local."""
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
        """Guarda la base de participantes a disco de manera atómica."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.participantes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando caché de participantes: {e}")

    def aprender_participante(
        self,
        nombre: str,
        edad: str = "",
        municipio: str = "",
        eapb: str = "",
        documento: str = ""
    ):
        """Agrega o actualiza un participante en la base."""
        nom = limpiar_texto(nombre)
        if not nom or len(nom) < 4:
            return

        item = {
            "nombre": nom,
            "edad": limpiar_texto(edad),
            "municipio": limpiar_texto(municipio),
            "eapb": limpiar_texto(eapb),
            "documento": limpiar_texto(documento)
        }

        # Guardar bajo clave canónica
        self.participantes[nom] = item
        self.guardar()

    def buscar_coincidencia(self, nombre_raw: str, municipio_hint: str = "") -> Optional[Dict[str, str]]:
        """
        Busca un participante coincidente mediante comparación difusa.
        Retorna el registro si la similitud supera el umbral (0.80, o 0.72 si coincide municipio).
        """
        nom_busqueda = limpiar_texto(nombre_raw)
        if not nom_busqueda or len(nom_busqueda) < 4:
            return None

        # 1. Coincidencia exacta directa
        if nom_busqueda in self.participantes:
            return self.participantes[nom_busqueda]

        # 2. Coincidencia difusa
        mejor_match = None
        mejor_score = 0.0
        mun_hint_limpio = limpiar_texto(municipio_hint)

        for clave_nom, data in self.participantes.items():
            # Similitud en nombre
            ratio = difflib.SequenceMatcher(None, nom_busqueda, clave_nom).ratio()

            # Bonificación si el municipio coincide
            if mun_hint_limpio and data.get("municipio") == mun_hint_limpio:
                ratio += 0.06

            if ratio > mejor_score:
                mejor_score = ratio
                mejor_match = data

        umbral = 0.78
        if mejor_score >= umbral and mejor_match:
            logger.info(f"Coincidencia difusa encontrada: '{nom_busqueda}' -> '{mejor_match['nombre']}' (Score: {mejor_score:.2f})")
            return mejor_match

        return None

    def importar_desde_csv(self, csv_texto: str) -> int:
        """
        Importa participantes desde un CSV exportado de Google Sheets (Fichas de Caracterización).
        Detecta dinámicamente columnas de Nombre, Edad, Municipio/Territorio y EPS.
        Retorna la cantidad de participantes importados.
        """
        lector = csv.reader(io.StringIO(csv_texto), delimiter=",")
        filas = list(lector)
        if not filas:
            return 0

        encabezados = [limpiar_texto(c) for c in filas[0]]

        def idx_col(*nombres_posibles) -> int:
            for nom in nombres_posibles:
                nom_limpio = limpiar_texto(nom)
                for i, h in enumerate(encabezados):
                    if nom_limpio in h or h in nom_limpio:
                        return i
            return -1

        idx_nombre = idx_col("Nombre completo del participante", "NOMBRE", "PARTICIPANTE")
        idx_edad = idx_col("Edad", "EDAD")
        idx_mun = idx_col("Municipio", "TERRITORIO", "MUNICIPIO")
        idx_eps = idx_col("EPS (si tienes)", "EAPB (EPS)", "EPS", "EAPB")
        idx_doc = idx_col("Numero de documento identidad", "DOCUMENTO", "IDENTIFICACION")

        if idx_nombre == -1:
            # Si no encontró por nombre exacto, intentar por la columna 2 o 3 (índices canónicos)
            idx_nombre = 2 if len(encabezados) > 2 else 0

        agregados = 0
        for fila in filas[1:]:
            if not fila or len(fila) <= idx_nombre:
                continue
            nombre = fila[idx_nombre].strip()
            if not nombre:
                continue

            edad = fila[idx_edad].strip() if 0 <= idx_edad < len(fila) else ""
            municipio = fila[idx_mun].strip() if 0 <= idx_mun < len(fila) else ""
            eps = fila[idx_eps].strip() if 0 <= idx_eps < len(fila) else ""
            doc = fila[idx_doc].strip() if 0 <= idx_doc < len(fila) else ""

            self.aprender_participante(nombre, edad, municipio, eps, doc)
            agregados += 1

        self.guardar()
        logger.info(f"Importación completada: {agregados} participantes importados.")
        return agregados

    def contar(self) -> int:
        return len(self.participantes)

    def obtener_resumen(self, limit: int = 50) -> Dict[str, Any]:
        """Retorna resumen y muestra de participantes cargados."""
        municipios = {}
        for p in self.participantes.values():
            m = p.get("municipio") or "SIN MUNICIPIO"
            municipios[m] = municipios.get(m, 0) + 1

        return {
            "total": len(self.participantes),
            "por_municipio": municipios,
            "muestra": list(self.participantes.values())[:limit]
        }


# Instancia singleton accesible globalmente
participant_cache = ParticipantCache()
