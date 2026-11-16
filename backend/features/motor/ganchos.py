"""Ganchos: la única vía por la que la calificación y el diagnóstico avisan al motor.

Los llama 02 (evaluaciones y cold start). **Un gancho nunca lanza**: cada
llamada interna va aislada, se registra en el log y se sigue, para que un motor
sin terminar o con fallos no pueda romper nunca la calificación.

Los módulos de destino se importan dentro de cada gancho (el módulo, no la
función), así el reemplazo de los stubs y los imports circulares son seguros.
"""

import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


def _seguro(descripcion: str, llamada: Callable[[], object]) -> None:
    try:
        llamada()
    except NotImplementedError:
        logger.debug("Gancho %s: destino pendiente de implementar.", descripcion)
    except Exception:
        logger.exception("Gancho %s: fallo ignorado.", descripcion)


def al_evaluar_modulo(
    usuario_id: str, tema: dict, calificacion: int, detalle: List[dict], aprobado: bool
) -> None:
    """Tras calificar un módulo.

    `tema = {"id", "curso_id", "orden"}`; `detalle = [{"ejercicio_id", "es_correcta"}]`.
    Registra `quiz_intento`, actualiza el dominio por concepto y, si aprobó,
    registra `tema_completado`.
    """
    try:
        tema_id = tema["id"]
        curso_id = tema.get("curso_id")
        puntaje = calificacion / 100
    except Exception:
        logger.exception("Gancho al_evaluar_modulo: argumentos inválidos.")
        return

    def evento_intento() -> None:
        from features.motor.eventos import service as eventos

        eventos.registrar_servidor(
            usuario_id,
            "quiz_intento",
            objeto_tipo="tema",
            objeto_id=tema_id,
            curso_id=curso_id,
            valor=puntaje,
            datos={"detalle": detalle},
        )

    def dominio() -> None:
        from features.motor.perfil import service as perfil

        perfil.actualizar_dominio_por_tema(usuario_id, tema_id, puntaje)

    def evento_completado() -> None:
        from features.motor.eventos import service as eventos

        eventos.registrar_servidor(
            usuario_id,
            "tema_completado",
            objeto_tipo="tema",
            objeto_id=tema_id,
            curso_id=curso_id,
        )

    _seguro("al_evaluar_modulo:quiz_intento", evento_intento)
    _seguro("al_evaluar_modulo:dominio", dominio)
    if aprobado:
        _seguro("al_evaluar_modulo:tema_completado", evento_completado)


def al_completar_curso(usuario_id: str, curso_id: int, calificacion_final: float) -> None:
    """Al terminar un curso. Registra `curso_completado`."""

    def evento() -> None:
        from features.motor.eventos import service as eventos

        eventos.registrar_servidor(
            usuario_id,
            "curso_completado",
            objeto_tipo="curso",
            objeto_id=curso_id,
            curso_id=curso_id,
            valor=calificacion_final,
        )

    _seguro("al_completar_curso", evento)


def al_completar_diagnostico(usuario_id: str, resultados: Dict[int, bool], nivel: str) -> None:
    """Tras el diagnóstico inicial.

    `resultados = {ejercicio_id: acertó?}`. Siembra el dominio por concepto y
    registra `diagnostico` con la proporción de aciertos.
    """
    try:
        resultados = dict(resultados or {})
        aciertos = sum(1 for correcto in resultados.values() if correcto)
        proporcion = aciertos / len(resultados) if resultados else 0.0
        datos = {
            "resultados": {str(k): bool(v) for k, v in resultados.items()},
            "nivel": nivel,
        }
    except Exception:
        logger.exception("Gancho al_completar_diagnostico: argumentos inválidos.")
        return

    def dominio() -> None:
        from features.motor.perfil import service as perfil

        perfil.sembrar_dominio(usuario_id, resultados, nivel)

    def evento() -> None:
        from features.motor.eventos import service as eventos

        eventos.registrar_servidor(usuario_id, "diagnostico", valor=proporcion, datos=datos)

    _seguro("al_completar_diagnostico:dominio", dominio)
    _seguro("al_completar_diagnostico:evento", evento)
