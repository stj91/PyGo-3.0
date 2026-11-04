"""Vista HTTP del estado adaptativo."""

from core.auth import require_self
from core.http import endpoint, ok

from . import service


@endpoint("GET")
def estado(request, usuario_id):
    """GET /api/adaptativo/estado/<usuario_id>

    Expone el nivel del usuario, así que exige ser ese usuario.
    """
    require_self(request, usuario_id)
    return ok(configuracion=service.obtener_estado(usuario_id))
