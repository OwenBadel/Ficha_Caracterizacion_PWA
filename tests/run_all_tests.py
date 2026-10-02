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
import test_image_orientation

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

    print("\n=========================================")
    print("TODAS LAS PRUEBAS COMPLETADAS CON ÉXITO (VERDE)")
    print("=========================================")

if __name__ == "__main__":
    run()
