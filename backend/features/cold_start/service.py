"""Lógica de la evaluación inicial (Cold Start).

Asigna el nivel de partida del usuario a partir de su familiaridad declarada y
de los aciertos en las preguntas del diagnóstico (ejercicios de tipo
`evaluacion_tecnica`), guarda sus metas de estudio e intereses y avisa al motor.
"""

import logging
from typing import Any, Collection, Dict, List, Mapping, Sequence, Tuple

from core.errors import ValidationError
from core.functional import to_int
from core.http import require_fields
from features.motor import config, ganchos

from . import repository

logger = logging.getLogger(__name__)

NIVEL_PRINCIPIANTE = "Principiante"
NIVEL_INTERMEDIO = "Intermedio"
NIVEL_AVANZADO = "Avanzado"

FAMILIARIDAD_NULA = "No sé nada"

#: Umbrales (máximo de aciertos -> nivel), evaluados en orden ascendente.
UMBRALES_NIVEL = (
    (1, NIVEL_PRINCIPIANTE),
    (3, NIVEL_INTERMEDIO),
)

#: Minutos semanales por opción de disponibilidad. Las claves son los textos
#: exactos de `ColdStart.jsx`.
MINUTOS_SEMANALES_POR_DISPONIBILIDAD = {
    "5 a 10 minutos al día (Sesiones micro)": 70,
    "Un par de horas a la semana": 120,
    "Fines de semana exclusivamente": 180,
    "1 hora diaria estructurada": 420,
}
META_DIARIA_POR_DEFECTO = 30
META_SEMANAL_POR_DEFECTO = 210


# --- Reglas puras -----------------------------------------------------------


def formatear_preguntas(ejercicios: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """`[{id, consigna, opciones: [{id, texto_opcion}]}]` por id. Pura.

    Copia solo los campos públicos, así que `es_correcta` no puede salir aunque
    venga en la entrada. Las opciones se ordenan por `orden` (y por id a igualdad).
    """
    return [
        {
            "id": ejercicio.get("id"),
            "consigna": ejercicio.get("consigna") or "",
            "opciones": [
                {"id": opcion.get("id"), "texto_opcion": opcion.get("texto_opcion")}
                for opcion in sorted(
                    ejercicio.get("opciones_ejercicios") or [],
                    key=lambda o: (to_int(o.get("orden"), 0), to_int(o.get("id"), 0)),
                )
            ],
        }
        for ejercicio in sorted(ejercicios, key=lambda e: to_int(e.get("id"), 0))
    ]


def ids_de_opciones(respuestas: Sequence[Any]) -> List[int]:
    """Ids de opción enviados que son enteros, sin repetir. Pura."""
    vistos: List[int] = []
    for respuesta in respuestas:
        if not isinstance(respuesta, dict):
            continue
        opcion_id = _entero(respuesta.get("opcion_id"))
        if opcion_id is not None and opcion_id not in vistos:
            vistos.append(opcion_id)
    return vistos


def corregir_diagnostico(
    respuestas: Sequence[Any],
    opciones_por_id: Mapping[int, Mapping[str, Any]],
    ejercicios_diagnostico: Collection[int],
) -> Dict[int, bool]:
    """`{ejercicio_id: acertó?}` de las preguntas del diagnóstico. Pura.

    Una respuesta solo cuenta si su opción existe, pertenece al ejercicio que
    dice responder y ese ejercicio es del diagnóstico. Una por ejercicio: gana
    la última válida. Las preguntas sin responder no aparecen.
    """
    diagnostico = {int(e) for e in ejercicios_diagnostico}
    resultados: Dict[int, bool] = {}
    for respuesta in respuestas:
        if not isinstance(respuesta, dict):
            continue
        ejercicio_id = _entero(respuesta.get("ejercicio_id"))
        opcion = opciones_por_id.get(_entero(respuesta.get("opcion_id")))
        if (
            ejercicio_id is None
            or ejercicio_id not in diagnostico
            or not opcion
            or _entero(opcion.get("ejercicio_id")) != ejercicio_id
        ):
            continue
        resultados[ejercicio_id] = bool(opcion.get("es_correcta"))
    return resultados


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


def metas_estudio(disponibilidad: Any) -> Dict[str, int]:
    """`{meta_diaria_minutos, meta_semanal_minutos}` según la disponibilidad. Pura.

    Un número se lee como minutos diarios. Cualquier otro valor da 30 / 210.
    """
    if isinstance(disponibilidad, str) and disponibilidad in MINUTOS_SEMANALES_POR_DISPONIBILIDAD:
        semanal = MINUTOS_SEMANALES_POR_DISPONIBILIDAD[disponibilidad]
        return {"meta_diaria_minutos": max(1, round(semanal / 7)), "meta_semanal_minutos": semanal}

    diaria = _entero(disponibilidad)
    if diaria is not None and diaria > 0:
        return {"meta_diaria_minutos": diaria, "meta_semanal_minutos": diaria * 7}

    return {
        "meta_diaria_minutos": META_DIARIA_POR_DEFECTO,
        "meta_semanal_minutos": META_SEMANAL_POR_DEFECTO,
    }


def areas_de_intereses(
    intereses: Any, objetivo: Any, areas_validas: Collection[str]
) -> List[Tuple[str, float]]:
    """Pares `(área, peso)` declarados más el área del objetivo. Pura.

    Solo claves válidas y sin repetir, con `PESO_INTERES_DECLARADO`; el área del
    objetivo (`OBJETIVO_A_AREA`) entra con `PESO_INTERES_OBJETIVO` si no estaba
    ya declarada.
    """
    validas = set(areas_validas)
    declaradas: List[str] = []
    for clave in intereses if isinstance(intereses, (list, tuple)) else ():
        if isinstance(clave, str) and clave in validas and clave not in declaradas:
            declaradas.append(clave)

    pares = [(clave, config.PESO_INTERES_DECLARADO) for clave in declaradas]
    area_objetivo = config.OBJETIVO_A_AREA.get(objetivo) if isinstance(objetivo, str) else None
    if area_objetivo and area_objetivo in validas and area_objetivo not in declaradas:
        pares.append((area_objetivo, config.PESO_INTERES_OBJETIVO))
    return pares


def construir_intentos(usuario_id: str, resultados: Mapping[int, bool]) -> List[Dict[str, Any]]:
    """Una fila de `intentos_ejercicios` por pregunta respondida. Pura."""
    return [
        {
            "usuario_id": usuario_id,
            "ejercicio_id": ejercicio_id,
            "calificacion_obtenida": 100 if correcta else 0,
            "numero_aciertos": 1 if correcta else 0,
            "numero_errores": 0 if correcta else 1,
            "tiempo_resolucion_segundos": 0,
        }
        for ejercicio_id, correcta in resultados.items()
    ]


def _entero(valor: Any):
    """Entero estricto: descarta booleanos y textos no numéricos. Pura."""
    if isinstance(valor, bool):
        return None
    return to_int(valor)


# --- Orquestación -----------------------------------------------------------


def preguntas() -> List[Dict[str, Any]]:
    """Preguntas del diagnóstico listas para el cliente (sin `es_correcta`)."""
    return formatear_preguntas(repository.listar_preguntas())


def _areas_validas() -> Collection[str]:
    """Claves de área del catálogo. Si no se puede leer, ninguna: no bloquea el diagnóstico."""
    try:
        from features.motor import catalogo

        return set(catalogo.cargar_catalogo()["areas"].keys())
    except Exception:
        logger.exception("Cold start: no se pudieron leer las áreas del catálogo.")
        return set()


def _guardar_intereses(usuario_id: str, areas: List[Tuple[str, float]]) -> None:
    from features.motor.perfil import service as perfil

    try:
        perfil.guardar_intereses_declarados(usuario_id, areas)
    except NotImplementedError:
        logger.debug("Cold start: guardar_intereses_declarados aún no implementado.")


def evaluar(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Evalúa el diagnóstico inicial y persiste nivel, metas, intentos e intereses.

    Devuelve `{"nivel_asignado", "aciertos", "total"}`.
    """
    require_fields(datos, ("usuario_id",), "usuario_id es requerido.")

    usuario_id = datos["usuario_id"]
    respuestas = datos.get("respuestas_tecnicas") or []
    if not isinstance(respuestas, list):
        raise ValidationError(
            "El campo `respuestas_tecnicas` debe ser una lista.", campos=["respuestas_tecnicas"]
        )
    familiaridad = datos.get("familiaridad")
    objetivo = datos.get("objetivo") or None

    if omite_prueba_tecnica(familiaridad, respuestas):
        resultados: Dict[int, bool] = {}
        total = 0
        nivel = NIVEL_PRINCIPIANTE
    else:
        diagnostico = repository.listar_ids_diagnostico()
        opciones = repository.buscar_opciones(ids_de_opciones(respuestas))
        opciones_por_id = {
            int(o["id"]): o for o in opciones if _entero(o.get("id")) is not None
        }
        resultados = corregir_diagnostico(respuestas, opciones_por_id, diagnostico)
        total = len(diagnostico)
        nivel = nivel_por_aciertos(sum(1 for correcta in resultados.values() if correcta))

    repository.actualizar_nivel(usuario_id, nivel_asignado=nivel, objetivo_aprendizaje=objetivo)

    disponibilidad = datos.get("disponibilidad")
    if disponibilidad:
        repository.guardar_metas(usuario_id, **metas_estudio(disponibilidad))

    repository.registrar_intentos(construir_intentos(usuario_id, resultados))

    _guardar_intereses(
        usuario_id, areas_de_intereses(datos.get("intereses"), objetivo, _areas_validas())
    )

    ganchos.al_completar_diagnostico(usuario_id, resultados, nivel)

    return {
        "nivel_asignado": nivel,
        "aciertos": sum(1 for correcta in resultados.values() if correcta),
        "total": total,
    }
