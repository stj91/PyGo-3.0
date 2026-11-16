"""Endpoints de perfil. Cada uno exige que el usuario autenticado sea el dueño (`require_self`)."""

from typing import Any, List

from core.auth import require_self
from core.errors import ValidationError
from core.http import endpoint, ok, parse_json_body

from .. import config
from ..catalogo import cargar_catalogo
from . import service

#: Máximo de áreas que se pueden declarar.
MAX_AREAS = 4


def validar_areas(valor: Any, areas_validas) -> List[str]:
    """Lista de claves de área sin repetir, en el orden recibido. **Pura.**"""
    if not isinstance(valor, list) or not all(isinstance(a, str) for a in valor):
        raise ValidationError("`areas` debe ser una lista de claves de área.", campos=["areas"])
    claves = list(dict.fromkeys(a.strip() for a in valor))
    if len(claves) > MAX_AREAS:
        raise ValidationError(f"Puedes elegir como mucho {MAX_AREAS} áreas.", campos=["areas"])
    desconocidas = [a for a in claves if a not in areas_validas]
    if desconocidas:
        raise ValidationError("Hay áreas desconocidas.", campos=["areas"])
    return claves


@endpoint("GET")
def detalle(request, usuario_id):
    """GET /api/perfil/<usuario_id>. `require_self`. Respuesta `{success, perfil: PerfilPublico}`."""
    require_self(request, usuario_id)
    return ok(perfil=service.obtener_perfil_publico(usuario_id))


@endpoint("PUT")
def intereses(request, usuario_id):
    """PUT /api/perfil/<usuario_id>/intereses. `require_self`. Cuerpo `{areas: [clave]}`."""
    require_self(request, usuario_id)
    cuerpo = parse_json_body(request)
    claves = validar_areas(cuerpo.get("areas"), cargar_catalogo()["areas"])
    service.guardar_intereses_declarados(
        usuario_id, [(clave, config.PESO_INTERES_DECLARADO) for clave in claves]
    )
    return ok(intereses=claves)
