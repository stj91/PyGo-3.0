"""Asignación al grupo del experimento A/B y lista del grupo de control (paquete 08)."""

import hashlib
from typing import Literal

from . import config
from .tipos import Contexto, Perfil

TEXTO_CONTROL = "Es el siguiente curso del temario."
ORIGEN_CONTROL = "control:temario"


def grupo(usuario_id: str, experimento: str = config.EXPERIMENTO) -> Literal["motor", "control"]:
    """Grupo determinista del usuario en el experimento. **Pura.** Paquete 08.

    Primer byte de `sha256("{experimento}:{usuario_id}")`: par -> `control`,
    impar -> `motor` (guía, cap. 11).
    """
    primer_byte = hashlib.sha256(f"{experimento}:{usuario_id}".encode("utf-8")).digest()[0]
    return "control" if primer_byte % 2 == 0 else "motor"


def grupo_asignado(usuario_id: str) -> Literal["motor", "control"]:
    """Grupo con el que se atiende al usuario: `motor` si el experimento está apagado."""
    if not config.EXPERIMENTO_ACTIVO:
        return "motor"
    return grupo(usuario_id, config.EXPERIMENTO)


def recomendar_control(perfil: Perfil, contexto: Contexto, limite: int) -> dict:
    """Mismos candidatos y filtros que el motor, en orden del temario `(dificultad, id)`. **Pura.**

    Misma forma de salida que `hibrido.recomendar`.
    """
    # Import diferido: `hibrido` importa este módulo.
    from . import hibrido

    catalogo = contexto["catalogo"]
    cursos = sorted(
        hibrido.candidatos_permitidos(perfil, contexto),
        key=lambda c: (c.get("dificultad", 0), c["id"]),
    )[: max(int(limite), 0)]
    items = [
        {
            "curso_id": curso["id"],
            "codigo_curso": curso["codigo_curso"],
            "titulo": curso["titulo"],
            "puntuacion": 0.0,
            "posicion": posicion,
            "explicacion": TEXTO_CONTROL,
            "origen": [ORIGEN_CONTROL],
        }
        for posicion, curso in enumerate(cursos, start=1)
    ]
    return {"modo": "control", "items": items, "continuar": hibrido.continuar(perfil, catalogo)}
