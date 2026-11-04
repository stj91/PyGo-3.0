"""Vistas HTTP de autenticación.

Endpoints deliberadamente anónimos: son la puerta de entrada, exigir token aquí
dejaría fuera a todo el mundo.
"""

from core.http import endpoint, ok, parse_json_body

from . import service


@endpoint("POST")
def registro(request):
    """POST /api/auth/registro"""
    resultado = service.registrar_usuario(parse_json_body(request))
    return ok(**resultado), 201


@endpoint("POST")
def login(request):
    """POST /api/auth/login"""
    return ok(**service.iniciar_sesion(parse_json_body(request)))
