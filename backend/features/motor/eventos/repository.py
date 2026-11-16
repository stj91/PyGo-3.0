"""Acceso a datos de la tabla `eventos` (solo inserción y lectura)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from django.utils.dateparse import parse_datetime

from core import supabase
from core.errors import DataAccessError, ValidationError
from core.supabase import eq

from ..tipos import Evento

_COLUMNAS_RECIENTES = "id,usuario_id,tipo,objeto_id,datos,fecha"
_MAX_RECIENTES = 20
_FK_INEXISTENTE = "23503"


def a_fecha(valor: Any) -> Optional[datetime]:
    """Timestamp de PostgREST (ISO-8601) como `datetime` con zona. **Pura.**"""
    if valor is None or isinstance(valor, datetime):
        return valor
    return parse_datetime(str(valor))


def _resumen(fila: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": fila.get("id"), "tipo": fila.get("tipo"), "fecha": a_fecha(fila.get("fecha"))}


def insertar(evento: Evento) -> Dict[str, Any]:
    """Inserta el evento y devuelve `{id, tipo, fecha}`."""
    fila = {**evento, "fecha": evento["fecha"].isoformat()}
    try:
        insertada = supabase.insert("eventos", fila, operation="insertar_evento")
    except DataAccessError as error:
        # `curso_id` apunta a `cursos`: un id inexistente es un error del cliente, no del servicio.
        if error.upstream_code == _FK_INEXISTENTE:
            raise ValidationError("El curso indicado no existe.", campos=["curso_id"]) from error
        raise
    return _resumen(insertada or {})


def recientes(usuario_id: str, tipo: str, desde: datetime) -> List[Evento]:
    """Eventos del usuario de ese tipo desde `desde`, del más reciente al más antiguo."""
    filas = supabase.select(
        "eventos",
        columns=_COLUMNAS_RECIENTES,
        filters=(
            eq("usuario_id", usuario_id),
            eq("tipo", tipo),
            ("fecha", f"gte.{desde.isoformat()}"),
        ),
        order="fecha.desc",
        limit=_MAX_RECIENTES,
        operation="eventos_recientes",
    )
    return [{**fila, "fecha": a_fecha(fila.get("fecha"))} for fila in filas]
