"""Vista HTTP de configuración de usuario."""

from core.auth import require_self
from core.http import endpoint, ok, parse_json_body

from . import service


@endpoint("PUT", "PATCH")
def configuracion(request, usuario_id):
    """PUT /api/usuarios/configuracion/<usuario_id>

    Escribe el perfil y las preferencias, así que exige ser ese usuario. En el
    backend Node este endpoint no comprobaba nada: cualquiera podía sobrescribir
    la configuración de otra cuenta conociendo su id.
    """
    require_self(request, usuario_id)
    return ok(**service.actualizar_configuracion(usuario_id, parse_json_body(request)))
