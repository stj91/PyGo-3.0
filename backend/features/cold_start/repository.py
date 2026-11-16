"""Acceso a datos de la evaluación inicial.

Las preguntas del diagnóstico son `ejercicios` con `tipo = 'evaluacion_tecnica'`
(migración 0007). `es_correcta` solo se lee en `buscar_opciones`, cuyo resultado
se queda en el servidor: la consulta de preguntas que viaja al cliente no lo
selecciona nunca.
"""

from typing import Any, Dict, List, Optional, Sequence

from core import supabase
from core.supabase import eq, in_

TIPO_DIAGNOSTICO = "evaluacion_tecnica"

#: Columnas visibles de una pregunta. Sin `es_correcta`, a propósito.
PREGUNTA_COLUMNS = "id,consigna,opciones_ejercicios(id,texto_opcion,orden)"


def listar_preguntas() -> List[Dict[str, Any]]:
    """Ejercicios del diagnóstico con sus opciones visibles, por id."""
    return supabase.select(
        "ejercicios",
        columns=PREGUNTA_COLUMNS,
        filters=(eq("tipo", TIPO_DIAGNOSTICO),),
        order="id.asc",
        operation="listar_preguntas_diagnostico",
    )


def listar_ids_diagnostico() -> List[int]:
    """Ids de los ejercicios del diagnóstico."""
    filas = supabase.select(
        "ejercicios",
        columns="id",
        filters=(eq("tipo", TIPO_DIAGNOSTICO),),
        operation="listar_ids_diagnostico",
    )
    return [int(fila["id"]) for fila in filas if fila.get("id") is not None]


def buscar_opciones(opciones_ids: Sequence[int]) -> List[Dict[str, Any]]:
    """Opciones enviadas con su ejercicio y corrección. Solo uso en servidor."""
    if not opciones_ids:
        return []
    return supabase.select(
        "opciones_ejercicios",
        columns="id,ejercicio_id,es_correcta",
        filters=(in_("id", opciones_ids),),
        operation="buscar_opciones_diagnostico",
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


def guardar_metas(
    usuario_id: str, *, meta_diaria_minutos: int, meta_semanal_minutos: int
) -> Optional[Dict[str, Any]]:
    """Crea o actualiza las metas de estudio en las preferencias del usuario."""
    return supabase.upsert(
        "usuario_preferencias",
        {
            "usuario_id": usuario_id,
            "meta_diaria_minutos": meta_diaria_minutos,
            "meta_semanal_minutos": meta_semanal_minutos,
        },
        operation="guardar_metas_estudio",
    )


def registrar_intentos(intentos: Sequence[Dict[str, Any]]) -> None:
    """Guarda un intento por cada pregunta del diagnóstico respondida."""
    if not intentos:
        return
    supabase.insert(
        "intentos_ejercicios",
        list(intentos),
        returning=False,
        operation="registrar_intentos_diagnostico",
    )
