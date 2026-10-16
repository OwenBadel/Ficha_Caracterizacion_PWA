"""
Pruebas Unitarias para el Esquema y Procesamiento del Anexo 17 (Pellízcate con Generación B+).
Autor: Owen Badel Hooker — Ingeniero de Sistemas / Software Architect.
"""

import sys
import unittest
from pathlib import Path

# Asegurar importación desde backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from schema_anexo17 import (
    PrePostTestAnexo17,
    COLUMNAS_ANEXO17,
    ENCABEZADOS_ANEXO17_SHEETS,
    normalizar_opcion_anexo17,
    normalizar_fecha,
    normalizar_municipio
)
from participant_cache import participant_cache


class TestAnexo17Schema(unittest.TestCase):
    """Batería de pruebas automatizadas para el modelo canónico de Anexo 17."""

    def test_columnas_count(self):
        """Verifica exactamente 15 columnas de datos y 16 columnas con Marca temporal para Sheets."""
        self.assertEqual(len(COLUMNAS_ANEXO17), 15)
        self.assertEqual(len(ENCABEZADOS_ANEXO17_SHEETS), 16)
        self.assertEqual(ENCABEZADOS_ANEXO17_SHEETS[0], "Marca temporal")
        self.assertEqual(ENCABEZADOS_ANEXO17_SHEETS[1:], COLUMNAS_ANEXO17)

    def test_normalizacion_tipo_evaluacion(self):
        """Verifica que PRE y POST se normalicen a PRE-TEST o POST-TEST."""
        # Caso PRE-TEST
        d1 = {
            "TIPO DE EVALUACIÓN": "PRE TEST",
            "NOMBRE": "Carlos Rodriguez",
            "MUNICIPIO": "Santa Rosa",
            "EDAD": "16",
        }
        obj1 = PrePostTestAnexo17.model_validate(d1)
        self.assertEqual(obj1.tipo_evaluacion, "PRE-TEST")

        # Caso POST-TEST (POS TEST en los docs Word)
        d2 = {
            "TIPO DE EVALUACIÓN": "POS TES",
            "NOMBRE": "Maria Gomez",
            "MUNICIPIO": "Cartagena",
            "EDAD": "15",
        }
        obj2 = PrePostTestAnexo17.model_validate(d2)
        self.assertEqual(obj2.tipo_evaluacion, "POST-TEST")

    def test_normalizacion_fecha(self):
        """Verifica la estandarización de fechas manuscritas a DD/MM/AAAA."""
        self.assertEqual(normalizar_fecha("16/10/2026"), "16/10/2026")
        self.assertEqual(normalizar_fecha("5-9-2026"), "05/09/2026")
        self.assertEqual(normalizar_fecha("14.10.26"), "14/10/2026")
        self.assertEqual(normalizar_fecha(""), "")

    def test_normalizacion_municipio(self):
        """Verifica coincidencia difusa con los municipios autorizados."""
        self.assertEqual(normalizar_municipio("santa rosa"), "SANTA ROSA DEL SUR")
        self.assertEqual(normalizar_municipio("turbaco"), "TURBACO")
        self.assertEqual(normalizar_municipio("carmen de bolivar"), "EL CARMEN DE BOLIVAR")

    def test_normalizacion_10_preguntas_por_letra(self):
        """Verifica que las opciones a, b, c mapeen exactamente al texto canónico prefijado."""
        p1_a = normalizar_opcion_anexo17(1, "a")
        self.assertEqual(p1_a, "A. UN PLAN SOBRE LO QUE QUIERO LOGRAR EN EL FUTURO")

        p2_b = normalizar_opcion_anexo17(2, "b")
        self.assertEqual(p2_b, "B. DECIR “NO”, ALEJARTE Y BUSCAR AYUDA")

        p3_a = normalizar_opcion_anexo17(3, "a")
        self.assertEqual(p3_a, "A. EL USO CORRECTO DEL CONDÓN")

        p4_c = normalizar_opcion_anexo17(4, "c")
        self.assertEqual(p4_c, "C. CONTÁRSELO A UN ADULTO DE CONFIANZA Y PEDIR AYUDA")

        p5_a = normalizar_opcion_anexo17(5, "a")
        self.assertEqual(p5_a, "A. HABLAR CON ALGUIEN DE CONFIANZA")

        p6_b = normalizar_opcion_anexo17(6, "b")
        self.assertEqual(p6_b, "B. ESCUCHARLO Y BUSCAR INMEDIATAMENTE LA AYUDA DE UN ADULTO")

        p7_a = normalizar_opcion_anexo17(7, "a")
        self.assertEqual(p7_a, "A. EXPRESAR LO QUE PIENSO Y SIENTO CON RESPETO")

        p8_a = normalizar_opcion_anexo17(8, "a")
        self.assertEqual(p8_a, "A. PERSONAS E INSTITUCIONES QUE PUEDEN ORIENTARNOS Y AYUDARNOS")

        p9_b = normalizar_opcion_anexo17(9, "b")
        self.assertEqual(p9_b, "B. SER OBLIGADO A TRABAJAR O VINCULARSE A UN GRUPO ARMADO")

        p10_a = normalizar_opcion_anexo17(10, "a")
        self.assertEqual(p10_a, "A. PENSAR EN LAS CONSECUENCIAS Y PEDIR ORIENTACIÓN")

    def test_cero_alucinaciones_en_blanco(self):
        """Verifica que preguntas sin responder permanezcan como string vacío."""
        self.assertEqual(normalizar_opcion_anexo17(1, ""), "")
        self.assertEqual(normalizar_opcion_anexo17(5, None), "")
        self.assertEqual(normalizar_opcion_anexo17(10, "   "), "")

    def test_modelo_completo_anexo17_y_fila_ordenada(self):
        """Valida que un objeto completo devuelva la fila de 15 valores en el orden exacto."""
        raw_data = {
            "TIPO DE EVALUACIÓN": "PRE-TEST",
            "NOMBRE": "ANDREA CASTILLO",
            "MUNICIPIO": "TURBACO",
            "FECHA": "14/10/2026",
            "EDAD": "14",
            "1. ¿QUÉ ES UN PROYECTO DE VIDA?": "un plan sobre lo que quiero lograr en el futuro",
            "2. SI ALGUIEN QUIERE TOCAR TU CUERPO Y TÚ NO DESEAS, ¿QUÉ PUEDES HACER?": "decir no, alejarte",
            "3. ¿CUÁL AYUDA A PREVENIR UN EMBARAZO Y LAS INFECCIONES DE TRANSMISIÓN SEXUAL?": "el uso correcto del condon",
            "4. ¿QUÉ DEBES HACER SI SUFRES BULLYING O CIBERACOSO?": "c",
            "5. ¿CUÁL ES UNA FORMA SALUDABLE DE MANEJAR UNA EMOCIÓN DIFÍCIL?": "hablar con alguien de confianza",
            "6. SI UN AMIGO DICE QUE NO QUIERE SEGUIR VIVIENDO, ¿QUÉ DEBES HACER?": "b",
            "7. ¿QUÉ SIGNIFICA COMUNICARSE DE MANERA ASERTIVA?": "expresar lo que pienso",
            "8. ¿QUÉ ES UNA RED DE APOYO?": "personas e instituciones",
            "9. ¿CUÁL DE ESTAS SITUACIONES PUEDE AFECTAR LOS DERECHOS DE UN ADOLESCENTE?": "ser obligado a trabajar",
            "10. ANTES DE TOMAR UNA DECISIÓN IMPORTANTE, LO MEJOR ES:": "a"
        }

        test_anexo17 = PrePostTestAnexo17.model_validate(raw_data)
        fila = test_anexo17.to_ordered_row()

        self.assertEqual(len(fila), 15)
        self.assertEqual(fila[0], "PRE-TEST")
        self.assertEqual(fila[1], "ANDREA CASTILLO")
        self.assertEqual(fila[2], "TURBACO")
        self.assertEqual(fila[3], "14/10/2026")
        self.assertEqual(fila[4], "14")
        self.assertTrue(fila[5].startswith("A."))
        self.assertTrue(fila[6].startswith("B."))
        self.assertTrue(fila[7].startswith("A."))
        self.assertTrue(fila[8].startswith("C."))
        self.assertTrue(fila[9].startswith("A."))
        self.assertTrue(fila[10].startswith("B."))
        self.assertTrue(fila[11].startswith("A."))
        self.assertTrue(fila[12].startswith("A."))
        self.assertTrue(fila[13].startswith("B."))
        self.assertTrue(fila[14].startswith("A."))


if __name__ == "__main__":
    unittest.main()
