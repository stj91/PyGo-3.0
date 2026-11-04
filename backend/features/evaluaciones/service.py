"""Lógica de evaluación de módulos y motor adaptativo.

La corrección es una función pura sobre las respuestas enviadas y las opciones
consultadas; los efectos (registrar intento, desbloquear el siguiente tema,
recalcular avance) quedan aparte y ocurren después.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.errors import ValidationError
from core.functional import index_by, percentage, to_int
from core.http import require_fields

from . import repository

logger = logging.getLogger(__name__)

UMBRAL_APROBADO = 80
UMBRAL_REFUERZO = 70

ESTADO_COMPLETADO = "completado"
ESTADO_REFUERZO = "actividades_de_refuerzo"
ESTADO_DESBLOQUEADO = "desbloqueado"

MENSAJE_CORRECTO = "¡Correcto!"
MENSAJE_INCORRECTO = "Respuesta incorrecta."


# --- Reglas puras -----------------------------------------------------------


def corregir(
    respuestas: Sequence[Dict[str, Any]], opciones: Sequence[Dict[str, Any]]
) -> Tuple[int, List[Dict[str, Any]]]:
    """Corrige las respuestas y devuelve `(aciertos, retroalimentación)`. Pura."""
    por_id = index_by("id", opciones)

    detalle = [
        _detalle_respuesta(respuesta, por_id.get(respuesta.get("opcion_id")))
        for respuesta in respuestas
    ]
    aciertos = sum(1 for item in detalle if item["es_correcta"])
    return aciertos, detalle


def _detalle_respuesta(
    respuesta: Dict[str, Any], opcion: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Entrada de retroalimentación para una respuesta. Pura.

    Una opción que no existe cuenta como incorrecta, igual que el original. El
    `ejercicio_id` se toma de la opción cuando el cliente no lo envía, que es la
    fuente fiable: lo dice la propia base de datos.
    """
    es_correcta = bool(opcion.get("es_correcta")) if opcion else False
    return {
        "ejercicio_id": respuesta.get("ejercicio_id") or (opcion or {}).get("ejercicio_id"),
        "opcion_id": respuesta.get("opcion_id"),
        "es_correcta": es_correcta,
        "retroalimentacion": MENSAJE_CORRECTO if es_correcta else MENSAJE_INCORRECTO,
    }


def construir_intentos(
    usuario_id: str, detalle: Sequence[Dict[str, Any]], tiempo_total: int
) -> List[Dict[str, Any]]:
    """Filas de `intentos_ejercicios`, una por ejercicio respondido. Pura.

    La tabla registra por ejercicio, mientras que el cliente envía un tiempo
    total para todo el módulo, así que se reparte a partes iguales y el resto se
    asigna a la primera fila; de ese modo la suma sigue siendo el tiempo real.
    """
    con_ejercicio = [item for item in detalle if item.get("ejercicio_id") is not None]
    if not con_ejercicio:
        return []

    base, resto = divmod(max(tiempo_total, 0), len(con_ejercicio))

    return [
        {
            "usuario_id": usuario_id,
            "ejercicio_id": item["ejercicio_id"],
            "calificacion_obtenida": 100 if item["es_correcta"] else 0,
            "numero_aciertos": 1 if item["es_correcta"] else 0,
            "numero_errores": 0 if item["es_correcta"] else 1,
            "tiempo_resolucion_segundos": base + (resto if indice == 0 else 0),
        }
        for indice, item in enumerate(con_ejercicio)
    ]


def calificar(aciertos: int, total: int) -> int:
    """Calificación sobre 100. Pura; 0 si no hubo respuestas."""
    return percentage(aciertos, total)


def resultado(calificacion: int) -> Dict[str, bool]:
    """Veredicto derivado de la calificación. Pura."""
    return {
        "aprobado": calificacion >= UMBRAL_APROBADO,
        "requiere_refuerzo": calificacion < UMBRAL_REFUERZO,
    }


def extraer_opciones(respuestas: Sequence[Dict[str, Any]]) -> List[Any]:
    """Ids de opción enviados, descartando entradas inválidas. Pura."""
    return [
        respuesta.get("opcion_id")
        for respuesta in respuestas
        if isinstance(respuesta, dict) and respuesta.get("opcion_id") is not None
    ]


# --- Orquestación -----------------------------------------------------------


def _recalcular_avance_curso(usuario_id: str, curso_id: Any) -> None:
    """Recalcula el porcentaje global del usuario en el curso."""
    if not curso_id:
        return

    temas = repository.listar_temas_de_curso(curso_id)
    if not temas:
        return

    tema_ids = [tema["id"] for tema in temas if tema.get("id") is not None]
    completados = repository.contar_temas_completados(usuario_id, tema_ids)
    repository.guardar_avance_curso(usuario_id, curso_id, percentage(completados, len(temas)))


def _desbloquear_siguiente_tema(usuario_id: str, tema_actual: Dict[str, Any]) -> None:
    """Marca como desbloqueado el tema siguiente del temario, si existe."""
    orden = to_int(tema_actual.get("orden"))
    curso_id = tema_actual.get("curso_id")
    if orden is None or not curso_id:
        return

    siguiente = repository.buscar_tema_por_orden(curso_id, orden + 1)
    if siguiente:
        repository.marcar_estado_tema(usuario_id, siguiente["id"], ESTADO_DESBLOQUEADO)


def _aplicar_progreso(usuario_id: str, tema_id: Any, veredicto: Dict[str, bool]) -> None:
    """Aplica las consecuencias adaptativas del resultado."""
    if veredicto["requiere_refuerzo"]:
        repository.marcar_estado_tema(usuario_id, tema_id, ESTADO_REFUERZO)
        return

    if not veredicto["aprobado"]:
        # Zona intermedia (70-79): ni refuerzo ni aprobado, no se toca el estado.
        return

    repository.marcar_estado_tema(usuario_id, tema_id, ESTADO_COMPLETADO)

    tema_actual = repository.buscar_tema(tema_id)
    if not tema_actual:
        return

    _desbloquear_siguiente_tema(usuario_id, tema_actual)
    _recalcular_avance_curso(usuario_id, tema_actual.get("curso_id"))


def evaluar_modulo(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Corrige un módulo, registra el intento y avanza el progreso.

    Devuelve la misma forma que el backend Node: sin clave `success`, para no
    romper al cliente que ya consume este endpoint.
    """
    respuestas = datos.get("respuestas") or []
    require_fields(
        {**datos, "respuestas": respuestas},
        ("usuario_id", "tema_id", "respuestas"),
        "Faltan parámetros requeridos para la evaluación.",
    )

    if not isinstance(respuestas, list):
        raise ValidationError(
            "El campo `respuestas` debe ser una lista.", campos=["respuestas"]
        )

    usuario_id = datos["usuario_id"]
    tema_id = datos["tema_id"]

    opciones_ids = extraer_opciones(respuestas)
    opciones = repository.buscar_opciones(opciones_ids) if opciones_ids else []

    aciertos, retroalimentacion = corregir(respuestas, opciones)
    calificacion = calificar(aciertos, len(respuestas))
    veredicto = resultado(calificacion)

    repository.registrar_intentos(
        construir_intentos(
            usuario_id,
            retroalimentacion,
            to_int(datos.get("tiempo_resolucion_segundos"), 0) or 0,
        )
    )

    _aplicar_progreso(usuario_id, tema_id, veredicto)

    return {
        "calificacion": calificacion,
        "aprobado": veredicto["aprobado"],
        "requiere_refuerzo": veredicto["requiere_refuerzo"],
        "retroalimentacion": retroalimentacion,
    }
