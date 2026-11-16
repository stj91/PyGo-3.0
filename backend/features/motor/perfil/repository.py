"""Acceso a datos del perfil (`usuarios`, `usuario_cursos`, `usuario_temas`,
`intentos_ejercicios`, `dominio_concepto`, `intereses_usuario`, `eventos`, `perfiles`).

Toda la E/S del paquete pasa por aquí, a través de `core.supabase`. Las filas se
devuelven aplanadas (recursos embebidos resueltos) y sin interpretar.

`core.supabase` no tiene borrado: «quitar» un interés lo deja con `peso = 0`, y
el constructor del perfil ignora esas filas. Cuando exista un `delete`, solo
cambia `retirar_intereses`.
"""

from typing import Any, Dict, List, Optional, Sequence

from core import supabase
from core.supabase import Filter, eq, in_

#: Intentos más recientes que se leen para el perfil.
LIMITE_INTENTOS = 500


def _embebido(recurso: Any) -> Dict[str, Any]:
    if isinstance(recurso, list):
        recurso = recurso[0] if recurso else None
    return recurso if isinstance(recurso, dict) else {}


def _mayor_que(columna: str, valor: Any) -> Filter:
    return (columna, f"gt.{valor}")


def _desde(columna: str, valor: Any) -> Filter:
    return (columna, f"gte.{valor}")


# --- Lectura del perfil -----------------------------------------------------


def leer_usuario(usuario_id: str) -> Optional[Dict[str, Any]]:
    fila = supabase.select_one(
        "usuarios",
        columns="id,nivel_asignado,carreras(clave)",
        filters=(eq("id", usuario_id),),
        operation="motor:perfil:usuario",
    )
    if not fila:
        return None
    return {
        "id": fila.get("id"),
        "nivel_asignado": fila.get("nivel_asignado"),
        "carrera_clave": _embebido(fila.get("carreras")).get("clave"),
    }


def leer_inscripciones(usuario_id: str) -> List[Dict[str, Any]]:
    return supabase.select(
        "usuario_cursos",
        columns="curso_id,estado,porcentaje_avance_global,calificacion_final,"
                "fecha_inscripcion,completado_en,origen",
        filters=(eq("usuario_id", usuario_id),),
        operation="motor:perfil:inscripciones",
    )


def leer_estados_temas(usuario_id: str) -> List[Dict[str, Any]]:
    return supabase.select(
        "usuario_temas",
        columns="tema_id,estado",
        filters=(eq("usuario_id", usuario_id),),
        operation="motor:perfil:estados_temas",
    )


def leer_intentos(usuario_id: str) -> List[Dict[str, Any]]:
    filas = supabase.select(
        "intentos_ejercicios",
        columns="ejercicio_id,calificacion_obtenida,fecha_intento,ejercicios(tema_id,tipo)",
        filters=(eq("usuario_id", usuario_id),),
        order="fecha_intento.desc",
        limit=LIMITE_INTENTOS,
        operation="motor:perfil:intentos",
    )
    return [
        {
            "ejercicio_id": f.get("ejercicio_id"),
            "tema_id": _embebido(f.get("ejercicios")).get("tema_id"),
            "tipo": _embebido(f.get("ejercicios")).get("tipo"),
            "calificacion_obtenida": f.get("calificacion_obtenida"),
            "fecha_intento": f.get("fecha_intento"),
        }
        for f in filas
    ]


def leer_dominio(usuario_id: str, concepto_ids: Optional[Sequence[int]] = None) -> List[Dict[str, Any]]:
    """Filas `{concepto_id, concepto_clave, dominio, evidencias}`; todas o solo las de `concepto_ids`."""
    filtros = [eq("usuario_id", usuario_id)]
    if concepto_ids is not None:
        filtros.append(in_("concepto_id", concepto_ids))
    filas = supabase.select(
        "dominio_concepto",
        columns="concepto_id,dominio,evidencias,conceptos(clave)",
        filters=tuple(filtros),
        operation="motor:perfil:dominio",
    )
    return [
        {
            "concepto_id": f.get("concepto_id"),
            "concepto_clave": _embebido(f.get("conceptos")).get("clave"),
            "dominio": f.get("dominio"),
            "evidencias": f.get("evidencias"),
        }
        for f in filas
    ]


def leer_intereses(usuario_id: str, origen: Optional[str] = None) -> List[Dict[str, Any]]:
    """Filas `{concepto_id, concepto_clave, origen, peso}`, incluidas las retiradas (peso 0)."""
    filtros = [eq("usuario_id", usuario_id)]
    if origen is not None:
        filtros.append(eq("origen", origen))
    filas = supabase.select(
        "intereses_usuario",
        columns="concepto_id,origen,peso,conceptos(clave)",
        filters=tuple(filtros),
        operation="motor:perfil:intereses",
    )
    return [
        {
            "concepto_id": f.get("concepto_id"),
            "concepto_clave": _embebido(f.get("conceptos")).get("clave"),
            "origen": f.get("origen"),
            "peso": f.get("peso"),
        }
        for f in filas
    ]


def leer_ultimo_evento(usuario_id: str, curso_id: Optional[int] = None) -> Optional[str]:
    """Fecha del último evento del usuario (en ese curso, si se indica)."""
    filtros = [eq("usuario_id", usuario_id)]
    if curso_id is not None:
        filtros.append(eq("curso_id", curso_id))
    fila = supabase.select_one(
        "eventos",
        columns="fecha",
        filters=tuple(filtros),
        order="fecha.desc",
        operation="motor:perfil:ultimo_evento",
    )
    return fila.get("fecha") if fila else None


def leer_vistas(usuario_id: str, desde_iso: str) -> List[Dict[str, Any]]:
    """Eventos `curso_vista` del usuario desde `desde_iso`: `{curso_id, fecha}`."""
    return supabase.select(
        "eventos",
        columns="curso_id,fecha",
        filters=(eq("usuario_id", usuario_id), eq("tipo", "curso_vista"), _desde("fecha", desde_iso)),
        operation="motor:perfil:vistas",
    )


def listar_usuarios(despues_de: Optional[str], limite: int) -> List[str]:
    """Ids de usuario por orden, paginados por clave (los mayores que `despues_de`)."""
    filtros = (_mayor_que("id", despues_de),) if despues_de else ()
    filas = supabase.select(
        "usuarios",
        columns="id",
        filters=filtros,
        order="id.asc",
        limit=limite,
        operation="motor:perfil:listar_usuarios",
    )
    return [str(f["id"]) for f in filas if f.get("id")]


# --- Escritura --------------------------------------------------------------


def guardar_dominio(usuario_id: str, concepto_id: int, dominio: float, evidencias: int, ahora_iso: str) -> None:
    supabase.upsert(
        "dominio_concepto",
        {
            "usuario_id": usuario_id,
            "concepto_id": concepto_id,
            "dominio": dominio,
            "evidencias": evidencias,
            "actualizado_en": ahora_iso,
        },
        on_conflict="usuario_id,concepto_id",
        operation="motor:perfil:guardar_dominio",
    )


def guardar_interes(usuario_id: str, concepto_id: int, origen: str, peso: float) -> None:
    supabase.upsert(
        "intereses_usuario",
        {"usuario_id": usuario_id, "concepto_id": concepto_id, "origen": origen, "peso": peso},
        on_conflict="usuario_id,concepto_id,origen",
        operation="motor:perfil:guardar_interes",
    )


def retirar_intereses(usuario_id: str, origen: str, concepto_ids: Sequence[int]) -> None:
    """Retira intereses dejando `peso = 0` (no hay borrado en `core.supabase`)."""
    if not concepto_ids:
        return
    supabase.update(
        "intereses_usuario",
        {"peso": 0},
        filters=(eq("usuario_id", usuario_id), eq("origen", origen), in_("concepto_id", concepto_ids)),
        operation="motor:perfil:retirar_intereses",
    )


def marcar_abandonado(usuario_id: str, curso_id: int) -> None:
    supabase.update(
        "usuario_cursos",
        {"estado": "abandonado"},
        filters=(eq("usuario_id", usuario_id), eq("curso_id", curso_id), eq("estado", "activo")),
        operation="motor:perfil:marcar_abandonado",
    )


def guardar_snapshot(usuario_id: str, nivel_inferido: Optional[str], caracteristicas: Dict[str, Any],
                     calculado_en_iso: str) -> None:
    supabase.upsert(
        "perfiles",
        {
            "usuario_id": usuario_id,
            "nivel_inferido": nivel_inferido,
            "caracteristicas": caracteristicas,
            "calculado_en": calculado_en_iso,
        },
        on_conflict="usuario_id",
        operation="motor:perfil:guardar_snapshot",
    )
