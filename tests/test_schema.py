"""
Pruebas de validación de esquema para PROJ-006 Ficha Caracterización
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.schema import FichaCaracterizacion, COLUMNAS_FICHA


def test_schema_columns_count():
    assert len(COLUMNAS_FICHA) == 43, f"Se esperaban 43 columnas, se encontraron {len(COLUMNAS_FICHA)}"


def test_uppercase_normalization():
    raw_data = {
        "NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA": "juan perez",
        "TERRITORIO": "zona norte",
        "Nombre completo del participante": "maria camila gomez",
        "Tipo de documento identidad": "ti",
        "Numero de documento identidad": "1002345678",
        "Edad": "16",
        "¿Cuándo fue la última vez?": "hace tres meses",
        "¿Qué tiempo empleas en esta actividad?": "2",
        "¿Consumes o has consumido cigarrillo o vapeador?": "si",
        "¿Consumes o has consumido alcohol?": "no",
        "¿Has recibido información sobre salud sexual, ITS o métodos de prevención?": "si",
        "¿Has vivido o conoces algún caso cercano de embarazo adolescente?": "si",
        "¿Por que?": "me gustaria aprender mas sobre salud"
    }

    ficha = FichaCaracterizacion.model_validate(raw_data)
    dict_res = ficha.to_canonical_dict()

    assert dict_res["NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA"] == "JUAN PEREZ"
    assert dict_res["TERRITORIO"] == "ZONA NORTE"
    assert dict_res["Nombre completo del participante"] == "MARIA CAMILA GOMEZ"
    assert dict_res["Tipo de documento identidad"] == "TI"
    assert dict_res["¿Cuándo fue la última vez?"] == "HACE TRES MESES"
    assert dict_res["¿Qué tiempo empleas en esta actividad?"] == "2 HORAS"
    assert dict_res["¿Consumes o has consumido cigarrillo o vapeador?"] == "SI"
    assert dict_res["¿Consumes o has consumido alcohol?"] == "NO"
    assert dict_res["¿Has recibido información sobre salud sexual, ITS o métodos de prevención?"] == "SI"
    assert dict_res["¿Has vivido o conoces algún caso cercano de embarazo adolescente?"] == "SI"
    assert dict_res["¿Por que?"] == "ME GUSTARIA APRENDER MAS SOBRE SALUD"
    # Campo no proporcionado debe ser string vacío
    assert dict_res["EPS (si tienes)"] == ""
    assert dict_res["Grado escolar"] == ""

    row = ficha.to_ordered_row()
    assert len(row) == 43
    assert row[0] == "JUAN PEREZ"
    assert row[1] == "ZONA NORTE"
    assert row[2] == "MARIA CAMILA GOMEZ"
    # Verificar posición de campo 22 y 25
    assert row[21] == "HACE TRES MESES"
    assert row[24] == "2 HORAS"
    # Verificar casilla 38
    assert row[37] == "SI"


def test_mayo_2026_and_date_handling():
    raw_data = {
        "Nombre completo del participante": "Carlos Sanchez",
        "¿Cuándo fue la última vez?": "mayo 2026",
        "¿Qué tiempo empleas en esta actividad?": "3",
        "¿Has vivido o conoces algún caso cercano de embarazo adolescente?": "si",
        "¿Cuándo fue la ultima vez?": "mayo 2026"
    }

    ficha = FichaCaracterizacion.model_validate(raw_data)
    row = ficha.to_ordered_row()

    # Campo 22 (índice 21)
    assert row[21] == "MAYO 2026", f"Esperado 'MAYO 2026', obtenido '{row[21]}'"
    # Campo 25 (índice 24)
    assert row[24] == "3 HORAS", f"Esperado '3 HORAS', obtenido '{row[24]}'"
    # Casilla 38 (índice 37)
    assert row[37] == "SI", f"Esperado 'SI', obtenido '{row[37]}'"
    # Probar que si el OCR lee 2020 lo corrige automáticamente a 2026
    ficha_2020 = FichaCaracterizacion.model_validate({
        "¿Cuándo fue la última vez?": "mayo 2020",
        "¿Cuándo fue la ultima vez?": "junio 2020"
    })
    row_2020 = ficha_2020.to_ordered_row()
    assert row_2020[21] == "MAYO 2026", f"Esperado 'MAYO 2026', obtenido '{row_2020[21]}'"
    assert row_2020[39] == "JUNIO 2026", f"Esperado 'JUNIO 2026', obtenido '{row_2020[39]}'"


def test_encuestadores_autorizados():
    casos = [
        ("pamela", "PAMELA VERGARA"),
        ("PAMELA VERGARA", "PAMELA VERGARA"),
        ("vergara", "PAMELA VERGARA"),
        ("karen", "KAREN TORRES"),
        ("karen torres", "KAREN TORRES"),
        ("TORRES", "KAREN TORRES"),
        ("wendy", "WENDY TAPIAS"),
        ("WENDY TAPIAS", "WENDY TAPIAS"),
        ("tapias", "WENDY TAPIAS"),
        ("gisel", "GISEL MORENO"),
        ("giselle", "GISEL MORENO"),
        ("moreno", "GISEL MORENO"),
        ("GISEL MORENO", "GISEL MORENO"),
        ("mauricio", "MAURICIO FORTICH"),
        ("mauricio fortich", "MAURICIO FORTICH"),
        ("fortich", "MAURICIO FORTICH")
    ]

    for entrada, esperado in casos:
        ficha = FichaCaracterizacion.model_validate({
            "NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA": entrada
        })
        res = ficha.to_canonical_dict()["NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA"]
        assert res == esperado, f"Para '{entrada}' se esperaba '{esperado}', pero se obtuvo '{res}'"
        row = ficha.to_ordered_row()
        assert row[0] == esperado, f"En fila ordenada para '{entrada}' se esperaba '{esperado}', obtenido '{row[0]}'"


def test_estandarizacion_catalogos_completos():
    data = {
        "TERRITORIO": "turbaco",
        "Tipo de documento identidad": "cedula de ciudadania",
        "Grado escolar": "9",
        "Zona": "urbana",
        "EPS (si tienes)": "sura",
        "Régimen": "contributivo",
        "Sexo con el que te identificas": "femenino",
        "Identidad de género": "heterosexual",
        "¿Perteneces a alguna población o grupo étnico?": "afrocolombiano",
        "¿Tienes alguna condición de discapacidad?": "no"
    }

    ficha = FichaCaracterizacion.model_validate(data)
    d = ficha.to_canonical_dict()

    assert d["TERRITORIO"] == "TURBACO"
    assert d["Municipio"] == "TURBACO", "Regla: Municipio debe ser el mismo que Territorio"
    assert d["Tipo de documento identidad"] == "CC"
    assert d["Grado escolar"] == "9°"
    assert d["Zona"] == "URBANA"
    assert d["EPS (si tienes)"] == "SURA"
    assert d["Régimen"] == "CONTRIBUTIVO"
    assert d["Sexo con el que te identificas"] == "FEMENINO"
    assert d["Identidad de género"] == "HETEROSEXUAL"
    assert d["¿Perteneces a alguna población o grupo étnico?"] == "AFROCOLOMBIANO"
    assert d["¿Tienes alguna condición de discapacidad?"] == "NO"

    # Probar otros catálogos autorizados
    ficha2 = FichaCaracterizacion.model_validate({
        "TERRITORIO": "barranco de loba",
        "Tipo de documento identidad": "tarjeta de identidad",
        "Grado escolar": "once",
        "Zona": "rural",
        "EPS (si tienes)": "mutual ser",
        "Régimen": "subsidiado",
        "Sexo con el que te identificas": "masculino",
        "Identidad de género": "homosexual",
        "¿Perteneces a alguna población o grupo étnico?": "palenquero",
        "¿Tienes alguna condición de discapacidad?": "si"
    })
    d2 = ficha2.to_canonical_dict()
    assert d2["TERRITORIO"] == "BARRANCO DE LOBA"
    assert d2["Municipio"] == "BARRANCO DE LOBA"
    assert d2["Tipo de documento identidad"] == "TI"
    assert d2["Grado escolar"] == "11°"
    assert d2["Zona"] == "RURAL"
    assert d2["EPS (si tienes)"] == "MUTUAL SER"
    assert d2["Régimen"] == "SUBSIDIADO"
    assert d2["Sexo con el que te identificas"] == "MASCULINO"
    assert d2["Identidad de género"] == "HOMOSEXUAL"
    assert d2["¿Perteneces a alguna población o grupo étnico?"] == "PALENQUERO"
    assert d2["¿Tienes alguna condición de discapacidad?"] == "SI"


def test_campos_sin_espacios_telefono_e_id():
    casos = [
        # Documento de identidad
        ("Numero de documento identidad", "1 045 678 901", "1045678901"),
        ("Numero de documento identidad", "1.045.678.901", "1045678901"),
        ("Numero de documento identidad", "1045-678-901", "1045678901"),
        ("Numero de documento identidad", " 73 123 456 ", "73123456"),
        # Teléfono
        ("Teléfono de contacto", "300 123 4567", "3001234567"),
        ("Teléfono de contacto", "(300) 123-4567", "3001234567"),
        ("Teléfono de contacto", "300.123.4567", "3001234567"),
        ("Teléfono de contacto", "315 890 12 34", "3158901234"),
    ]

    for campo, entrada, esperado in casos:
        ficha = FichaCaracterizacion.model_validate({campo: entrada})
        d = ficha.to_canonical_dict()
        assert d[campo] == esperado, f"Para '{campo}' con entrada '{entrada}' se esperaba '{esperado}', pero se obtuvo '{d[campo]}'"


def test_menor_de_18_es_ti():
    casos = [
        # (tipo_entrada, edad_entrada, esperado)
        ("CC", "16", "TI"),
        ("CEDULA", "15", "TI"),
        ("", "14", "TI"),
        ("RC", "17", "TI"),
        ("TI", "16 AÑOS", "TI"),
        ("PASAPORTE", "16", "PASAPORTE"),
        ("PERMISO", "15", "PERMISO"),
        ("CC", "18", "CC"),
        ("CC", "25", "CC"),
    ]

    for tipo_doc, edad, esperado in casos:
        ficha = FichaCaracterizacion.model_validate({
            "Tipo de documento identidad": tipo_doc,
            "Edad": edad
        })
        d = ficha.to_canonical_dict()
        assert d["Tipo de documento identidad"] == esperado, (
            f"Para tipo='{tipo_doc}' y edad='{edad}', se esperaba '{esperado}' pero se obtuvo '{d['Tipo de documento identidad']}'"
        )
        row = ficha.to_ordered_row()
        assert row[3] == esperado, (
            f"En fila ordenada (columna 4), se esperaba '{esperado}' pero se obtuvo '{row[3]}'"
        )


def test_fuzzy_matching_vocabulario():
    # 1. Método anticonceptivo ¿Cual?_3: reconocimiento de YADEL / JADELLE y variantes fonéticas
    for var in ["YADEL", "YADUL", "YADOL", "JADEL", "JADELLE", "YADELL", "JADUL", "YADLE"]:
        f = FichaCaracterizacion.model_validate({"¿Cual?_3": var})
        assert f.to_canonical_dict()["¿Cual?_3"] == "YADEL", f"Fallo con variante de Jadelle: {var}"

    # 2. Otros métodos anticonceptivos
    f_condon = FichaCaracterizacion.model_validate({"¿Cual?_3": "PRESERBATIBO"})
    assert f_condon.to_canonical_dict()["¿Cual?_3"] == "PRESERVATIVO"

    # 3. Dirección / Barrios aprendidos
    f_barrio = FichaCaracterizacion.model_validate({"Dirección de residencia (barrio o vereda)": "BARRIO SAN RAFAELL"})
    assert "SAN RAFAEL" in f_barrio.to_canonical_dict()["Dirección de residencia (barrio o vereda)"]

    # 4. Actividades de ocio y sustancias
    f_act = FichaCaracterizacion.model_validate({"¿Qué actividades recreativas haces en tu tiempo libre?": "FUTBOLL"})
    assert "FUTBOL" in f_act.to_canonical_dict()["¿Qué actividades recreativas haces en tu tiempo libre?"]

    f_sust = FichaCaracterizacion.model_validate({"¿Cual?_2": "MARIHUANNA"})
    assert f_sust.to_canonical_dict()["¿Cual?_2"] == "MARIHUANA"

    # 5. Campos personales NUNCA deben alterarse por fuzzy matching
    f_pers = FichaCaracterizacion.model_validate({
        "Nombre completo del participante": "YADUL PEREZ",
        "Numero de documento identidad": "1045678901"
    })
    d_pers = f_pers.to_canonical_dict()
    assert d_pers["Nombre completo del participante"] == "YADUL PEREZ"
    assert d_pers["Numero de documento identidad"] == "1045678901"


def test_uso_condon_y_dicotomicas():
    col_condon = "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?"
    casos_condon = [
        ("siempre", "SIEMPRE"),
        ("SIEMPRE", "SIEMPRE"),
        ("casi siempre", "CASI SIEMPRE"),
        ("a veces", "CASI SIEMPRE"),
        ("nunca", "NUNCA"),
        ("NUNCA", "NUNCA"),
        ("", "")
    ]
    for entrada, esperado in casos_condon:
        f = FichaCaracterizacion.model_validate({col_condon: entrada})
        assert f.to_canonical_dict()[col_condon] == esperado, f"Para condón entrada '{entrada}', se esperaba '{esperado}'"

    # Dicotómicas estandarizadas a SI / NO
    f_dico = FichaCaracterizacion.model_validate({
        "¿Has vivido situaciones de discriminación, rechazo o violencia?": "si",
        "¿Has iniciado tu vida sexual?": "no",
        "¿Has recibido información sobre salud sexual, ITS o métodos de prevención?": "si",
        "¿Conoces algún método anticonceptico?": "si"
    })
    d_dico = f_dico.to_canonical_dict()
    assert d_dico["¿Has vivido situaciones de discriminación, rechazo o violencia?"] == "SI"
    assert d_dico["¿Has iniciado tu vida sexual?"] == "NO"
    assert d_dico["¿Has recibido información sobre salud sexual, ITS o métodos de prevención?"] == "SI"
    assert d_dico["¿Conoces algún método anticonceptico?"] == "SI"


def test_casilla_39_y_no_alucinacion_fecha():
    # 1. Casilla 39 con diversas variaciones de claves generadas por OCR
    variantes_casilla_39 = [
        ("¿Te han entregado preservativos en la EPS o institución de salud?", "si", "SI"),
        ("¿Te han entregado preservativos en la EPS o institucion de salud?", "si", "SI"),
        ("¿Te han entregado preservativos en la EPS?", "no", "NO"),
        ("¿Te han entregado preservativos en la EPS o institución de salud? ", "si", "SI"),
        ("entregado preservativos en la eps", "si", "SI")
    ]
    for k, v, esperado in variantes_casilla_39:
        f = FichaCaracterizacion.model_validate({k: v})
        res = f.to_canonical_dict()["¿Te han entregado preservativos en la EPS o institución de salud?"]
        assert res == esperado, f"Para clave '{k}' con valor '{v}', se esperaba '{esperado}' pero se obtuvo '{res}'"
        row = f.to_ordered_row()
        assert row[38] == esperado, f"En fila ordenada col 39 (índice 38) se esperaba '{esperado}', obtenido '{row[38]}'"

    # 2. No alucinación en Columna 22 (¿Cuándo fue la última vez?)
    # Si la persona no asistió al médico, la fecha debe ser vacía ""
    f_no_medico = FichaCaracterizacion.model_validate({
        "¿Has asistido al médico en el último año?": "NO",
        "¿Cuándo fue la última vez?": "MAYO 2026"
    })
    assert f_no_medico.to_canonical_dict()["¿Cuándo fue la última vez?"] == ""
    assert f_no_medico.to_ordered_row()[21] == ""

    # Si vino vacío, debe mantenerse estrictamente vacío ""
    f_vacio = FichaCaracterizacion.model_validate({
        "¿Cuándo fue la última vez?": ""
    })
    assert f_vacio.to_canonical_dict()["¿Cuándo fue la última vez?"] == ""
    assert f_vacio.to_ordered_row()[21] == ""


def test_temas_interes_separador_coma():
    casos = [
        # (entrada, esperado)
        ("VIH, SIFILIS, METODOS ANTICONCEPTIVOS", "VIH, SIFILIS, METODOS ANTICONCEPTIVOS"),
        ("VIH; SIFILIS; METODOS ANTICONCEPTIVOS", "VIH, SIFILIS, METODOS ANTICONCEPTIVOS"),
        ("VIH - SIFILIS", "VIH, SIFILIS"),
        ("VIH / SÍFILIS", "VIH, SIFILIS"),
        (["VIH", "USO CORRECTO DEL PRESERVATIVO"], "VIH, USO CORRECTO DEL PRESERVATIVO"),
        ("VIH\nSIFILIS", "VIH, SIFILIS"),
        ("VIH SIFILIS", "VIH, SIFILIS"),
        ("VIH, SIFILIS, AUTOESTIMA Y DERECHOS", "VIH, SIFILIS, AUTOESTIMA Y DERECHOS"),
        ("VIH", "VIH"),
        ("", ""),
    ]

    for entrada, esperado in casos:
        f = FichaCaracterizacion.model_validate({
            "¿Qué tema te gustaria aprender o entender mejor?": entrada
        })
        res_dict = f.to_canonical_dict()["¿Qué tema te gustaria aprender o entender mejor?"]
        assert res_dict == esperado, (
            f"Para entrada '{entrada}', se esperaba '{esperado}' pero se obtuvo '{res_dict}'"
        )
        res_row = f.to_ordered_row()[40]
        assert res_row == esperado, (
            f"En fila ordenada col 41 (índice 40), se esperaba '{esperado}' pero se obtuvo '{res_row}'"
        )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    test_schema_columns_count()
    test_uppercase_normalization()
    test_mayo_2026_and_date_handling()
    test_encuestadores_autorizados()
    test_estandarizacion_catalogos_completos()
    test_campos_sin_espacios_telefono_e_id()
    test_menor_de_18_es_ti()
    test_fuzzy_matching_vocabulario()
    test_uso_condon_y_dicotomicas()
    test_casilla_39_y_no_alucinacion_fecha()
    test_temas_interes_separador_coma()
    print("OK: Todas las pruebas de esquema, fuzzy matching y normalizacion pasaron exitosamente.")
