"""Diversificación de la lista recomendada (MMR). La implementa el paquete 08."""

from typing import Callable, List


def mmr(items: List[dict], similitud: Callable[[int, int], float], n: int, lambda_: float) -> List[dict]:
    """Máxima relevancia marginal (Carbonell y Goldstein 1998; guía, cap. 9). **Pura.**

    Elige uno a uno el ítem que maximiza
    `(1 − λ) × puntuacion_norm − λ × max(similitud(c, e) for e in elegidos)`,
    con `puntuacion_norm = puntuacion / max puntuacion`. Empates: orden original.
    Devuelve como mucho `n` ítems (los mismos dicts, sin copiarlos ni cambiarlos).
    """
    if n <= 0 or not items:
        return []
    maximo = max(float(item["puntuacion"]) for item in items)
    norm = [float(item["puntuacion"]) / maximo if maximo > 0 else 0.0 for item in items]

    restantes = list(range(len(items)))
    elegidos: List[int] = []
    while restantes and len(elegidos) < n:
        mejor, mejor_valor = restantes[0], None
        for i in restantes:
            redundancia = max(
                (similitud(items[i]["curso_id"], items[e]["curso_id"]) for e in elegidos),
                default=0.0,
            )
            valor = (1 - lambda_) * norm[i] - lambda_ * redundancia
            if mejor_valor is None or valor > mejor_valor:
                mejor, mejor_valor = i, valor
        elegidos.append(mejor)
        restantes.remove(mejor)
    return [items[i] for i in elegidos]
