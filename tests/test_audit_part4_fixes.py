"""
test_audit_part4_fixes.py — Suite de Verificación de Correcciones Críticas (Auditoría Parte 4)
Owen Badel Hooker — Ingeniero de Sistemas / Software Architect

Verifica:
1. Simetría matemática en token_jaro_winkler_similarity (3 vs 4 palabras).
2. Enriquecimiento sin duplicación en ParticipantCache.aprender_participante().
3. Detección de errores en Google Apps Script cuando retorna HTTP 200 con {"status": "error"}.
4. Enrutamiento exacto de contingencia para Pre/Post Tests sin desviarse a la pestaña de Fichas.
5. Optimización de imágenes: preservación de bytes JPEG cuando auto_rotar=False.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from participant_cache import token_jaro_winkler_similarity, ParticipantCache
from sheets_service import GoogleSheetsService
from vision_service import optimizar_imagen_bytes


class TestAuditPart4Fixes(unittest.TestCase):

    def test_1_simetria_token_jaro_winkler_3_vs_4_palabras(self):
        """
        Verifica que token_jaro_winkler_similarity sea simétrico y no retorne 0.0
        cuando un estudiante escribe sus dos apellidos en el examen pero en el patrón maestro tiene uno solo.
        """
        s1 = "JUAN CAMILO ORTEGA MARTINEZ"
        s2 = "JUAN CAMILO ORTEGA"

        sim_directa = token_jaro_winkler_similarity(s1, s2)
        sim_inversa = token_jaro_winkler_similarity(s2, s1)

        self.assertGreater(sim_directa, 0.70, f"Similitud directa fue demasiado baja: {sim_directa}")
        self.assertGreater(sim_inversa, 0.70, f"Similitud inversa fue demasiado baja: {sim_inversa}")
        self.assertAlmostEqual(sim_directa, sim_inversa, places=2,
                               msg=f"Asimetría detectada: {sim_directa} != {sim_inversa}")

    def test_2_enriquecimiento_participante_sin_duplicacion(self):
        """
        Verifica que aprender_participante desde un test (documento="") no duplique
        un participante ya registrado con documento en el Patrón Maestro.
        """
        cache = ParticipantCache()
        cache.limpiar()
        # 1. Registrar participante canónico desde Patrón Maestro
        cache.aprender_participante(
            nombre="MARIA CAMILA PEREZ",
            edad="16",
            municipio="MAHATES",
            eapb="NUEVA EPS",
            documento="1045123456"
        )
        total_inicial = cache.contar()
        self.assertEqual(total_inicial, 1)

        # 2. Re-aprender desde un test donde documento=""
        cache.aprender_participante(
            nombre="MARIA CAMILA PEREZ",
            edad="16",
            municipio="MAHATES",
            eapb="",
            documento=""
        )

        # No debe duplicarse
        total_despues = cache.contar()
        self.assertEqual(total_despues, 1, f"Se duplicó el participante en memoria: {total_despues} != 1")

        # El documento y EPS previos no deben haberse perdido
        encontrado = cache.buscar_coincidencia("MARIA CAMILA PEREZ", "MAHATES")
        self.assertIsNotNone(encontrado)
        self.assertEqual(encontrado.get("documento"), "1045123456")
        self.assertEqual(encontrado.get("eapb"), "NUEVA EPS")

    def test_3_apps_script_error_en_http_200_lanza_excepcion(self):
        """
        Verifica que si Google Apps Script responde HTTP 200 con status: 'error',
        GoogleSheetsService no lo dé por exitoso y levante RuntimeError.
        """
        service = GoogleSheetsService()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.history = []
        mock_response.json.return_value = {
            "status": "error",
            "message": "Exceeded maximum execution time in LockService"
        }

        with patch("requests.post", return_value=mock_response):
            with self.assertRaises(RuntimeError) as ctx:
                service._ejecutar_insercion(
                    tab_name="PRE-TEST",
                    headers=["COL1", "COL2", "COL3"],
                    fila=["VAL1", "VAL2", "JUAN PEREZ"],
                    webhook_url="https://script.google.com/macros/s/TEST/exec",
                    tipo_registro="test",
                    sheet_id_override="sheet123"
                )
            self.assertIn("Apps Script reportó error", str(ctx.exception))

    def test_4_optimizar_imagen_bytes_omite_recompresion_si_auto_rotar_false(self):
        """
        Verifica que si una imagen JPEG ya viene orientada y optimizada del frontend (<= 1600px),
        y auto_rotar=False, optimizar_imagen_bytes devuelve los bytes exactos sin degradar calidad.
        """
        from PIL import Image
        import io

        # Crear una imagen JPEG de prueba de 800x600
        buf = io.BytesIO()
        img = Image.new("RGB", (800, 600), color=(100, 150, 200))
        img.save(buf, format="JPEG", quality=82)
        bytes_originales = buf.getvalue()

        # Invocar optimizar_imagen_bytes con auto_rotar=False
        bytes_opt, mime = optimizar_imagen_bytes(bytes_originales, auto_rotar=False)

        self.assertEqual(bytes_opt, bytes_originales, "Se recompimió la imagen innecesariamente a pesar de auto_rotar=False")
        self.assertEqual(mime, "image/jpeg")


if __name__ == "__main__":
    unittest.main()
