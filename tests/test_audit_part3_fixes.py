"""
Suite de pruebas unitarias para la 3ra tanda de hallazgos de auditoría:
1. Rechazo de cruce entre homónimos o nombres comunes (MARIA JOSE PEREZ vs MARIA JOSE GOMEZ).
2. Clave compuesta y desempate por municipio en ParticipantCache.
3. Bono territorial a 0.03 y exclusión en Santa Catalina.
4. Prevención de cruce entre Pregunta 1 y Pregunta 10 en buscar_valor (schema_anexo17 y schema_test).
5. Falso positivo en Pregunta 2 de Anexo 17 ante respuestas en blanco / no marcadas.
6. Respeto de auto_rotar=False en optimizar_imagen_bytes (no deshacer rotación manual del cliente).
7. Respeto de GOOGLE_SHEET_TAB="Respuestas" y lectura de GOOGLE_SHEET_TAB_PRE_TEST / POST_TEST.
8. Pregunta 5 de Anexo 4 normaliza múltiples casillas marcadas a "TODAS LAS ANTERIORES".
"""

import sys
import os
import io
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from participant_cache import (
    token_jaro_winkler_similarity,
    ParticipantCache,
    limpiar_texto
)
from schema_anexo17 import normalizar_opcion_anexo17, PrePostTestAnexo17
from schema_test import normalizar_pregunta_5, PrePostTest
from vision_service import optimizar_imagen_bytes
from sheets_service import GoogleSheetsService


def test_1_homonimos_distintos_apellidos_no_cruzan():
    """Verifica que MARIA JOSE PEREZ y MARIA JOSE GOMEZ den score 0.0."""
    score = token_jaro_winkler_similarity("MARIA JOSE PEREZ", "MARIA JOSE GOMEZ")
    assert score == 0.0, f"Se esperaba 0.0 para distintos apellidos, pero dio {score}"

    score2 = token_jaro_winkler_similarity("CARLOS ANDRES MARTINEZ", "CARLOS ANDRES HERNANDEZ")
    assert score2 == 0.0, f"Se esperaba 0.0, dio {score2}"


def test_2_cache_clave_compuesta_homonimos_mismo_nombre():
    """Verifica que dos participantes con el mismo nombre pero diferente documento o municipio no se sobrescriban."""
    temp_cache_file = Path(__file__).resolve().parent / "temp_cache_homonimos.json"
    if temp_cache_file.exists():
        temp_cache_file.unlink()

    cache = ParticipantCache(cache_file=temp_cache_file)
    try:
        cache.aprender_participante(
            nombre="MARIA JOSE PEREZ",
            municipio="MAHATES",
            documento="1001",
            edad="15"
        )
        cache.aprender_participante(
            nombre="MARIA JOSE PEREZ",
            municipio="SANTA ROSA",
            documento="1002",
            edad="16"
        )

        assert cache.contar() == 2, f"Deben existir 2 participantes, hay {cache.contar()}"

        # Búsqueda con hint de municipio debe resolver al del municipio correspondiente
        match_mahates = cache.buscar_coincidencia("MARIA JOSE PEREZ", municipio_hint="MAHATES")
        assert match_mahates is not None
        assert match_mahates["municipio"] == "MAHATES"
        assert match_mahates["documento"] == "1001"

        match_santarosa = cache.buscar_coincidencia("MARIA JOSE PEREZ", municipio_hint="SANTA ROSA")
        assert match_santarosa is not None
        assert match_santarosa["municipio"] == "SANTA ROSA DEL SUR"
        assert match_santarosa["documento"] == "1002"

    finally:
        if temp_cache_file.exists():
            temp_cache_file.unlink()


def test_3_bono_territorial_santa_catalina_desactivado():
    """Verifica que en Santa Catalina no se añada bono territorial falso."""
    temp_cache_file = Path(__file__).resolve().parent / "temp_cache_bono.json"
    if temp_cache_file.exists():
        temp_cache_file.unlink()

    cache = ParticipantCache(cache_file=temp_cache_file)
    try:
        cache.aprender_participante(
            nombre="VALENTINA CASTRO RODRIGUEZ",
            municipio="SANTA CATALINA"
        )
        # Nombre con pequeña variación
        res = cache.buscar_coincidencia("VALENTINA CASTRO RODRIGUES", municipio_hint="SANTA CATALINA")
        assert res is not None
        # Score debe ser el JW puro sin sumar 0.08 ni 0.03 de bono
        jw_puro = token_jaro_winkler_similarity("VALENTINA CASTRO RODRIGUES", "VALENTINA CASTRO RODRIGUEZ")
        assert abs(res["score"] - round(jw_puro, 3)) < 0.01

    finally:
        if temp_cache_file.exists():
            temp_cache_file.unlink()


def test_4_no_cruce_pregunta_1_y_10_anexo17():
    """Verifica que Pregunta 1 no capture la Pregunta 10 cuando se busca en el diccionario."""
    dict_simulado = {
        "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, ¿QUÉ ES RECOMENDABLE HACER?": "A. PENSAR EN LAS CONSECUENCIAS Y PEDIR ORIENTACIÓN",
        "1. ¿QUÉ ES UN PROYECTO DE VIDA?": "A. UN PLAN SOBRE LO QUE QUIERO LOGRAR EN EL FUTURO",
        "NOMBRE": "ANDRES LOPEZ",
        "MUNICIPIO": "SANTA CATALINA"
    }

    obj = PrePostTestAnexo17.model_validate(dict_simulado)
    assert obj.pregunta_1 == "A. UN PLAN SOBRE LO QUE QUIERO LOGRAR EN EL FUTURO", f"P1 capturó erróneamente: {obj.pregunta_1}"
    assert obj.pregunta_10 == "A. PENSAR EN LAS CONSECUENCIAS Y PEDIR ORIENTACIÓN", f"P10 capturó erróneamente: {obj.pregunta_10}"


def test_5_pregunta_2_anexo17_no_marca_blancos():
    """Verifica que si la pregunta 2 está en blanco, no marcada o la IA retorna 'NO MARCADA', no devuelva la opción B."""
    assert normalizar_opcion_anexo17(2, "") == ""
    assert normalizar_opcion_anexo17(2, "NO MARCADA") == ""
    assert normalizar_opcion_anexo17(2, "NO RESPONDIO") == ""
    assert normalizar_opcion_anexo17(2, "NO MARCO") == ""
    assert normalizar_opcion_anexo17(2, "VACIO") == ""
    assert normalizar_opcion_anexo17(2, "NO") == ""

    # Y que sí reconozca respuestas válidas de la opción B
    res_b = normalizar_opcion_anexo17(2, 'DECIR "NO", ALEJARTE Y BUSCAR AYUDA')
    assert "DECIR NO" in res_b or 'DECIR "NO"' in res_b or "ALEJARTE" in res_b


def test_6_auto_rotar_false_preserva_orientacion_horizontal():
    """Verifica que con auto_rotar=False una imagen horizontal de 1200x800 conserve su orientación horizontal."""
    img = Image.new("RGB", (1200, 800), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    bytes_in = buf.getvalue()

    # Con auto_rotar=False (como cuando ya_orientada=True)
    bytes_out, _ = optimizar_imagen_bytes(bytes_in, auto_rotar=False)
    img_res = Image.open(io.BytesIO(bytes_out))
    assert img_res.width > img_res.height, "Con auto_rotar=False la imagen horizontal no debió ser girada"

    # Con auto_rotar=True (por defecto para fotos directas)
    bytes_out_rot, _ = optimizar_imagen_bytes(bytes_in, auto_rotar=True)
    img_res_rot = Image.open(io.BytesIO(bytes_out_rot))
    assert img_res_rot.height > img_res_rot.width, "Con auto_rotar=True debió orientarse a vertical"


def test_7_sheets_service_respeta_env_tab_respuestas():
    """Verifica que si GOOGLE_SHEET_TAB es 'Respuestas', sheets_service no lo ignore."""
    os.environ["GOOGLE_SHEET_TAB"] = "Respuestas"
    os.environ["GOOGLE_SHEET_TAB_PRE_TEST"] = "MI_PRE_TEST"
    os.environ["GOOGLE_SHEET_TAB_POST_TEST"] = "MI_POST_TEST"

    svc = GoogleSheetsService()
    assert svc.sheet_tab == "Respuestas"
    assert svc.sheet_tab_pre_test == "MI_PRE_TEST"
    assert svc.sheet_tab_post_test == "MI_POST_TEST"


def test_8_pregunta_5_anexo4_varias_opciones_a_todas_las_anteriores():
    """Verifica que si el estudiante marca 2 o las 3 opciones de la pregunta 5, se normalice a TODAS LAS ANTERIORES."""
    # Caso 1: Marcó las 3 opciones
    txt1 = "USAR PRESERVATIVO, TENER INFORMACIÓN CLARA SOBRE SALUD SEXUAL, EVITAR COMPARTIR AGUJAS O ELEMENTOS CORTOPUNZANTES"
    assert normalizar_pregunta_5(txt1) == "TODAS LAS ANTERIORES"

    # Caso 2: Marcó 2 de las 3 opciones
    txt2 = "USAR PRESERVATIVO Y EVITAR COMPARTIR AGUJAS"
    assert normalizar_pregunta_5(txt2) == "TODAS LAS ANTERIORES"

    # Caso 3: Marcó solo 1 opción
    txt3 = "USAR PRESERVATIVO"
    assert normalizar_pregunta_5(txt3) == "USAR PRESERVATIVO"

    # Caso 4: Marcó explícitamente "Todas las anteriores"
    txt4 = "TODAS LAS ANTERIORES"
    assert normalizar_pregunta_5(txt4) == "TODAS LAS ANTERIORES"


if __name__ == "__main__":
    print("Corriendo pruebas unitarias de la 3ra tanda de auditoria...")
    test_1_homonimos_distintos_apellidos_no_cruzan()
    print("[PASS] Test 1: Homonimos con distintos apellidos no cruzan identidades.")
    test_2_cache_clave_compuesta_homonimos_mismo_nombre()
    print("[PASS] Test 2: Clave compuesta e indice secundario evitan sobrescritura.")
    test_3_bono_territorial_santa_catalina_desactivado()
    print("[PASS] Test 3: Bono territorial desactivado en Santa Catalina.")
    test_4_no_cruce_pregunta_1_y_10_anexo17()
    print("[PASS] Test 4: Sin colision entre Pregunta 1 y 10 en Anexo 17.")
    test_5_pregunta_2_anexo17_no_marca_blancos()
    print("[PASS] Test 5: Pregunta 2 no genera falsos positivos ante blancos / no marcadas.")
    test_6_auto_rotar_false_preserva_orientacion_horizontal()
    print("[PASS] Test 6: auto_rotar=False respeta rotacion manual del cliente.")
    test_7_sheets_service_respeta_env_tab_respuestas()
    print("[PASS] Test 7: Variables .env de pestanas respetadas correctamente.")
    test_8_pregunta_5_anexo4_varias_opciones_a_todas_las_anteriores()
    print("[PASS] Test 8: Pregunta 5 normaliza multiples casillas a TODAS LAS ANTERIORES.")
    print("\n[OK] TODAS LAS PRUEBAS DE LA 3RA TANDA PASARON CON EXITO.")
