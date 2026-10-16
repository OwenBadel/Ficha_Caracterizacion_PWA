"""
Script de Prueba de Inserción en Vivo para Anexo 17 (Pellízcate con Generación B+).
Soporta inserción parametrizada o por defecto para PRE-TEST y POST-TEST.
Uso:
  python tests/probar_anexo17_live.py [NOMBRE] [EDAD] [PRE|POST|AMBOS]
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Configurar path a backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schema_anexo17 import PrePostTestAnexo17, COLUMNAS_ANEXO17, ENCABEZADOS_ANEXO17_SHEETS
from sheets_service import GoogleSheetsService


def ejecutar_prueba(nombre_base: str = None, edad: str = "15", modo: str = "AMBOS", fecha_custom: str = None):
    hora_actual = datetime.now().strftime("%H:%M:%S")
    fecha_a_usar = fecha_custom if fecha_custom else datetime.now().strftime("%d/%m/%Y")

    if not nombre_base:
        nombre_pre = f"DANIELA MARGARITA TORRES CASTRO ({hora_actual})"
        nombre_post = f"DANIELA MARGARITA TORRES CASTRO ({hora_actual})"
    else:
        nombre_pre = f"{nombre_base.strip().upper()} ({hora_actual})"
        nombre_post = f"{nombre_base.strip().upper()} ({hora_actual})"

    print("=" * 65)
    print("INICIANDO INSERCIÓN EN VIVO: ANEXO 17 (PELLÍZCATE)")
    print(f"-> Participante: {nombre_pre}")
    print(f"-> Municipio: EL CARMEN DE BOLIVAR | Fecha Entrada: {fecha_a_usar} | Edad: {edad}")
    print(f"-> Modo: {modo.upper()}")
    print("=" * 65)

    svc = GoogleSheetsService()
    print(f"-> Sheet ID Anexo 17: {svc.sheet_id_anexo17}")
    print(f"-> Webhook Anexo 17: {svc.webhook_url_anexo17}")
    print("-" * 65)

    resultados = {}

    # 1. Inserción PRE-TEST
    if modo.upper() in ("PRE", "PRE-TEST", "AMBOS"):
        datos_pre = {
            "TIPO DE EVALUACIÓN": "PRE-TEST",
            "NOMBRE": nombre_pre,
            "MUNICIPIO": "EL CARMEN DE BOLIVAR",
            "FECHA": fecha_a_usar,
            "EDAD": str(edad),
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
        print(f"\n[+] Enviando registro PRE-TEST para: {obj_pre.nombre}...")
        res_pre = svc.insertar_anexo17(valores_ordenados=fila_pre, tipo_evaluacion=obj_pre.tipo_evaluacion)
        print(f"Resultado PRE-TEST: {json.dumps(res_pre, indent=2, ensure_ascii=False)}")
        resultados["PRE-TEST"] = res_pre

    # 2. Inserción POST-TEST
    if modo.upper() in ("POST", "POST-TEST", "AMBOS"):
        datos_post = {
            "TIPO DE EVALUACIÓN": "POST-TEST",
            "NOMBRE": nombre_post,
            "MUNICIPIO": "EL CARMEN DE BOLIVAR",
            "FECHA": fecha_a_usar,
            "EDAD": str(edad),
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
        print(f"\n[+] Enviando registro POST-TEST para: {obj_post.nombre}...")
        res_post = svc.insertar_anexo17(valores_ordenados=fila_post, tipo_evaluacion=obj_post.tipo_evaluacion)
        print(f"Resultado POST-TEST: {json.dumps(res_post, indent=2, ensure_ascii=False)}")
        resultados["POST-TEST"] = res_post

    print("\n" + "=" * 65)
    todos_ok = all(r.get("success") for r in resultados.values())
    if todos_ok:
        print(">>> INSERCIÓN EN VIVO COMPLETADA EXITOSAMENTE EN GOOGLE SHEETS <<<")
    else:
        print(">>> ATENCIÓN: Al menos una inserción tuvo incidencias. <<<")
    print("=" * 65)
    return resultados


if __name__ == "__main__":
    nombre_arg = sys.argv[1] if len(sys.argv) > 1 else None
    edad_arg = sys.argv[2] if len(sys.argv) > 2 else "15"
    modo_arg = sys.argv[3] if len(sys.argv) > 3 else "AMBOS"
    fecha_arg = sys.argv[4] if len(sys.argv) > 4 else None
    ejecutar_prueba(nombre_base=nombre_arg, edad=edad_arg, modo=modo_arg, fecha_custom=fecha_arg)
