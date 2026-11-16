"""Acceso a datos de inscripciones (`usuario_cursos`) y del primer módulo (`usuario_temas`)."""

from typing import Any, Dict, Optional

from core import supabase
from core.supabase import eq

COLUMNAS_INSCRIPCION = (
    "curso_id,estado,porcentaje_avance_global,calificacion_final,"
    "fecha_inscripcion,completado_en,origen"
)


def buscar(usuario_id: str, curso_id: int) -> Optional[Dict[str, Any]]:
    """Inscripción del usuario en el curso, o `None`."""
    return supabase.select_one(
        "usuario_cursos",
        columns=COLUMNAS_INSCRIPCION,
        filters=(eq("usuario_id", usuario_id), eq("curso_id", curso_id)),
        operation="buscar_inscripcion",
    )


def insertar(fila: Dict[str, Any]) -> Dict[str, Any]:
    """Inserta la inscripción y devuelve la fila creada."""
    return supabase.insert("usuario_cursos", fila, operation="insertar_inscripcion") or {}


def tiene_fila_tema(usuario_id: str, tema_id: int) -> bool:
    """True si el usuario ya tiene estado en ese tema."""
    return supabase.select_one(
        "usuario_temas",
        columns="id",
        filters=(eq("usuario_id", usuario_id), eq("tema_id", tema_id)),
        operation="buscar_estado_tema",
    ) is not None


def desbloquear_tema(usuario_id: str, tema_id: int) -> None:
    """Crea la fila del tema en estado `desbloqueado`."""
    supabase.insert(
        "usuario_temas",
        {"usuario_id": usuario_id, "tema_id": tema_id, "estado": "desbloqueado"},
        returning=False,
        operation="desbloquear_primer_tema",
    )
