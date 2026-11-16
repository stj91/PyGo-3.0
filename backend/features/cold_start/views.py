"""Vistas HTTP de la evaluación inicial."""

from core.auth import require_self, require_user
from core.http import endpoint, ok, parse_json_body

from . import service


@endpoint("POST")
def evaluar(request):
    """POST /api/cold-start/evaluar

    Escribe el nivel y las preferencias del usuario, así que exige ser ese
    usuario: con sólo el id en el cuerpo, cualquiera podría reasignar el nivel
    de otra persona. Sin sesión es 401 aunque falte el `usuario_id`.
    """
    require_user(request)
    datos = parse_json_body(request)

    if datos.get("usuario_id"):
        require_self(request, datos["usuario_id"])

    return ok(**service.evaluar(datos))


@endpoint("GET")
def preguntas(request):
    """GET /api/cold-start/preguntas

    Preguntas del diagnóstico inicial con sus opciones, **sin `es_correcta`**.
    Exige sesión.
    """
    require_user(request)
    return ok(preguntas=service.preguntas())
