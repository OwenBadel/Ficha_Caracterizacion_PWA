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


def test_todos_los_municipios_autorizados():
    casos = [
        # (Entrada, Esperado)
        ("mahates", "MAHATES"),
        ("mahate", "MAHATES"),
        ("turbana", "TURBANA"),
        ("turbaco", "TURBACO"),
        ("barranco de loba", "BARRANCO DE LOBA"),
        ("barranco", "BARRANCO DE LOBA"),
        ("san jacinto del cauca", "SAN JACINTO DEL CAUCA"),
        ("san jacinto", "SAN JACINTO DEL CAUCA"),
        ("jacinto del cauca", "SAN JACINTO DEL CAUCA"),
        ("calamar", "CALAMAR"),
        ("morales", "MORALES"),
        ("morale", "MORALES"),
        ("santa rosa del sur", "SANTA ROSA DEL SUR"),
        ("santa rosa", "SANTA ROSA DEL SUR"),
        ("sta rosa del sur", "SANTA ROSA DEL SUR"),
        ("arenal", "ARENAL"),
        ("soplaviento", "SOPLAVIENTO"),
        ("sopla viento", "SOPLAVIENTO")
    ]

    for entrada, esperado in casos:
        # Probando vía campo TERRITORIO
        f1 = FichaCaracterizacion.model_validate({"TERRITORIO": entrada})
        d1 = f1.to_canonical_dict()
        assert d1["TERRITORIO"] == esperado, f"Para '{entrada}' en TERRITORIO se esperaba '{esperado}', obtenido '{d1['TERRITORIO']}'"
        assert d1["Municipio"] == esperado, f"Regla Municipio=Territorio falló para '{entrada}'"
        row1 = f1.to_ordered_row()
        assert row1[1] == esperado, f"Fila col 2 (TERRITORIO) falló para '{entrada}'"
        assert row1[9] == esperado, f"Fila col 10 (Municipio) falló para '{entrada}'"

        # Probando vía campo Municipio (fallback)
        f2 = FichaCaracterizacion.model_validate({"Municipio": entrada})
        d2 = f2.to_canonical_dict()
        assert d2["Municipio"] == esperado, f"Para '{entrada}' en Municipio se esperaba '{esperado}', obtenido '{d2['Municipio']}'"
        assert d2["TERRITORIO"] == esperado, f"Fallback de Territorio desde Municipio falló para '{entrada}'"


def test_casilla_34_vida_sexual():
    col_vida_sexual = "¿Has iniciado tu vida sexual?"

    # 1. Variaciones de clave generadas por OCR
    claves_variantes = [
        "¿Has iniciado tu vida sexual?",
        "¿Has iniciado tus relaciones sexuales?",
        "¿Has iniciado tu relacion sexual?",
        "Has empezado tu relacion sexual",
        "empezado tu relacion sexual",
        "iniciaste tu vida sexual",
        "iniciaste relaciones sexuales",
        "iniciado tu vida sexual",
        "vida sexual",
        "iniciado vida sexual"
    ]
    for k in claves_variantes:
        f = FichaCaracterizacion.model_validate({k: "si"})
        d = f.to_canonical_dict()
        assert d[col_vida_sexual] == "SI", f"Fallo al mapear clave '{k}' a SI"
        # En fila ordenada col 34 (índice 33)
        row = f.to_ordered_row()
        assert row[33] == "SI", f"En fila ordenada col 34 (índice 33) falló para clave '{k}'"

    # 2. Regla de coherencia: Si marcó SIEMPRE o CASI SIEMPRE en condón, se infiere SI en vida sexual
    f_condon = FichaCaracterizacion.model_validate({
        "¿Has iniciado tu vida sexual?": "no",
        "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?": "siempre"
    })
    d_condon = f_condon.to_canonical_dict()
    assert d_condon[col_vida_sexual] == "SI", "Inconsistencia: Si usa condón en relaciones, vida sexual DEBE ser SI"
    assert f_condon.to_ordered_row()[33] == "SI"

    # 3. Regla de coherencia: Si indicó método anticonceptivo (ej. YADEL), se infiere SI en vida sexual
    f_metodo = FichaCaracterizacion.model_validate({
        "¿Has iniciado tu vida sexual?": "no",
        "¿Cual?_3": "YADEL"
    })
    d_metodo = f_metodo.to_canonical_dict()
    assert d_metodo[col_vida_sexual] == "SI", "Inconsistencia: Si tiene método anticonceptivo activo, vida sexual DEBE ser SI"
    assert f_metodo.to_ordered_row()[33] == "SI"

    # 4. Caso genuino NO: No ha iniciado vida sexual y sin condón ni anticonceptivo
    f_no = FichaCaracterizacion.model_validate({
        "¿Has iniciado tu vida sexual?": "no"
    })
    assert f_no.to_canonical_dict()[col_vida_sexual] == "NO"
    assert f_no.to_ordered_row()[33] == "NO"


def test_coherencia_casillas_34_a_43():
    """Valida exhaustivamente consistencia, mapeo difuso y coherencia lógica de columnas 34 a 43."""
    # 1. Casilla 34 y 35: Si no ha iniciado vida sexual, casilla 35 debe limpiarse (vacía)
    f_no_sex = FichaCaracterizacion.model_validate({
        "¿Has iniciado tu vida sexual?": "no",
        "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?": "nunca"
    })
    d_no_sex = f_no_sex.to_canonical_dict()
    assert d_no_sex["¿Has iniciado tu vida sexual?"] == "NO"
    assert d_no_sex["Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?"] == "", \
        "Inconsistencia: Si vida sexual es NO, la casilla de condón en relaciones debe estar vacía"

    # Si casilla 35 tiene SIEMPRE o CASI SIEMPRE pero no se especificó vida sexual, se infiere SI
    f_siempre = FichaCaracterizacion.model_validate({
        "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?": "siempre"
    })
    assert f_siempre.to_canonical_dict()["¿Has iniciado tu vida sexual?"] == "SI"

    # 2. Casilla 36 y 37: Métodos anticonceptivos
    # Variantes de clave
    for k_var in ["conoce algun metodo anticonceptivo", "conoce metodo anticonceptivo", "metodo anticonceptivo"]:
        f = FichaCaracterizacion.model_validate({k_var: "si"})
        assert f.to_canonical_dict()["¿Conoces algún método anticonceptico?"] == "SI"

    for k_var in ["cual metodo", "cual_3", "que metodo anticonceptivo", "nombre metodo anticonceptivo"]:
        f = FichaCaracterizacion.model_validate({"¿Conoces algún método anticonceptico?": "si", k_var: "pastillas"})
        assert f.to_canonical_dict()["¿Cual?_3"] == "PASTILLAS"

    # Coherencia: Si tiene método pero casilla 36 venía vacía o NO -> infiere SI
    f_met = FichaCaracterizacion.model_validate({
        "¿Conoces algún método anticonceptico?": "no",
        "¿Cual?_3": "IMPLANTE"
    })
    d_met = f_met.to_canonical_dict()
    assert d_met["¿Conoces algún método anticonceptico?"] == "SI"
    assert d_met["¿Cual?_3"] == "IMPLANTE"

    # Coherencia: Si casilla 36 es NO genuino -> limpia casilla 37
    f_no_met = FichaCaracterizacion.model_validate({
        "¿Conoces algún método anticonceptico?": "no",
        "¿Cual?_3": ""
    })
    assert f_no_met.to_canonical_dict()["¿Conoces algún método anticonceptico?"] == "NO"
    assert f_no_met.to_canonical_dict()["¿Cual?_3"] == ""

    # 3. Casilla 38: Embarazo adolescente
    for k_var in ["embarazo en adolescentes", "embarazos adolescentes", "caso cercano de embarazo"]:
        f = FichaCaracterizacion.model_validate({k_var: "si"})
        assert f.to_canonical_dict()["¿Has vivido o conoces algún caso cercano de embarazo adolescente?"] == "SI"

    # 4. Casilla 39 y 40: Preservativos EPS y desambiguación vs Col 22
    f_ambas = FichaCaracterizacion.model_validate({
        "¿Has asistido al médico en el último año?": "si",
        "¿Cuándo fue la última vez?": "enero 2026",
        "¿Te han entregado preservativos en la EPS o institución de salud?": "si",
        "¿Cuándo fue la ultima vez?": "junio 2026"
    })
    d_ambas = f_ambas.to_canonical_dict()
    row_ambas = f_ambas.to_ordered_row()
    # Col 22 (médico, índice 21)
    assert d_ambas["¿Cuándo fue la última vez?"] == "ENERO 2026"
    assert row_ambas[21] == "ENERO 2026"
    # Col 40 (preservativos, índice 39)
    assert d_ambas["¿Cuándo fue la ultima vez?"] == "JUNIO 2026"
    assert row_ambas[39] == "JUNIO 2026"

    # Si casilla 39 es NO -> casilla 40 debe quedar vacía
    f_no_pres = FichaCaracterizacion.model_validate({
        "¿Te han entregado preservativos en la EPS o institución de salud?": "no",
        "¿Cuándo fue la ultima vez?": "hace un mes"
    })
    d_no_pres = f_no_pres.to_canonical_dict()
    assert d_no_pres["¿Te han entregado preservativos en la EPS o institución de salud?"] == "NO"
    assert d_no_pres["¿Cuándo fue la ultima vez?"] == "", "Inconsistencia: Si no le han entregado preservativos, la fecha debe ser vacía"

    # Si casilla 40 tiene fecha pero casilla 39 venía vacía -> infiere SI
    f_fecha_pres = FichaCaracterizacion.model_validate({
        "¿Cuándo fue la ultima vez?": "febrero 2026"
    })
    assert f_fecha_pres.to_canonical_dict()["¿Te han entregado preservativos en la EPS o institución de salud?"] == "SI"

    # 5. Casilla 41: Temas de interés
    for k_var in ["temas que te gustaria aprender", "temas de interes", "tema a aprender"]:
        f = FichaCaracterizacion.model_validate({k_var: "vih, sifilis"})
        assert "VIH" in f.to_canonical_dict()["¿Qué tema te gustaria aprender o entender mejor?"]

    # 6. Casilla 42 y 43: Espacios de diálogo y Por qué
    for k_var in ["espacios para dialogar", "espacios de dialogo", "mas espacios para dialogar"]:
        f = FichaCaracterizacion.model_validate({k_var: "si"})
        assert f.to_canonical_dict()["¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?"] == "SI"

    for k_var in ["porque", "motivo", "razon"]:
        f = FichaCaracterizacion.model_validate({k_var: "para estar mas informados"})
        assert f.to_canonical_dict()["¿Por que?"] == "PARA ESTAR MAS INFORMADOS"

    # Coherencia: Si casilla 42 viene vacía pero en Por qué hay una justificación -> infiere SI
    f_esp_inf = FichaCaracterizacion.model_validate({
        "¿Por que?": "porque nos ayuda a cuidarnos mejor"
    })
    d_esp_inf = f_esp_inf.to_canonical_dict()
    assert d_esp_inf["¿Te gustaria que en tu institución educativa se hicieran mas espacios para dialogar de estos temas?"] == "SI"
    assert d_esp_inf["¿Por que?"] == "PORQUE NOS AYUDA A CUIDARNOS MEJOR"


def test_todas_las_dependencias_condicionales_anti_alucinacion():
    """Valida que si una pregunta principal es NO, sus campos dependientes se limpien a vacío sin alucinación."""
    # Entrada simulando alucinaciones del OCR donde el usuario marcó NO pero el modelo inventó respuestas
    raw_alucinado = {
        # 1. Discapacidad: marcó NO pero la IA inventó VISUAL
        "¿Tienes alguna condición de discapacidad?": "no",
        "¿Cual?": "visual",
        # 2. Enfermedad: marcó NO pero la IA inventó ASMA
        "¿Tienes antecedentes de alguna enfermedad personal o familiar importante?": "no",
        "¿Cual?_1": "asma",
        # 3. Médico: marcó NO pero la IA inventó una fecha
        "¿Has asistido al médico en el último año?": "no",
        "¿Cuándo fue la última vez?": "hace un mes",
        # 4. Cigarrillo: marcó NO pero la IA inventó frecuencia
        "¿Consumes o has consumido cigarrillo o vapeador?": "no",
        "Cada cuánto?": "diario",
        # 5. Alcohol: marcó NO pero la IA inventó fines de semana
        "¿Consumes o has consumido alcohol?": "no",
        "Cada cuánto?_1": "fines de semana",
        # 6. Sustancias: marcó NO pero la IA inventó marihuana
        "¿Has consumido alguna sustancia psicoactiva?": "no",
        "¿Cual?_2": "marihuana",
        # 7. Vida sexual: marcó NO pero la IA inventó condón nunca
        "¿Has iniciado tu vida sexual?": "no",
        "Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?": "nunca",
        # 8. Métodos anticonceptivos: marcó NO pero la IA inventó pastillas
        "¿Conoces algún método anticonceptico?": "no",
        "¿Cual?_3": "",
        # 9. Preservativos EPS: marcó NO pero la IA inventó fecha
        "¿Te han entregado preservativos en la EPS o institución de salud?": "no",
        "¿Cuándo fue la ultima vez?": "enero 2026"
    }

    f = FichaCaracterizacion.model_validate(raw_alucinado)
    d = f.to_canonical_dict()

    # Verificar que el backend limpió absolutamente todas las respuestas secundarias
    assert d["¿Tienes alguna condición de discapacidad?"] == "NO"
    assert d["¿Cual?"] == "", "Alucinación en discapacidad no fue limpiada"

    assert d["¿Tienes antecedentes de alguna enfermedad personal o familiar importante?"] == "NO"
    assert d["¿Cual?_1"] == "", "Alucinación en enfermedad no fue limpiada"

    assert d["¿Has asistido al médico en el último año?"] == "NO"
    assert d["¿Cuándo fue la última vez?"] == "", "Alucinación en fecha médico no fue limpiada"

    assert d["¿Consumes o has consumido cigarrillo o vapeador?"] == "NO"
    assert d["Cada cuánto?"] == "", "Alucinación en frecuencia cigarrillo no fue limpiada"

    assert d["¿Consumes o has consumido alcohol?"] == "NO"
    assert d["Cada cuánto?_1"] == "", "Alucinación en frecuencia alcohol no fue limpiada"

    assert d["¿Has consumido alguna sustancia psicoactiva?"] == "NO"
    assert d["¿Cual?_2"] == "", "Alucinación en sustancia psicoactiva no fue limpiada"

    assert d["¿Has iniciado tu vida sexual?"] == "NO"
    assert d["Si respondiste Si ¿Usas condón o preservativo en tus relaciones sexuales?"] == "", "Alucinación en condón no fue limpiada"

    assert d["¿Conoces algún método anticonceptico?"] == "NO"
    assert d["¿Cual?_3"] == "", "Alucinación en método anticonceptivo no fue limpiada"

    assert d["¿Te han entregado preservativos en la EPS o institución de salud?"] == "NO"
    assert d["¿Cuándo fue la ultima vez?"] == "", "Alucinación en fecha preservativos no fue limpiada"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    test_schema_columns_count()
    test_uppercase_normalization()
    test_mayo_2026_and_date_handling()
    test_encuestadores_autorizados()
    test_estandarizacion_catalogos_completos()
    test_todos_los_municipios_autorizados()
    test_campos_sin_espacios_telefono_e_id()
    test_menor_de_18_es_ti()
    test_fuzzy_matching_vocabulario()
    test_uso_condon_y_dicotomicas()
    test_casilla_34_vida_sexual()
    test_casilla_39_y_no_alucinacion_fecha()
    test_temas_interes_separador_coma()
    test_coherencia_casillas_34_a_43()
    test_todas_las_dependencias_condicionales_anti_alucinacion()
    print("OK: Todas las pruebas de esquema, municipios, dependencias anti-alucinacion y normalizacion pasaron exitosamente.")
