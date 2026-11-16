"""Servicio de inscripción explícita a cursos.

Los prerrequisitos no se exigen aquí: la inscripción es orientativa, igual que
los bloqueos de módulos.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from core.errors import DataAccessError, NotFoundError, ValidationError
from core.functional import omit_none

from .. import registro
from ..catalogo import cargar_catalogo
from ..eventos import service as eventos
from ..eventos.repository import a_fecha
from ..eventos.validacion import ORIGENES_CURSO, es_recomendacion_id
from ..tipos import Inscripcion
from . import repository

logger = logging.getLogger(__name__)

ORIGEN_POR_DEFECTO = "catalogo"
_CLAVE_DUPLICADA = "23505"


def _curso_id(valor: Any) -> int:
    """Id de curso de la URL o del cuerpo como entero positivo; si no, 404."""
    texto = str(valor)
    if not (texto.isascii() and texto.isdigit()) or int(texto) <= 0:
        raise NotFoundError("Curso no encontrado.")
    return int(texto)


def _origen(valor: Optional[str]) -> str:
    if valor is None or valor == "":
        return ORIGEN_POR_DEFECTO
    if not isinstance(valor, str) or valor not in ORIGENES_CURSO:
        raise ValidationError("`origen` no es válido.", campos=["origen"])
    return valor


def _numero(valor: Any) -> Optional[float]:
    return None if valor is None else float(valor)


def a_inscripcion(fila: Dict[str, Any]) -> Inscripcion:
    """Fila de `usuario_cursos` con la forma `Inscripcion`. **Pura.**"""
    return {
        "curso_id": int(fila["curso_id"]),
        "estado": fila.get("estado") or "activo",
        "porcentaje_avance_global": _numero(fila.get("porcentaje_avance_global")) or 0.0,
        "calificacion_final": _numero(fila.get("calificacion_final")),
        "fecha_inscripcion": a_fecha(fila.get("fecha_inscripcion")),
        "completado_en": a_fecha(fila.get("completado_en")),
        "origen": fila.get("origen"),
    }


def _crear(usuario_id: str, curso_id: int, origen: str, recomendacion_id: Optional[str]) -> Optional[dict]:
    """Inserta la inscripción; `None` si otra petición simultánea la creó antes."""
    fila = omit_none({
        "usuario_id": usuario_id,
        "curso_id": curso_id,
        "estado": "activo",
        "porcentaje_avance_global": 0,
        "origen": origen,
        "recomendacion_id": recomendacion_id,
    })
    try:
        return repository.insertar(fila)
    except DataAccessError as error:
        if error.upstream_code == _CLAVE_DUPLICADA:
            return None
        raise


def _desbloquear_primer_tema(usuario_id: str, curso: dict) -> None:
    temas = curso.get("temas") or []
    if not temas:
        return
    tema_id = temas[0]["id"]
    if repository.tiene_fila_tema(usuario_id, tema_id):
        return
    try:
        repository.desbloquear_tema(usuario_id, tema_id)
    except DataAccessError as error:
        if error.upstream_code != _CLAVE_DUPLICADA:
            raise


def _registrar_evento(usuario_id: str, curso_id: int, origen: str, recomendacion_id: Optional[str]) -> None:
    # La inscripción ya está guardada: un fallo de analítica no debe convertirla en error.
    try:
        eventos.registrar_servidor(
            usuario_id, "curso_inscripcion", objeto_tipo="curso", objeto_id=curso_id,
            curso_id=curso_id, datos=omit_none({"origen": origen, "recomendacion_id": recomendacion_id}),
        )
    except Exception:
        logger.exception("No se pudo registrar curso_inscripcion para el curso %s", curso_id)


def _marcar_aceptada(recomendacion_id: str, usuario_id: str) -> None:
    try:
        registro.marcar_aceptada(recomendacion_id, usuario_id)
    except NotImplementedError:
        logger.debug("registro.marcar_aceptada aún no está implementado")
    except Exception:
        logger.exception("No se pudo marcar como aceptada la recomendación %s", recomendacion_id)


def inscribir_o_recuperar(
    usuario_id: str, curso_id: Any, origen: Optional[str], recomendacion_id: Optional[str]
) -> Tuple[Inscripcion, bool]:
    """Como `inscribir`, pero dice además si la inscripción es nueva (201) o ya existía (200)."""
    curso_id = _curso_id(curso_id)
    curso = cargar_catalogo()["cursos"].get(curso_id)
    if curso is None:
        raise NotFoundError("Curso no encontrado.")

    existente = repository.buscar(usuario_id, curso_id)
    if existente is not None:
        return a_inscripcion(existente), False

    origen = _origen(origen)
    recomendacion_id = recomendacion_id if es_recomendacion_id(recomendacion_id) else None
    creada = _crear(usuario_id, curso_id, origen, recomendacion_id)
    if creada is None:
        return a_inscripcion(repository.buscar(usuario_id, curso_id) or {"curso_id": curso_id}), False

    _desbloquear_primer_tema(usuario_id, curso)
    _registrar_evento(usuario_id, curso_id, origen, recomendacion_id)
    if recomendacion_id is not None:
        _marcar_aceptada(recomendacion_id, usuario_id)
    return a_inscripcion(creada), True


def inscribir(
    usuario_id: str, curso_id: int, origen: Optional[str], recomendacion_id: Optional[str]
) -> Inscripcion:
    """Inscribe al usuario en un curso publicado, o devuelve la inscripción existente sin cambiarla."""
    return inscribir_o_recuperar(usuario_id, curso_id, origen, recomendacion_id)[0]
