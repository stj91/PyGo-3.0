"""Endpoints de recomendaciones y retroalimentación (paquete 08)."""

import re
from functools import wraps
from typing import Optional, Tuple

from core.auth import require_self, require_user
from core.errors import NotFoundError, ValidationError
from core.http import endpoint, parse_json_body, query_param

from . import hibrido, registro
from .eventos import service as eventos

_RECOMENDACION_ID = re.compile(r"^r-[0-9a-f-]{36}\Z")
_ENTERO = re.compile(r"^-?[0-9]{1,6}\Z")
ACCIONES = frozenset({"mostrada", "clic", "descartada"})
MOTIVOS = frozenset({"ya_lo_conozco", "no_me_interesa", "no_es_mi_nivel", "otro"})


def _limite(valor: Optional[str]) -> Optional[int]:
    """`limite` de la query como entero, `None` si falta; 400 si no es un entero."""
    if valor is None:
        return None
    if not _ENTERO.match(valor):
        raise ValidationError("`limite` debe ser un número entero.", campos=["limite"])
    return int(valor)


def validar_retroalimentacion(cuerpo: dict) -> Tuple[str, str, Optional[str]]:
    """(recomendacion_id, accion, motivo) del cuerpo, o `ValidationError`. **Pura.**"""
    recomendacion_id = cuerpo.get("recomendacion_id")
    if not isinstance(recomendacion_id, str) or not _RECOMENDACION_ID.match(recomendacion_id):
        raise ValidationError("`recomendacion_id` no es válido.", campos=["recomendacion_id"])
    accion = cuerpo.get("accion")
    if not isinstance(accion, str) or accion not in ACCIONES:
        raise ValidationError("`accion` debe ser mostrada, clic o descartada.", campos=["accion"])
    motivo = cuerpo.get("motivo")
    if motivo is not None:
        if accion != "descartada":
            raise ValidationError("`motivo` solo se admite al descartar.", campos=["motivo"])
        if not isinstance(motivo, str) or motivo not in MOTIVOS:
            raise ValidationError("`motivo` no es válido.", campos=["motivo"])
    return recomendacion_id, accion, motivo


def _registrar_retroalimentacion(usuario_id: str, recomendacion_id: str, accion: str,
                                 motivo: Optional[str]) -> None:
    """Aplica la transición y registra el evento. 404 si la recomendación no es del usuario."""
    fila = registro.de_usuario(recomendacion_id, usuario_id)
    if fila is None:
        raise NotFoundError("Recomendación no encontrada.")
    nuevo = registro.siguiente_estado(fila.get("estado"), accion)
    if nuevo is not None:
        registro.cambiar_estado(recomendacion_id, usuario_id, nuevo, motivo if nuevo == "descartada" else None)
    datos = {"recomendacion_id": recomendacion_id, "posicion": fila.get("posicion"),
             **({"motivo": motivo} if motivo else {})}
    eventos.registrar_servidor(usuario_id, f"recomendacion_{accion}", datos=datos)


@endpoint("GET")
def recomendaciones_cursos(request):
    """GET /api/recomendaciones/cursos?usuario_id=&limite=. `require_self(usuario_id)`.

    Respuesta: 00-arquitectura.md §6.2.
    """
    require_user(request)
    usuario_id = query_param(request, "usuario_id")
    if not usuario_id:
        raise ValidationError("Falta el parámetro usuario_id.", campos=["usuario_id"])
    usuario = require_self(request, usuario_id)
    limite = _limite(query_param(request, "limite"))
    return hibrido.recomendar_cursos(str(usuario["id"]), limite)


def _sin_cuerpo_en_204(vista):
    """Un 204 no lleva cuerpo (RFC 9110 §15.3.5); `@endpoint` siempre serializa uno."""
    @wraps(vista)
    def envuelta(request, *args, **kwargs):
        respuesta = vista(request, *args, **kwargs)
        if respuesta.status_code == 204:
            respuesta.content = b""
            if "Content-Type" in respuesta:
                del respuesta["Content-Type"]
        return respuesta
    return envuelta


@_sin_cuerpo_en_204
@endpoint("POST")
def retroalimentacion(request):
    """POST /api/retroalimentacion. `require_user`; la recomendación debe ser del llamante. Responde 204.

    Cuerpo: `{recomendacion_id, accion: mostrada|clic|descartada, motivo?}`. Una
    recomendación inexistente o de otro usuario responde 404 (no se distingue).
    """
    usuario = require_user(request)
    recomendacion_id, accion, motivo = validar_retroalimentacion(parse_json_body(request))
    _registrar_retroalimentacion(str(usuario["id"]), recomendacion_id, accion, motivo)
    return {}, 204
