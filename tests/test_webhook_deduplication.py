"""
Pruebas de Deduplicación Transversal en sheets_service.py:
Verifica que la deduplicación por Documento y por Nombre funcione antes de llamar al Webhook
o cuando se usa exclusivamente Webhook sin credenciales de gspread.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sheets_service import GoogleSheetsService


class TestWebhookDeduplication(unittest.TestCase):

    def setUp(self):
        self.service = GoogleSheetsService()
        # Forzar sin cliente gspread para simular uso exclusivo de Webhook
        self.service._gspread_client = None
        self.service.skip_first_col = True
        self.service.sheet_id = "test_sheet_id_123"
        self.service.webhook_url = "https://script.google.com/macros/s/test/exec"

    def test_deduplicacion_documento_en_memoria_antes_de_webhook(self):
        """Verifica que si un documento ya fue procesado en la sesión, no reenvía al webhook."""
        fila_ficha = ["", "JUAN PEREZ", "BOLIVAR", "CARLOS ANDRES MENDOZA", "CC", "1045678901", "11"]

        # 1. Simular primera inserción exitosa vía webhook
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.history = []
            mock_resp.json.return_value = {"deduplicated": False}
            mock_post.return_value = mock_resp

            res1 = self.service._ejecutar_insercion(
                tab_name="Respuestas",
                headers=["H1", "H2", "H3", "H4", "H5", "H6", "H7"],
                fila=fila_ficha,
                webhook_url=self.service.webhook_url,
                tipo_registro="ficha"
            )

            self.assertTrue(res1["success"])
            self.assertFalse(res1["deduplicated"])
            self.assertEqual(mock_post.call_count, 1)

        # 2. Segunda inserción con el MISMO documento (reintento o colisión)
        # Debe detectarse antes del webhook sin llamar a requests.post
        with patch("requests.post") as mock_post_2:
            res2 = self.service._ejecutar_insercion(
                tab_name="Respuestas",
                headers=["H1", "H2", "H3", "H4", "H5", "H6", "H7"],
                fila=fila_ficha,
                webhook_url=self.service.webhook_url,
                tipo_registro="ficha"
            )

            self.assertTrue(res2["success"])
            self.assertTrue(res2["deduplicated"])
            self.assertEqual(res2["method"], "session_cache")
            self.assertIn("1045678901", res2["message"])
            self.assertEqual(mock_post_2.call_count, 0)

    def test_deduplicacion_test_en_memoria_antes_de_webhook(self):
        """Verifica que un test con el mismo nombre se deduplica antes del webhook en la misma pestaña."""
        fila_test = ["01/01/2026", "PRE-TEST", "MARIA JOSE DELGADO", "CARTAGENA"]

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.history = []
            mock_resp.json.return_value = {"deduplicated": False}
            mock_post.return_value = mock_resp

            res1 = self.service._ejecutar_insercion(
                tab_name="PRE-TEST",
                headers=["H1", "H2", "H3", "H4"],
                fila=fila_test,
                webhook_url=self.service.webhook_url,
                tipo_registro="test"
            )
            self.assertTrue(res1["success"])
            self.assertFalse(res1["deduplicated"])

        with patch("requests.post") as mock_post_2:
            res2 = self.service._ejecutar_insercion(
                tab_name="PRE-TEST",
                headers=["H1", "H2", "H3", "H4"],
                fila=fila_test,
                webhook_url=self.service.webhook_url,
                tipo_registro="test"
            )
            self.assertTrue(res2["success"])
            self.assertTrue(res2["deduplicated"])
            self.assertEqual(mock_post_2.call_count, 0)


if __name__ == "__main__":
    unittest.main()
