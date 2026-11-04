"""Vista HTTP de evaluación de módulos."""

from core.auth import require_self
from core.http import endpoint, parse_json_body

from . import service


@endpoint("POST")
def evaluar_modulo(request):
    """POST /api/evaluaciones/evaluar-modulo

    Registra intentos y progreso del usuario, así que exige ser ese usuario.
    La respuesta no lleva clave `success`: se conserva el contrato original.
    """
    datos = parse_json_body(request)

    if datos.get("usuario_id"):
        require_self(request, datos["usuario_id"])

    return service.evaluar_modulo(datos)
