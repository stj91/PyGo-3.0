"""Constructor del perfil del alumno (guía, caps. 1 y 5). **Puro.**

Lo usan la API (con datos vivos), el dataset de 07 y la evaluación de 10 (con
historia reproducida), así todos ven el mismo perfil.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypedDict

from .. import config
from ..tipos import Catalogo, Inscripcion, Nivel, Perfil
from ._comun import (
    TIPO_DIAGNOSTICO,
    a_entero,
    a_fecha,
    a_float,
    nivel_valido,
    rango_estado,
    temas_por_id,
)

#: Intentos de un mismo módulo dentro de esta ventana cuentan como un envío.
_VENTANA_ENVIO = timedelta(minutes=10)


class EntradaPerfil(TypedDict):
    """Datos crudos de un alumno. Fechas como `datetime` o ISO-8601."""

    usuario: dict                 # {"id", "nivel_asignado", "carrera_clave"}
    inscripciones: List[Inscripcion]
    estados_temas: List[dict]     # [{"tema_id", "estado"}]; puede tener duplicados
    intentos: List[dict]          # [{"ejercicio_id", "tema_id", "tipo", "calificacion_obtenida", "fecha_intento"}]
    dominio: Dict[str, float]
    evidencias: Dict[str, int]
    intereses: List[dict]         # [{"concepto_clave", "origen": "declarado"|"inferido", "peso"}]
    ultimo_evento: Optional[datetime]


def construir_perfil(entrada: EntradaPerfil, catalogo: Catalogo, ahora: datetime) -> Perfil:
    """Perfil del alumno a partir de sus datos crudos. **Pura** (no lee el reloj)."""
    usuario = entrada.get("usuario") or {}
    nivel_asignado = nivel_valido(usuario.get("nivel_asignado"))
    carrera = usuario.get("carrera_clave")
    dominio = {k: float(v) for k, v in (entrada.get("dominio") or {}).items() if v is not None}
    evidencias = {k: int(v) for k, v in (entrada.get("evidencias") or {}).items() if v}

    inferido = nivel_inferido(dominio, evidencias)
    usar_inferido = inferido is not None and sum(evidencias.values()) >= config.EVIDENCIAS_MIN_NIVEL_INFERIDO

    inscripciones = _inscripciones(entrada.get("inscripciones") or [])
    completadas = sorted(
        (i for i in inscripciones.values() if i["estado"] == "completado"),
        key=lambda i: (i["completado_en"] is None, i["completado_en"] or ahora, i["curso_id"]),
    )
    envios = _envios(entrada.get("intentos") or [])

    return {
        "usuario_id": str(usuario.get("id") or ""),
        "nivel": inferido if usar_inferido else nivel_asignado,
        "nivel_asignado": nivel_asignado,
        "nivel_inferido": inferido,
        "carrera_clave": carrera,
        "intereses": intereses_por_concepto(entrada.get("intereses") or [], carrera, catalogo),
        "dominio": dominio,
        "evidencias": evidencias,
        "inscripciones": inscripciones,
        "cursos_completados": [i["curso_id"] for i in completadas],
        "calificacion_por_curso": {
            i["curso_id"]: i["calificacion_final"]
            for i in completadas
            if i["calificacion_final"] is not None
        },
        "modulos_en_refuerzo": _modulos_en_refuerzo(entrada.get("estados_temas") or [], catalogo),
        "tasa_aprobacion_modulos": _tasa_aprobacion(envios),
        "intentos_promedio": _intentos_promedio(envios),
        "dias_inactivo": _dias_inactivo(entrada.get("ultimo_evento"), entrada.get("intentos") or [], ahora),
        "calculado_en": ahora,
    }


# --- Intereses --------------------------------------------------------------


def expandir(clave: str, peso: float, catalogo: Catalogo) -> Dict[str, float]:
    """Un área se expande a cada uno de sus conceptos con el mismo peso; un concepto queda igual."""
    if clave in catalogo.get("areas", {}):
        return {c: peso for c in catalogo["areas"][clave]}
    if clave in catalogo.get("conceptos", {}):
        return {clave: peso}
    return {}


def combinar_max(*vectores: Dict[str, float]) -> Dict[str, float]:
    """Combina por máximo y limita a [0, 1], con 3 decimales."""
    resultado: Dict[str, float] = {}
    for vector in vectores:
        for clave, peso in vector.items():
            acotado = round(min(1.0, max(0.0, float(peso))), 3)
            if acotado > resultado.get(clave, -1.0):
                resultado[clave] = acotado
    return resultado


def intereses_por_concepto(
    filas: Iterable[Dict[str, Any]], carrera_clave: Optional[str], catalogo: Catalogo
) -> Dict[str, float]:
    """Intereses declarados, inferidos y de la carrera, expandidos y combinados por máximo.

    Las filas con peso ≤ 0 no cuentan (así se retiran mientras no haya borrado; ver repository).
    """
    vectores = []
    for fila in filas:
        peso = a_float(fila.get("peso"), 0.0)
        if fila.get("concepto_clave") and peso > 0:
            vectores.append(expandir(fila["concepto_clave"], peso, catalogo))
    for area, peso in (catalogo.get("carrera_areas", {}).get(carrera_clave or "", {}) or {}).items():
        if peso > 0:
            vectores.append(expandir(area, peso, catalogo))
    return {k: v for k, v in combinar_max(*vectores).items() if v > 0}


# --- Nivel ------------------------------------------------------------------


def nivel_inferido(dominio: Dict[str, float], evidencias: Dict[str, int]) -> Optional[Nivel]:
    """Nivel según el dominio medio de los conceptos con evidencia; `None` sin evidencia."""
    valores = [dominio[c] for c, n in evidencias.items() if n >= 1 and c in dominio]
    if not valores:
        return None
    media = sum(valores) / len(valores)
    if media >= config.UMBRAL_NIVEL_INFERIDO["Avanzado"]:
        return "Avanzado"
    if media >= config.UMBRAL_NIVEL_INFERIDO["Intermedio"]:
        return "Intermedio"
    return "Principiante"


# --- Inscripciones y módulos ------------------------------------------------


def _inscripciones(filas: Iterable[Dict[str, Any]]) -> Dict[int, Inscripcion]:
    """Por curso; ante duplicados gana el mayor avance (a igualdad, la primera)."""
    resultado: Dict[int, Inscripcion] = {}
    for fila in filas:
        curso_id = a_entero(fila.get("curso_id"))
        if curso_id is None:
            continue
        inscripcion: Inscripcion = {
            "curso_id": curso_id,
            "estado": fila.get("estado") or "activo",
            "porcentaje_avance_global": a_float(fila.get("porcentaje_avance_global"), 0.0),
            "calificacion_final": a_float(fila.get("calificacion_final")),
            "fecha_inscripcion": a_fecha(fila.get("fecha_inscripcion")),
            "completado_en": a_fecha(fila.get("completado_en")),
            "origen": fila.get("origen"),
        }
        actual = resultado.get(curso_id)
        if actual is None or inscripcion["porcentaje_avance_global"] > actual["porcentaje_avance_global"]:
            resultado[curso_id] = inscripcion
    return resultado


def estados_por_tema(filas: Iterable[Dict[str, Any]]) -> Dict[int, str]:
    """Estado más avanzado de cada módulo (mismo rango que `avanza_estado` de 02)."""
    resultado: Dict[int, str] = {}
    for fila in filas:
        tema_id, estado = a_entero(fila.get("tema_id")), fila.get("estado")
        if tema_id is None or not estado:
            continue
        if tema_id not in resultado or rango_estado(estado) > rango_estado(resultado[tema_id]):
            resultado[tema_id] = estado
    return resultado


def _modulos_en_refuerzo(filas: Iterable[Dict[str, Any]], catalogo: Catalogo) -> Dict[int, List[int]]:
    temas = temas_por_id(catalogo)
    en_refuerzo = sorted(
        (temas[t] for t, e in estados_por_tema(filas).items()
         if e == "actividades_de_refuerzo" and t in temas),
        key=lambda t: (t["curso_id"], t["orden"], t["id"]),
    )
    resultado: Dict[int, List[int]] = {}
    for tema in en_refuerzo:
        resultado[tema["curso_id"]] = [*resultado.get(tema["curso_id"], []), tema["id"]]
    return resultado


# --- Intentos ---------------------------------------------------------------


def _envios(intentos: Iterable[Dict[str, Any]]) -> Dict[int, List[bool]]:
    """tema -> lista ordenada de envíos (aprobado?), sin el diagnóstico.

    Un envío agrupa los intentos del mismo módulo hechos a menos de 10 minutos
    del primero del grupo; aprueba si su media ≥ `UMBRAL_APROBADO`.
    """
    por_tema: Dict[int, List[Tuple[datetime, float]]] = {}
    for intento in intentos:
        if intento.get("tipo") == TIPO_DIAGNOSTICO:
            continue
        tema_id, fecha = a_entero(intento.get("tema_id")), a_fecha(intento.get("fecha_intento"))
        if tema_id is None or fecha is None:
            continue
        nota = a_float(intento.get("calificacion_obtenida"), 0.0)
        por_tema[tema_id] = [*por_tema.get(tema_id, []), (fecha, nota)]

    resultado: Dict[int, List[bool]] = {}
    for tema_id, lista in por_tema.items():
        grupos: List[List[float]] = []
        inicio: Optional[datetime] = None
        for fecha, nota in sorted(lista, key=lambda t: t[0]):
            if inicio is None or fecha - inicio > _VENTANA_ENVIO:
                grupos.append([])
                inicio = fecha
            grupos[-1].append(nota)
        resultado[tema_id] = [sum(g) / len(g) >= config.UMBRAL_APROBADO for g in grupos]
    return resultado


def _tasa_aprobacion(envios: Dict[int, List[bool]]) -> Optional[float]:
    total = sum(len(e) for e in envios.values())
    if total == 0:
        return None
    aprobados = sum(1 for e in envios.values() if any(e))
    return round(aprobados / total, 3)


def _intentos_promedio(envios: Dict[int, List[bool]]) -> Optional[float]:
    if not envios:
        return None
    hasta_aprobar = [
        (e.index(True) + 1) if True in e else len(e)
        for e in envios.values()
    ]
    return round(sum(hasta_aprobar) / len(hasta_aprobar), 3)


def _dias_inactivo(ultimo_evento: Any, intentos: Iterable[Dict[str, Any]], ahora: datetime) -> Optional[int]:
    fechas = [a_fecha(ultimo_evento), *(a_fecha(i.get("fecha_intento")) for i in intentos)]
    fechas = [f for f in fechas if f is not None]
    if not fechas:
        return None
    return max(0, (a_fecha(ahora) - max(fechas)).days)
