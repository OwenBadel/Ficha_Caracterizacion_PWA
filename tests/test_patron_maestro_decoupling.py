import unittest
from pathlib import Path
from fastapi.testclient import TestClient
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app
from backend.participant_cache import participant_cache


class TestPatronMaestroDecoupling(unittest.TestCase):
    """
    Verifica el desacoplamiento total de Google Sheets en el Patrón Maestro:
    1. index.html ya no tiene sincronización por Sheets para Patrón Maestro.
    2. app.js maneja la visibilidad contextual exclusiva para Anexo 4 y Anexo 17.
    3. El endpoint /api/participants/sync-sheet está formalmente deshabilitado.
    4. El Patrón Maestro se gestiona exclusivamente por archivo Excel (.xlsx / .csv).
    """

    def setUp(self):
        self.client = TestClient(app)

    def test_frontend_index_html_no_contiene_sync_sheet_patron_maestro(self):
        html_path = PROJECT_ROOT / "frontend" / "index.html"
        self.assertTrue(html_path.exists())
        content = html_path.read_text(encoding="utf-8")

        # No debe existir inputMasterSheetId ni btnSyncMasterSheet
        self.assertNotIn("id=\"inputMasterSheetId\"", content)
        self.assertNotIn("id=\"btnSyncMasterSheet\"", content)

        # Debe contener la carga por archivo Excel/CSV
        self.assertIn("id=\"inputMasterExcel\"", content)
        self.assertIn("id=\"btnUploadMasterExcel\"", content)

        # El botón de Base Maestra debe iniciar con display: none por defecto (modo ficha)
        self.assertIn("id=\"btnOpenMasterModal\"", content)
        self.assertIn("style=\"display: none;\"", content)

    def test_frontend_app_js_contextual_visibility(self):
        js_path = PROJECT_ROOT / "frontend" / "js" / "app.js"
        self.assertTrue(js_path.exists())
        content = js_path.read_text(encoding="utf-8")

        # No debe hacer addEventListener sobre btnSyncMasterSheet
        self.assertNotIn("btnSyncMasterSheet.addEventListener", content)

        # Debe mostrar btnOpenMasterModal en anexo4 y anexo17, y ocultarlo en ficha
        self.assertIn("nuevoModo === 'ficha'", content)
        self.assertIn("btnOpenMasterModal.style.display = 'none'", content)
        self.assertIn("btnOpenMasterModal.style.display = 'inline-flex'", content)

    def test_endpoint_sync_sheet_deshabilitado(self):
        resp = self.client.post("/api/participants/sync-sheet", data={"sheet_id": "test_id"})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertIn("deshabilitada", data.get("detail", ""))

    def test_ingesta_patron_maestro_via_csv_texto_local(self):
        csv_data = "NOMBRE,EDAD,MUNICIPIO,EPS\nJUAN CAMILO ORTEGA,17,MAHATES,NUEVA EPS\n"
        total = participant_cache.sincronizar_desde_csv_texto(csv_data)
        self.assertGreaterEqual(total, 1)

        coincidencia = participant_cache.buscar_coincidencia("JUAN C ORTEGA", "MAHATES")
        self.assertIsNotNone(coincidencia)
        self.assertEqual(coincidencia["nombre"], "JUAN CAMILO ORTEGA")


if __name__ == "__main__":
    unittest.main()
