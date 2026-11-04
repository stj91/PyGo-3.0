#!/usr/bin/env python
"""Utilidad de línea de comandos de Django para el backend PyGo."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

#: Puerto por defecto: 5001, el que espera el frontend (ver
#: frontend/src/services/api.js). No se usa el 5000 porque en macOS lo ocupa el
#: receptor de AirPlay (ControlCenter), que responde 403 sin cabeceras CORS.
#: Siempre en loopback: la API no debe quedar accesible desde otras máquinas.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "5001"


def _default_addrport(argv: list) -> list:
    """Añade `127.0.0.1:<PORT>` a `runserver` si no se indicó dirección.

    Evita que Django use su 8000 por defecto, que no coincide con la URL que
    espera el frontend.
    """
    if len(argv) < 2 or argv[1] != "runserver":
        return argv

    # Cualquier argumento posicional tras `runserver` ya es una dirección.
    if any(not arg.startswith("-") for arg in argv[2:]):
        return argv

    port = os.environ.get("PORT", DEFAULT_PORT)
    return [*argv, f"{DEFAULT_HOST}:{port}"]


def main() -> None:
    sys.path.insert(0, str(BASE_DIR))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pygo.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. ¿Está instalado y activado el entorno virtual? "
            "Instala las dependencias con: pip install -r requirements.txt"
        ) from exc

    execute_from_command_line(_default_addrport(sys.argv))


if __name__ == "__main__":
    main()
