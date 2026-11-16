"""Explicaciones en español de cada recomendación. La implementa el paquete 08."""

from typing import Dict, List, Optional

from .tipos import Perfil, Razon

TEXTO_SIGUIENTE = "Es la continuación natural de lo que ya completaste."
TEXTO_NIVEL = "Encaja con tu nivel {nivel}."
NIVEL_POR_DEFECTO = "Principiante"


def _frase(texto: Optional[str]) -> Optional[str]:
    """El texto como frase terminada en punto; `None` si está vacío o no es texto."""
    if not isinstance(texto, str) or not texto.strip():
        return None
    texto = texto.strip()
    return texto if texto.endswith((".", "!", "?")) else f"{texto}."


def elegir(razones_por_estrategia: Dict[str, List[Razon]], pesos: Dict[str, float],
           es_siguiente: bool, perfil: Perfil) -> str:
    """La explicación que se muestra para un curso. **Pura.** Nunca devuelve una cadena vacía.

    Gana la razón con texto y mayor `peso_estrategia × aporte_norm`, solo entre
    contribuciones positivas (empates: la primera). `aporte_norm` lo añade
    `hibrido`; si falta se usa `aporte`. Sin ninguna, una frase de respaldo.
    """
    mejor, mejor_valor = None, 0.0
    for estrategia, razones in razones_por_estrategia.items():
        peso = float(pesos.get(estrategia, 0.0))
        for razon in razones or []:
            texto = _frase(razon.get("texto"))
            if texto is None:
                continue
            valor = peso * float(razon.get("aporte_norm", razon.get("aporte", 0.0)))
            if valor > mejor_valor:
                mejor, mejor_valor = texto, valor
    if mejor is not None:
        return mejor
    if es_siguiente:
        return TEXTO_SIGUIENTE
    return TEXTO_NIVEL.format(nivel=perfil.get("nivel") or NIVEL_POR_DEFECTO)
