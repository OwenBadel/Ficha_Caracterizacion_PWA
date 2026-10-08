"""
Pruebas unitarias de regresión para la arquitectura soberana:
- Thread safety y rendimiento de I/O en ParticipantCache
- Sincronización thread-safe en VocabularyLearner
- Caché de verificación de pestañas en GoogleSheetsService
- Verificación SSL obligatoria en VisionService
- Integridad de Service Worker y scripts frontend
- Reconciliación Jaro-Winkler con PATRON MAESTRO y remoción total de Gemini
"""

import sys
import tempfile
import threading
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from participant_cache import (
    ParticipantCache,
    jaro_similarity,
    jaro_winkler_similarity,
    token_jaro_winkler_similarity
)
from vocabulary_learner import VocabularyLearner
from sheets_service import GoogleSheetsService
from vision_service import VisionService


def test_participant_cache_thread_safety_and_batch_io():
    """Valida la concurrencia y persistencia eficiente de ParticipantCache con Jaro-Winkler."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_participantes.json"
        cache = ParticipantCache(cache_file=cache_file)

        # 1. Simular aprendizaje de participantes
        for i in range(50):
            cache.aprender_participante(
                nombre=f"PARTICIPANTE PRUEBA {i}",
                edad="16",
                municipio="MAHATES",
                eapb="MUTUAL SER",
                documento=f"100{i:04d}",
                guardar_inmediato=False
            )
        cache.guardar()

        assert cache.contar() == 50
        assert cache_file.exists()

        # 2. Concurrencia de múltiples hilos
        def worker(idx):
            cache.aprender_participante(
                nombre=f"CONCURRENTE {idx}",
                edad="17",
                municipio="TURBANA",
                eapb="COOSALUD"
            )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cache.contar() == 65
        match = cache.buscar_coincidencia("PARTICIPANTE PRUEBA 10")
        assert match is not None
        assert match["nombre"] == "PARTICIPANTE PRUEBA 10"


def test_jaro_winkler_and_patron_maestro_reconciliation():
    """Valida la matemática de Jaro-Winkler y la reconciliación con PATRON MAESTRO."""
    # 1. Casos de similitud Jaro-Winkler
    # Nombres con variaciones ortográficas típicas en campo
    score1 = token_jaro_winkler_similarity("MAIKOL PEREZ", "MICHAEL PEREZ")
    assert score1 >= 0.80, f"Score insuficiente: {score1}"

    score2 = token_jaro_winkler_similarity("YEISON RODRIGUEZ", "JEYSON RODRIGUEZ")
    assert score2 >= 0.85, f"Score insuficiente: {score2}"

    # Inversión de nombre/apellido: "PEREZ MICHAEL" vs "MICHAEL PEREZ"
    score_inv = token_jaro_winkler_similarity("PEREZ MICHAEL", "MICHAEL PEREZ")
    assert score_inv >= 0.90, f"Token score insuficiente para orden invertido: {score_inv}"

    # 2. Ingesta de PATRON MAESTRO desde CSV con las columnas exactas del usuario
    csv_maestro = """Marca temporal,NOMBRE COMPLETO DE QUIEN DILIGENCIA LA FICHA:,TERRITORIO:,Nombre completo del participante:,Tipo de documento identidad:,Numero de documento identidad:,Edad:,Grado escolar:,Teléfono de contacto:,Dirección de residencia (barrio o vereda):,Municipio:,Zona:,EPS (si tienes):
2026/02/01 10:00:00,PAMELA VERGARA,MAHATES,MICHAEL STEVEN PEREZ,TI,1045678901,15,9°,3001234567,BARRIO EL CARMEN,MAHATES,URBANA,MUTUAL SER
2026/02/01 10:05:00,KAREN TORRES,TURBANA,ANA SOFIA MARTINEZ,TI,1045678902,14,8°,3019876543,SECTOR CENTRO,TURBANA,URBANA,COOSALUD
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_patron.json"
        cache = ParticipantCache(cache_file=cache_file)
        cargados = cache.sincronizar_desde_csv_texto(csv_maestro)
        assert cargados == 2
        assert cache.contar() == 2

        # Reconciliar un test escrito a mano con error ("MAIKOL PEREZ") en MAHATES
        match = cache.buscar_coincidencia("MAIKOL PEREZ", municipio_hint="MAHATES")
        assert match is not None
        assert match["nombre"] == "MICHAEL STEVEN PEREZ"
        assert match["edad"] == "15"
        assert match["municipio"] == "MAHATES"
        assert match["eapb"] == "MUTUAL SER"
        assert match["documento"] == "1045678901"


def test_vocabulary_learner_thread_safety():
    """Valida la sincronización con lock en VocabularyLearner."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vocab_file = Path(tmpdir) / "test_vocab.json"
        learner = VocabularyLearner(cache_path=vocab_file)

        def worker(word):
            learner.aprender_fila({"¿Cual?_3": word, "Dirección de residencia (barrio o vereda)": "CENTRO"})

        threads = [
            threading.Thread(target=worker, args=(f"METODO_{i}",))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert vocab_file.exists()
        assert "¿Cual?_3" in learner.vocabulario


def test_sheets_service_tab_cache():
    """Verifica que GoogleSheetsService mantenga la caché de pestañas inicializadas."""
    service = GoogleSheetsService()
    assert hasattr(service, "_tabs_inicializados")
    assert isinstance(service._tabs_inicializados, set)


def test_sheets_service_pre_and_post_test_tab_routing():
    """Verifica que insertar_test dirija a 'PRE-TEST' y 'POST-TEST' respectivamente."""
    service = GoogleSheetsService()
    llamadas = []
    service._ejecutar_insercion = lambda tab_name, headers, fila, webhook_url, tipo_registro: llamadas.append((tab_name, tipo_registro))

    # Prueba 1: Pre-Test explícito
    fila_pre = ["PRE-TEST", "MICHAEL PEREZ", "15", "MAHATES", "MUTUAL SER"] + ["VERDADERO"] * 9
    service.insertar_test(fila_pre, tipo_evaluacion="PRE-TEST")
    assert llamadas[-1] == ("PRE-TEST", "pre_test")

    # Prueba 2: Post-Test explícito
    fila_post = ["POST-TEST", "MICHAEL PEREZ", "15", "MAHATES", "MUTUAL SER"] + ["VERDADERO"] * 9
    service.insertar_test(fila_post, tipo_evaluacion="POST-TEST")
    assert llamadas[-1] == ("POST-TEST", "post_test")

    # Prueba 3: Post-Test deducido por valor en fila sin override
    llamadas.clear()
    service.insertar_test(fila_post, tipo_evaluacion=None)
    assert llamadas[-1] == ("POST-TEST", "post_test")

    # Prueba 4: Ficha de Caracterización -> Respuestas de formulario 1
    fila_ficha = ["VALOR"] * 43
    service.insertar_encuesta(fila_ficha)
    assert llamadas[-1][0] == "Respuestas de formulario 1"



def test_vision_service_ssl_security():
    """Verifica que ningún cliente HTTP en vision_service desactive la verificación SSL."""
    vision_file = Path(__file__).resolve().parent.parent / "backend" / "vision_service.py"
    contenido = vision_file.read_text(encoding="utf-8")
    assert "verify=False" not in contenido, "Vulnerabilidad detectada: verify=False encontrado en vision_service.py"


def test_frontend_scripts_integrity():
    """Verifica la integridad de app.js y sw.js."""
    base_dir = Path(__file__).resolve().parent.parent
    sw_file = base_dir / "frontend" / "sw.js"
    app_file = base_dir / "frontend" / "js" / "app.js"

    sw_text = sw_file.read_text(encoding="utf-8")
    app_text = app_file.read_text(encoding="utf-8")

    # sw.js debe incluir ignoreSearch para soportar cache busting
    assert "ignoreSearch: true" in sw_text
    assert "Ing." not in sw_text, "Directiva violada: prefijo Ing. en sw.js"

    # app.js debe tener implementada la función cargarResumenParticipantes
    assert "function cargarResumenParticipantes" in app_text


def test_openrouter_removed_and_gemini_rate_limited():
    """Verifica que OpenRouter permanezca purgado y Gemini cuente con rate limiter de seguridad."""
    vision_file = Path(__file__).resolve().parent.parent / "backend" / "vision_service.py"
    contenido = vision_file.read_text(encoding="utf-8")

    assert "openrouter" not in contenido.lower(), "OpenRouter aún presente en vision_service.py"
    assert "PipelineRateLimiter" in contenido, "PipelineRateLimiter no está configurado en vision_service.py"


def test_gemini_models_and_exponential_backoff():
    """Verifica que gemini-2.5-flash esté removido y que el Exponential Backoff con Jitter funcione ante 503."""
    vision_file = Path(__file__).resolve().parent.parent / "backend" / "vision_service.py"
    contenido = vision_file.read_text(encoding="utf-8")

    # 1. Validación de modelos
    assert "gemini-2.5-flash" not in contenido, "gemini-2.5-flash no debe estar en la lista de modelos de reserva"
    assert "gemini-3.8-flash" in contenido, "gemini-3.8-flash debe estar presente como modelo recomendado"
    assert "gemini-3.5-flash-lite" in contenido, "gemini-3.5-flash-lite debe estar presente"

    # 2. Validación de detección de errores transitorios
    from vision_service import _es_error_transitorio, VisionService

    assert _es_error_transitorio(Exception("503 Service Unavailable")), "503 debe ser transitorio"
    assert _es_error_transitorio(Exception("429 ResourceExhausted")), "429 debe ser transitorio"
    assert _es_error_transitorio(Exception("The service is overloaded")), "overloaded debe ser transitorio"
    assert _es_error_transitorio(Exception("Read timed out")), "timeout debe ser transitorio"
    assert not _es_error_transitorio(Exception("404 Model Not Found")), "404 no debe ser transitorio"

    # 3. Validación de Backoff con Mock
    service = VisionService()

    class MockModelResponse:
        text = '{"status": "ok"}'

    class MockModels:
        def __init__(self):
            self.intentos = 0

        def generate_content(self, model, contents, config):
            self.intentos += 1
            if self.intentos == 1:
                # Simular error 503 en primer intento
                raise RuntimeError("503 Service Unavailable: High server load")
            return MockModelResponse()

    class MockClient:
        models = MockModels()

    # Ejecutar con base_delay mínimo (0.01s) para que el test sea instantáneo
    mock_client = MockClient()
    resultado = service._invocar_gemini_con_backoff(
        client=mock_client,
        contents=["test"],
        models_to_try=["gemini-3.5-flash-lite"],
        config=None,
        descripcion="Test Mock",
        max_reintentos_por_modelo=2,
        base_delay=0.01
    )

    assert resultado == '{"status": "ok"}'
    assert mock_client.models.intentos == 2, f"Se esperaban 2 intentos tras 503, se ejecutaron {mock_client.models.intentos}"


if __name__ == "__main__":
    test_participant_cache_thread_safety_and_batch_io()
    print("[PASS] test_participant_cache_thread_safety_and_batch_io")
    test_jaro_winkler_and_patron_maestro_reconciliation()
    print("[PASS] test_jaro_winkler_and_patron_maestro_reconciliation")
    test_vocabulary_learner_thread_safety()
    print("[PASS] test_vocabulary_learner_thread_safety")
    test_sheets_service_tab_cache()
    print("[PASS] test_sheets_service_tab_cache")
    test_vision_service_ssl_security()
    print("[PASS] test_vision_service_ssl_security")
    test_frontend_scripts_integrity()
    print("[PASS] test_frontend_scripts_integrity")
    test_openrouter_removed_and_gemini_rate_limited()
    print("[PASS] test_openrouter_removed_and_gemini_rate_limited")
    test_gemini_models_and_exponential_backoff()
    print("[PASS] test_gemini_models_and_exponential_backoff")
    print("Todas las pruebas de auditoría pasaron exitosamente.")
