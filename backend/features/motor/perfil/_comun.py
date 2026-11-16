"""Utilidades puras compartidas por el paquete de perfil: fechas, niveles y catálogo."""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..tipos import Catalogo, TemaCatalogo

#: Orden de los niveles: Principiante < Intermedio < Avanzado.
RANGO_NIVEL = {"Principiante": 0, "Intermedio": 1, "Avanzado": 2}

#: Rango de los estados de un módulo; el mismo que usa la migración 0005 y
#: `avanza_estado` de evaluaciones (02). Se reimplementa para no depender de 02.
RANGO_ESTADO_TEMA = {
    "completado": 3,
    "actividades_de_refuerzo": 2,
    "desbloqueado": 1,
}

#: Tipo de ejercicio del diagnóstico inicial.
TIPO_DIAGNOSTICO = "evaluacion_tecnica"

_FRACCION = re.compile(r"\.(\d+)")


def rango_nivel(nivel: Optional[str]) -> int:
    return RANGO_NIVEL.get(nivel or "", 0)


def nivel_valido(nivel: Optional[str]) -> str:
    return nivel if nivel in RANGO_NIVEL else "Principiante"


def rango_estado(estado: Optional[str]) -> int:
    return RANGO_ESTADO_TEMA.get(estado or "", 0)


def a_fecha(valor: Any) -> Optional[datetime]:
    """`datetime` con zona horaria a partir de un `datetime` o una cadena ISO-8601.

    Python 3.9 no acepta `Z` ni fracciones de longitud arbitraria (PostgREST
    devuelve las que haya), así que se normalizan antes de parsear. Una fecha
    sin zona se toma como UTC. `None` si no se puede interpretar.
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        fecha = valor
    elif isinstance(valor, str) and valor.strip():
        texto = valor.strip().replace(" ", "T", 1)
        if texto.endswith(("Z", "z")):
            texto = texto[:-1] + "+00:00"
        texto = _FRACCION.sub(lambda m: "." + (m.group(1) + "000000")[:6], texto, count=1)
        try:
            fecha = datetime.fromisoformat(texto)
        except ValueError:
            return None
    else:
        return None
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


def a_iso(fecha: Optional[datetime]) -> Optional[str]:
    """Cadena ISO-8601 en UTC con `Z`, como en los contratos HTTP."""
    if fecha is None:
        return None
    utc = fecha.astimezone(timezone.utc).replace(microsecond=0)
    return utc.isoformat().replace("+00:00", "Z")


def temas_por_id(catalogo: Catalogo) -> Dict[int, TemaCatalogo]:
    return {
        tema["id"]: tema
        for curso in catalogo.get("cursos", {}).values()
        for tema in curso.get("temas", [])
    }


def a_entero(valor: Any) -> Optional[int]:
    if isinstance(valor, bool):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def a_float(valor: Any, defecto: Optional[float] = None) -> Optional[float]:
    if valor is None:
        return defecto
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto
