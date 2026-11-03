"""Pruebas de extremo a extremo en navegador (Playwright, opt-in con E2E=1).

El paquete existe para que `python -m unittest discover -s tests` encuentre
`test_demo_e2e.py` y lo marque como omitido (skip) cuando falta Playwright o
la variable E2E no vale "1"; asi la suite normal sigue rapida y en verde.
"""
