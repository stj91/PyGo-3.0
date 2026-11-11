"""Vistas HTTP de los catálogos académicos.

Públicas a propósito: los dos desplegables están en la pantalla de registro, que
por definición se ve sin sesión. Exigir token aquí dejaría el formulario vacío y
nadie podría crear una cuenta. No exponen nada sensible: son listas de campus y
de carreras de la universidad.
"""

from core.http import endpoint, ok

from . import service


@endpoint("GET")
def listar_centros(request):
    """GET /api/centros — campus para el desplegable del registro."""
    return ok(centros=service.obtener_centros())


@endpoint("GET")
def listar_carreras(request):
    """GET /api/carreras — carreras para el desplegable del registro."""
    return ok(carreras=service.obtener_carreras())
