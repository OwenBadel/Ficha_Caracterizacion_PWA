"""
Servicio de Integración con Google Sheets.
Soporta dos métodos de inserción de filas:
1. API Oficial de Google Sheets (Service Account / credentials.json o variable de entorno) mediante gspread.
2. Webhook de Google Apps Script (POST simple) como alternativa sin archivos de credenciales.
"""

from __future__ import annotations
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv

try:
    from .schema import COLUMNAS_FICHA
except (ImportError, ValueError):
    from schema import COLUMNAS_FICHA

load_dotenv()
logger = logging.getLogger("sheets_service")


class GoogleSheetsService:
    """Gestiona la inserción atómica de encuestas en la hoja de cálculo de Google."""

    def __init__(self):
        self.sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        self.sheet_tab = os.getenv("GOOGLE_SHEET_TAB", "Respuestas").strip()
        self.webhook_url = os.getenv("GOOGLE_APPS_SCRIPT_URL", "").strip()
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        self.credentials_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        # Si la primera columna es 'Marca temporal', dejar vacía la primera celda
        self.skip_first_col = os.getenv("GOOGLE_SHEET_SKIP_FIRST_COL", "true").lower() in ("true", "1", "yes")

        self._gspread_client = None
        self._init_gspread()

    def _init_gspread(self):
        """Inicializa el cliente de gspread si existen credenciales válidas."""
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]

            if self.credentials_json_env:
                creds_dict = json.loads(self.credentials_json_env)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                self._gspread_client = gspread.authorize(creds)
                logger.info("Google Sheets autorizado mediante GOOGLE_CREDENTIALS_JSON (env)")
                return

            # Buscar archivo credentials.json si no está en env
            possible_paths = [
                Path(self.credentials_path) if self.credentials_path else None,
                Path(__file__).resolve().parent.parent / "credentials.json",
                Path(__file__).resolve().parent / "credentials.json",
            ]

            for p in possible_paths:
                if p and p.exists() and p.is_file():
                    creds = Credentials.from_service_account_file(str(p), scopes=scopes)
                    self._gspread_client = gspread.authorize(creds)
                    logger.info(f"Google Sheets autorizado mediante archivo: {p}")
                    return

        except Exception as e:
            logger.warning(f"No se pudo inicializar gspread: {e}. Se utilizará Webhook si está configurado.")

    def insertar_encuesta(self, valores_ordenados: List[str]) -> Dict[str, Any]:
        """
        Inserta una fila con los valores ordenados de la encuesta.
        Retorna dict con status y detalles.
        """
        errores = []

        # Forzar que absolutamente todos los valores estén en MAYÚSCULAS
        valores_upper = [str(v or "").strip().upper() for v in valores_ordenados]
        fila_final = ([""] + valores_upper) if self.skip_first_col else valores_upper
        headers_final = (["Marca temporal"] + COLUMNAS_FICHA) if self.skip_first_col else COLUMNAS_FICHA

        # 1. Intentar con API Oficial (gspread) si está configurado
        if self._gspread_client and self.sheet_id:
            try:
                sheet = self._gspread_client.open_by_key(self.sheet_id)
                try:
                    worksheet = sheet.worksheet(self.sheet_tab)
                except Exception:
                    # Crear la pestaña si no existe
                    worksheet = sheet.add_worksheet(title=self.sheet_tab, rows=1000, cols=len(headers_final))
                    worksheet.append_row(headers_final, value_input_option="USER_ENTERED")

                # Verificar si tiene encabezados
                primera_fila = worksheet.row_values(1)
                if not primera_fila:
                    worksheet.append_row(headers_final, value_input_option="USER_ENTERED")

                # Insertar los datos
                res = worksheet.append_row(fila_final, value_input_option="USER_ENTERED")
                return {
                    "success": True,
                    "method": "google_sheets_api",
                    "sheet_id": self.sheet_id,
                    "tab": self.sheet_tab,
                    "updated_cells": getattr(res, "get", lambda k, d: d)("updates", {}).get("updatedCells", len(fila_final))
                }
            except Exception as e:
                err_msg = f"Error en Google Sheets API: {e}"
                logger.error(err_msg)
                errores.append(err_msg)

        # 2. Intentar con Webhook de Google Apps Script si está disponible
        if self.webhook_url:
            try:
                payload = {
                    "headers": headers_final,
                    "row": fila_final,
                    "data": dict(zip(headers_final, fila_final))
                }
                resp = requests.post(self.webhook_url, json=payload, timeout=45)
                if resp.status_code in [200, 201, 302]:
                    return {
                        "success": True,
                        "method": "apps_script_webhook",
                        "status_code": resp.status_code
                    }
                else:
                    errores.append(f"Webhook respondió con código HTTP {resp.status_code}: {resp.text[:150]}")
            except Exception as e:
                err_msg = f"Error en Webhook Google Apps Script: {e}"
                logger.error(err_msg)
                errores.append(err_msg)

        if not self._gspread_client and not self.webhook_url:
            raise ValueError(
                "No hay método de integración configurado para Google Sheets. "
                "Configura GOOGLE_SHEET_ID y credentials.json O BIEN define GOOGLE_APPS_SCRIPT_URL en .env"
            )

        raise RuntimeError("Falló la inserción en Google Sheets: " + " | ".join(errores))
