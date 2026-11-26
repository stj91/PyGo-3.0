"""Filtrado colaborativo ítem-ítem: "alumnos que hicieron X luego hicieron Y".

Similitud coseno entre las columnas de curso de la matriz alumno × curso
(guía, cap. 8; Sarwar et al. 2001). El cálculo es puro y se hace en el lote
`calcular_similitudes`; la API sólo lee la tabla `similitud_cursos`.
Sólo librería estándar.
"""

import math
from typing import Any, Callable, Dict, List, Optional, Sequence

from django.core.cache import cache

from core import supabase

from .. import config
from ..tipos import Contexto, Curso, Perfil, Puntuacion, Similitud

_CACHE_CLAVE = "pygo:motor:similitudes"

#: Tamaño de página al leer tablas enteras (el máximo por defecto de PostgREST en Supabase).
TAMANO_PAGINA = 1000

_CALIFICACION_ALTA = 90


# --- Interacciones (puro) ---------------------------------------------------


"""
Aplicamos filtrado colaborativo ítem-ítem. Un proceso por lotes calcula
la similitud coseno entre pares de cursos basándose en las inscripciones
históricas de todos los usuarios y guarda la matriz en la tabla
similitud_cursos. En tiempo real, la API solo consulta esa
tabla para recomendar cursos que tomaron estudiantes con
trayectorias similares.

We apply item-item collaborative filtering. A batch process calculates
the cosine similarity between pairs of courses based on the historical 
enrollments of all users and stores the matrix in similitud_cursos table. 
In real time, the API only queries that table to recommend courses 
taken by users with similar learning paths.
"""

def _numero(valor: Any) -> Optional[float]:
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def valor_interaccion(estado: Any, calificacion_final: Any) -> Optional[float]:
    """Valor implícito de una inscripción, o `None` si el estado no cuenta. **Pura.**"""
    base = config.VALOR_INTERACCION.get(estado)
    if base is None:
        return None
    calificacion = _numero(calificacion_final)
    if estado == "completado" and calificacion is not None and calificacion >= _CALIFICACION_ALTA:
        base += config.BONO_CALIFICACION_ALTA
    return min(float(base), 1.0)


def interacciones(inscripciones: Sequence[dict]) -> List[dict]:
    """Filas `{usuario_id, curso_id, estado, calificacion_final}` -> `{usuario_id, curso_id, valor}`. **Pura.**

    Estados desconocidos se ignoran; si un par (usuario, curso) se repite, gana
    el valor máximo.
    """
    mejor: Dict[tuple, float] = {}
    for fila in inscripciones:
        valor = valor_interaccion(fila.get("estado"), fila.get("calificacion_final"))
        if valor is None or fila.get("usuario_id") in (None, "") or fila.get("curso_id") in (None, ""):
            continue
        clave = (str(fila["usuario_id"]), int(fila["curso_id"]))
        if valor > mejor.get(clave, -1.0):
            mejor[clave] = valor
    return [
        {"usuario_id": usuario, "curso_id": curso, "valor": valor}
        for (usuario, curso), valor in sorted(mejor.items())
    ]


# --- Similitudes (puro) -----------------------------------------------------


def calcular_similitudes(interacciones: Sequence[dict]) -> Dict[int, Dict[int, Similitud]]:
    """Coseno entre columnas de curso de la matriz alumno × curso. **Pura.**

    `soporte` = alumnos con interacción en ambos cursos. Simétrica, sin
    autopares; los pares con soporte 0 se omiten.
    """
    por_usuario: Dict[str, Dict[int, float]] = {}
    for fila in interacciones:
        usuario, curso = str(fila["usuario_id"]), int(fila["curso_id"])
        cursos = por_usuario.setdefault(usuario, {})
        cursos[curso] = max(float(fila["valor"]), cursos.get(curso, float("-inf")))

    normas2: Dict[int, float] = {}
    productos: Dict[tuple, float] = {}
    soportes: Dict[tuple, int] = {}
    for cursos in por_usuario.values():
        ordenados = sorted(cursos.items())
        for i, (a, va) in enumerate(ordenados):
            normas2[a] = normas2.get(a, 0.0) + va * va
            for b, vb in ordenados[i + 1:]:
                productos[(a, b)] = productos.get((a, b), 0.0) + va * vb
                soportes[(a, b)] = soportes.get((a, b), 0) + 1

    resultado: Dict[int, Dict[int, Similitud]] = {}
    for (a, b), producto in productos.items():
        divisor = math.sqrt(normas2[a]) * math.sqrt(normas2[b])
        similitud = producto / divisor if divisor else 0.0
        par: Similitud = {"similitud": similitud, "soporte": soportes[(a, b)]}
        resultado.setdefault(a, {})[b] = dict(par)
        resultado.setdefault(b, {})[a] = dict(par)
    return resultado


# --- Puntuación (puro) ------------------------------------------------------


def puntuar(perfil: Perfil, candidatos: Sequence[Curso], contexto: Contexto) -> List[Puntuacion]:
    """Puntuación colaborativa usando `contexto["similitudes"]`. **Pura.**

    Para cada candidato c, sobre los cursos v del historial con
    `soporte >= SOPORTE_MINIMO`: Σ sim × valor / Σ |sim|. Se omiten los candidatos
    sin ningún par válido. El texto cita el curso *completado* con mayor
    sim × valor; `None` si ninguno aportó.
    """
    historial: Dict[int, float] = {}
    completados = set()
    for curso_id, inscripcion in (perfil.get("inscripciones") or {}).items():
        valor = valor_interaccion(inscripcion.get("estado"), inscripcion.get("calificacion_final"))
        if valor is None:
            continue
        historial[int(curso_id)] = valor
        if inscripcion.get("estado") == "completado":
            completados.add(int(curso_id))
    if not historial:
        return []

    similitudes = contexto.get("similitudes") or {}
    cursos = contexto["catalogo"]["cursos"]
    soporte_minimo = config.SOPORTE_MINIMO

    resultado: List[Puntuacion] = []
    for curso in candidatos:
        vecinos = similitudes.get(curso["id"], {})
        numerador = denominador = 0.0
        mejor: Optional[tuple] = None
        for v, valor in sorted(historial.items()):
            par = vecinos.get(v)
            if v == curso["id"] or par is None or par["soporte"] < soporte_minimo:
                continue
            sim = float(par["similitud"])
            numerador += sim * valor
            denominador += abs(sim)
            aporte = sim * valor
            if v in completados and v in cursos and aporte > 0 and (mejor is None or aporte > mejor[0]):
                mejor = (aporte, v)
        if denominador == 0:
            continue
        puntuacion = numerador / denominador
        texto = (
            f"Alumnos que completaron {cursos[mejor[1]]['titulo']} tomaron este curso después."
            if mejor is not None else None
        )
        resultado.append({
            "curso_id": curso["id"],
            "puntuacion": puntuacion,
            "razones": [{"origen": "colaborativo", "texto": texto, "aporte": puntuacion}],
        })
    return resultado


# --- Lectura (efectos) ------------------------------------------------------


def leer_paginado(
    leer_pagina: Callable[[int, int], List[Dict[str, Any]]], tamano: int = TAMANO_PAGINA
) -> List[Dict[str, Any]]:
    """Concatena páginas `leer_pagina(desde, tamano)` hasta una incompleta."""
    filas: List[Dict[str, Any]] = []
    while True:
        pagina = leer_pagina(len(filas), tamano)
        filas.extend(pagina)
        if len(pagina) < tamano:
            return filas


def _leer_pagina_similitudes(desde: int, tamano: int) -> List[Dict[str, Any]]:
    # `offset` es un parámetro de PostgREST; core.supabase.select no lo expone, pero
    # sus filtros son pares (clave, valor) que se envían tal cual en la query string.
    return supabase.select(
        "similitud_cursos",
        columns="curso_a,curso_b,similitud,soporte",
        filters=(("offset", str(desde)),),
        order="curso_a.asc,curso_b.asc",
        limit=tamano,
        operation="motor:similitudes:leer",
    )


def similitudes_desde_filas(filas: Sequence[Dict[str, Any]]) -> Dict[int, Dict[int, Similitud]]:
    """Filas de `similitud_cursos` -> curso_a -> curso_b -> Similitud. **Pura.**

    Las filas con soporte 0 son pares invalidados por el lote y se ignoran.
    """
    resultado: Dict[int, Dict[int, Similitud]] = {}
    for fila in filas:
        soporte = int(fila.get("soporte") or 0)
        if soporte <= 0:
            continue
        resultado.setdefault(int(fila["curso_a"]), {})[int(fila["curso_b"])] = {
            "similitud": float(fila["similitud"]),
            "soporte": soporte,
        }
    return resultado


def cargar_similitudes() -> Dict[int, Dict[int, Similitud]]:
    """Similitudes de `similitud_cursos`: curso_a -> curso_b -> Similitud. La usa 08.

    Se guardan ambas direcciones en la tabla. Memoizado en el proceso
    `CATALOGO_CACHE_SEGUNDOS` (`0` lo desactiva).
    """
    segundos = config.CATALOGO_CACHE_SEGUNDOS
    if segundos > 0:
        guardado = cache.get(_CACHE_CLAVE)
        if guardado is not None:
            return guardado

    similitudes = similitudes_desde_filas(leer_paginado(_leer_pagina_similitudes))

    if segundos > 0:
        cache.set(_CACHE_CLAVE, similitudes, segundos)
    return similitudes


def invalidar_similitudes() -> None:
    """Olvida las similitudes memoizadas en este proceso."""
    cache.delete(_CACHE_CLAVE)
