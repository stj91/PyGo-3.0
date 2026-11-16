"""POST /api/cursos/<curso_id>/inscripcion."""

from core.auth import require_user
from core.http import endpoint, ok, parse_json_body

from . import service


@endpoint("POST")
def inscribirse(request, curso_id):
    """POST /api/cursos/<curso_id>/inscripcion

    `require_user`. Cuerpo `{origen?, recomendacion_id?}`. Respuesta
    `201 {success, inscripcion}`, o `200` con la existente si ya estaba inscrito.
    """
    usuario = require_user(request)
    cuerpo = parse_json_body(request)
    inscripcion, nueva = service.inscribir_o_recuperar(
        str(usuario["id"]), curso_id, cuerpo.get("origen"), cuerpo.get("recomendacion_id")
    )
    return ok(inscripcion=inscripcion, nueva=nueva), (201 if nueva else 200)
