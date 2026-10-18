"""
test_audit_part2_fixes.py — Pruebas Unitarias para la Parte 2 de la Auditoría Profunda
Digitalizador de Fichas de Caracterización y Tests (PROJ-006)
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.
"""

import os
import sys
import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schema import FichaCaracterizacion, COLUMNAS_FICHA, normalizar_territorio, normalizar_eps
from schema_test import PrePostTest, COLUMNAS_TEST
from schema_anexo17 import PrePostTestAnexo17, COLUMNAS_ANEXO17, normalizar_municipio as normalizar_municipio_anexo17
from participant_cache import ParticipantCache, limpiar_texto
from vocabulary_learner import VocabularyLearner
from vision_service import deserializar_json_ficha


class TestAuditPart2Fixes(unittest.TestCase):

    def test_pre_post_test_schema_eapb_attribute(self):
        """Verifica que PrePostTest expone el atributo eapb (evitando AttributeError test_obj.eps)."""
        data = {
            "TIPO DE EVALUACIÓN": "PRE-TEST",
            "NOMBRE": "CARLOS MARIO GOMEZ",
            "EDAD": "16",
            "MUNICIPIO": "SANTA CATALINA",
            "EAPB (EPS)": "NUEVA EPS"
        }
        test_obj = PrePostTest.model_validate(data)
        self.assertTrue(hasattr(test_obj, "eapb"), "PrePostTest debe tener el atributo 'eapb'")
        self.assertEqual(test_obj.eapb, "NUEVA EPS")

    def test_participante_cache_sanitizacion_municipio_y_eps(self):
        """Verifica que aprender_participante normaliza automáticamente municipio y eps."""
        cache_tmp = Path(__file__).parent / "tmp_test_cache.json"
        try:
            p_cache = ParticipantCache(cache_file=cache_tmp)
            p_cache.aprender_participante(
                nombre="WILLIAM JAMES VILORIA",
                edad="17",
                municipio="SANTA CAROLINA", # Error común de OCR
                eapb="nueva eps",
                documento=""
            )
            res = p_cache.buscar_coincidencia("WILLIAM JAMES VILORIA")
            self.assertIsNotNone(res)
            # El municipio debe haberse normalizado a SANTA CATALINA
            self.assertEqual(res["municipio"], "SANTA CATALINA")
            # La EPS debe haberse normalizado a mayúsculas
            self.assertEqual(res["eapb"], "NUEVA EPS")
        finally:
            if cache_tmp.exists():
                cache_tmp.unlink()

    def test_vocabulary_anti_contaminacion_frecuencia_minima(self):
        """Verifica que una palabra aislada leída una sola vez con error (peso 1) no bloquea la corrección difusa."""
        vocab = VocabularyLearner()
        col = "¿Qué actividades recreativas haces en tu tiempo libre?"

        # Insertar una palabra con error con peso 1 en memoria
        vocab.vocabulario[col] = {"FUTB0L": 1, "FUTBOL": 50}

        # Cuando entra "FUTB0L", dado que su peso es 1 (< 3) y no está en la semilla,
        # corregir_valor debe aplicar fuzzy matching y corregirla a "FUTBOL" (semilla canónica)
        corregido = vocab.corregir_valor(col, "FUTB0L")
        self.assertEqual(corregido, "FUTBOL", "FUTB0L debe corregirse a FUTBOL a pesar de existir con peso 1 en el vocabulario")

    def test_deserializar_json_ficha_claves_indexadas(self):
        """Verifica la deserialización eficiente de claves indexadas c1..c43 devueltas por Gemini."""
        mock_gemini_resp = {
            "c1": "15/05/2026",
            "c2": "JUAN PEREZ",
            "c3": "CARLOS ANDRES GOMEZ", # c3 es Nombre completo del participante
            "c4": "TI",
            "c5": "1045234123",
            "c6": "16",
            "c7": "HOMBRE",
            "c8": "HETEROSEXUAL",
            "c9": "SANTA CATALINA",
            "c10": "SANTA CATALINA"
        }
        res = deserializar_json_ficha(mock_gemini_resp)
        self.assertIn("Nombre completo del participante", res)
        self.assertEqual(res["Nombre completo del participante"], "CARLOS ANDRES GOMEZ")
        self.assertEqual(res["Edad"], "16")
        self.assertEqual(res["Municipio"], "SANTA CATALINA")

    def test_ficha_to_ordered_row_y_canonical_dict_optimizados(self):
        """Verifica que to_ordered_row y to_canonical_dict entreguen los 43 campos sin fallo."""
        raw_data = {
            "Nombre completo del participante": "PEDRO PEREZ",
            "Edad": "15",
            "Tipo de documento identidad": "CC", # Menor de 18 -> debe ser TI por regla de coherencia
            "TERRITORIO": "MAHATES",
            "¿Has asistido al médico en el último año?": "NO",
            "¿Cuándo fue la última vez?": "HACE 2 MESES", # Si asistió es NO -> debe limpiarse a "" por coherencia
            "¿Consumes o has consumido cigarrillo o vapeador?": "NO",
            "Cada cuánto?": "TODOS LOS DIAS" # Si cigarrillo es NO -> debe limpiarse a ""
        }
        ficha = FichaCaracterizacion.model_validate(raw_data)
        fila = ficha.to_ordered_row()
        self.assertEqual(len(fila), 43)
        # Menor de 18 años normalizado a TI
        self.assertEqual(fila[3], "TI")
        # Asistió al médico NO -> última vez "" (Columna 22, índice 21)
        self.assertEqual(fila[21], "")
        # Cigarrillo NO -> frecuencia "" (Columna 27, índice 26)
        self.assertEqual(fila[26], "")

        canon = ficha.to_canonical_dict()
        self.assertEqual(len(canon), 43)
        self.assertEqual(canon["Tipo de documento identidad"], "TI")
        self.assertEqual(canon["Cada cuánto?"], "")

    def test_frontend_assets_offline_y_service_worker(self):
        """Verifica la existencia del icono SVG local y configuración de timeout en sw.js."""
        icon_path = FRONTEND_DIR / "img" / "icon.svg"
        self.assertTrue(icon_path.exists(), "frontend/img/icon.svg debe existir localmente")

        sw_path = FRONTEND_DIR / "sw.js"
        self.assertTrue(sw_path.exists(), "frontend/sw.js debe existir")
        sw_content = sw_path.read_text(encoding="utf-8")
        self.assertIn("/static/img/icon.svg", sw_content, "sw.js debe precachear /static/img/icon.svg")
        self.assertIn("1500", sw_content, "sw.js debe implementar timeout de 1500ms para evitar pantallas blancas")

        index_path = FRONTEND_DIR / "index.html"
        index_content = index_path.read_text(encoding="utf-8")
        self.assertNotIn("cdn.jsdelivr.net", index_content, "index.html no debe depender de cdn.jsdelivr.net para el icono")
        self.assertIn("/static/img/icon.svg", index_content, "index.html debe usar el icono local")


if __name__ == "__main__":
    unittest.main()
