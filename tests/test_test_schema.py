"""
Pruebas Unitarias para el Esquema de Pre-Test y Post-Test (Anexo 4 SSR ITS)
y el Sistema de Memoria / Coincidencia Difusa de Participantes.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from schema_test import PrePostTest, COLUMNAS_TEST, ENCABEZADOS_TEST_SHEETS
from participant_cache import ParticipantCache


def test_esquema_basico_pre_test():
    """Valida la creación y normalización canónica de un Pre-Test."""
    payload = {
        "TIPO DE EVALUACIÓN": "PRE-TEST PARTICIPANTES- ANEXO Nº 4",
        "NOMBRE": "carlos andres marrugo gomez",
        "EDAD": "16",
        "MUNICIPIO": "turbaco",
        "EAPB (EPS)": "mutual ser",
        "1. EL USO CORRECTO DEL PRESERVATIVO AYUDA A PREVENIR ITS COMO VIH Y SÍFILIS.": "verdadero",
        "2. LAS ITS PUEDEN TRANSMITIRSE DE LA MADRE AL BEBÉ DURANTE EL EMBARAZO.": "v",
        "3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA.": "falso",
        "4. LOS ANTICONCEPTIVOS ORALES PREVIENEN LAS ITS.": "f",
        "5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?": "todas las anteriores",
        "6. LA PREP ES UN MEDICAMENTO QUE AYUDA A PREVENIR EL VIH EN PERSONAS CON MAYOR RIESGO DE EXPOSICIÓN.": "verdadero",
        "7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B.": "verdadero",
        "8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.": "verdadero",
        "9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES.": "cierto"
    }

    test = PrePostTest.model_validate(payload)
    assert test.tipo_evaluacion == "PRE-TEST"
    assert test.nombre == "CARLOS ANDRES MARRUGO GOMEZ"
    assert test.edad == "16"
    assert test.municipio == "TURBACO"
    assert test.eapb == "MUTUAL SER"
    assert test.pregunta_1 == "VERDADERO"
    assert test.pregunta_2 == "VERDADERO"
    assert test.pregunta_3 == "FALSO"
    assert test.pregunta_4 == "FALSO"
    assert test.pregunta_5 == "TODAS LAS ANTERIORES"
    assert test.pregunta_6 == "VERDADERO"
    assert test.pregunta_7 == "VERDADERO"
    assert test.pregunta_8 == "VERDADERO"
    assert test.pregunta_9 == "VERDADERO"

    # Verificar longitud de fila ordenada
    row = test.to_ordered_row()
    assert len(row) == 14
    assert row[0] == "PRE-TEST"
    assert row[1] == "CARLOS ANDRES MARRUGO GOMEZ"
    assert row[2] == "16"
    assert row[3] == "TURBACO"
    assert row[4] == "MUTUAL SER"
    assert len(COLUMNAS_TEST) == 14
    assert len(ENCABEZADOS_TEST_SHEETS) == 15


def test_post_test_deteccion_y_opcion_condon():
    """Valida la detección de POST-TEST y la opción de usar preservativo en P5."""
    payload = {
        "TIPO DE EVALUACIÓN": "post test",
        "NOMBRE": "MARIA JOSE RIVAS",
        "EDAD": "15 AÑOS",
        "MUNICIPIO": "San Jacinto Del Cauca",
        "EAPB (EPS)": "Coosalud",
        "1. EL USO CORRECTO DEL PRESERVATIVO AYUDA A PREVENIR ITS COMO VIH Y SÍFILIS.": "SI",
        "2. LAS ITS PUEDEN TRANSMITIRSE DE LA MADRE AL BEBÉ DURANTE EL EMBARAZO.": "NO",
        "3. UNA PERSONA CON VIH SIEMPRE SE VE ENFERMA.": "NO",
        "4. LOS ANTICONCEPTIVOS ORALES PREVIENEN LAS ITS.": "NO",
        "5. ¿CUÁL DE LAS SIGUIENTES ACCIONES AYUDA A PREVENIR EL VIH?": "usar condon",
        "6. LA PREP ES UN MEDICAMENTO QUE AYUDA A PREVENIR EL VIH EN PERSONAS CON MAYOR RIESGO DE EXPOSICIÓN.": "VERDADERO",
        "7. EXISTE VACUNA PARA PREVENIR LA HEPATITIS B.": "VERDADERO",
        "8. LA SÍFILIS TIENE TRATAMIENTO Y PUEDE PREVENIRSE.": "VERDADERO",
        "9. RESPETAR LAS DIFERENCIAS Y EVITAR LA DISCRIMINACIÓN AYUDA A CONSTRUIR RELACIONES SALUDABLES.": "VERDADERO"
    }

    test = PrePostTest.model_validate(payload)
    assert test.tipo_evaluacion == "POST-TEST"
    assert test.edad == "15"
    assert test.municipio == "SAN JACINTO DEL CAUCA"
    assert test.eapb == "COOSALUD"
    assert test.pregunta_1 == "VERDADERO"
    assert test.pregunta_2 == "FALSO"
    assert test.pregunta_5 == "USAR PRESERVATIVO"


def test_participant_cache_fuzzy_match(tmp_path):
    """Prueba que el catálogo de participantes reconozca nombres con typos o caligrafía imperfecta."""
    cache_path = tmp_path / "test_participantes.json"
    cache = ParticipantCache(cache_file=cache_path)

    cache.aprender_participante(
        nombre="LUIS ALBERTO CABARCAS MORALES",
        edad="17",
        municipio="MAHATES",
        eapb="NUEVA EPS",
        documento="1048392019"
    )

    # Simular que el OCR leyó con ligero ruido en el apellido o nombre
    match1 = cache.buscar_coincidencia("LUIS ALBERTO CABARCAS M", municipio_hint="MAHATES")
    assert match1 is not None
    assert match1["nombre"] == "LUIS ALBERTO CABARCAS MORALES"
    assert match1["municipio"] == "MAHATES"
    assert match1["edad"] == "17"

    # Simular importación masiva desde CSV
    csv_sample = """Marca temporal,NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA,TERRITORIO,Nombre completo del participante,Tipo de documento identidad,Numero de documento identidad,Edad,Municipio,EPS (si tienes)
2026/09/15,PAMELA VERGARA,TURBANA,ANA LUCIA HERRERA SILVA,TI,1048293847,15,TURBANA,MUTUAL SER
2026/09/15,PAMELA VERGARA,TURBANA,JORGE ELIECER PEÑA BLANCO,TI,1048293848,16,TURBANA,COOSALUD
"""
    total = cache.importar_desde_csv(csv_sample)
    assert total == 2
    assert cache.contar() == 3

    match2 = cache.buscar_coincidencia("ANA LUSIA HERRERA SILVA")
    assert match2 is not None
    assert match2["nombre"] == "ANA LUCIA HERRERA SILVA"
    assert match2["municipio"] == "TURBANA"


if __name__ == "__main__":
    test_esquema_basico_pre_test()
    test_post_test_deteccion_y_opcion_condon()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_participant_cache_fuzzy_match(Path(td))
    print("OK: Todas las pruebas de Pre/Post Test y Memoria de Participantes pasaron con exito.")
