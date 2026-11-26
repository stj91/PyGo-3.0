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


"""
Cuando el usuario empieza a estudiar, el motor necesita actualizar
su perfil sin acoplarse al módulo de evaluaciones. Para eso implementamos
un patrón de ganchos. Cada vez que un usuario termina un examen,
en la siguiente función se dispara de forma aislada bajo un bloque
_seguro para garantizar que, incluso si el motor fallara, la
calificación del usuario no se pierda.

When a user starts studying, the engine needs to update their profile
without being coupled to the evaluation module. That's why we implemented
a hook pattern. Every time a user finishes an exam, the next following 
function is triggered independently within a safe block to garanteed 
that even if the engine fails, the user's grade isn't lost.
"""

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

    """
    En esta parte medicomo cuánto sabe realmente el usuario acerca de cada tema.
    Cada ejercicio está etiquetado con conceptos de Python (bucles, condicionales,
    o clases). Actualizamos su nivel de dominio de 0 a 1 usando una media móvil
    exponencial.

    In this part we measure how much the user really knows about a topic.
    Every exercise is labeled with Python concepts (loops, conditionals or 
    classes). We update the user's profiency level on a scale from 0 to 1 using 
    an exponential moving average. 
    """

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
