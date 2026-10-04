"""
Módulo de Memoria y Coincidencia Difusa de Participantes (Caché Offline).
Permite reutilizar la base de datos de participantes ya digitalizados en las Fichas de Caracterización,
reconciliando nombres, edad, municipio y EPS mediante similitud difusa (Levenshtein/Difflib)
para evitar errores tipográficos o caligráficos al escanear los Pre-Test y Post-Test.
"""

from __future__ import annotations
import os
import json
import logging
import difflib
import re
import threading
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
    """Gestiona el catálogo de participantes y resuelve coincidencias difusas de forma thread-safe."""

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

        item = {
            "nombre": nom,
            "edad": limpiar_texto(edad),
            "municipio": limpiar_texto(municipio),
            "eapb": limpiar_texto(eapb),
            "documento": limpiar_texto(documento)
        }

        with self._lock:
            self.participantes[nom] = item

        if guardar_inmediato:
            self.guardar()

    def buscar_coincidencia(self, nombre_raw: str, municipio_hint: str = "") -> Optional[Dict[str, str]]:
        """
        Busca un participante coincidente mediante comparación difusa.
        Retorna el registro si la similitud supera el umbral (0.80, o 0.72 si coincide municipio).
        """
        nom_busqueda = limpiar_texto(nombre_raw)
        if not nom_busqueda or len(nom_busqueda) < 4:
            return None

        with self._lock:
            # 1. Coincidencia exacta directa
            if nom_busqueda in self.participantes:
                return dict(self.participantes[nom_busqueda])
            items_copia = list(self.participantes.items())

        # 2. Coincidencia difusa
        mejor_match = None
        mejor_score = 0.0
        mun_hint_limpio = limpiar_texto(municipio_hint)

        for clave_nom, data in items_copia:
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
            return dict(mejor_match)

        return None

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
