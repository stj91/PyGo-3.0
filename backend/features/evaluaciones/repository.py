"""Acceso a datos de evaluaciones y progreso adaptativo.

Sobre el esquema real:

* `intentos_ejercicios` se registra **por ejercicio**, no por tema: sus columnas
  son `ejercicio_id`, `calificacion_obtenida`, `numero_aciertos`,
  `numero_errores` y `tiempo_resolucion_segundos`.
* `usuario_temas` y `usuario_cursos` tienen `id` serial como clave primaria. La
  migración 0005 añade índices únicos sobre (usuario, tema) y (usuario, curso),
  pero hasta aplicarla puede haber duplicados, así que se usa `upsert_where` y
  los estados se leen todos (`estados_tema`).
* `es_correcta` se lee aquí para corregir; nunca sale tal cual al cliente.
"""

from typing import Any, Dict, List, Optional, Sequence

from core import supabase
from core.supabase import eq, in_


def buscar_tema(tema_id: int) -> Optional[Dict[str, Any]]:
    """Orden y curso al que pertenece un tema."""
    return supabase.select_one(
        "temas",
        columns="id,orden,curso_id",
        filters=(eq("id", tema_id),),
        operation="buscar_tema",
    )


def listar_ejercicios_de_temas(tema_ids: Sequence[int]) -> List[Dict[str, Any]]:
    """Ejercicios (`id`, `tema_id`, `tipo`) de esos temas, por id."""
    if not tema_ids:
        return []
    return supabase.select(
        "ejercicios",
        columns="id,tema_id,tipo",
        filters=(in_("tema_id", tema_ids),),
        order="id.asc",
        operation="listar_ejercicios_de_temas",
    )


def listar_opciones_de_ejercicios(ejercicio_ids: Sequence[int]) -> List[Dict[str, Any]]:
    """Todas las opciones de esos ejercicios, con su corrección. Solo uso en servidor."""
    if not ejercicio_ids:
        return []
    return supabase.select(
        "opciones_ejercicios",
        columns="id,ejercicio_id,es_correcta",
        filters=(in_("ejercicio_id", ejercicio_ids),),
        operation="listar_opciones_de_ejercicios",
    )


def registrar_intentos(intentos: Sequence[Dict[str, Any]]) -> None:
    """Guarda un intento por cada ejercicio del módulo."""
    if not intentos:
        return
    supabase.insert(
        "intentos_ejercicios",
        list(intentos),
        returning=False,
        operation="registrar_intentos",
    )


def listar_intentos(usuario_id: str, ejercicio_ids: Sequence[int]) -> List[Dict[str, Any]]:
    """Intentos del usuario en esos ejercicios."""
    if not ejercicio_ids:
        return []
    return supabase.select(
        "intentos_ejercicios",
        columns="id,ejercicio_id,calificacion_obtenida,fecha_intento",
        filters=(eq("usuario_id", usuario_id), in_("ejercicio_id", ejercicio_ids)),
        operation="listar_intentos",
    )


def estados_tema(usuario_id: str, tema_id: int) -> List[Optional[str]]:
    """Estados actuales del usuario en un tema (más de uno si hay duplicados)."""
    filas = supabase.select(
        "usuario_temas",
        columns="estado",
        filters=(eq("usuario_id", usuario_id), eq("tema_id", tema_id)),
        operation="estados_tema",
    )
    return [fila.get("estado") for fila in filas]


def marcar_estado_tema(usuario_id: str, tema_id: int, estado: str) -> Optional[Dict[str, Any]]:
    """Crea o actualiza el estado del usuario en un tema."""
    return supabase.upsert_where(
        "usuario_temas",
        match={"usuario_id": usuario_id, "tema_id": tema_id},
        values={"estado": estado},
        operation="marcar_estado_tema",
    )


def buscar_tema_por_orden(curso_id: Any, orden: int) -> Optional[Dict[str, Any]]:
    """Tema de un curso en una posición concreta del temario."""
    return supabase.select_one(
        "temas",
        columns="id",
        filters=(eq("curso_id", curso_id), eq("orden", orden)),
        operation="buscar_tema_por_orden",
    )


def listar_temas_de_curso(curso_id: Any) -> List[Dict[str, Any]]:
    """Todos los temas de un curso."""
    return supabase.select(
        "temas",
        columns="id",
        filters=(eq("curso_id", curso_id),),
        operation="listar_temas_de_curso",
    )


def contar_temas_completados(usuario_id: str, tema_ids: Sequence[Any]) -> int:
    """Cuántos de esos temas tiene el usuario en estado `completado`.

    Cuenta temas distintos: con filas duplicadas (antes de 0005) un tema no
    puede contar dos veces.
    """
    if not tema_ids:
        return 0
    filas = supabase.select(
        "usuario_temas",
        columns="tema_id",
        filters=(
            eq("usuario_id", usuario_id),
            eq("estado", "completado"),
            in_("tema_id", tema_ids),
        ),
        operation="contar_temas_completados",
    )
    return len({fila.get("tema_id") for fila in filas})


def guardar_avance_curso(
    usuario_id: str, curso_id: Any, porcentaje: int
) -> Optional[Dict[str, Any]]:
    """Persiste el porcentaje global de avance del usuario en un curso."""
    return supabase.upsert_where(
        "usuario_cursos",
        match={"usuario_id": usuario_id, "curso_id": curso_id},
        values={"porcentaje_avance_global": porcentaje},
        operation="guardar_avance_curso",
    )


def buscar_inscripcion(usuario_id: str, curso_id: Any) -> Optional[Dict[str, Any]]:
    """Estado de la inscripción del usuario en el curso (columna de 0005)."""
    return supabase.select_one(
        "usuario_cursos",
        columns="id,estado",
        filters=(eq("usuario_id", usuario_id), eq("curso_id", curso_id)),
        operation="buscar_inscripcion",
    )


def completar_curso(
    usuario_id: str, curso_id: Any, *, calificacion_final: float, completado_en: str
) -> Optional[Dict[str, Any]]:
    """Marca la inscripción como `completado` con su nota final."""
    return supabase.update(
        "usuario_cursos",
        {
            "estado": "completado",
            "completado_en": completado_en,
            "calificacion_final": calificacion_final,
        },
        filters=(eq("usuario_id", usuario_id), eq("curso_id", curso_id)),
        operation="completar_curso",
    )
