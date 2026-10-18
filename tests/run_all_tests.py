"""
Ejecutor integral de pruebas unitarias del proyecto.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import test_schema
import test_test_schema
import test_anexo17_schema
import test_image_orientation
import test_audit_fixes

def run():
    print("--- 1. Ejecutando pruebas de test_schema.py ---")
    for attr in dir(test_schema):
        if attr.startswith("test_"):
            func = getattr(test_schema, attr)
            if callable(func):
                func()
                print(f"  [PASS] {attr}")

    print("\n--- 2. Ejecutando pruebas de test_test_schema.py ---")
    import inspect, tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        for attr in dir(test_test_schema):
            if attr.startswith("test_"):
                func = getattr(test_test_schema, attr)
                if callable(func):
                    sig = inspect.signature(func)
                    if "tmp_path" in sig.parameters:
                        func(tmp_path=tmp_path)
                    else:
                        func()
                    print(f"  [PASS] {attr}")

    print("\n--- 3. Ejecutando pruebas de test_image_orientation.py ---")
    for attr in dir(test_image_orientation):
        if attr.startswith("test_"):
            func = getattr(test_image_orientation, attr)
            if callable(func):
                func()

    print("\n--- 4. Ejecutando pruebas de test_audit_fixes.py ---")
    for attr in dir(test_audit_fixes):
        if attr.startswith("test_"):
            func = getattr(test_audit_fixes, attr)
            if callable(func):
                func()
                print(f"  [PASS] {attr}")

    print("\n--- 5. Ejecutando pruebas de test_anexo17_schema.py ---")
    import unittest
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_anexo17_schema)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    assert result.wasSuccessful(), "Las pruebas de test_anexo17_schema fallaron"

    print("\n--- 6. Ejecutando pruebas de test_audit_part2_fixes.py (Auditoría Profunda Parte 2) ---")
    import test_audit_part2_fixes
    suite_part2 = unittest.defaultTestLoader.loadTestsFromModule(test_audit_part2_fixes)
    runner_part2 = unittest.TextTestRunner(verbosity=2)
    result_part2 = runner_part2.run(suite_part2)
    assert result_part2.wasSuccessful(), "Las pruebas de test_audit_part2_fixes fallaron"

    print("\n=========================================")
    print("TODAS LAS PRUEBAS COMPLETADAS CON ÉXITO (VERDE)")
    print("=========================================")

if __name__ == "__main__":
    run()
