"""Lógica de cursos: catálogo, detalle de curso y contenido de lección."""

from typing import Any, Dict, List, Optional

from core.errors import NotFoundError
from core.functional import index_by

from . import repository

AVANCE_POR_DEFECTO = 0


# --- Reglas puras -----------------------------------------------------------


def combinar_avance(
    cursos: List[Dict[str, Any]], avances: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Añade `porcentaje_avance_global` a cada curso. Pura, no muta la entrada.

    Indexar los avances por `curso_id` evita recorrer la lista de avances por
    cada curso, a diferencia del `.find()` anidado del código original.
    """
    por_curso = index_by("curso_id", avances)
    return [
        {
            **curso,
            "porcentaje_avance_global": por_curso.get(curso.get("id"), {}).get(
                "porcentaje_avance_global", AVANCE_POR_DEFECTO
            ),
        }
        for curso in cursos
    ]


# --- Orquestación -----------------------------------------------------------


def obtener_cursos(usuario_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Catálogo de cursos; con `usuario_id` incluye su avance en cada uno."""
    cursos = repository.listar_cursos()
    if not usuario_id:
        return cursos
    return combinar_avance(cursos, repository.listar_avances(usuario_id))


def obtener_curso(curso_id: Any) -> Dict[str, Any]:
    """Curso con su temario. Lanza `NotFoundError` si no existe."""
    curso = repository.buscar_curso(curso_id)
    if not curso:
        raise NotFoundError("Curso no encontrado.")
    return curso


def obtener_leccion(leccion_id: Any) -> Dict[str, Any]:
    """Contenido de una lección, que en este esquema es un **tema**.

    No existe tabla `lecciones` en Supabase (ver `repository`), así que el id
    recibido se resuelve contra `temas`. Lanza `NotFoundError` si no existe.
    """
    tema = repository.buscar_tema(leccion_id)
    if not tema:
        raise NotFoundError("Lección no encontrada.")
    return tema
