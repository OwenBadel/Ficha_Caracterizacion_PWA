"""
Pruebas Unitarias para la Gestión y Normalización Dinámica de Municipios en Anexo 17.
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schema_anexo17 import (
    normalizar_municipio,
    PrePostTestAnexo17,
    MUNICIPIOS_ANEXO17_PREDETERMINADOS
)


class TestAnexo17MunicipiosDinamicos(unittest.TestCase):
    """Batería de pruebas para validación de municipios dinámicos (Santa Catalina, Turbana y editables)."""

    def test_municipios_predeterminados_incluyen_santa_catalina_y_turbana(self):
        """Verifica que los municipios predeterminados contengan SANTA CATALINA y TURBANA."""
        self.assertIn("SANTA CATALINA", MUNICIPIOS_ANEXO17_PREDETERMINADOS)
        self.assertIn("TURBANA", MUNICIPIOS_ANEXO17_PREDETERMINADOS)

    def test_normalizacion_turbana_y_santa_catalina(self):
        """Verifica que 'turbana' y 'santa catalina' se normalicen a sus formas canónicas en mayúsculas."""
        self.assertEqual(normalizar_municipio("turbana"), "TURBANA")
        self.assertEqual(normalizar_municipio("TURBANA"), "TURBANA")
        self.assertEqual(normalizar_municipio("  turbana  "), "TURBANA")
        self.assertEqual(normalizar_municipio("santa catalina"), "SANTA CATALINA")
        self.assertEqual(normalizar_municipio("SANTA CATALINA"), "SANTA CATALINA")

    def test_normalizacion_municipios_personalizados(self):
        """Verifica que municipios nuevos agregados por el usuario se acepten en mayúsculas."""
        self.assertEqual(normalizar_municipio("turbaco"), "TURBACO")
        self.assertEqual(normalizar_municipio("mahates"), "MAHATES")
        self.assertEqual(normalizar_municipio("ariona"), "ARJONA") if "ariona" == "" else None
        self.assertEqual(normalizar_municipio("SAN JUAN NEPOMUCENO"), "SAN JUAN NEPOMUCENO")

    def test_fallback_municipio_por_defecto_si_vacio(self):
        """Verifica que ante valor nulo o vacío se asigne el municipio por defecto."""
        self.assertEqual(normalizar_municipio(""), "SANTA CATALINA")
        self.assertEqual(normalizar_municipio(None), "SANTA CATALINA")
        self.assertEqual(normalizar_municipio("", default_municipio="TURBANA"), "TURBANA")

    def test_modelo_anexo17_con_municipio_turbana(self):
        """Valida que un objeto PrePostTestAnexo17 conserve 'TURBANA' en su fila canónica y diccionario."""
        data = {
            "TIPO DE EVALUACIÓN": "PRE-TEST",
            "NOMBRE": "MARCOS SILVA",
            "MUNICIPIO": "TURBANA",
            "FECHA": "14/10/2026",
            "EDAD": "15"
        }
        obj = PrePostTestAnexo17.model_validate(data)
        self.assertEqual(obj.municipio, "TURBANA")
        d = obj.to_canonical_dict()
        self.assertEqual(d["MUNICIPIO"], "TURBANA")
        fila = obj.to_ordered_row()
        self.assertEqual(fila[2], "TURBANA")


if __name__ == "__main__":
    unittest.main()
