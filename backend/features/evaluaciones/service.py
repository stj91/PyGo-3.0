"""Lógica de evaluación de módulos y motor adaptativo.

La corrección es una función pura sobre las respuestas enviadas, los ejercicios
del módulo y sus opciones; los efectos (registrar intentos, avanzar estados,
recalcular avance, completar el curso, avisar al motor) ocurren después.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.errors import NotFoundError, ValidationError
from core.functional import percentage, to_int
from core.http import require_fields
from features.cursos.service import sin_diagnostico
from features.motor import config, ganchos

from . import repository

logger = logging.getLogger(__name__)

ESTADO_COMPLETADO = "completado"
ESTADO_REFUERZO = "actividades_de_refuerzo"
ESTADO_DESBLOQUEADO = "desbloqueado"

#: Rango de cada estado de `usuario_temas`; cualquier otro (o `Bloqueado`) es 0.
RANGO_ESTADO = {ESTADO_COMPLETADO: 3, ESTADO_REFUERZO: 2, ESTADO_DESBLOQUEADO: 1}

MENSAJE_CORRECTO = "¡Correcto!"
MENSAJE_INCORRECTO = "Respuesta incorrecta."
MENSAJE_SIN_RESPONDER = "Sin responder."


# --- Reglas puras -----------------------------------------------------------


def _entero(valor: Any) -> Optional[int]:
    """Entero estricto: descarta booleanos y textos no numéricos. Pura."""
    if isinstance(valor, bool):
        return None
    return to_int(valor)


def corregir(
    respuestas: Sequence[Any],
    opciones: Sequence[Mapping[str, Any]],
    ejercicios: Sequence[Mapping[str, Any]],
) -> Tuple[int, List[Dict[str, Any]], List[Any]]:
    """Corrige un módulo y devuelve `(aciertos, retroalimentación, opciones_rechazadas)`. Pura.

    Solo cuenta una opción que pertenezca a un ejercicio calificable del módulo;
    el ejercicio se toma de la propia opción, no del cliente. Una respuesta por
    ejercicio (gana la última). La retroalimentación lleva una entrada por
    ejercicio del módulo, en su orden; los no respondidos cuentan como fallo.
    """
    calificables = sin_diagnostico(ejercicios)
    ids_ejercicio = {_entero(e.get("id")) for e in calificables}
    opciones_del_modulo = {
        _entero(o.get("id")): o
        for o in opciones
        if _entero(o.get("ejercicio_id")) in ids_ejercicio and _entero(o.get("id")) is not None
    }

    elegidas: Dict[int, Mapping[str, Any]] = {}
    rechazadas: List[Any] = []
    for respuesta in respuestas:
        if not isinstance(respuesta, dict) or respuesta.get("opcion_id") is None:
            continue
        opcion = opciones_del_modulo.get(_entero(respuesta.get("opcion_id")))
        if opcion is None:
            rechazadas.append(respuesta.get("opcion_id"))
            continue
        elegidas[_entero(opcion.get("ejercicio_id"))] = opcion

    retroalimentacion = [
        _detalle_ejercicio(_entero(ejercicio.get("id")), elegidas.get(_entero(ejercicio.get("id"))))
        for ejercicio in calificables
    ]
    aciertos = sum(1 for item in retroalimentacion if item["es_correcta"])
    return aciertos, retroalimentacion, rechazadas


def _detalle_ejercicio(ejercicio_id: Optional[int], opcion: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Entrada de retroalimentación de un ejercicio del módulo. Pura."""
    if opcion is None:
        return {
            "ejercicio_id": ejercicio_id,
            "opcion_id": None,
            "es_correcta": False,
            "retroalimentacion": MENSAJE_SIN_RESPONDER,
        }
    es_correcta = bool(opcion.get("es_correcta"))
    return {
        "ejercicio_id": ejercicio_id,
        "opcion_id": _entero(opcion.get("id")),
        "es_correcta": es_correcta,
        "retroalimentacion": MENSAJE_CORRECTO if es_correcta else MENSAJE_INCORRECTO,
    }


def construir_intentos(
    usuario_id: str, detalle: Sequence[Mapping[str, Any]], tiempo_total: int
) -> List[Dict[str, Any]]:
    """Filas de `intentos_ejercicios`, una por ejercicio del módulo. Pura.

    El cliente envía un tiempo total para todo el módulo, así que se reparte a
    partes iguales y el resto va a la primera fila: la suma es el tiempo real.
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
    """Calificación sobre 100. Pura; 0 si no hay ejercicios."""
    return percentage(aciertos, total)


def resultado(calificacion: int) -> Dict[str, bool]:
    """Veredicto derivado de la calificación. Pura."""
    return {
        "aprobado": calificacion >= config.UMBRAL_APROBADO,
        "requiere_refuerzo": calificacion < config.UMBRAL_REFUERZO,
    }


def avanza_estado(actuales: Sequence[Optional[str]], nuevo: str) -> bool:
    """True si `nuevo` supera en rango a **todos** los estados actuales. Pura.

    completado 3 > actividades_de_refuerzo 2 > desbloqueado 1 > el resto 0. Sin
    filas, cualquier estado avanza.
    """
    rango_nuevo = RANGO_ESTADO.get(nuevo, 0)
    return all(rango_nuevo > RANGO_ESTADO.get(actual, 0) for actual in actuales)


def agrupar_intentos(
    intentos: Sequence[Mapping[str, Any]], ejercicios: Sequence[Mapping[str, Any]]
) -> Dict[int, List[Mapping[str, Any]]]:
    """Intentos por ejercicio, solo de ejercicios calificables. Pura."""
    validos = {_entero(e.get("id")) for e in sin_diagnostico(ejercicios)}
    agrupados: Dict[int, List[Mapping[str, Any]]] = {}
    for intento in intentos:
        ejercicio_id = _entero(intento.get("ejercicio_id"))
        if ejercicio_id in validos:
            agrupados[ejercicio_id] = [*agrupados.get(ejercicio_id, []), intento]
    return agrupados


def calificacion_final(intentos_por_ejercicio: Mapping[Any, Sequence[Mapping[str, Any]]]) -> float:
    """Media de la última `calificacion_obtenida` de cada ejercicio, a 2 decimales. Pura.

    El último intento es el de `fecha_intento` más reciente (y, a igualdad, id mayor).
    """
    ultimas = []
    for intentos in intentos_por_ejercicio.values():
        con_nota = [i for i in intentos if i.get("calificacion_obtenida") is not None]
        if not con_nota:
            continue
        ultimo = max(
            con_nota,
            key=lambda i: (str(i.get("fecha_intento") or ""), _entero(i.get("id")) or 0),
        )
        ultimas.append(float(ultimo["calificacion_obtenida"]))
    return round(sum(ultimas) / len(ultimas), 2) if ultimas else 0.0


# --- Orquestación -----------------------------------------------------------


def _marcar_si_avanza(usuario_id: str, tema_id: int, nuevo: str) -> None:
    """Escribe el estado solo si mejora todos los actuales."""
    if avanza_estado(repository.estados_tema(usuario_id, tema_id), nuevo):
        repository.marcar_estado_tema(usuario_id, tema_id, nuevo)


def _desbloquear_siguiente_tema(usuario_id: str, tema: Mapping[str, Any]) -> None:
    """Desbloquea el tema siguiente del temario, si existe."""
    orden = _entero(tema.get("orden"))
    curso_id = tema.get("curso_id")
    if orden is None or not curso_id:
        return

    siguiente = repository.buscar_tema_por_orden(curso_id, orden + 1)
    if siguiente and siguiente.get("id") is not None:
        _marcar_si_avanza(usuario_id, siguiente["id"], ESTADO_DESBLOQUEADO)


def _completar_curso_si_toca(usuario_id: str, curso_id: Any, tema_ids: List[Any]) -> None:
    """Cierra la inscripción la primera vez que el avance llega a 100."""
    inscripcion = repository.buscar_inscripcion(usuario_id, curso_id)
    if inscripcion and inscripcion.get("estado") == ESTADO_COMPLETADO:
        return

    ejercicios = repository.listar_ejercicios_de_temas(tema_ids)
    calificables = [e["id"] for e in sin_diagnostico(ejercicios) if e.get("id") is not None]
    intentos = repository.listar_intentos(usuario_id, calificables)
    nota = calificacion_final(agrupar_intentos(intentos, ejercicios))

    repository.completar_curso(
        usuario_id,
        curso_id,
        calificacion_final=nota,
        completado_en=datetime.now(timezone.utc).isoformat(),
    )
    ganchos.al_completar_curso(usuario_id, curso_id, nota)


def _recalcular_avance_curso(usuario_id: str, curso_id: Any) -> None:
    """Recalcula el porcentaje global y completa el curso si llega a 100."""
    if not curso_id:
        return

    temas = repository.listar_temas_de_curso(curso_id)
    tema_ids = [tema["id"] for tema in temas if tema.get("id") is not None]
    if not tema_ids:
        return

    completados = repository.contar_temas_completados(usuario_id, tema_ids)
    porcentaje = percentage(completados, len(tema_ids))
    repository.guardar_avance_curso(usuario_id, curso_id, porcentaje)

    if porcentaje >= 100:
        _completar_curso_si_toca(usuario_id, curso_id, tema_ids)


def _aplicar_progreso(usuario_id: str, tema: Mapping[str, Any], veredicto: Dict[str, bool]) -> None:
    """Aplica las consecuencias adaptativas del resultado sin retroceder estados."""
    tema_id = tema["id"]

    if veredicto["requiere_refuerzo"]:
        _marcar_si_avanza(usuario_id, tema_id, ESTADO_REFUERZO)
        return

    if not veredicto["aprobado"]:
        # Zona intermedia: ni refuerzo ni aprobado, no se toca el estado.
        return

    _marcar_si_avanza(usuario_id, tema_id, ESTADO_COMPLETADO)
    _desbloquear_siguiente_tema(usuario_id, tema)
    _recalcular_avance_curso(usuario_id, tema.get("curso_id"))


def evaluar_modulo(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Corrige un módulo, registra los intentos, avanza el progreso y avisa al motor.

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
        raise ValidationError("El campo `respuestas` debe ser una lista.", campos=["respuestas"])

    tema_id = _entero(datos["tema_id"])
    if tema_id is None:
        raise ValidationError("`tema_id` debe ser un número entero.", campos=["tema_id"])

    usuario_id = datos["usuario_id"]

    tema = repository.buscar_tema(tema_id)
    if not tema:
        raise NotFoundError("Tema no encontrado.")
    tema = {"id": tema_id, "curso_id": tema.get("curso_id"), "orden": tema.get("orden")}

    ejercicios = sin_diagnostico(repository.listar_ejercicios_de_temas([tema_id]))
    if not ejercicios:
        raise ValidationError("Este módulo no tiene ejercicios que calificar.", campos=["tema_id"])

    opciones = repository.listar_opciones_de_ejercicios([e["id"] for e in ejercicios])
    aciertos, retroalimentacion, rechazadas = corregir(respuestas, opciones, ejercicios)
    if rechazadas:
        logger.warning(
            "evaluar_modulo: %d opción(es) ajenas al tema %s ignoradas.", len(rechazadas), tema_id
        )

    calificacion = calificar(aciertos, len(ejercicios))
    veredicto = resultado(calificacion)

    repository.registrar_intentos(
        construir_intentos(
            usuario_id,
            retroalimentacion,
            to_int(datos.get("tiempo_resolucion_segundos"), 0) or 0,
        )
    )

    _aplicar_progreso(usuario_id, tema, veredicto)

    ganchos.al_evaluar_modulo(
        usuario_id,
        tema,
        calificacion,
        [{"ejercicio_id": r["ejercicio_id"], "es_correcta": r["es_correcta"]} for r in retroalimentacion],
        veredicto["aprobado"],
    )

    return {
        "calificacion": calificacion,
        "aprobado": veredicto["aprobado"],
        "requiere_refuerzo": veredicto["requiere_refuerzo"],
        "retroalimentacion": retroalimentacion,
    }
