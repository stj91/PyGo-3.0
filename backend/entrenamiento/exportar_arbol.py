"""Exporta un `DecisionTreeClassifier` entrenado al JSON que recorre la API.

Forma de cada nodo:
- interno: `{"hoja": False, "campo": str, "umbral": float, "izq": nodo, "der": nodo}`,
  con `izq` = `x[campo] <= umbral` (la misma regla que scikit-learn);
- hoja: `{"hoja": True, "prob": float, "n": int}`.

`prob` es la proporción de la clase 1 en el `value` de la hoja y `n` el número
de muestras de entrenamiento que llegaron a ella. Con
`class_weight="balanced"` el `value` está ponderado por clase, así que `prob`
es una **puntuación para ordenar, no una probabilidad calibrada** (coincide
con `predict_proba` del modelo, no con la tasa real de aprobados de la hoja).
"""

from typing import List

_HOJA = -1


def arbol_a_json(modelo, nombres: List[str]) -> dict:
    """Árbol de `modelo` como diccionario JSON; `nombres[i]` es la característica `i`."""
    arbol = modelo.tree_
    clases = [int(c) for c in modelo.classes_]
    indice_positivo = clases.index(1) if 1 in clases else None

    def nodo(i: int) -> dict:
        izquierdo, derecho = int(arbol.children_left[i]), int(arbol.children_right[i])
        if izquierdo == _HOJA:
            valores = [float(v) for v in arbol.value[i][0]]
            total = sum(valores)
            prob = valores[indice_positivo] / total if indice_positivo is not None and total > 0 else 0.0
            return {"hoja": True, "prob": prob, "n": int(arbol.n_node_samples[i])}
        return {
            "hoja": False,
            "campo": nombres[int(arbol.feature[i])],
            "umbral": round(float(arbol.threshold[i]), 6),
            "izq": nodo(izquierdo),
            "der": nodo(derecho),
        }

    return nodo(0)
