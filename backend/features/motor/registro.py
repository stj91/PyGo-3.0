"""Registro de recomendaciones emitidas y su ciclo de vida (paquete 08).

Partes puras (`nuevo_id` aparte): `snapshot`, `siguiente_estado`, `ultima_tanda`.
El resto es acceso a las tablas `recomendaciones` y `eventos` mediante
`core/supabase.py`.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from core import supabase
from core.supabase import eq, in_

from .tipos import Perfil

#: Estado -> {acción: estado nuevo}. Lo que no aparece no cambia el estado.
_TRANSICIONES: Dict[str, Dict[str, str]] = {
    "emitida": {"mostrada": "mostrada", "clic": "clic", "descartada": "descartada", "inscripcion": "aceptada"},
    "mostrada": {"clic": "clic", "descartada": "descartada", "inscripcion": "aceptada"},
    "clic": {"descartada": "descartada", "inscripcion": "aceptada"},
    "descartada": {"inscripcion": "aceptada"},
    "aceptada": {},
}
ACCIONES = frozenset({"mostrada", "clic", "descartada", "inscripcion"})

_COLUMNAS = "id,usuario_id,curso_id,puntuacion,posicion,motor,grupo,origen,explicacion,estado,creada_en"
#: Tope de filas leídas en la ventana de estabilidad (varias tandas de hasta LIMITE_MAXIMO).
_MAX_RECIENTES = 64


# --- Puras ------------------------------------------------------------------


def nuevo_id() -> str:
    """Id de recomendación: `"r-"` + uuid4 (36 caracteres)."""
    return f"r-{uuid.uuid4()}"


def _fecha_iso(valor: Any) -> Optional[str]:
    return valor.isoformat() if isinstance(valor, datetime) else valor


def snapshot(perfil: Perfil) -> dict:
    """Lo que el motor sabía del alumno al recomendar. **Pura.** Sin nombre, email ni datos personales.

    Claves enteras como texto, para que el JSON guardado sea estable.
    """
    return {
        "nivel": perfil.get("nivel"),
        "nivel_asignado": perfil.get("nivel_asignado"),
        "intereses": dict(perfil.get("intereses") or {}),
        "dominio": dict(perfil.get("dominio") or {}),
        "evidencias": dict(perfil.get("evidencias") or {}),
        "cursos_completados": list(perfil.get("cursos_completados") or []),
        "calificacion_por_curso": {
            str(k): v for k, v in (perfil.get("calificacion_por_curso") or {}).items()
        },
        "modulos_en_refuerzo": {
            str(k): list(v) for k, v in (perfil.get("modulos_en_refuerzo") or {}).items()
        },
        "dias_inactivo": perfil.get("dias_inactivo"),
        "calculado_en": _fecha_iso(perfil.get("calculado_en")),
    }


def siguiente_estado(actual: str, accion: str) -> Optional[str]:
    """Estado tras `accion` (`mostrada`|`clic`|`descartada`|`inscripcion`), o `None` si no cambia. **Pura.**"""
    return _TRANSICIONES.get(actual, {}).get(accion)


def ultima_tanda(filas: Sequence[dict]) -> List[dict]:
    """Filas de la emisión más reciente (mismo `creada_en`), ordenadas por `posicion`. **Pura.**

    Todas las filas de un mismo `registrar` comparten `creada_en`: van en un
    único INSERT y `now()` es el de la transacción.
    """
    if not filas:
        return []
    ultima = max(str(f.get("creada_en")) for f in filas)
    return sorted((f for f in filas if str(f.get("creada_en")) == ultima), key=lambda f: f.get("posicion") or 0)


# --- E/S --------------------------------------------------------------------


def registrar(usuario_id, items, motor, grupo, perfil) -> None:
    """Una fila de `recomendaciones` por ítem (en estado `emitida`), en una sola inserción.

    Cada ítem trae ya su `recomendacion_id`.
    """
    if not items:
        return
    foto = snapshot(perfil)
    filas = [
        {
            "id": item["recomendacion_id"],
            "usuario_id": str(usuario_id),
            "curso_id": item["curso_id"],
            "puntuacion": item["puntuacion"],
            "posicion": item["posicion"],
            "motor": motor,
            "grupo": grupo,
            "origen": list(item.get("origen") or []),
            "explicacion": item["explicacion"],
            "perfil_snapshot": foto,
            "estado": "emitida",
        }
        for item in items
    ]
    supabase.insert("recomendaciones", filas, returning=False, operation="registrar_recomendaciones")


def de_usuario(recomendacion_id: str, usuario_id: str) -> Optional[dict]:
    """La recomendación si existe **y** es del usuario; si no, `None` (no distingue los dos casos)."""
    return supabase.select_one(
        "recomendaciones",
        columns="id,usuario_id,curso_id,posicion,estado",
        filters=(eq("id", recomendacion_id), eq("usuario_id", usuario_id)),
        operation="recomendacion_de_usuario",
    )


def cambiar_estado(recomendacion_id: str, usuario_id: str, estado: str, motivo: Optional[str] = None) -> None:
    """Actualiza `estado` (y `motivo_descarte` si se da) de una recomendación del usuario."""
    valores = {"estado": estado, **({"motivo_descarte": motivo} if motivo else {})}
    supabase.update(
        "recomendaciones",
        valores,
        filters=(eq("id", recomendacion_id), eq("usuario_id", usuario_id)),
        operation="estado_recomendacion",
    )


def marcar_aceptada(recomendacion_id: str, usuario_id: str) -> None:
    """Marca como `aceptada` una recomendación del usuario. Paquete 08; lo usa 03 (inscripción).

    Solo si la fila es del usuario; idempotente; un id desconocido no hace nada.
    """
    fila = de_usuario(recomendacion_id, usuario_id)
    if fila is None:
        return
    nuevo = siguiente_estado(fila.get("estado"), "inscripcion")
    if nuevo is not None:
        cambiar_estado(recomendacion_id, usuario_id, nuevo)


def recientes(usuario_id, desde) -> List[dict]:
    """Recomendaciones del usuario creadas desde `desde`: la más reciente primero, luego por `posicion`."""
    return supabase.select(
        "recomendaciones",
        columns=_COLUMNAS,
        filters=(eq("usuario_id", usuario_id), ("creada_en", f"gte.{desde.isoformat()}")),
        order="creada_en.desc,posicion.asc",
        limit=_MAX_RECIENTES,
        operation="recomendaciones_recientes",
    )


def hay_eventos_desde(usuario_id: str, tipos: Sequence[str], desde: str) -> bool:
    """¿Tiene el usuario algún evento de esos tipos posterior a `desde` (ISO-8601)?"""
    return bool(supabase.select(
        "eventos",
        columns="id",
        filters=(eq("usuario_id", usuario_id), in_("tipo", tipos), ("fecha", f"gt.{desde}")),
        limit=1,
        operation="eventos_desde_recomendacion",
    ))
