"""
Pruebas unitarias de regresión para las correcciones de auditoría:
- Thread safety y rendimiento de I/O en ParticipantCache
- Sincronización thread-safe en VocabularyLearner
- Caché de verificación de pestañas en GoogleSheetsService
- Verificación SSL obligatoria en VisionService
- Integridad de Service Worker y scripts frontend
"""

import sys
import tempfile
import threading
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from participant_cache import ParticipantCache
from vocabulary_learner import VocabularyLearner
from sheets_service import GoogleSheetsService
from vision_service import VisionService, PipelineRateLimiter, pipeline_rate_limiter


def test_participant_cache_thread_safety_and_batch_io():
    """Valida la concurrencia y persistencia eficiente de ParticipantCache sin métodos CSV."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_participantes.json"
        cache = ParticipantCache(cache_file=cache_file)

        # Verificar que el método obsoleto CSV fue totalmente eliminado
        assert not hasattr(cache, "importar_desde_csv")

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


def test_pipeline_rate_limiter_and_qwen_removal():
    """Valida la disciplina de throttling de 4s del Rate Limiter y la remoción total de Qwen."""
    import time
    # 1. Validar que la configuración global de rate limit sea de al menos 4.0s
    assert pipeline_rate_limiter.min_interval >= 4.0, "El intervalo mínimo debe ser al menos 4.0 segundos"

    # 2. Validar funcionamiento y cálculo de espera con un limiter de prueba rápido (0.15s)
    limiter = PipelineRateLimiter(min_interval_seconds=0.15)
    t0 = time.time()
    espera1 = limiter.esperar_turno()
    assert espera1 == 0.0

    # Llamada consecutiva inmediata: debe esperar el remanente
    espera2 = limiter.esperar_turno()
    t1 = time.time()
    assert espera2 > 0.0
    assert (t1 - t0) >= 0.14, f"Se esperaba al menos 0.14s transcurridos, pero fue {t1 - t0}"

    # 3. Concurrencia de múltiples hilos espaciados
    hilos = []
    tiempos = []

    def peticion():
        t = limiter.esperar_turno()
        tiempos.append(t)

    for _ in range(3):
        h = threading.Thread(target=peticion)
        hilos.append(h)
        h.start()

    for h in hilos:
        h.join()

    assert len(tiempos) == 3

    # 4. Verificar que Qwen fue completamente purgado del código y render.yaml
    vision_file = Path(__file__).resolve().parent.parent / "backend" / "vision_service.py"
    render_file = Path(__file__).resolve().parent.parent / "render.yaml"

    assert "qwen" not in vision_file.read_text(encoding="utf-8").lower(), "Qwen no debe existir en vision_service.py"
    assert "qwen" not in render_file.read_text(encoding="utf-8").lower(), "Qwen no debe existir en render.yaml"


if __name__ == "__main__":
    test_participant_cache_thread_safety_and_batch_io()
    print("[PASS] test_participant_cache_thread_safety_and_batch_io")
    test_vocabulary_learner_thread_safety()
    print("[PASS] test_vocabulary_learner_thread_safety")
    test_sheets_service_tab_cache()
    print("[PASS] test_sheets_service_tab_cache")
    test_vision_service_ssl_security()
    print("[PASS] test_vision_service_ssl_security")
    test_frontend_scripts_integrity()
    print("[PASS] test_frontend_scripts_integrity")
    test_pipeline_rate_limiter_and_qwen_removal()
    print("[PASS] test_pipeline_rate_limiter_and_qwen_removal")
    print("Todas las pruebas de auditoría pasaron exitosamente.")
