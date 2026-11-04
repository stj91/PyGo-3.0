"""Vistas HTTP de cursos y lecciones.

Autorización: el contenido del catálogo se sirve sin sesión (igual que el
backend Node, y el frontend no protege esas rutas), pero pedir el avance de un
`usuario_id` concreto exige ser ese usuario. Sin esa comprobación cualquiera
podría leer el progreso de otra persona pasando su id en la query string.
"""

from django.conf import settings

from core.auth import require_self, require_user
from core.http import endpoint, ok, query_param

from . import service


def _gate_contenido(request) -> None:
    """Exige sesión para leer contenido sólo si está configurado así."""
    if settings.REQUIRE_AUTH_FOR_CONTENT:
        require_user(request)


@endpoint("GET")
def listar_cursos(request):
    """GET /api/cursos[?usuario_id=...]"""
    usuario_id = query_param(request, "usuario_id")

    if usuario_id:
        require_self(request, usuario_id)
    else:
        _gate_contenido(request)

    return ok(cursos=service.obtener_cursos(usuario_id))


@endpoint("GET")
def detalle_curso(request, curso_id):
    """GET /api/cursos/<curso_id>"""
    _gate_contenido(request)
    return ok(curso=service.obtener_curso(curso_id))


@endpoint("GET")
def detalle_leccion(request, leccion_id):
    """GET /api/lecciones/<leccion_id> y GET /api/cursos/lecciones/<leccion_id>"""
    _gate_contenido(request)
    return ok(leccion=service.obtener_leccion(leccion_id))
