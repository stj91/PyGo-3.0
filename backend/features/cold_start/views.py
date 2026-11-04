"""Vista HTTP de la evaluación inicial."""

from core.auth import require_self
from core.http import endpoint, ok, parse_json_body

from . import service


@endpoint("POST")
def evaluar(request):
    """POST /api/cold-start/evaluar

    Escribe el nivel y las preferencias del usuario, así que exige ser ese
    usuario: con sólo el id en el cuerpo, cualquiera podría reasignar el nivel
    de otra persona.
    """
    datos = parse_json_body(request)

    if datos.get("usuario_id"):
        require_self(request, datos["usuario_id"])

    return ok(**service.evaluar(datos))
