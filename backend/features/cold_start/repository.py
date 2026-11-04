"""Acceso a datos de la evaluación inicial."""

from typing import Any, Dict, Optional, Sequence

from core import supabase
from core.supabase import eq, in_


def contar_opciones_correctas(opciones_ids: Sequence[Any]) -> int:
    """Cuántas de las opciones indicadas están marcadas como correctas."""
    return supabase.count_rows(
        "opciones_ejercicios",
        filters=(in_("id", opciones_ids), eq("es_correcta", "true")),
        operation="contar_opciones_correctas",
    )


def actualizar_nivel(
    usuario_id: str, *, nivel_asignado: str, objetivo_aprendizaje: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Guarda el nivel asignado y el objetivo de aprendizaje del usuario."""
    return supabase.update(
        "usuarios",
        {"nivel_asignado": nivel_asignado, "objetivo_aprendizaje": objetivo_aprendizaje},
        filters=(eq("id", usuario_id),),
        operation="actualizar_nivel",
    )


def guardar_meta_diaria(usuario_id: str, minutos: int) -> Optional[Dict[str, Any]]:
    """Crea o actualiza la meta diaria en las preferencias del usuario."""
    return supabase.upsert(
        "usuario_preferencias",
        {"usuario_id": usuario_id, "meta_diaria_minutos": minutos},
        operation="guardar_meta_diaria",
    )
