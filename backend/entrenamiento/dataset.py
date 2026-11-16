"""Dataset supervisado: una fila por inscripción con desenlace (solo librería estándar).

Para cada inscripción `completado` o `abandonado` se reconstruye el perfil del
alumno **tal como era en `t = fecha_inscripcion`** con las funciones puras de
04 (`reproducir_dominio`, `construir_perfil`) y se calculan las
características con `caracteristicas_para`, la misma función que usa la API.

Nada con fecha `>= t` entra en las características (fuga de datos): a 04 solo
se le pasan eventos, intentos e inscripciones anteriores a `t`.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from features.motor import config
from features.motor.estrategias import modelo
from features.motor.perfil import construir as perfil_construir
from features.motor.perfil import dominio as perfil_dominio
from features.motor.tipos import Catalogo

from .sinteticos import TIPO_DIAGNOSTICO, fecha

COLUMNAS_DATASET = ["usuario_id", "curso_id", "fecha_inscripcion", *modelo.CARACTERISTICAS, "aprobo"]

_VENTANA_ENVIO = timedelta(minutes=10)
_RESULTADOS = ("completado", "abandonado")


# --- Normalización (pura): filas de CSV (texto) o de `generar` (tipadas) -----


def _entero(valor: Any) -> Optional[int]:
    return None if valor is None or valor == "" else int(float(valor))


def _real(valor: Any) -> Optional[float]:
    return None if valor is None or valor == "" else float(valor)


def _texto(valor: Any) -> Optional[str]:
    return None if valor is None or valor == "" else str(valor)


def _lista(valor: Any) -> List[str]:
    if isinstance(valor, (list, tuple)):
        return [str(v) for v in valor if v]
    return [v for v in str(valor or "").split(";") if v]


def _datos(valor: Any) -> dict:
    if isinstance(valor, dict):
        return valor
    return json.loads(valor) if valor else {}


def _alumno(f: dict) -> dict:
    return {
        "usuario_id": str(f["usuario_id"]),
        "nivel_asignado": _texto(f.get("nivel_asignado")) or "Principiante",
        "carrera_clave": _texto(f.get("carrera_clave")),
        "intereses": _lista(f.get("intereses")),
    }


def _inscripcion(f: dict) -> dict:
    return {
        "usuario_id": str(f["usuario_id"]),
        "curso_id": _entero(f["curso_id"]),
        "estado": _texto(f.get("estado")) or "activo",
        "porcentaje_avance_global": _real(f.get("porcentaje_avance_global")) or 0.0,
        "calificacion_final": _real(f.get("calificacion_final")),
        "fecha_inscripcion": fecha(f.get("fecha_inscripcion")),
        "completado_en": fecha(f.get("completado_en")),
        "origen": _texto(f.get("origen")),
    }


def _intento(f: dict) -> dict:
    return {
        "ejercicio_id": _entero(f.get("ejercicio_id")),
        "tema_id": _entero(f.get("tema_id")),
        "tipo": _texto(f.get("tipo")),
        "calificacion_obtenida": _real(f.get("calificacion_obtenida")) or 0.0,
        "fecha_intento": fecha(f.get("fecha_intento")),
    }


def _evento(f: dict) -> dict:
    return {
        "usuario_id": str(f["usuario_id"]),
        "tipo": str(f["tipo"]),
        "objeto_tipo": _texto(f.get("objeto_tipo")),
        "objeto_id": _entero(f.get("objeto_id")),
        "curso_id": _entero(f.get("curso_id")),
        "valor": _real(f.get("valor")),
        "datos": _datos(f.get("datos")),
        "fecha": fecha(f.get("fecha")),
    }


def _por_usuario(filas: Iterable[dict], normalizar) -> Dict[str, List[dict]]:
    grupos: Dict[str, List[dict]] = {}
    for fila in filas:
        normal = {**normalizar(fila), "usuario_id": str(fila["usuario_id"])}
        grupos.setdefault(normal["usuario_id"], []).append(normal)
    return grupos


# --- Estado en t (puro) -----------------------------------------------------


def _envios(intentos: Sequence[dict]) -> List[Tuple[int, datetime, float]]:
    """`(tema_id, inicio, media)` por envío: intentos de un módulo en 10 minutos son uno."""
    por_tema: Dict[int, List[dict]] = {}
    for i in intentos:
        if i["tipo"] != TIPO_DIAGNOSTICO and i["tema_id"] is not None:
            por_tema.setdefault(i["tema_id"], []).append(i)
    envios = []
    for tema_id, filas in por_tema.items():
        grupo: List[dict] = []
        for fila in sorted(filas, key=lambda i: i["fecha_intento"]):
            if grupo and fila["fecha_intento"] - grupo[0]["fecha_intento"] > _VENTANA_ENVIO:
                envios.append(_cerrar_envio(tema_id, grupo))
                grupo = []
            grupo.append(fila)
        if grupo:
            envios.append(_cerrar_envio(tema_id, grupo))
    return sorted(envios, key=lambda e: (e[1], e[0]))


def _cerrar_envio(tema_id: int, grupo: List[dict]) -> Tuple[int, datetime, float]:
    media = sum(i["calificacion_obtenida"] for i in grupo) / len(grupo)
    return tema_id, grupo[0]["fecha_intento"], media


def _estado_envio(media: float) -> str:
    if media >= config.UMBRAL_APROBADO:
        return "completado"
    if media < config.UMBRAL_REFUERZO:
        return "actividades_de_refuerzo"
    return "desbloqueado"


def _inscripciones_en(
    inscripciones: Sequence[dict], t: datetime, temas_aprobados: set, catalogo: Catalogo
) -> List[dict]:
    """Inscripciones como estaban en `t`: completadas solo si `completado_en < t`; el resto activas."""
    resultado = []
    for i in inscripciones:
        if i["fecha_inscripcion"] is None or i["fecha_inscripcion"] >= t:
            continue
        base = {k: v for k, v in i.items() if k != "usuario_id"}
        if i["estado"] == "completado" and i["completado_en"] is not None and i["completado_en"] < t:
            resultado.append(base)
            continue
        temas = [tema["id"] for tema in catalogo["cursos"].get(i["curso_id"], {}).get("temas", [])]
        avance = 100.0 * sum(1 for x in temas if x in temas_aprobados) / len(temas) if temas else 0.0
        resultado.append({
            **base,
            "estado": "activo",
            "porcentaje_avance_global": round(avance, 2),
            "calificacion_final": None,
            "completado_en": None,
        })
    return resultado


def entrada_en(
    alumno: dict,
    inscripciones: Sequence[dict],
    intentos: Sequence[dict],
    eventos: Sequence[dict],
    catalogo: Catalogo,
    t: datetime,
) -> perfil_construir.EntradaPerfil:
    """`EntradaPerfil` del alumno con solo lo ocurrido estrictamente antes de `t`. **Pura.**"""
    eventos_previos = [e for e in eventos if e["fecha"] is not None and e["fecha"] < t]
    intentos_previos = [i for i in intentos if i["fecha_intento"] is not None and i["fecha_intento"] < t]

    dominio, evidencias = perfil_dominio.reproducir_dominio(
        eventos_previos, catalogo, alumno["nivel_asignado"], hasta=t
    )
    envios = _envios(intentos_previos)
    temas_aprobados = {tema for tema, _, media in envios if media >= config.UMBRAL_APROBADO}

    return {
        "usuario": {
            "id": alumno["usuario_id"],
            "nivel_asignado": alumno["nivel_asignado"],
            "carrera_clave": alumno["carrera_clave"],
        },
        "inscripciones": _inscripciones_en(inscripciones, t, temas_aprobados, catalogo),
        "estados_temas": [{"tema_id": tema, "estado": _estado_envio(media)} for tema, _, media in envios],
        "intentos": [dict(i) for i in intentos_previos],
        "dominio": dominio,
        "evidencias": evidencias,
        "intereses": [
            {"concepto_clave": clave, "origen": "declarado", "peso": config.PESO_INTERES_DECLARADO}
            for clave in alumno["intereses"]
        ],
        "ultimo_evento": max((e["fecha"] for e in eventos_previos), default=None),
    }


def _etiqueta(inscripcion: dict) -> int:
    calificacion = inscripcion["calificacion_final"]
    return int(
        inscripcion["estado"] == "completado"
        and calificacion is not None
        and calificacion >= config.UMBRAL_ETIQUETA_APROBO
    )


def construir(alumnos, inscripciones, intentos, eventos, catalogo) -> List[dict]:
    """Filas `{usuario_id, curso_id, fecha_inscripcion, **x, aprobo}`, ordenadas por fecha. **Pura.**

    Acepta filas de CSV (texto) o de `sinteticos.generar` (tipadas). Se omiten
    las inscripciones activas y las de cursos que no están en el catálogo.
    """
    insc_por_usuario = _por_usuario(inscripciones, _inscripcion)
    intentos_por_usuario = _por_usuario(intentos, _intento)
    eventos_por_usuario = _por_usuario(eventos, _evento)

    filas = []
    for alumno in (_alumno(a) for a in alumnos):
        uid = alumno["usuario_id"]
        propias = insc_por_usuario.get(uid, [])
        for inscripcion in propias:
            curso = catalogo["cursos"].get(inscripcion["curso_id"])
            t = inscripcion["fecha_inscripcion"]
            if inscripcion["estado"] not in _RESULTADOS or curso is None or t is None:
                continue
            entrada = entrada_en(
                alumno, propias, intentos_por_usuario.get(uid, []),
                eventos_por_usuario.get(uid, []), catalogo, t,
            )
            perfil = perfil_construir.construir_perfil(entrada, catalogo, ahora=t)
            filas.append({
                "usuario_id": uid,
                "curso_id": inscripcion["curso_id"],
                "fecha_inscripcion": t.isoformat(),
                **modelo.caracteristicas_para(perfil, curso, catalogo),
                "aprobo": _etiqueta(inscripcion),
            })
    return sorted(filas, key=lambda f: (f["fecha_inscripcion"], f["usuario_id"], f["curso_id"]))


# --- Lectura desde la base (efectos; lo ejecuta el usuario, no los tests) ----

_PAGINA = 1000


def _leer_todo(tabla: str, columnas: str, orden: str, filtros: Sequence[tuple] = ()) -> List[dict]:
    from core import supabase

    filas: List[dict] = []
    while True:
        pagina = supabase.select(
            tabla, columns=columnas, order=orden, limit=_PAGINA,
            filters=(*filtros, ("offset", str(len(filas)))),
            operation=f"motor:dataset:{tabla}",
        )
        filas.extend(pagina)
        if len(pagina) < _PAGINA:
            return filas


def _clave(recurso: Any, campo: str = "clave") -> Any:
    if isinstance(recurso, list):
        recurso = recurso[0] if recurso else None
    return recurso.get(campo) if isinstance(recurso, dict) else None


def leer_desde_bd() -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    """`(alumnos, inscripciones, intentos, eventos)` leídos de Supabase con las formas de los CSV.

    Solo lectura. Los intereses son los declarados (los inferidos los calcula un
    batch en fechas desconocidas y filtrarían información del futuro).
    """
    from core.supabase import eq

    usuarios = _leer_todo("usuarios", "id,nivel_asignado,carreras(clave)", "id.asc")
    declarados: Dict[str, List[str]] = {}
    for f in _leer_todo(
        "intereses_usuario", "usuario_id,conceptos(clave)", "usuario_id.asc,concepto_id.asc",
        (eq("origen", "declarado"),),
    ):
        clave = _clave(f.get("conceptos"))
        if clave:
            declarados.setdefault(str(f["usuario_id"]), []).append(clave)

    alumnos = [
        {
            "usuario_id": str(u["id"]),
            "nivel_asignado": u.get("nivel_asignado") or "Principiante",
            "carrera_clave": _clave(u.get("carreras")),
            "intereses": declarados.get(str(u["id"]), []),
        }
        for u in usuarios
    ]
    inscripciones = _leer_todo(
        "usuario_cursos",
        "usuario_id,curso_id,estado,porcentaje_avance_global,calificacion_final,"
        "fecha_inscripcion,completado_en,origen",
        "id.asc",
    )
    intentos = [
        {
            "usuario_id": f["usuario_id"],
            "ejercicio_id": f["ejercicio_id"],
            "tema_id": _clave(f.get("ejercicios"), "tema_id"),
            "tipo": _clave(f.get("ejercicios"), "tipo"),
            "calificacion_obtenida": f.get("calificacion_obtenida"),
            "fecha_intento": f.get("fecha_intento"),
        }
        for f in _leer_todo(
            "intentos_ejercicios",
            "usuario_id,ejercicio_id,calificacion_obtenida,fecha_intento,ejercicios(tema_id,tipo)",
            "id.asc",
        )
        if f.get("fecha_intento")
    ]
    eventos = _leer_todo(
        "eventos", "usuario_id,tipo,objeto_tipo,objeto_id,curso_id,valor,datos,fecha", "id.asc"
    )
    return alumnos, inscripciones, intentos, eventos
