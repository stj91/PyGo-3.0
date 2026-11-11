"""Acceso a datos de los catálogos académicos: centros y carreras.

`centros` son los campus de la universidad (CUCEI, CUCEA...) y `carreras` las
licenciaturas e ingenierías. Las creó la migración 0004; antes estos dos datos
eran texto libre en `usuarios`, con los errores de tecleo que eso implica.
"""

from typing import Any, Dict, List, Optional

from core import supabase
from core.supabase import eq

#: Columnas que viajan al cliente. `activo` se queda dentro: es un detalle de
#: administración, no algo que el desplegable deba mostrar.
COLUMNAS = "id,clave,nombre"


def listar_centros() -> List[Dict[str, Any]]:
    """Centros activos, ordenados por nombre."""
    return supabase.select(
        "centros",
        columns=COLUMNAS,
        filters=(eq("activo", "true"),),
        order="nombre.asc",
        operation="listar_centros",
    )


def listar_carreras() -> List[Dict[str, Any]]:
    """Carreras activas, ordenadas por nombre."""
    return supabase.select(
        "carreras",
        columns=COLUMNAS,
        filters=(eq("activo", "true"),),
        order="nombre.asc",
        operation="listar_carreras",
    )


def buscar_centro(centro_id: Any) -> Optional[Dict[str, Any]]:
    """Centro activo con ese id, o `None`."""
    return supabase.select_one(
        "centros",
        columns=COLUMNAS,
        filters=(eq("id", centro_id), eq("activo", "true")),
        operation="buscar_centro",
    )


def buscar_carrera(carrera_id: Any) -> Optional[Dict[str, Any]]:
    """Carrera activa con ese id, o `None`."""
    return supabase.select_one(
        "carreras",
        columns=COLUMNAS,
        filters=(eq("id", carrera_id), eq("activo", "true")),
        operation="buscar_carrera",
    )
