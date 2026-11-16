"""Estrategia por modelo: árbol de decisión "¿aprobará este curso si lo empieza ahora?".

El árbol se entrena por lotes con scikit-learn (`backend/entrenamiento/`) y se
guarda como JSON en `modelos.parametros`. Aquí se recorre con una función pura:
este módulo solo usa la librería estándar y nunca carga pickle/joblib.

`caracteristicas_para` alimenta tanto el entrenamiento (dataset) como el
servicio; por eso ambos ven exactamente las mismas variables.
"""

import logging
from typing import Dict, List, Optional, Sequence, Tuple

from django.core.cache import cache

from core import supabase
from core.errors import DataAccessError
from core.supabase import eq

from .. import config
from ..tipos import Catalogo, Contexto, Curso, ModeloActivo, Perfil, Puntuacion

logger = logging.getLogger(__name__)

CARACTERISTICAS = [
    "dominio_medio", "dominio_conceptos_curso", "cursos_previos", "calificacion_prerrequisitos",
    "tasa_aprobacion_modulos", "intentos_promedio", "dificultad_curso", "nivel_ordinal", "coincide_interes",
]

_NIVEL_ORDINAL = {"Principiante": 0, "Intermedio": 1, "Avanzado": 2}

_UMBRAL_INTERES = 0.5

_PLANTILLAS_EXPLICACION = {
    "dominio_conceptos_curso": "Ya tienes buena base en los temas de este curso.",
    "calificacion_prerrequisitos": "Te fue bien en los cursos previos.",
    "tasa_aprobacion_modulos": "Sueles aprobar los módulos a la primera.",
    "coincide_interes": "Coincide con lo que te interesa.",
}

_CACHE_PREFIJO = "pygo:motor:modelo:"


# --- Características (puro) -------------------------------------------------


def _media(valores: Sequence[float], defecto: float) -> float:
    return sum(valores) / len(valores) if valores else defecto


def caracteristicas_para(perfil: Perfil, curso: Curso, catalogo: Catalogo) -> Dict[str, float]:
    """Vector de características (alumno, curso), en el orden de `CARACTERISTICAS`. **Pura.**

    Sin evidencia de dominio se usa `DOMINIO_SIN_EVIDENCIA_MODELO`; las tasas
    ausentes del perfil valen 0.0. Valores redondeados a 6 decimales, como los
    umbrales del árbol exportado.
    """
    sin_evidencia = config.DOMINIO_SIN_EVIDENCIA_MODELO
    dominio = perfil.get("dominio") or {}
    evidencias = perfil.get("evidencias") or {}
    intereses = perfil.get("intereses") or {}
    calificaciones = perfil.get("calificacion_por_curso") or {}
    completados = set(perfil.get("cursos_completados") or [])

    con_evidencia = [dominio[c] for c, n in evidencias.items() if n >= 1 and c in dominio]

    pesos = curso.get("conceptos") or {}
    peso_total = sum(pesos.values())
    dominio_curso = (
        sum(peso * dominio.get(c, sin_evidencia) for c, peso in pesos.items()) / peso_total
        if peso_total > 0
        else sin_evidencia
    )

    notas_previas = [
        float(calificaciones[p["curso_id"]])
        for p in curso.get("prerrequisitos") or []
        if p["curso_id"] in completados and p["curso_id"] in calificaciones
    ]

    x = {
        "dominio_medio": _media(con_evidencia, sin_evidencia),
        "dominio_conceptos_curso": dominio_curso,
        "cursos_previos": float(len(perfil.get("cursos_completados") or [])),
        "calificacion_prerrequisitos": _media(notas_previas, 0.0),
        "tasa_aprobacion_modulos": float(perfil.get("tasa_aprobacion_modulos") or 0.0),
        "intentos_promedio": float(perfil.get("intentos_promedio") or 0.0),
        "dificultad_curso": float(curso.get("dificultad") or 0),
        "nivel_ordinal": float(_NIVEL_ORDINAL.get(perfil.get("nivel"), 0)),
        "coincide_interes": 1.0 if any(intereses.get(c, 0.0) >= _UMBRAL_INTERES for c in pesos) else 0.0,
    }
    return {nombre: round(x[nombre], 6) for nombre in CARACTERISTICAS}


# --- Árbol (puro) -----------------------------------------------------------


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def validar_arbol(arbol: dict, caracteristicas: List[str], profundidad_max: int = 10) -> bool:
    """`True` si `arbol` tiene la forma exportada por 07 y solo usa `caracteristicas`. **Pura.**

    Interno: `{"hoja": False, "campo", "umbral", "izq", "der"}`; hoja:
    `{"hoja": True, "prob" en [0, 1], "n" >= 0}`. La raíz tiene profundidad 0.
    """
    conocidas = set(caracteristicas)

    def valido(nodo, profundidad: int) -> bool:
        if not isinstance(nodo, dict) or profundidad > profundidad_max:
            return False
        hoja = nodo.get("hoja")
        if hoja is True:
            prob, n = nodo.get("prob"), nodo.get("n")
            return _es_numero(prob) and 0.0 <= prob <= 1.0 and _es_numero(n) and n >= 0
        if hoja is not False:
            return False
        return (
            nodo.get("campo") in conocidas
            and _es_numero(nodo.get("umbral"))
            and valido(nodo.get("izq"), profundidad + 1)
            and valido(nodo.get("der"), profundidad + 1)
        )

    return valido(arbol, 0)


def predecir(arbol: dict, x: Dict[str, float]) -> Tuple[float, List[dict]]:
    """Recorre el árbol desde la raíz: `(prob de la hoja, camino)`. **Pura.**

    `izq` = `x[campo] <= umbral`. Una característica ausente vale 0.0. El
    camino es `[{"campo", "umbral", "izq": bool}]`, de la raíz a la hoja.
    """
    nodo = arbol
    camino: List[dict] = []
    while not nodo["hoja"]:
        izq = float(x.get(nodo["campo"], 0.0)) <= nodo["umbral"]
        camino.append({"campo": nodo["campo"], "umbral": nodo["umbral"], "izq": izq})
        nodo = nodo["izq"] if izq else nodo["der"]
    return float(nodo["prob"]), camino


def explicar(camino: List[dict], prob: float) -> Optional[str]:
    """Frase para el alumno a partir del camino, o `None`. **Pura.**

    Solo si `prob >= 0.5`: el primer paso (de la raíz a la hoja) que fue a la
    derecha (`x > umbral`) en una característica con plantilla.
    """
    if prob < 0.5:
        return None
    for paso in camino:
        if not paso["izq"] and paso["campo"] in _PLANTILLAS_EXPLICACION:
            return _PLANTILLAS_EXPLICACION[paso["campo"]]
    return None


def puntuar(perfil: Perfil, candidatos: Sequence[Curso], contexto: Contexto) -> List[Puntuacion]:
    """Probabilidad de aprobar cada candidato; `[]` si `contexto["modelo"]` es None. **Pura.**

    `prob` es una puntuación para ordenar, no una probabilidad calibrada (el
    árbol se entrena con `class_weight="balanced"`).
    """
    modelo = contexto.get("modelo")
    if modelo is None:
        return []
    origen = f"modelo:{modelo['nombre']}@{modelo['version']}"
    puntuaciones: List[Puntuacion] = []
    for curso in candidatos:
        x = caracteristicas_para(perfil, curso, contexto["catalogo"])
        prob, camino = predecir(modelo["arbol"], x)
        puntuaciones.append({
            "curso_id": curso["id"],
            "puntuacion": prob,
            "razones": [{"origen": origen, "aporte": prob, "texto": explicar(camino, prob)}],
        })
    return puntuaciones


# --- Carga del modelo activo (efectos) ---------------------------------------


def _leer_activo(nombre: str) -> Optional[dict]:
    return supabase.select_one(
        "modelos",
        columns="nombre,version,caracteristicas,parametros",
        filters=(eq("nombre", nombre), eq("activo", "true")),
        operation="motor:modelo:activo",
    )


def _modelo_de_fila(fila: Optional[dict]) -> Optional[ModeloActivo]:
    if fila is None:
        return None
    caracteristicas = fila.get("caracteristicas")
    arbol = fila.get("parametros")
    if (
        not isinstance(caracteristicas, list)
        or not set(caracteristicas) <= set(CARACTERISTICAS)
        or not validar_arbol(arbol, caracteristicas)
    ):
        logger.error(
            "Modelo %s@%s descartado: árbol o características no válidos.",
            fila.get("nombre"), fila.get("version"),
        )
        return None
    return {
        "nombre": fila["nombre"],
        "version": fila["version"],
        "caracteristicas": list(caracteristicas),
        "arbol": arbol,
    }


def cargar_activo(nombre: str = "aprobacion") -> Optional[ModeloActivo]:
    """Modelo activo con ese nombre en `modelos` (por defecto `MODELO_NOMBRE`), o `None`. Lo usa 08.

    Un árbol inválido da `None` y un `logger.error`. Memoizado en el proceso
    `CATALOGO_CACHE_SEGUNDOS`, también cuando no hay modelo. Si la tabla no se
    puede leer, `None` sin memoizar: el motor sigue funcionando sin modelo.
    """
    clave = _CACHE_PREFIJO + nombre
    segundos = config.CATALOGO_CACHE_SEGUNDOS
    if segundos > 0:
        guardado = cache.get(clave)
        if guardado is not None:
            return guardado["modelo"]

    try:
        modelo = _modelo_de_fila(_leer_activo(nombre))
    except DataAccessError:
        logger.exception("No se pudo leer el modelo activo %s.", nombre)
        return None

    if segundos > 0:
        cache.set(clave, {"modelo": modelo}, segundos)
    return modelo
