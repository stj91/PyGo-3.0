"""POST /api/eventos."""

from core.auth import require_user
from core.http import endpoint, ok, parse_json_body

from . import limite, service


@endpoint("POST")
def registrar(request):
    """POST /api/eventos

    `require_user`; el `usuario_id` del cuerpo debe ser el llamante.
    Respuesta: `201 {success, evento: {id, tipo, fecha}}`.
    """
    usuario = require_user(request)
    limite.exigir_cupo(usuario["id"])
    limite.exigir_tamano(request)
    evento = service.registrar_cliente(parse_json_body(request), usuario)
    return ok(evento=evento), 201
