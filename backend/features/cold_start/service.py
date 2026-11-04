"""Lógica de la evaluación inicial (Cold Start).

Asigna el nivel de partida del usuario a partir de su familiaridad declarada y
de los aciertos en las preguntas técnicas.
"""

from typing import Any, Dict, List, Optional, Sequence

from core.functional import to_int
from core.http import require_fields

from . import repository

NIVEL_PRINCIPIANTE = "Principiante"
NIVEL_INTERMEDIO = "Intermedio"
NIVEL_AVANZADO = "Avanzado"

FAMILIARIDAD_NULA = "No sé nada"
META_DIARIA_POR_DEFECTO_MINUTOS = 30

#: Umbrales (máximo de aciertos -> nivel), evaluados en orden ascendente.
UMBRALES_NIVEL = (
    (1, NIVEL_PRINCIPIANTE),
    (3, NIVEL_INTERMEDIO),
)


# --- Reglas puras -----------------------------------------------------------


def nivel_por_aciertos(aciertos: int) -> str:
    """Traduce un número de aciertos a nivel asignado. Pura.

    <=1 Principiante, <=3 Intermedio, el resto Avanzado.
    """
    return next(
        (nivel for umbral, nivel in UMBRALES_NIVEL if aciertos <= umbral),
        NIVEL_AVANZADO,
    )


def omite_prueba_tecnica(familiaridad: Any, respuestas: Sequence[Any]) -> bool:
    """True si no procede puntuar: no declara conocimientos o no respondió nada."""
    return familiaridad == FAMILIARIDAD_NULA or not respuestas


def extraer_opciones(respuestas: Sequence[Dict[str, Any]]) -> List[Any]:
    """Ids de opción enviados, descartando entradas sin `opcion_id`. Pura."""
    return [
        respuesta.get("opcion_id")
        for respuesta in respuestas
        if isinstance(respuesta, dict) and respuesta.get("opcion_id") is not None
    ]


def meta_diaria(disponibilidad: Any) -> int:
    """Minutos diarios a partir de la disponibilidad declarada. Pura."""
    return to_int(disponibilidad, META_DIARIA_POR_DEFECTO_MINUTOS) or (
        META_DIARIA_POR_DEFECTO_MINUTOS
    )


# --- Orquestación -----------------------------------------------------------


def _contar_aciertos(respuestas: Sequence[Dict[str, Any]]) -> int:
    """Cuenta cuántas de las opciones enviadas están marcadas como correctas."""
    opciones = extraer_opciones(respuestas)
    if not opciones:
        return 0
    return repository.contar_opciones_correctas(opciones)


def evaluar(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Evalúa el diagnóstico inicial y persiste el nivel asignado.

    Devuelve `{"nivel_asignado": ..., "aciertos": ...}`.
    """
    require_fields(datos, ("usuario_id",), "usuario_id es requerido.")

    usuario_id = datos["usuario_id"]
    respuestas = datos.get("respuestas_tecnicas") or []
    familiaridad = datos.get("familiaridad")

    if omite_prueba_tecnica(familiaridad, respuestas):
        aciertos = 0
        nivel = NIVEL_PRINCIPIANTE
    else:
        aciertos = _contar_aciertos(respuestas)
        nivel = nivel_por_aciertos(aciertos)

    repository.actualizar_nivel(
        usuario_id,
        nivel_asignado=nivel,
        objetivo_aprendizaje=datos.get("objetivo") or None,
    )

    disponibilidad = datos.get("disponibilidad")
    if disponibilidad:
        repository.guardar_meta_diaria(usuario_id, meta_diaria(disponibilidad))

    return {"nivel_asignado": nivel, "aciertos": aciertos}
