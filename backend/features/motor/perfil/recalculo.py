"""Decisiones puras del batch nocturno `recalcular_perfiles`: intereses inferidos y abandono."""

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from .. import config
from ..tipos import Catalogo, Perfil
from ._comun import a_entero, a_fecha, temas_por_id
from .construir import combinar_max

#: Ventana de las visitas a cursos que cuentan como interés inferido.
DIAS_VISTAS = 90


def intereses_inferidos(perfil: Perfil, vistas: Iterable[int], catalogo: Catalogo) -> Dict[str, float]:
    """Intereses inferidos por concepto.

    Conceptos de los cursos completados a `PESO_INTERES_INFERIDO_COMPLETADO × peso`
    y de los cursos vistos (`vistas`: ids de curso con `curso_vista` en los últimos
    90 días, ya filtrados por el llamante) a `PESO_INTERES_INFERIDO_VISTO × peso`,
    combinados por máximo.
    """
    cursos = catalogo.get("cursos", {})
    vectores = []
    for curso_id in perfil.get("cursos_completados", []):
        if curso_id in cursos:
            vectores.append({
                c: config.PESO_INTERES_INFERIDO_COMPLETADO * p
                for c, p in cursos[curso_id]["conceptos"].items()
            })
    for curso_id in vistas:
        curso = cursos.get(a_entero(curso_id))
        if curso is not None:
            vectores.append({
                c: config.PESO_INTERES_INFERIDO_VISTO * p for c, p in curso["conceptos"].items()
            })
    return {c: p for c, p in combinar_max(*vectores).items() if p > 0}


def ultima_actividad_por_curso(
    intentos: Iterable[Dict[str, Any]],
    eventos: Iterable[Dict[str, Any]],
    catalogo: Catalogo,
) -> Dict[int, datetime]:
    """curso -> fecha de la última actividad: un intento en uno de sus módulos o un evento con su `curso_id`."""
    temas = temas_por_id(catalogo)
    resultado: Dict[int, datetime] = {}

    def anotar(curso_id: Optional[int], fecha: Optional[datetime]) -> None:
        if curso_id is not None and fecha is not None and (
            curso_id not in resultado or fecha > resultado[curso_id]
        ):
            resultado[curso_id] = fecha

    for intento in intentos:
        tema = temas.get(a_entero(intento.get("tema_id")))
        anotar(tema["curso_id"] if tema else None, a_fecha(intento.get("fecha_intento")))
    for evento in eventos:
        anotar(a_entero(evento.get("curso_id")), a_fecha(evento.get("fecha")))
    return resultado


def cursos_abandonados(
    inscripciones: Dict[int, Dict[str, Any]],
    actividad: Dict[int, datetime],
    ahora: datetime,
) -> List[int]:
    """Inscripciones `activo` cuya última actividad (o, sin ella, la fecha de
    inscripción) tiene más de `DIAS_PARA_ABANDONO` días."""
    limite = a_fecha(ahora) - timedelta(days=config.DIAS_PARA_ABANDONO)
    resultado = []
    for curso_id, inscripcion in sorted(inscripciones.items()):
        if inscripcion.get("estado") != "activo":
            continue
        referencia = actividad.get(curso_id) or a_fecha(inscripcion.get("fecha_inscripcion"))
        if referencia is not None and referencia < limite:
            resultado.append(curso_id)
    return resultado
