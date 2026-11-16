"""Candidatos y filtros duros (docs/motor/05-reglas-y-candidatos.md §1).

- F03: solo son candidatos los cursos publicados en los que el alumno no está
  inscrito como `activo` o `completado`. Siempre se aplica.
- F01: un prerrequisito se cumple si el curso requerido está completado con la
  calificación mínima.
- F02: si está activa, un prerrequisito también se cumple cuando el nivel del
  alumno alcanza el del curso requerido y su dominio de los conceptos de ese
  curso llega a `F02_DOMINIO_MINIMO`.

Todo es puro: sin I/O, sin reloj y sin modificar los argumentos.
"""

from typing import Dict, List, Optional, Sequence

from . import config
from .perfil.dominio import dominio_inicial
from .tipos import Catalogo, Curso, Perfil, Prerrequisito, Regla

_RANGO_NIVEL = {"Principiante": 0, "Intermedio": 1, "Avanzado": 2}
_ESTADOS_EXCLUIDOS = frozenset({"activo", "completado"})


def _dominio_ponderado(perfil: Perfil, curso: Curso, catalogo: Optional[Catalogo] = None) -> float:
    """Media de `perfil.dominio` ponderada por `curso.conceptos`.

    Un concepto sin evidencias cuenta con el valor de partida del nivel asignado
    (`dominio_inicial`): así el nivel del diagnóstico pesa mientras no haya
    práctica. Sin `catalogo`, o un curso sin conceptos, cuenta como
    `DOMINIO_SIN_EVIDENCIA`.
    """
    sin_evidencia = float(config.DOMINIO_SIN_EVIDENCIA)
    nivel_asignado = perfil.get("nivel_asignado")
    dominio: Dict[str, float] = perfil.get("dominio") or {}
    total = 0.0
    suma = 0.0
    for clave, peso in (curso.get("conceptos") or {}).items():
        peso = float(peso)
        if peso <= 0:
            continue
        valor = dominio.get(clave)
        if valor is None:
            valor = dominio_inicial(clave, nivel_asignado, catalogo) if catalogo else sin_evidencia
        suma += peso * float(valor)
        total += peso
    return suma / total if total > 0 else sin_evidencia


def _regla_activa(reglas: Sequence[Regla], codigo: str) -> bool:
    return any(
        r.get("ambito") == "filtro" and r.get("codigo") == codigo and r.get("activa", True) is True
        for r in reglas
    )


def candidatos(perfil: Perfil, catalogo: Catalogo) -> List[Curso]:
    """Cursos publicados en los que el alumno no está inscrito (F03). **Pura.** Paquete 05.

    Los cursos `abandonado` vuelven a ser candidatos. Ordenados por `id`.
    """
    inscripciones = perfil.get("inscripciones") or {}
    excluidos = {
        int(curso_id)
        for curso_id, inscripcion in inscripciones.items()
        if (inscripcion or {}).get("estado") in _ESTADOS_EXCLUIDOS
    }
    return [
        curso
        for curso_id, curso in sorted(catalogo["cursos"].items())
        if curso.get("publicado", True) and curso_id not in excluidos
    ]


def prerrequisito_cumplido(
    perfil: Perfil, prerrequisito: Prerrequisito, catalogo: Catalogo, f02_activa: bool
) -> bool:
    """¿Cumple el alumno este prerrequisito? F01 y, si `f02_activa`, F02. **Pura.**"""
    requerido = int(prerrequisito["curso_id"])
    minima = float(prerrequisito.get("calificacion_minima", 80))

    completados = {int(c) for c in perfil.get("cursos_completados") or []}
    calificacion = (perfil.get("calificacion_por_curso") or {}).get(requerido)
    # Un curso completado sin nota (p. ej. marcado por la migración 0005 al estar
    # al 100 %) cuenta como aprobado: no hay forma de saber la nota real.
    if requerido in completados and (calificacion is None or float(calificacion) >= minima):
        return True

    if not f02_activa:
        return False
    curso_requerido = catalogo["cursos"].get(requerido)
    if curso_requerido is None:
        return False
    rango_alumno = _RANGO_NIVEL.get(perfil.get("nivel"))
    rango_curso = _RANGO_NIVEL.get(curso_requerido.get("nivel"))
    if rango_alumno is None or rango_curso is None or rango_alumno < rango_curso:
        return False
    return _dominio_ponderado(perfil, curso_requerido, catalogo) >= float(config.F02_DOMINIO_MINIMO)


def filtrar(
    perfil: Perfil, cursos: Sequence[Curso], catalogo: Catalogo, reglas: Sequence[Regla]
) -> List[Curso]:
    """Aplica los filtros de prerrequisitos F01/F02. **Pura.** Paquete 05.

    Sin F01 activa no se comprueban prerrequisitos; sin F02 activa solo cuenta
    haber completado el curso requerido.
    """
    if not _regla_activa(reglas, "F01"):
        return list(cursos)
    f02 = _regla_activa(reglas, "F02")
    return [
        curso
        for curso in cursos
        if all(
            prerrequisito_cumplido(perfil, p, catalogo, f02)
            for p in curso.get("prerrequisitos") or []
        )
    ]


def siguiente_en_ruta(perfil: Perfil, catalogo: Catalogo) -> List[int]:
    """Ids de los cursos que son el siguiente paso natural del alumno. **Pura.** Paquete 05.

    Candidatos con al menos un prerrequisito y todos cumplidos por F01
    (completados con la nota mínima; F02 no cuenta aquí). Ordenados por `id`.
    """
    return [
        curso["id"]
        for curso in candidatos(perfil, catalogo)
        if curso.get("prerrequisitos")
        and all(
            prerrequisito_cumplido(perfil, p, catalogo, False) for p in curso["prerrequisitos"]
        )
    ]


def prerrequisitos_pendientes(perfil: Perfil, curso: Curso, catalogo: Catalogo) -> List[int]:
    """Ids de los prerrequisitos del curso que el alumno aún no cumple. **Pura.**

    Cumplir es haberlo completado o tener nivel y dominio suficientes (como F02).
    Alimenta la regla suave R07, que baja la puntuación en vez de excluir el curso.
    """
    return [
        int(p["curso_id"])
        for p in curso.get("prerrequisitos") or []
        if not prerrequisito_cumplido(perfil, p, catalogo, True)
    ]
