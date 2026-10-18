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
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

try:
    from .schema import COLUMNAS_FICHA, ENCABEZADOS_FICHA_SHEETS
    from .schema_test import ENCABEZADOS_TEST_SHEETS
    from .schema_anexo17 import ENCABEZADOS_ANEXO17_SHEETS
except (ImportError, ValueError):
    from schema import COLUMNAS_FICHA, ENCABEZADOS_FICHA_SHEETS
    from schema_test import ENCABEZADOS_TEST_SHEETS
    from schema_anexo17 import ENCABEZADOS_ANEXO17_SHEETS

load_dotenv()
logger = logging.getLogger("sheets_service")


class GoogleSheetsService:
    """Gestiona la inserción atómica y deduplicación de encuestas y tests en Google Sheets."""

    def __init__(self):
        self.sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        self.sheet_tab = os.getenv("GOOGLE_SHEET_TAB", "Respuestas").strip()
        self.webhook_url = os.getenv("GOOGLE_APPS_SCRIPT_URL", "").strip()
        self.sheet_tab_tests = os.getenv("GOOGLE_SHEET_TAB_TESTS", "Respuestas de formulario 1").strip()
        self.webhook_url_tests = os.getenv("GOOGLE_APPS_SCRIPT_URL_TESTS", "").strip() or self.webhook_url
        self.sheet_tab_pre_test = os.getenv("GOOGLE_SHEET_TAB_PRE_TEST", "PRE-TEST").strip()
        self.sheet_tab_post_test = os.getenv("GOOGLE_SHEET_TAB_POST_TEST", "POST-TEST").strip()

        # Configuración específica para Anexo 17 (Pellízcate con Generación B+)
        self.sheet_id_anexo17 = os.getenv("GOOGLE_SHEET_ID_ANEXO17", "").strip() or self.sheet_id
        self.webhook_url_anexo17 = os.getenv("GOOGLE_APPS_SCRIPT_URL_ANEXO17", "").strip() or self.webhook_url_tests or self.webhook_url
        self.sheet_tab_anexo17_pre = os.getenv("GOOGLE_SHEET_TAB_ANEXO17_PRE", "PRE-TEST").strip()
        self.sheet_tab_anexo17_post = os.getenv("GOOGLE_SHEET_TAB_ANEXO17_POST", "POST-TEST").strip()

        self.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        self.credentials_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
        # Si la primera columna es 'Marca temporal', dejar vacía la primera celda
        self.skip_first_col = os.getenv("GOOGLE_SHEET_SKIP_FIRST_COL", "true").lower() in ("true", "1", "yes")

        self._gspread_client = None
        self._tabs_inicializados = set()
        self._lock = threading.Lock()
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
        tipo_registro: str = "ficha",
        sheet_id_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta la inserción atómica en Google Sheets, intentando primero la API oficial (gspread)
        con caché de encabezados en memoria, y fallback automático al Webhook de Google Apps Script.
        """
        errores = []
        target_sheet_id = sheet_id_override or self.sheet_id

        # Serialización atómica para evitar colisiones concurrentes entre dispositivos
        with self._lock:
            # 1. Intentar con API Oficial (gspread) si está configurado
            if self._gspread_client and target_sheet_id:
                try:
                    sheet = self._gspread_client.open_by_key(target_sheet_id)
                    cache_key = f"{target_sheet_id}:{tab_name}"
                    try:
                        worksheet = sheet.worksheet(tab_name)
                    except Exception:
                        # Crear la pestaña si no existe
                        worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
                        worksheet.append_row(headers, value_input_option="USER_ENTERED")
                        self._tabs_inicializados.add(cache_key)

                    # Verificar encabezados una única vez por pestaña durante el ciclo de vida del servicio
                    if cache_key not in self._tabs_inicializados:
                        primera_fila = worksheet.row_values(1)
                        if not primera_fila:
                            worksheet.append_row(headers, value_input_option="USER_ENTERED")
                        self._tabs_inicializados.add(cache_key)

                    # DEDUPLICACIÓN ATÓMICA EN GSPREAD:
                    if tipo_registro.lower() == "ficha":
                        col_nombre_idx = 4 if self.skip_first_col else 3
                        col_doc_idx = 6 if self.skip_first_col else 5
                        nombre_candidato = str(fila[col_nombre_idx - 1] if len(fila) >= col_nombre_idx else "").strip().upper()
                        doc_candidato = str(fila[col_doc_idx - 1] if len(fila) >= col_doc_idx else "").strip().upper()

                        # Deduplicar por documento de identidad si es válido
                        if doc_candidato and doc_candidato not in ("SIN DOCUMENTO", "NONE", "NULL", "0", ""):
                            try:
                                col_docs = [str(x or "").strip().upper() for x in worksheet.col_values(col_doc_idx)[1:]]
                                if doc_candidato in col_docs:
                                    logger.info(f"Deduplicación gspread activa (ficha): Documento '{doc_candidato}' ya existe en {tab_name}.")
                                    return {
                                        "success": True,
                                        "method": "google_sheets_api",
                                        "sheet_id": target_sheet_id,
                                        "tab": tab_name,
                                        "deduplicated": True,
                                        "message": f"Ficha con documento '{doc_candidato}' ({nombre_candidato}) ya existe en {tab_name}. Deduplicado exitosamente.",
                                        "updated_cells": 0
                                    }
                            except Exception as e_dedup:
                                logger.warning(f"No se pudo consultar duplicados por documento en gspread: {e_dedup}")

                        # Deduplicar por nombre completo si es válido
                        if nombre_candidato and nombre_candidato not in ("SIN NOMBRE", "NONE", "NULL", ""):
                            try:
                                col_nombres = [str(x or "").strip().upper() for x in worksheet.col_values(col_nombre_idx)[1:]]
                                if nombre_candidato in col_nombres:
                                    logger.info(f"Deduplicación gspread activa (ficha): Nombre '{nombre_candidato}' ya existe en {tab_name}.")
                                    return {
                                        "success": True,
                                        "method": "google_sheets_api",
                                        "sheet_id": target_sheet_id,
                                        "tab": tab_name,
                                        "deduplicated": True,
                                        "message": f"Ficha para '{nombre_candidato}' ya existe en {tab_name}. Deduplicado exitosamente.",
                                        "updated_cells": 0
                                    }
                            except Exception as e_dedup:
                                logger.warning(f"No se pudo consultar duplicados por nombre en gspread: {e_dedup}")

                    elif "anexo17" in tipo_registro.lower() or "test" in tipo_registro.lower():
                        nombre_candidato = str(fila[2] if len(fila) > 2 else "").strip().upper()
                        if nombre_candidato and nombre_candidato != "SIN NOMBRE":
                            try:
                                col_nombres = [str(x or "").strip().upper() for x in worksheet.col_values(3)[1:]]
                                if nombre_candidato in col_nombres:
                                    logger.info(f"Deduplicación gspread activa ({tipo_registro}): '{nombre_candidato}' ya existe en {tab_name}.")
                                    return {
                                        "success": True,
                                        "method": "google_sheets_api",
                                        "sheet_id": target_sheet_id,
                                        "tab": tab_name,
                                        "deduplicated": True,
                                        "message": f"Registro ya existente para '{nombre_candidato}' en {tab_name}. Deduplicado exitosamente.",
                                        "updated_cells": 0
                                    }
                            except Exception as e_dedup:
                                logger.warning(f"No se pudo consultar duplicados en gspread: {e_dedup}")

                    # Insertar los datos si no existe duplicado
                    res = worksheet.append_row(fila, value_input_option="USER_ENTERED")
                    return {
                        "success": True,
                        "method": "google_sheets_api",
                        "sheet_id": target_sheet_id,
                        "tab": tab_name,
                        "deduplicated": False,
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
                max_intentos = 2
                timeout_segundos = 20
                for intento in range(1, max_intentos + 1):
                    try:
                        logger.info(f"Enviando webhook Google Apps Script ({tipo_registro}, intento {intento}/{max_intentos})...")
                        resp = requests.post(webhook_url, json=payload, timeout=timeout_segundos)
                        hubo_redirect_exitoso = any(h.status_code in [301, 302, 307, 308] for h in resp.history)

                        if resp.status_code in [200, 201, 302] or hubo_redirect_exitoso:
                            dedup = False
                            msg = "Registro insertado exitosamente en Google Sheets."
                            try:
                                res_json = resp.json()
                                dedup = bool(res_json.get("deduplicated", False))
                                if dedup:
                                    msg = res_json.get("message", "Registro ya existente en Google Sheets. Deduplicado exitosamente.")
                            except Exception:
                                pass

                            return {
                                "success": True,
                                "method": "apps_script_webhook",
                                "tab": tab_name,
                                "status_code": resp.status_code,
                                "redirected": hubo_redirect_exitoso,
                                "intento": intento,
                                "deduplicated": dedup,
                                "message": msg
                            }
                        else:
                            errores.append(f"Webhook ({tipo_registro}, intento {intento}) respondió con código HTTP {resp.status_code}: {resp.text[:150]}")
                    except requests.exceptions.Timeout as e:
                        err_msg = f"Timeout ({timeout_segundos}s) en Webhook Google Apps Script ({tipo_registro}, intento {intento}/{max_intentos}): {e}"
                        logger.warning(err_msg)
                        if intento == max_intentos:
                            errores.append(err_msg)
                        else:
                            time.sleep(2.0 * intento)
                    except Exception as e:
                        err_msg = f"Error en Webhook Google Apps Script ({tipo_registro}, intento {intento}/{max_intentos}): {e}"
                        logger.error(err_msg)
                        if intento == max_intentos:
                            errores.append(err_msg)
                        else:
                            time.sleep(1.5 * intento)

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
        headers_final = ENCABEZADOS_FICHA_SHEETS if self.skip_first_col else COLUMNAS_FICHA
        tab_destino = self.sheet_tab or "Respuestas de formulario 1"

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
        Inserta una fila con los 14 valores ordenados de Pre/Post Test Anexo 4 (+ Marca temporal).
        Enruta automáticamente a la pestaña 'PRE-TEST' o 'POST-TEST' según la selección en interfaz
        o la lectura forense de la IA.
        """
        valores_upper = [str(v or "").strip().upper() for v in valores_ordenados]
        timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        fila_final = [timestamp_str] + valores_upper

        # Determinar pestaña exacta: PRE-TEST o POST-TEST
        tipo_candidato = (tipo_evaluacion or (valores_upper[0] if valores_upper else "")).strip().upper()
        if "POST" in tipo_candidato:
            tab_destino = self.sheet_tab_post_test or "POST-TEST"
            tipo_reg = "post_test"
        else:
            tab_destino = self.sheet_tab_pre_test or "PRE-TEST"
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

    def insertar_anexo17(
        self,
        valores_ordenados: List[str],
        tipo_evaluacion: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Inserta una fila con los 15 valores ordenados de Pre/Post Test Anexo 17 (+ Marca temporal).
        Enruta automáticamente a la pestaña 'PRE-TEST' o 'POST-TEST' según la selección en interfaz
        o la lectura forense de la IA.
        """
        valores_upper = [str(v or "").strip().upper() for v in valores_ordenados]
        timestamp_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        fila_final = [timestamp_str] + valores_upper

        tipo_candidato = (tipo_evaluacion or (valores_upper[0] if valores_upper else "")).strip().upper()
        if "POST" in tipo_candidato or "POS" in tipo_candidato:
            tab_destino = self.sheet_tab_anexo17_post or "POST-TEST"
            tipo_reg = "anexo17_post_test"
        else:
            tab_destino = self.sheet_tab_anexo17_pre or "PRE-TEST"
            tipo_reg = "anexo17_pre_test"

        url_destino = self.webhook_url_anexo17 or self.webhook_url_tests or self.webhook_url
        target_sheet_id = self.sheet_id_anexo17 or self.sheet_id
        logger.info(f"Enrutando Anexo 17 hacia Google Sheets -> Pestaña: '{tab_destino}' (Tipo: {tipo_reg})")

        return self._ejecutar_insercion(
            tab_name=tab_destino,
            headers=ENCABEZADOS_ANEXO17_SHEETS,
            fila=fila_final,
            webhook_url=url_destino,
            tipo_registro=tipo_reg,
            sheet_id_override=target_sheet_id
        )

