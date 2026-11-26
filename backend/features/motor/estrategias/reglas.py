"""Estrategia por reglas (docs/motor/05-reglas-y-candidatos.md §2–4).

Las reglas viven como datos en la tabla `reglas` (JSON) y las lee un evaluador
pequeño que solo conoce una lista fija de operadores. El texto guardado nunca
se ejecuta: no hay `eval`, `exec` ni código construido a partir de la base.

Forma de una condición:
- `{}`: siempre se cumple;
- grupo: `{"todas": [...]}`, `{"alguna": [...]}` o `{"ninguna": [...]}`;
- hoja: `{"campo": "curso.nivel", "op": "=", "valor": "Intermedio"}`.

Partes:
- hechos (`hechos_alumno`, `hechos_curso`) y evaluador (`obtener`, `cumple`,
  `resolver_texto`, `validar_regla`), puros;
- `puntuar`, puro;
- `cargar_reglas()`, lectura memoizada.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from django.core.cache import cache

from core import supabase
from core.supabase import eq

from .. import config
from ..candidatos import _dominio_ponderado, prerrequisitos_pendientes, siguiente_en_ruta
from ..tipos import Catalogo, Contexto, Curso, Perfil, Puntuacion, Razon, Regla

logger = logging.getLogger(__name__)

_CACHE_CLAVE = "pygo:motor:reglas"

OPERADORES = frozenset({"=", "!=", "<", "<=", ">", ">=", "en", "contiene", "existe"})
_GRUPOS = ("todas", "alguna", "ninguna")
_CLAVES_HOJA = frozenset({"campo", "op", "valor"})
_AMBITOS = frozenset({"filtro", "recomendacion", "adaptacion", "inferencia"})
_ORDEN = frozenset({"<", "<=", ">", ">="})

#: Máximo de grupos anidados en una condición.
PROFUNDIDAD_MAXIMA = 5

#: Peso mínimo de interés para que un concepto cuente como interés del alumno.
_UMBRAL_INTERES = 0.5

_MARCADOR = re.compile(r"\{([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)\}")


# --- Hechos (puros) ---------------------------------------------------------


def hechos_alumno(perfil: Perfil) -> dict:
    """Hechos del alumno que leen las reglas. **Pura.**"""
    intereses = perfil.get("intereses") or {}
    refuerzo = perfil.get("modulos_en_refuerzo") or {}
    return {
        "nivel": perfil.get("nivel"),
        "nivel_asignado": perfil.get("nivel_asignado"),
        "intereses": sorted(c for c, p in intereses.items() if float(p) >= _UMBRAL_INTERES),
        "dominio": dict(perfil.get("dominio") or {}),
        "cursos_completados": list(perfil.get("cursos_completados") or []),
        "dias_inactivo": perfil.get("dias_inactivo"),
        "tiene_refuerzo": any(bool(temas) for temas in refuerzo.values()),
    }


def _area_de_mayor_interes(perfil: Perfil, curso: Curso, catalogo: Catalogo) -> Optional[str]:
    """Área del curso con mayor peso de interés (empates: alfabético); None si no hay interés."""
    intereses = perfil.get("intereses") or {}
    conceptos = catalogo.get("conceptos") or {}
    peso_por_area: Dict[str, float] = {}
    for clave in curso.get("conceptos") or {}:
        concepto = conceptos.get(clave)
        if concepto is None:
            continue
        area = concepto["area"] if concepto["area"] is not None else clave
        peso = max(float(intereses.get(clave, 0.0)), float(intereses.get(area, 0.0)))
        peso_por_area[area] = max(peso_por_area.get(area, 0.0), peso)
    con_interes = [(area, peso) for area, peso in peso_por_area.items() if peso > 0]
    if not con_interes:
        return None
    return sorted(con_interes, key=lambda par: (-par[1], par[0]))[0][0]


def _titulo(catalogo: Catalogo, curso_id: int) -> Optional[str]:
    curso = catalogo["cursos"].get(curso_id)
    return curso["titulo"] if curso is not None else None


def _prerrequisito_titulo(perfil: Perfil, curso: Curso, catalogo: Catalogo) -> Optional[str]:
    """Título del prerrequisito completado más reciente; si no hay, del primero."""
    requeridos = [
        int(p["curso_id"])
        for p in curso.get("prerrequisitos") or []
        if int(p["curso_id"]) in catalogo["cursos"]
    ]
    if not requeridos:
        return None
    completados = [int(c) for c in perfil.get("cursos_completados") or []]
    inscripciones = perfil.get("inscripciones") or {}
    minimo = datetime.min.replace(tzinfo=timezone.utc)

    def reciente(curso_id: int):
        fecha = (inscripciones.get(curso_id) or {}).get("completado_en")
        return (fecha if isinstance(fecha, datetime) else minimo, completados.index(curso_id))

    hechos = [c for c in requeridos if c in completados]
    elegido = max(hechos, key=reciente) if hechos else requeridos[0]
    return _titulo(catalogo, elegido)


def hechos_curso(perfil: Perfil, curso: Curso, catalogo: Catalogo, siguientes: Sequence[int]) -> dict:
    """Hechos de un curso candidato para este alumno. **Pura.**"""
    intereses = perfil.get("intereses") or {}
    refuerzo = perfil.get("modulos_en_refuerzo") or {}
    area = _area_de_mayor_interes(perfil, curso, catalogo)
    concepto_area = (catalogo.get("conceptos") or {}).get(area) if area else None
    en_refuerzo = [
        int(p["curso_id"])
        for p in curso.get("prerrequisitos") or []
        if refuerzo.get(int(p["curso_id"]))
    ]
    pendientes = prerrequisitos_pendientes(perfil, curso, catalogo)
    return {
        "id": curso["id"],
        "codigo_curso": curso.get("codigo_curso"),
        "titulo": curso.get("titulo"),
        "dificultad": curso.get("dificultad"),
        "nivel": curso.get("nivel"),
        "coincide_interes": any(
            float(intereses.get(clave, 0.0)) >= _UMBRAL_INTERES
            for clave in curso.get("conceptos") or {}
        ),
        "area": area,
        "area_nombre": concepto_area["nombre"] if concepto_area else None,
        "es_siguiente_en_ruta": curso["id"] in set(siguientes),
        "prerrequisito_titulo": _prerrequisito_titulo(perfil, curso, catalogo),
        "dominio_conceptos_curso": _dominio_ponderado(perfil, curso, catalogo),
        "prerrequisito_pendiente": bool(pendientes),
        "prerrequisito_pendiente_titulo": _titulo(catalogo, pendientes[0]) if pendientes else None,
        "prerrequisito_en_refuerzo": bool(en_refuerzo),
        "prerrequisito_refuerzo_titulo": _titulo(catalogo, en_refuerzo[0]) if en_refuerzo else None,
    }


# --- Evaluador (puro) -------------------------------------------------------


def obtener(hechos: dict, ruta: str) -> Any:
    """Valor en la ruta con puntos (`curso.nivel`); None si falta algún paso."""
    if not isinstance(ruta, str) or not ruta:
        return None
    actual: Any = hechos
    for paso in ruta.split("."):
        if not isinstance(actual, dict) or paso not in actual:
            return None
        actual = actual[paso]
    return actual


def _familia(valor: Any) -> Optional[str]:
    if isinstance(valor, bool):
        return "bool"
    if isinstance(valor, (int, float)):
        return "num"
    if isinstance(valor, str):
        return "str"
    if isinstance(valor, (list, tuple)):
        return "lista"
    if isinstance(valor, dict):
        return "dict"
    return None


def _iguales(a: Any, b: Any) -> bool:
    familia = _familia(a)
    if familia is None or familia != _familia(b):
        return False
    if familia == "lista":
        return len(a) == len(b) and all(_iguales(x, y) for x, y in zip(a, b))
    return a == b


def _comparar(valor: Any, op: str, esperado: Any) -> bool:
    if op == "existe":
        return valor is not None and not (isinstance(valor, (list, tuple)) and len(valor) == 0)
    if valor is None:
        return False
    if op == "=":
        return _iguales(valor, esperado)
    if op == "!=":
        familia = _familia(valor)
        return familia is not None and familia == _familia(esperado) and not _iguales(valor, esperado)
    if op in _ORDEN:
        familia = _familia(valor)
        if familia not in ("num", "str") or familia != _familia(esperado):
            return False
        if op == "<":
            return valor < esperado
        if op == "<=":
            return valor <= esperado
        if op == ">":
            return valor > esperado
        return valor >= esperado
    if op == "en":
        return isinstance(esperado, (list, tuple)) and any(_iguales(valor, e) for e in esperado)
    if op == "contiene":
        if isinstance(valor, (list, tuple)):
            return any(_iguales(e, esperado) for e in valor)
        return isinstance(valor, str) and isinstance(esperado, str) and esperado in valor
    return False


def _problemas_condicion(nodo: Any, ruta: str, grupos: int) -> List[str]:
    if not isinstance(nodo, dict):
        return [f"{ruta}: la condición debe ser un objeto"]
    if not nodo:
        return []
    claves = set(nodo)
    grupo = [g for g in _GRUPOS if g in claves]
    if grupo:
        if len(claves) != 1:
            return [f"{ruta}: un grupo lleva una sola clave ({', '.join(sorted(claves))})"]
        nombre = grupo[0]
        if grupos + 1 > PROFUNDIDAD_MAXIMA:
            return [f"{ruta}: más de {PROFUNDIDAD_MAXIMA} grupos anidados"]
        hijos = nodo[nombre]
        if not isinstance(hijos, list):
            return [f"{ruta}.{nombre}: debe ser una lista"]
        problemas: List[str] = []
        for i, hijo in enumerate(hijos):
            problemas.extend(_problemas_condicion(hijo, f"{ruta}.{nombre}[{i}]", grupos + 1))
        return problemas

    sobrantes = claves - _CLAVES_HOJA
    if sobrantes:
        return [f"{ruta}: claves desconocidas {', '.join(sorted(sobrantes))}"]
    problemas = []
    campo, op = nodo.get("campo"), nodo.get("op")
    if not isinstance(campo, str) or not campo.strip():
        problemas.append(f"{ruta}: falta `campo`")
    if op not in OPERADORES:
        problemas.append(f"{ruta}: operador desconocido {op!r}")
    elif op != "existe":
        if "valor" not in nodo:
            problemas.append(f"{ruta}: el operador {op!r} necesita `valor`")
        else:
            valor = nodo["valor"]
            if op == "en" and not isinstance(valor, list):
                problemas.append(f"{ruta}: `en` necesita una lista en `valor`")
            if op in _ORDEN and _familia(valor) not in ("num", "str"):
                problemas.append(f"{ruta}: {op!r} necesita un número o un texto en `valor`")
            if op == "contiene" and valor is None:
                problemas.append(f"{ruta}: `contiene` necesita `valor`")
    return problemas


def _evaluar(nodo: dict, hechos: dict) -> bool:
    if not nodo:
        return True
    if "todas" in nodo:
        return all(_evaluar(h, hechos) for h in nodo["todas"])
    if "alguna" in nodo:
        return any(_evaluar(h, hechos) for h in nodo["alguna"])
    if "ninguna" in nodo:
        return not any(_evaluar(h, hechos) for h in nodo["ninguna"])
    return _comparar(obtener(hechos, nodo["campo"]), nodo["op"], nodo.get("valor"))


def cumple(condicion: dict, hechos: dict) -> bool:
    """¿Se cumple la condición con estos hechos? Nunca lanza.

    Una condición mal formada (operador desconocido, anidación excesiva, …) no
    se cumple, entera: así un `ninguna` con una hoja rota no pasa por verdadero.
    """
    try:
        if _problemas_condicion(condicion, "condicion", 0):
            return False
        return _evaluar(condicion, hechos)
    except Exception:  # defensa: el evaluador no debe romper una recomendación
        logger.exception("Error evaluando una condición de regla")
        return False


def resolver_texto(plantilla: Optional[str], hechos: dict) -> Optional[str]:
    """Sustituye los marcadores `{ruta}`; None si alguno no tiene valor o el texto queda vacío."""
    if not isinstance(plantilla, str) or not plantilla.strip():
        return None
    faltan = False

    def sustituir(m: "re.Match[str]") -> str:
        nonlocal faltan
        valor = obtener(hechos, m.group(1))
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            faltan = True
            return ""
        return str(valor)

    texto = _MARCADOR.sub(sustituir, plantilla)
    if faltan or not texto.strip():
        return None
    return texto


def validar_regla(regla: dict) -> List[str]:
    """Problemas de la regla; lista vacía si es válida. **Pura.**"""
    if not isinstance(regla, dict):
        return ["la regla debe ser un objeto"]
    problemas: List[str] = []
    codigo = regla.get("codigo")
    if not isinstance(codigo, str) or not codigo.strip():
        problemas.append("falta `codigo`")
    ambito = regla.get("ambito")
    if ambito not in _AMBITOS:
        problemas.append(f"ámbito desconocido {ambito!r}")
    if "prioridad" in regla and _familia(regla["prioridad"]) != "num":
        problemas.append("`prioridad` debe ser un número")
    if "activa" in regla and not isinstance(regla["activa"], bool):
        problemas.append("`activa` debe ser booleano")

    problemas.extend(_problemas_condicion(regla.get("condicion"), "condicion", 0))

    accion = regla.get("accion")
    if not isinstance(accion, dict):
        problemas.append("`accion` debe ser un objeto")
        return problemas
    if ambito == "recomendacion":
        if "filtro" not in accion:
            problemas.append("accion: falta `filtro`")
        else:
            problemas.extend(_problemas_condicion(accion["filtro"], "accion.filtro", 0))
        if _familia(accion.get("puntos")) != "num":
            problemas.append("accion: `puntos` debe ser un número")
        explicacion = accion.get("explicacion")
        if explicacion is not None:
            if not isinstance(explicacion, str):
                problemas.append("accion: `explicacion` debe ser texto")
            elif re.search(r"[{}]", _MARCADOR.sub("", explicacion)):
                problemas.append("accion: `explicacion` tiene llaves que no son un marcador {ruta}")
    return problemas


# --- Puntuación (pura) ------------------------------------------------------


def puntuar(perfil: Perfil, candidatos: Sequence[Curso], contexto: Contexto) -> List[Puntuacion]:
    """Puntuación por reglas (puede ser negativa). Como mucho una por candidato. **Pura.** Paquete 05.

    Recorre las reglas `recomendacion` en el orden recibido; las inválidas o
    inactivas se ignoran. Devuelve, en el orden de `candidatos`, solo los que
    tienen al menos una regla disparada, con las razones en orden de regla.
    """
    reglas = [
        r
        for r in contexto.get("reglas") or []
        if r.get("ambito") == "recomendacion" and r.get("activa", True) is True and not validar_regla(r)
    ]
    if not reglas or not candidatos:
        return []

    catalogo = contexto["catalogo"]
    alumno = hechos_alumno(perfil)
    siguientes = siguiente_en_ruta(perfil, catalogo)
    hechos = {
        curso["id"]: {**alumno, "curso": hechos_curso(perfil, curso, catalogo, siguientes)}
        for curso in candidatos
    }
    razones: Dict[int, List[Razon]] = {}

    for regla in reglas:
        if not cumple(regla["condicion"], alumno):
            continue
        accion = regla["accion"]
        puntos = float(accion["puntos"])
        for curso in candidatos:
            h = hechos[curso["id"]]
            if not cumple(accion["filtro"], h):
                continue
            razon: Razon = {
                "origen": f"regla:{regla['codigo']}",
                "texto": resolver_texto(accion.get("explicacion"), h),
                "aporte": puntos,
            }
            razones[curso["id"]] = [*razones.get(curso["id"], []), razon]

    resultado: List[Puntuacion] = []
    vistos = set()
    for curso in candidatos:
        curso_id = curso["id"]
        if curso_id not in razones or curso_id in vistos:
            continue
        vistos.add(curso_id)
        resultado.append({
            "curso_id": curso_id,
            "puntuacion": float(sum(r["aporte"] for r in razones[curso_id])),
            "razones": razones[curso_id],
        })
    return resultado

"""
Las reglas viven como datos JSON en la base de datos. Construimos un
evaluador seguro que interpreta operadores (=, <, >) sin usar
eval(). Por ejemplo, la regla R02 suma puntos si es el siguiente curso
en la ruta, mientras que R05 penaliza un curso si su prerrequisito está
actualmente enn repaso o refuerzo.

The rules are stored as JSON data in the database. We built a safe evaluator
that interprets operators (=, <, >) without using eval(). For example, rule 
R02 adds 2 points if it's the next course on the route, while the rule R05 
penalizes a course if its prerequisite is under review or reinforcement.
"""

def _leer_reglas() -> List[Dict[str, Any]]:
    return supabase.select(
        "reglas",
        columns="id,codigo,nombre,descripcion,ambito,condicion,accion,prioridad,activa",
        filters=(eq("activa", "true"),),
        order="prioridad.desc,id.asc",
        operation="motor:reglas",
    )


def _normalizar(fila: Dict[str, Any]) -> Regla:
    return {
        "id": int(fila["id"]),
        "codigo": fila.get("codigo"),
        "nombre": fila.get("nombre") or "",
        "descripcion": fila.get("descripcion") or "",
        "ambito": fila.get("ambito"),
        "condicion": fila.get("condicion"),
        "accion": fila.get("accion"),
        "prioridad": int(fila.get("prioridad") or 0),
        "activa": fila.get("activa") is True,
    }


def _validas(filas: Sequence[Dict[str, Any]]) -> List[Regla]:
    reglas: List[Regla] = []
    for fila in filas:
        regla = _normalizar(fila)
        if not regla["activa"]:
            continue
        problemas = validar_regla(regla)
        if problemas:
            logger.error("Regla %s descartada: %s", regla["codigo"], "; ".join(problemas))
            continue
        reglas.append(regla)
    return sorted(reglas, key=lambda r: (-r["prioridad"], r["id"]))


def cargar_reglas() -> List[Regla]:
    """Reglas activas de la tabla `reglas`. Paquete 05; lo usa 08.

    Ordenadas por `prioridad desc, id asc`; las inválidas se descartan con
    `logger.error`. Memoizadas `CATALOGO_CACHE_SEGUNDOS` (0 desactiva la caché).
    """
    segundos = config.CATALOGO_CACHE_SEGUNDOS
    if segundos > 0:
        guardadas = cache.get(_CACHE_CLAVE)
        if guardadas is not None:
            return guardadas
    reglas = _validas(_leer_reglas())
    if segundos > 0:
        cache.set(_CACHE_CLAVE, reglas, segundos)
    return reglas


def invalidar_reglas() -> None:
    """Olvida las reglas memoizadas; la próxima carga vuelve a leer la base."""
    cache.delete(_CACHE_CLAVE)
