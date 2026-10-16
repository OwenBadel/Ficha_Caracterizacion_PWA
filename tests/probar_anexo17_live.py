"""
Script de Prueba de Inserción en Vivo para Anexo 17 (Pellízcate con Generación B+).
Inserta un registro de prueba en la pestaña 'PRE-TEST' y uno en 'POST-TEST'.
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.
"""

import sys
import json
from pathlib import Path

# Configurar path a backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schema_anexo17 import PrePostTestAnexo17, COLUMNAS_ANEXO17, ENCABEZADOS_ANEXO17_SHEETS
from sheets_service import GoogleSheetsService


def ejecutar_prueba():
    print("=" * 65)
    print("INICIANDO PRUEBA DE REGISTRO EN VIVO: ANEXO 17 (PRE-TEST & POST-TEST)")
    print("=" * 65)

    svc = GoogleSheetsService()
    print(f"-> GSpread Client: {'Activo' if svc._gspread_client else 'Inactivo (Uso de Webhook GAS)'}")
    print(f"-> Sheet ID Anexo 17: {svc.sheet_id_anexo17}")
    print(f"-> Webhook Anexo 17: {svc.webhook_url_anexo17}")
    print(f"-> Pestaña PRE-TEST: {svc.sheet_tab_anexo17_pre}")
    print(f"-> Pestaña POST-TEST: {svc.sheet_tab_anexo17_post}")
    print("-" * 65)

    # 1. Preparar datos PRE-TEST
    datos_pre = {
        "TIPO DE EVALUACIÓN": "PRE-TEST",
        "NOMBRE": "OWEN PRUEBA PRE-TEST",
        "MUNICIPIO": "EL CARMEN DE BOLIVAR",
        "FECHA": "16/10/2026",
        "EDAD": "16",
        "1. ¿QUÉ ES UN PROYECTO DE VIDA?": "A",
        "2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?": "B",
        "3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?": "A",
        "4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?": "C",
        "5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?": "A",
        "6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?": "B",
        "7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?": "A",
        "8. ¿QUÉ ES UNA RED DE APOYO?": "A",
        "9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?": "B",
        "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:": "A"
    }

    obj_pre = PrePostTestAnexo17.model_validate(datos_pre)
    fila_pre = [str(x or "").strip().upper() for x in obj_pre.to_ordered_row()]
    print(f"\n[1/2] Enviando registro PRE-TEST para: {obj_pre.nombre}...")
    res_pre = svc.insertar_anexo17(valores_ordenados=fila_pre, tipo_evaluacion=obj_pre.tipo_evaluacion)
    print(f"Resultado PRE-TEST: {json.dumps(res_pre, indent=2, ensure_ascii=False)}")

    # 2. Preparar datos POST-TEST
    datos_post = {
        "TIPO DE EVALUACIÓN": "POST-TEST",
        "NOMBRE": "OWEN PRUEBA POST-TEST",
        "MUNICIPIO": "EL CARMEN DE BOLIVAR",
        "FECHA": "16/10/2026",
        "EDAD": "16",
        "1. ¿QUÉ ES UN PROYECTO DE VIDA?": "A. UN PLAN SOBRE LO QUE QUIERO LOGRAR EN EL FUTURO",
        "2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?": "B. DECIR “NO”, ALEJARTE Y BUSCAR AYUDA",
        "3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?": "A. EL USO CORRECTO DEL CONDÓN",
        "4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?": "C. CONTÁRSELO A UN ADULTO DE CONFIANZA Y PEDIR AYUDA",
        "5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?": "A. HABLAR CON ALGUIEN DE CONFIANZA",
        "6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?": "B. ESCUCHARLO Y BUSCAR INMEDIATAMENTE LA AYUDA DE UN ADULTO",
        "7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?": "A. EXPRESAR LO QUE PIENSO Y SIENTO CON RESPETO",
        "8. ¿QUÉ ES UNA RED DE APOYO?": "A. PERSONAS E INSTITUCIONES QUE PUEDEN ORIENTARNOS Y AYUDARNOS",
        "9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?": "B. SER OBLIGADO A TRABAJAR O VINCULARSE A UN GRUPO ARMADO",
        "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:": "A. PENSAR EN LAS CONSECUENCIAS Y PEDIR ORIENTACIÓN"
    }

    obj_post = PrePostTestAnexo17.model_validate(datos_post)
    fila_post = [str(x or "").strip().upper() for x in obj_post.to_ordered_row()]
    print(f"\n[2/2] Enviando registro POST-TEST para: {obj_post.nombre}...")
    res_post = svc.insertar_anexo17(valores_ordenados=fila_post, tipo_evaluacion=obj_post.tipo_evaluacion)
    print(f"Resultado POST-TEST: {json.dumps(res_post, indent=2, ensure_ascii=False)}")

    print("\n" + "=" * 65)
    if res_pre.get("success") and res_post.get("success"):
        print(">>> PRUEBA EXITOSA: Ambos registros fueron insertados en Google Sheets. <<<")
    else:
        print(">>> ATENCIÓN: Hubo observaciones o fallos en alguna inserción. <<<")
    print("=" * 65)


if __name__ == "__main__":
    ejecutar_prueba()
