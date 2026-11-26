"""Dominio por concepto (guía, cap. 5). Todo puro: sin E/S, sin reloj, sin mutar argumentos.

Las mismas funciones sirven en vivo (`service`) y al reproducir el historial
(`reproducir_dominio`, que usan 07 y 10), así el dominio reproducido coincide
con el que se calculó en su momento.
"""

from datetime import datetime
from typing import Dict, Optional, Sequence, Tuple

from .. import config
from ..tipos import Catalogo, Evento
from ._comun import a_entero, a_fecha, a_float, nivel_valido, rango_nivel, temas_por_id


"""
Con ALFA_DOMINIO = 0.3, las evaluaciones recientes tienen mayor peso, pero conservando
la memoria histórica del desempeño del usuario.

With ALFA_DOMINIO = 0.3, the recent evaluations have more weight, while preserving the
historical record of the user's performance.
"""

def nuevo_dominio(
    anterior: Optional[float], puntaje: float, inicial: float, peso: float = 1.0
) -> float:
    """Media móvil exponencial: `base + ALFA_DOMINIO × peso × (puntaje − base)`.

    `base` es `inicial` si no hay valor anterior. Resultado en [0, 1] con 3 decimales.
    """
    base = inicial if anterior is None else anterior
    valor = base + config.ALFA_DOMINIO * peso * (puntaje - base)
    return round(min(1.0, max(0.0, valor)), 3)


def dominio_inicial(concepto: str, nivel_asignado: str, catalogo: Catalogo) -> float:
    """Valor de partida de un concepto sin evidencias.

    `DOMINIO_INICIAL_POR_NIVEL[nivel]` si el concepto aparece en algún curso de
    nivel igual o inferior al del alumno; si no, `DOMINIO_SIN_EVIDENCIA`.
    """
    nivel = nivel_valido(nivel_asignado)
    rango = rango_nivel(nivel)
    cubierto = any(
        concepto in curso.get("conceptos", {}) and rango_nivel(curso.get("nivel")) <= rango
        for curso in catalogo.get("cursos", {}).values()
    )
    if cubierto:
        return config.DOMINIO_INICIAL_POR_NIVEL[nivel]
    return config.DOMINIO_SIN_EVIDENCIA


def aplicar_tema(
    dominio: Dict[str, float],
    evidencias: Dict[str, int],
    tema_id: int,
    puntaje: float,
    nivel_asignado: str,
    catalogo: Catalogo,
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """Evidencia de un módulo calificado: cada concepto suyo se actualiza con su peso."""
    tema = temas_por_id(catalogo).get(a_entero(tema_id))
    nuevo, cuenta = dict(dominio), dict(evidencias)
    if tema is None:
        return nuevo, cuenta
    for clave, peso in tema.get("conceptos", {}).items():
        nuevo[clave] = nuevo_dominio(
            nuevo.get(clave), puntaje, dominio_inicial(clave, nivel_asignado, catalogo), float(peso)
        )
        cuenta[clave] = cuenta.get(clave, 0) + 1
    return nuevo, cuenta


def conceptos_del_diagnostico(resultados: Dict[int, bool], catalogo: Catalogo) -> Dict[str, Tuple[int, int]]:
    """concepto -> (aciertos, preguntas) de los ejercicios de diagnóstico respondidos."""
    temas = temas_por_id(catalogo)
    mapa = catalogo.get("ejercicios_diagnostico", {})
    cuentas: Dict[str, Tuple[int, int]] = {}
    for ejercicio_id, correcto in (resultados or {}).items():
        tema = temas.get(mapa.get(a_entero(ejercicio_id)))
        if tema is None:
            continue
        for clave in tema.get("conceptos", {}):
            aciertos, preguntas = cuentas.get(clave, (0, 0))
            cuentas[clave] = (aciertos + (1 if correcto else 0), preguntas + 1)
    return cuentas


def aplicar_diagnostico(
    dominio: Dict[str, float],
    evidencias: Dict[str, int],
    resultados: Dict[int, bool],
    nivel_asignado: str,
    catalogo: Catalogo,
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """Siembra el dominio con el diagnóstico inicial `{ejercicio_id: acertó?}`.

    Por concepto, `p` = aciertos ÷ preguntas de sus módulos. Sin valor previo:
    `FALLO + p × (ACIERTO − FALLO)`; con valor previo: `nuevo_dominio`. Una
    evidencia por concepto.
    """
    nuevo, cuenta = dict(dominio), dict(evidencias)
    fallo, acierto = config.DOMINIO_DIAGNOSTICO_FALLO, config.DOMINIO_DIAGNOSTICO_ACIERTO
    for clave, (aciertos, preguntas) in conceptos_del_diagnostico(resultados, catalogo).items():
        p = aciertos / preguntas
        if nuevo.get(clave) is None:
            nuevo[clave] = round(min(1.0, max(0.0, fallo + p * (acierto - fallo))), 3)
        else:
            nuevo[clave] = nuevo_dominio(
                nuevo[clave], p, dominio_inicial(clave, nivel_asignado, catalogo)
            )
        cuenta[clave] = cuenta.get(clave, 0) + 1
    return nuevo, cuenta


def reproducir_dominio(
    eventos: Sequence[Evento],
    catalogo: Catalogo,
    nivel_asignado: str,
    hasta: Optional[datetime],
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """Reconstruye `(dominio, evidencias)` reproduciendo eventos. **Pura.**

    Reproduce `diagnostico` (`datos.resultados`, claves = id de ejercicio en
    texto) y `quiz_intento` (`objeto_id` = tema, `valor` = puntaje 0..1) en
    orden de `fecha` (estable a igualdad), ignorando los que tengan
    `fecha >= hasta` si `hasta` no es `None`. `fecha` puede ser `datetime` o
    ISO-8601; los eventos sin fecha interpretable se ignoran.
    """
    limite = a_fecha(hasta)
    fechados = []
    for posicion, evento in enumerate(eventos):
        fecha = a_fecha(evento.get("fecha"))
        if fecha is None or (limite is not None and fecha >= limite):
            continue
        fechados.append((fecha, posicion, evento))
    fechados.sort(key=lambda t: (t[0], t[1]))

    dominio: Dict[str, float] = {}
    evidencias: Dict[str, int] = {}
    for _, _, evento in fechados:
        tipo = evento.get("tipo")
        if tipo == "diagnostico":
            resultados = _resultados(evento.get("datos"))
            if resultados:
                dominio, evidencias = aplicar_diagnostico(
                    dominio, evidencias, resultados, nivel_asignado, catalogo
                )
        elif tipo == "quiz_intento":
            tema_id, puntaje = a_entero(evento.get("objeto_id")), a_float(evento.get("valor"))
            if tema_id is not None and puntaje is not None:
                dominio, evidencias = aplicar_tema(
                    dominio, evidencias, tema_id, puntaje, nivel_asignado, catalogo
                )
    return dominio, evidencias


def _resultados(datos) -> Dict[int, bool]:
    crudos = datos.get("resultados") if isinstance(datos, dict) else None
    if not isinstance(crudos, dict):
        return {}
    resultado = {}
    for clave, valor in crudos.items():
        ejercicio_id = a_entero(clave)
        if ejercicio_id is not None:
            resultado[ejercicio_id] = bool(valor)
    return resultado
