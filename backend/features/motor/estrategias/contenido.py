"""Estrategia basada en contenido: "cursos parecidos a lo que te interesa".

Compara por coseno el vector de conceptos del alumno (intereses más lo ya
cursado) con el de cada curso. Funciona en cuanto hay intereses, así que cubre
el arranque en frío. Pura y sólo con la librería estándar.
"""

import math
from typing import Dict, List, Optional, Sequence

from ..tipos import Catalogo, Contexto, Curso, Perfil, Puntuacion

#: Peso de los conceptos de un curso completado en el vector del alumno.
_FACTOR_COMPLETADO = 0.5

#: Por debajo de esta puntuación la coincidencia es demasiado débil para explicarla.
_UMBRAL_TEXTO = 0.2


"""
Construimos un vector con los conceptos de interés del alumno y los
temas que ya aprobó, y calculamos la similitud coseno contra el
vector de conceptos de cada curso candidato.

We built a vector with the user's interests and topics they've already 
passed, and calculate the cosine similarity with the concept vector
of each candidate course.
"""

def coseno(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Similitud coseno entre dos vectores dispersos. 0.0 si alguno es vacío o nulo. **Pura.**"""
    norma_a = math.sqrt(sum(v * v for v in a.values()))
    norma_b = math.sqrt(sum(v * v for v in b.values()))
    if norma_a == 0 or norma_b == 0:
        return 0.0
    producto = sum(peso * b[clave] for clave, peso in a.items() if clave in b)
    return producto / (norma_a * norma_b)


def vector_alumno(perfil: Perfil, catalogo: Catalogo) -> Dict[str, float]:
    """Intereses + 0.5 × conceptos de cada curso completado, sumados y topados a 1.0. **Pura.**"""
    suma: Dict[str, float] = {
        clave: float(peso) for clave, peso in (perfil.get("intereses") or {}).items()
    }
    cursos = catalogo.get("cursos", {})
    for curso_id in perfil.get("cursos_completados") or []:
        curso = cursos.get(curso_id)
        if curso is None:
            continue
        for clave, peso in curso["conceptos"].items():
            suma[clave] = suma.get(clave, 0.0) + _FACTOR_COMPLETADO * float(peso)
    return {clave: min(valor, 1.0) for clave, valor in suma.items() if valor > 0}


def _concepto_principal(alumno: Dict[str, float], curso: Dict[str, float]) -> Optional[str]:
    """Concepto con mayor producto peso_alumno × peso_curso (empate: clave menor)."""
    productos = [(alumno[c] * p, c) for c, p in curso.items() if c in alumno and alumno[c] * p > 0]
    if not productos:
        return None
    return min(productos, key=lambda par: (-par[0], par[1]))[1]


def puntuar(perfil: Perfil, candidatos: Sequence[Curso], contexto: Contexto) -> List[Puntuacion]:
    """Afinidad entre los intereses del alumno y los conceptos de cada curso. **Pura.**

    `puntuacion` = coseno(vector_alumno, curso.conceptos); se omiten los
    candidatos con 0. Una razón `contenido` que nombra el concepto que más aporta;
    sin texto si la puntuación es menor que 0.2.
    """
    catalogo = contexto["catalogo"]
    alumno = vector_alumno(perfil, catalogo)
    if not alumno:
        return []

    resultado: List[Puntuacion] = []
    for curso in candidatos:
        puntuacion = coseno(alumno, curso["conceptos"])
        if puntuacion <= 0:
            continue
        texto = None
        if puntuacion >= _UMBRAL_TEXTO:
            clave = _concepto_principal(alumno, curso["conceptos"])
            concepto = catalogo["conceptos"].get(clave) if clave else None
            if concepto is not None:
                texto = f"Coincide con tu interés en {concepto['nombre']}."
        resultado.append({
            "curso_id": curso["id"],
            "puntuacion": puntuacion,
            "razones": [{"origen": "contenido", "texto": texto, "aporte": puntuacion}],
        })
    return resultado


def similitud_entre_cursos(a: Curso, b: Curso) -> float:
    """Similitud de contenido entre dos cursos (coseno de sus conceptos). **Pura.** La usa 08."""
    return coseno(a.get("conceptos") or {}, b.get("conceptos") or {})
