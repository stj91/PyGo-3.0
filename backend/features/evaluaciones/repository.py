"""Acceso a datos de evaluaciones y progreso adaptativo.

Sobre el esquema real:

* `intentos_ejercicios` se registra **por ejercicio**, no por tema: sus columnas
  son `ejercicio_id`, `calificacion_obtenida`, `numero_aciertos`,
  `numero_errores` y `tiempo_resolucion_segundos`. El backend Node insertaba
  `tema_id`, `puntaje_obtenido` y `requiere_refuerzo`, que no existen, así que
  ese registro fallaba en silencio en cada evaluación.
* `usuario_temas` y `usuario_cursos` tienen `id` serial como clave primaria y no
  declaran índice único sobre las columnas de negocio, por lo que un upsert de
  PostgREST insertaría una fila nueva cada vez. Se usa `upsert_where`, que busca
  la fila antes de decidir.
"""

from typing import Any, Dict, List, Optional, Sequence

from core import supabase
from core.supabase import eq, in_


def buscar_opciones(opciones_ids: Sequence[Any]) -> List[Dict[str, Any]]:
    """Opciones enviadas, con su corrección y ejercicio asociado.

    `opciones_ejercicios` no tiene columna de retroalimentación en el esquema
    actual, así que los mensajes se generan en la capa de servicio.
    """
    return supabase.select(
        "opciones_ejercicios",
        columns="id,ejercicio_id,es_correcta",
        filters=(in_("id", opciones_ids),),
        operation="buscar_opciones",
    )


def registrar_intentos(intentos: Sequence[Dict[str, Any]]) -> None:
    """Guarda un intento por cada ejercicio respondido."""
    if not intentos:
        return
    supabase.insert(
        "intentos_ejercicios",
        list(intentos),
        returning=False,
        operation="registrar_intentos",
    )


def marcar_estado_tema(usuario_id: str, tema_id: Any, estado: str) -> Optional[Dict[str, Any]]:
    """Crea o actualiza el estado del usuario en un tema."""
    return supabase.upsert_where(
        "usuario_temas",
        match={"usuario_id": usuario_id, "tema_id": tema_id},
        values={"estado": estado},
        operation="marcar_estado_tema",
    )


def buscar_tema(tema_id: Any) -> Optional[Dict[str, Any]]:
    """Orden y curso al que pertenece un tema."""
    return supabase.select_one(
        "temas",
        columns="id,orden,curso_id",
        filters=(eq("id", tema_id),),
        operation="buscar_tema",
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
    """Cuántos de esos temas tiene el usuario en estado `completado`."""
    if not tema_ids:
        return 0
    return supabase.count_rows(
        "usuario_temas",
        filters=(
            eq("usuario_id", usuario_id),
            eq("estado", "completado"),
            in_("tema_id", tema_ids),
        ),
        operation="contar_temas_completados",
    )


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
