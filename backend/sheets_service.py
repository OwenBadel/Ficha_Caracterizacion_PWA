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
import time
from datetime import datetime
from dotenv import load_dotenv

try:
    from .schema import COLUMNAS_FICHA
    from .schema_test import COLUMNAS_TEST, ENCABEZADOS_TEST_SHEETS
except (ImportError, ValueError):
    from schema import COLUMNAS_FICHA
    from schema_test import COLUMNAS_TEST, ENCABEZADOS_TEST_SHEETS

load_dotenv()
logger = logging.getLogger("sheets_service")


class GoogleSheetsService:
    """Gestiona la inserción atómica de encuestas y tests en Google Sheets."""

    def __init__(self):
        self.sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        self.sheet_tab = os.getenv("GOOGLE_SHEET_TAB", "Respuestas").strip()
        self.webhook_url = os.getenv("GOOGLE_APPS_SCRIPT_URL", "").strip()
        self.sheet_tab_tests = os.getenv("GOOGLE_SHEET_TAB_TESTS", "Respuestas de formulario 1").strip()
        self.webhook_url_tests = os.getenv("GOOGLE_APPS_SCRIPT_URL_TESTS", "").strip() or self.webhook_url
        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        self.credentials_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        # Si la primera columna es 'Marca temporal', dejar vacía la primera celda
        self.skip_first_col = os.getenv("GOOGLE_SHEET_SKIP_FIRST_COL", "true").lower() in ("true", "1", "yes")

        self._gspread_client = None
        self._tabs_inicializados = set()
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

    def _ejecutar_insercion(
        self,
        tab_name: str,
        headers: List[str],
        fila: List[str],
        webhook_url: Optional[str],
        tipo_registro: str = "ficha"
    ) -> Dict[str, Any]:
        """
        Ejecuta la inserción atómica en Google Sheets, intentando primero la API oficial (gspread)
        con caché de encabezados en memoria, y fallback automático al Webhook de Google Apps Script.
        """
        errores = []

        # 1. Intentar con API Oficial (gspread) si está configurado
        if self._gspread_client and self.sheet_id:
            try:
                sheet = self._gspread_client.open_by_key(self.sheet_id)
                try:
                    worksheet = sheet.worksheet(tab_name)
                except Exception:
                    # Crear la pestaña si no existe
                    worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
                    worksheet.append_row(headers, value_input_option="USER_ENTERED")
                    self._tabs_inicializados.add(tab_name)

                # Verificar encabezados una única vez por pestaña durante el ciclo de vida del servicio
                if tab_name not in self._tabs_inicializados:
                    primera_fila = worksheet.row_values(1)
                    if not primera_fila:
                        worksheet.append_row(headers, value_input_option="USER_ENTERED")
                    self._tabs_inicializados.add(tab_name)

                # Insertar los datos
                res = worksheet.append_row(fila, value_input_option="USER_ENTERED")
                return {
                    "success": True,
                    "method": "google_sheets_api",
                    "sheet_id": self.sheet_id,
                    "tab": tab_name,
                    "updated_cells": getattr(res, "get", lambda k, d: d)("updates", {}).get("updatedCells", len(fila))
                }
            except Exception as e:
                err_msg = f"Error en Google Sheets API ({tipo_registro}): {e}"
                logger.error(err_msg)
                errores.append(err_msg)

        # 2. Intentar con Webhook de Google Apps Script como alternativa con reintentos
        if webhook_url:
            payload = {
                "tipo": tipo_registro,
                "tab": tab_name,
                "sheet_name": tab_name,
                "hoja": tab_name,
                "headers": headers,
                "row": fila,
                "data": dict(zip(headers, fila))
            }
            max_intentos = 3
            timeout_segundos = 65
            for intento in range(1, max_intentos + 1):
                try:
                    logger.info(f"Enviando webhook Google Apps Script ({tipo_registro}, intento {intento}/{max_intentos})...")
                    resp = requests.post(webhook_url, json=payload, timeout=timeout_segundos)
                    hubo_redirect_exitoso = any(h.status_code in [301, 302, 307, 308] for h in resp.history)

                    if resp.status_code in [200, 201, 302] or hubo_redirect_exitoso:
                        return {
                            "success": True,
                            "method": "apps_script_webhook",
                            "tab": tab_name,
                            "status_code": resp.status_code,
                            "redirected": hubo_redirect_exitoso,
                            "intento": intento
                        }
                    else:
                        errores.append(f"Webhook ({tipo_registro}, intento {intento}) respondió con código HTTP {resp.status_code}: {resp.text[:150]}")
                except requests.exceptions.Timeout as e:
                    err_msg = f"Timeout ({timeout_segundos}s) en Webhook Google Apps Script ({tipo_registro}, intento {intento}/{max_intentos}): {e}"
                    logger.warning(err_msg)
                    if intento == max_intentos:
                        errores.append(err_msg)
                    else:
                        time.sleep(2.0)
                except Exception as e:
                    err_msg = f"Error en Webhook Google Apps Script ({tipo_registro}, intento {intento}/{max_intentos}): {e}"
                    logger.error(err_msg)
                    if intento == max_intentos:
                        errores.append(err_msg)
                    else:
                        time.sleep(1.5)

        if not self._gspread_client and not webhook_url:
            raise ValueError(
                f"No hay método de integración configurado para Google Sheets ({tipo_registro}). "
                "Configura GOOGLE_SHEET_ID y credentials.json O BIEN define GOOGLE_APPS_SCRIPT_URL en .env"
            )

        raise RuntimeError(f"Falló la inserción ({tipo_registro}) en Google Sheets: " + " | ".join(errores))

    def insertar_encuesta(self, valores_ordenados: List[str]) -> Dict[str, Any]:
        """
        Inserta una fila con los valores ordenados de la encuesta.
        Pestaña por defecto: 'Respuestas de formulario 1' o la configurada en GOOGLE_SHEET_TAB.
        """
        valores_upper = [str(v or "").strip().upper() for v in valores_ordenados]
        fila_final = ([""] + valores_upper) if self.skip_first_col else valores_upper
        headers_final = (["Marca temporal"] + COLUMNAS_FICHA) if self.skip_first_col else COLUMNAS_FICHA
        tab_destino = self.sheet_tab if self.sheet_tab and self.sheet_tab != "Respuestas" else "Respuestas de formulario 1"

        return self._ejecutar_insercion(
            tab_name=tab_destino,
            headers=headers_final,
            fila=fila_final,
            webhook_url=self.webhook_url,
            tipo_registro="ficha"
        )

    def insertar_test(
        self,
        valores_ordenados: List[str],
        tipo_evaluacion: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Inserta una fila con los 14 valores ordenados de Pre/Post Test (+ Marca temporal).
        Enruta automáticamente a la pestaña 'PRE-TEST' o 'POST-TEST' según la selección en interfaz
        o la lectura forense de la IA.
        """
        valores_upper = [str(v or "").strip().upper() for v in valores_ordenados]
        timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        fila_final = [timestamp_str] + valores_upper

        # Determinar pestaña exacta: PRE-TEST o POST-TEST
        tipo_candidato = (tipo_evaluacion or (valores_upper[0] if valores_upper else "")).strip().upper()
        if "POST" in tipo_candidato:
            tab_destino = "POST-TEST"
            tipo_reg = "post_test"
        else:
            tab_destino = "PRE-TEST"
            tipo_reg = "pre_test"

        url_destino = self.webhook_url_tests or self.webhook_url
        logger.info(f"Enrutando test hacia Google Sheets -> Pestaña: '{tab_destino}' (Tipo: {tipo_reg})")

        return self._ejecutar_insercion(
            tab_name=tab_destino,
            headers=ENCABEZADOS_TEST_SHEETS,
            fila=fila_final,
            webhook_url=url_destino,
            tipo_registro=tipo_reg
        )

