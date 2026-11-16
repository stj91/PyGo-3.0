"""Lógica de cursos: catálogo, detalle de curso y contenido de lección."""

from typing import Any, Dict, List, Optional

from core.errors import NotFoundError
from core.functional import index_by

from . import repository

AVANCE_POR_DEFECTO = 0
TIPO_DIAGNOSTICO = "evaluacion_tecnica"


# --- Reglas puras -----------------------------------------------------------


def combinar_avance(
    cursos: List[Dict[str, Any]], avances: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Añade `porcentaje_avance_global` e `inscrito` a cada curso. Pura, no muta la entrada.

    `inscrito` es True si el usuario tiene fila en `usuario_cursos` para el curso,
    aunque su avance sea 0. Indexar los avances por `curso_id` evita recorrer la
    lista de avances por cada curso.
    """
    por_curso = index_by("curso_id", avances)
    return [
        {
            **curso,
            "porcentaje_avance_global": por_curso.get(curso.get("id"), {}).get(
                "porcentaje_avance_global", AVANCE_POR_DEFECTO
            ),
            "inscrito": curso.get("id") in por_curso,
        }
        for curso in cursos
    ]


def sin_diagnostico(ejercicios: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Ejercicios sin los del diagnóstico inicial (`evaluacion_tecnica`). Pura.

    Las preguntas del diagnóstico cuelgan de un tema para mapear la evidencia a
    conceptos, pero no son contenido de la lección.
    """
    return [e for e in (ejercicios or []) if e.get("tipo") != TIPO_DIAGNOSTICO]


def _tema_sin_diagnostico(tema: Dict[str, Any]) -> Dict[str, Any]:
    """Copia del tema con sus ejercicios filtrados. Pura."""
    if "ejercicios" not in tema:
        return tema
    return {**tema, "ejercicios": sin_diagnostico(tema.get("ejercicios"))}


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
    if "temas" not in curso:
        return curso
    return {**curso, "temas": [_tema_sin_diagnostico(t) for t in curso.get("temas") or []]}


def obtener_leccion(leccion_id: Any) -> Dict[str, Any]:
    """Contenido de una lección, que en este esquema es un **tema**.

    No existe tabla `lecciones` en Supabase (ver `repository`), así que el id
    recibido se resuelve contra `temas`. Lanza `NotFoundError` si no existe.
    """
    tema = repository.buscar_tema(leccion_id)
    if not tema:
        raise NotFoundError("Lección no encontrada.")
    return _tema_sin_diagnostico(tema)
