"""Acceso a datos de cursos, temas y ejercicios.

Sobre el esquema real: la jerarquía en Supabase es
`cursos -> temas -> ejercicios -> opciones_ejercicios`. No existe tabla
`lecciones`; el backend Node la consultaba y por eso sus endpoints de curso y
lección fallaban siempre. Aquí el "contenido de una lección" es un **tema** con
sus ejercicios, que es la unidad de contenido que la base de datos sí tiene.
"""

from typing import Any, Dict, List, Optional

from core import supabase
from core.supabase import eq

#: Curso con su temario anidado (temas y sus ejercicios).
CURSO_DETALLE_COLUMNS = "*,temas(id,titulo,orden,descripcion,ejercicios(id,titulo,tipo))"

#: Tema con sus ejercicios y las opciones visibles.
#: `es_correcta` se omite a propósito: la respuesta correcta no viaja al cliente.
TEMA_DETALLE_COLUMNS = (
    "id,titulo,descripcion,orden,curso_id,"
    "ejercicios(id,titulo,tipo,consigna,opciones_ejercicios(id,texto_opcion,orden))"
)


def listar_cursos() -> List[Dict[str, Any]]:
    """Todos los cursos ordenados por id ascendente."""
    return supabase.select("cursos", order="id.asc", operation="listar_cursos")


def listar_avances(usuario_id: str) -> List[Dict[str, Any]]:
    """Porcentaje de avance del usuario en cada curso en el que está inscrito."""
    return supabase.select(
        "usuario_cursos",
        columns="curso_id,porcentaje_avance_global",
        filters=(eq("usuario_id", usuario_id),),
        operation="listar_avances",
    )


def buscar_curso(curso_id: Any) -> Optional[Dict[str, Any]]:
    """Curso con su temario anidado, o `None` si no existe."""
    return supabase.select_one(
        "cursos",
        columns=CURSO_DETALLE_COLUMNS,
        filters=(eq("id", curso_id),),
        operation="buscar_curso",
    )


def buscar_tema(tema_id: Any) -> Optional[Dict[str, Any]]:
    """Tema con sus ejercicios y opciones, o `None` si no existe."""
    return supabase.select_one(
        "temas",
        columns=TEMA_DETALLE_COLUMNS,
        filters=(eq("id", tema_id),),
        operation="buscar_tema",
    )
