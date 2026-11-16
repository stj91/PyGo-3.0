"""Servicio de perfil: lee con `repository`, decide con las funciones puras y escribe.

Únicas funciones del paquete que leen el reloj.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from core.errors import NotFoundError

from ..catalogo import cargar_catalogo
from ..tipos import Catalogo, Perfil
from . import repository
from ._comun import a_entero, a_fecha, a_float, a_iso, temas_por_id
from .construir import EntradaPerfil, construir_perfil
from .dominio import aplicar_diagnostico, aplicar_tema, conceptos_del_diagnostico
from .publico import areas_declaradas, perfil_publico
from .recalculo import (
    DIAS_VISTAS,
    cursos_abandonados,
    intereses_inferidos,
    ultima_actividad_por_curso,
)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# --- Lectura ----------------------------------------------------------------


def leer_entrada(usuario_id: str) -> EntradaPerfil:
    """Datos crudos del alumno en 7 consultas. `NotFoundError` si no existe."""
    usuario = repository.leer_usuario(usuario_id)
    if not usuario:
        raise NotFoundError("Usuario no encontrado.")

    dominio: Dict[str, float] = {}
    evidencias: Dict[str, int] = {}
    for fila in repository.leer_dominio(usuario_id):
        clave, valor = fila.get("concepto_clave"), a_float(fila.get("dominio"))
        if clave and valor is not None:
            dominio[clave] = valor
            evidencias[clave] = a_entero(fila.get("evidencias")) or 0

    return {
        "usuario": usuario,
        "inscripciones": repository.leer_inscripciones(usuario_id),
        "estados_temas": repository.leer_estados_temas(usuario_id),
        "intentos": repository.leer_intentos(usuario_id),
        "dominio": dominio,
        "evidencias": evidencias,
        "intereses": repository.leer_intereses(usuario_id),
        "ultimo_evento": a_fecha(repository.leer_ultimo_evento(usuario_id)),
    }


def obtener_perfil(usuario_id: str) -> Perfil:
    """Perfil actual del usuario (`NotFoundError` si no existe). Lo usa 08."""
    return construir_perfil(leer_entrada(usuario_id), cargar_catalogo(), _ahora())


def obtener_perfil_publico(usuario_id: str) -> Dict[str, Any]:
    """`PerfilPublico` del usuario, para `GET /api/perfil/<id>`."""
    entrada = leer_entrada(usuario_id)
    catalogo = cargar_catalogo()
    perfil = construir_perfil(entrada, catalogo, _ahora())
    return perfil_publico(perfil, areas_declaradas(entrada["intereses"], catalogo), catalogo)


# --- Dominio ----------------------------------------------------------------


def _ids_de(claves: Iterable[str], catalogo: Catalogo) -> Dict[str, int]:
    conceptos = catalogo.get("conceptos", {})
    return {c: conceptos[c]["id"] for c in claves if c in conceptos}


def _dominio_actual(usuario_id: str, ids: Dict[str, int]) -> Tuple[Dict[str, float], Dict[str, int]]:
    dominio: Dict[str, float] = {}
    evidencias: Dict[str, int] = {}
    if not ids:
        return dominio, evidencias
    for fila in repository.leer_dominio(usuario_id, sorted(ids.values())):
        clave, valor = fila.get("concepto_clave"), a_float(fila.get("dominio"))
        if clave in ids and valor is not None:
            dominio[clave] = valor
            evidencias[clave] = a_entero(fila.get("evidencias")) or 0
    return dominio, evidencias


def _guardar_dominio(usuario_id: str, ids: Dict[str, int], dominio: Dict[str, float],
                     evidencias: Dict[str, int]) -> None:
    ahora_iso = a_iso(_ahora())
    for clave, concepto_id in sorted(ids.items()):
        if clave in dominio:
            repository.guardar_dominio(
                usuario_id, concepto_id, dominio[clave], evidencias.get(clave, 0), ahora_iso
            )


def actualizar_dominio_por_tema(usuario_id: str, tema_id: int, puntaje: float) -> None:
    """Actualiza el dominio de los conceptos del módulo con `puntaje` (0..1). Lo usan los ganchos."""
    catalogo = cargar_catalogo()
    tema = temas_por_id(catalogo).get(a_entero(tema_id))
    ids = _ids_de(tema["conceptos"], catalogo) if tema else {}
    if not ids:
        return
    usuario = repository.leer_usuario(usuario_id)
    if not usuario:
        raise NotFoundError("Usuario no encontrado.")
    puntaje = min(1.0, max(0.0, float(puntaje)))

    dominio, evidencias = _dominio_actual(usuario_id, ids)
    dominio, evidencias = aplicar_tema(
        dominio, evidencias, tema["id"], puntaje, usuario.get("nivel_asignado"), catalogo
    )
    _guardar_dominio(usuario_id, ids, dominio, evidencias)


def sembrar_dominio(usuario_id: str, resultados: Dict[int, bool], nivel: str) -> None:
    """Siembra el dominio a partir del diagnóstico `{ejercicio_id: acertó?}`. Lo usan los ganchos."""
    catalogo = cargar_catalogo()
    ids = _ids_de(conceptos_del_diagnostico(resultados, catalogo), catalogo)
    if not ids:
        return
    dominio, evidencias = _dominio_actual(usuario_id, ids)
    dominio, evidencias = aplicar_diagnostico(dominio, evidencias, resultados, nivel, catalogo)
    _guardar_dominio(usuario_id, ids, dominio, evidencias)


# --- Intereses --------------------------------------------------------------


def _reemplazar_intereses(usuario_id: str, origen: str, nuevos: Dict[str, float],
                          existentes: Iterable[Dict[str, Any]], catalogo: Catalogo) -> None:
    """Deja como intereses `origen` exactamente `nuevos` (clave -> peso)."""
    ids = _ids_de(nuevos, catalogo)
    for clave, concepto_id in sorted(ids.items()):
        repository.guardar_interes(usuario_id, concepto_id, origen, nuevos[clave])
    sobrantes = sorted({
        a_entero(f.get("concepto_id"))
        for f in existentes
        if f.get("origen") == origen
        and a_entero(f.get("concepto_id")) not in ids.values()
        and (a_float(f.get("peso"), 0.0) or 0.0) > 0
        and a_entero(f.get("concepto_id")) is not None
    })
    repository.retirar_intereses(usuario_id, origen, sobrantes)


def normalizar_areas(areas: Sequence[Tuple[str, float]], catalogo: Catalogo) -> Dict[str, float]:
    """Áreas válidas -> peso en [0, 1]; claves desconocidas fuera, duplicadas por máximo. **Pura.**"""
    validas = catalogo.get("areas", {})
    resultado: Dict[str, float] = {}
    for clave, peso in areas:
        valor = a_float(peso)
        if clave not in validas or valor is None:
            continue
        valor = round(min(1.0, max(0.0, valor)), 2)
        if valor > resultado.get(clave, -1.0):
            resultado[clave] = valor
    return {k: v for k, v in resultado.items() if v > 0}


def guardar_intereses_declarados(usuario_id: str, areas: Sequence[Tuple[str, float]]) -> None:
    """Sustituye los intereses declarados por `areas` (clave de área, peso). Lo usan 02 y la vista de 04.

    Los inferidos no se tocan.
    """
    catalogo = cargar_catalogo()
    nuevos = normalizar_areas(areas, catalogo)
    existentes = repository.leer_intereses(usuario_id, "declarado")
    _reemplazar_intereses(usuario_id, "declarado", nuevos, existentes, catalogo)


# --- Batch nocturno ---------------------------------------------------------


def recalcular_perfil(usuario_id: str, catalogo: Catalogo, ahora: Optional[datetime] = None,
                      simular: bool = False) -> Dict[str, Any]:
    """Recalcula intereses inferidos, abandonos y la foto en `perfiles` de un usuario.

    Con `simular` solo lee y devuelve el resumen, sin escribir nada.
    """
    ahora = ahora or _ahora()
    entrada = leer_entrada(usuario_id)
    perfil = construir_perfil(entrada, catalogo, ahora)

    vistas = [
        f.get("curso_id")
        for f in repository.leer_vistas(usuario_id, a_iso(ahora - timedelta(days=DIAS_VISTAS)))
    ]
    inferidos = intereses_inferidos(perfil, vistas, catalogo)

    activos = [c for c, i in perfil["inscripciones"].items() if i["estado"] == "activo"]
    eventos_cursos = [
        {"curso_id": curso_id, "fecha": repository.leer_ultimo_evento(usuario_id, curso_id)}
        for curso_id in activos
    ]
    actividad = ultima_actividad_por_curso(entrada["intentos"], eventos_cursos, catalogo)
    abandonos = cursos_abandonados(perfil["inscripciones"], actividad, ahora)

    publico = perfil_publico(perfil, areas_declaradas(entrada["intereses"], catalogo), catalogo)
    caracteristicas = {
        **publico,
        "tasa_aprobacion_modulos": perfil["tasa_aprobacion_modulos"],
        "intentos_promedio": perfil["intentos_promedio"],
        "dias_inactivo": perfil["dias_inactivo"],
    }

    if not simular:
        _reemplazar_intereses(usuario_id, "inferido", inferidos, entrada["intereses"], catalogo)
        for curso_id in abandonos:
            repository.marcar_abandonado(usuario_id, curso_id)
        repository.guardar_snapshot(
            usuario_id, perfil["nivel_inferido"], caracteristicas, a_iso(ahora)
        )

    return {
        "usuario_id": usuario_id,
        "nivel": perfil["nivel"],
        "nivel_inferido": perfil["nivel_inferido"],
        "intereses_inferidos": len(inferidos),
        "abandonados": abandonos,
        "simulado": simular,
    }
