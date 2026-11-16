"""Orquestación híbrida (paquete 08; guía, cap. 9): reglas + ML.

candidatos -> filtros duros -> puntuar por estrategia -> normalizar -> combinar
con pesos según los datos del alumno -> ajuste por ruta -> diversificar ->
explicar. `recomendar` es pura; `recomendar_cursos` añade la E/S, la ventana
de estabilidad y el registro.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from . import config, diversidad, experimento, explicaciones, registro
from .candidatos import candidatos, filtrar, siguiente_en_ruta
from .catalogo import cargar_catalogo
from .estrategias import colaborativo, contenido, modelo, reglas
from .eventos.repository import a_fecha
from .perfil.service import obtener_perfil
from .tipos import Catalogo, Contexto, Curso, Perfil, Puntuacion

logger = logging.getLogger(__name__)

#: Estrategias que dependen de datos: si no puntúan un candidato, su peso pasa a reglas y contenido.
ESTRATEGIAS_DE_DATOS = ("colaborativo", "modelo")
ESTRATEGIAS_BASE = ("reglas", "contenido")

#: Eventos que invalidan la ventana de estabilidad.
EVENTOS_RELEVANTES = ("quiz_intento", "curso_inscripcion", "curso_completado", "diagnostico")

MOTOR_CONTROL = "control-temario"


def _estrategias_por_defecto() -> Dict[str, Callable]:
    return {
        "reglas": reglas.puntuar,
        "contenido": contenido.puntuar,
        "colaborativo": colaborativo.puntuar,
        "modelo": modelo.puntuar,
    }


# --- Piezas puras -----------------------------------------------------------


def candidatos_permitidos(perfil: Perfil, contexto: Contexto) -> List[Curso]:
    """Candidatos (F03) tras los filtros duros F01/F02. **Pura.**"""
    catalogo = contexto["catalogo"]
    return filtrar(perfil, candidatos(perfil, catalogo), catalogo, contexto.get("reglas") or [])


def modo(perfil: Perfil, contexto: Contexto) -> str:
    """`con_modelo`, `con_historia` o `nuevo` según los datos disponibles. **Pura.**"""
    con_historia = len(perfil.get("cursos_completados") or []) >= config.MIN_CURSOS_COMPLETADOS_PARA_HISTORIA
    if con_historia and contexto.get("modelo") is not None:
        return "con_modelo"
    return "con_historia" if con_historia else "nuevo"


def normalizar(puntuaciones: List[Puntuacion]) -> Dict[int, dict]:
    """curso_id -> `{norm, razones}` con `norm = puntuacion / max|puntuacion|`. **Pura.**

    Las razones conservan su `aporte` y ganan `aporte_norm = aporte / max`. Si el
    máximo es 0, todo vale 0. Si una estrategia repite candidato, cuenta el primero.
    """
    maximo = max((abs(float(p["puntuacion"])) for p in puntuaciones), default=0.0)
    resultado: Dict[int, dict] = {}
    for p in puntuaciones:
        curso_id = int(p["curso_id"])
        if curso_id in resultado:
            continue
        resultado[curso_id] = {
            "norm": float(p["puntuacion"]) / maximo if maximo > 0 else 0.0,
            "razones": [
                {**r, "aporte_norm": float(r.get("aporte", 0.0)) / maximo if maximo > 0 else 0.0}
                for r in p.get("razones") or []
            ],
        }
    return resultado


def pesos_para(curso_id: int, pesos: Dict[str, float], normalizadas: Dict[str, Dict[int, dict]]) -> Dict[str, float]:
    """Pesos efectivos de un candidato. **Pura.**

    El peso de una estrategia de datos sin puntuación para el candidato se
    reparte entre reglas y contenido en proporción a sus pesos.
    """
    efectivos = dict(pesos)
    libre = 0.0
    for estrategia in ESTRATEGIAS_DE_DATOS:
        if efectivos.get(estrategia, 0.0) > 0 and curso_id not in normalizadas.get(estrategia, {}):
            libre += efectivos[estrategia]
            efectivos[estrategia] = 0.0
    base = sum(efectivos.get(e, 0.0) for e in ESTRATEGIAS_BASE)
    if libre > 0 and base > 0:
        for estrategia in ESTRATEGIAS_BASE:
            peso = efectivos.get(estrategia, 0.0)
            efectivos[estrategia] = peso + libre * peso / base
    return efectivos


def _puntuar_todas(estrategias: Dict[str, Callable], pesos: Dict[str, float], perfil: Perfil,
                   cursos: List[Curso], contexto: Contexto):
    """Llama a cada estrategia con peso > 0. Devuelve (pesos con 0 para las que fallan, normalizadas).

    Una estrategia que lanza se registra y cuenta como peso 0: no rompe la lista.
    """
    pesos = dict(pesos)
    normalizadas: Dict[str, Dict[int, dict]] = {}
    for nombre, peso in list(pesos.items()):
        funcion = estrategias.get(nombre)
        if peso <= 0 or funcion is None:
            pesos[nombre] = 0.0
            continue
        try:
            normalizadas[nombre] = normalizar(funcion(perfil, cursos, contexto) or [])
        except Exception:
            logger.exception("La estrategia %s falló; se ignora en esta recomendación.", nombre)
            pesos[nombre] = 0.0
    return pesos, normalizadas


def origenes(razones_por_estrategia: Dict[str, List[dict]], pesos: Dict[str, float]) -> List[str]:
    """`Razon.origen` distintos con `aporte > 0`, por `peso × aporte_norm` desc. **Pura.**"""
    mejor: Dict[str, float] = {}
    orden: List[str] = []
    for estrategia, razones in razones_por_estrategia.items():
        peso = float(pesos.get(estrategia, 0.0))
        if peso <= 0:
            continue
        for razon in razones:
            if float(razon.get("aporte", 0.0)) <= 0:
                continue
            origen = razon["origen"]
            valor = peso * float(razon.get("aporte_norm", 0.0))
            if origen not in mejor:
                orden.append(origen)
                mejor[origen] = valor
            else:
                mejor[origen] = max(mejor[origen], valor)
    return sorted(orden, key=lambda o: -mejor[o])


def continuar(perfil: Perfil, catalogo: Catalogo) -> List[dict]:
    """Inscripciones `activo`, la más reciente primero, como mucho `MAX_CONTINUAR`. **Pura.**"""
    activas = [
        i for i in (perfil.get("inscripciones") or {}).values()
        if i.get("estado") == "activo" and int(i["curso_id"]) in catalogo["cursos"]
    ]
    minimo = datetime.min.replace(tzinfo=timezone.utc)
    activas.sort(key=lambda i: (i.get("fecha_inscripcion") or minimo, -int(i["curso_id"])), reverse=True)
    return [
        {
            "curso_id": int(i["curso_id"]),
            "codigo_curso": catalogo["cursos"][int(i["curso_id"])]["codigo_curso"],
            "titulo": catalogo["cursos"][int(i["curso_id"])]["titulo"],
            "porcentaje_avance_global": i.get("porcentaje_avance_global") or 0,
        }
        for i in activas[: config.MAX_CONTINUAR]
    ]


def recomendar(
    perfil: Perfil,
    contexto: Contexto,
    limite: int,
    estrategias: Optional[Dict[str, Callable]] = None,
) -> dict:
    """Candidatos -> filtros -> puntuar -> combinar -> diversificar -> explicar. **Pura.** Paquete 08.

    Devuelve `{"modo", "items": [ItemRecomendado], "continuar"}` con
    `ItemRecomendado = {curso_id, codigo_curso, titulo, puntuacion, posicion, explicacion, origen}`.
    """
    catalogo = contexto["catalogo"]
    modo_actual = modo(perfil, contexto)
    salida = {"modo": modo_actual, "items": [], "continuar": continuar(perfil, catalogo)}

    cursos = candidatos_permitidos(perfil, contexto)
    if not cursos:
        return salida

    pesos, normalizadas = _puntuar_todas(
        estrategias if estrategias is not None else _estrategias_por_defecto(),
        config.PESOS_ESTRATEGIA[modo_actual], perfil, cursos, contexto,
    )
    siguientes = set(siguiente_en_ruta(perfil, catalogo))

    puntuados = []
    for curso in cursos:
        curso_id = curso["id"]
        efectivos = pesos_para(curso_id, pesos, normalizadas)
        total = sum(
            efectivos.get(nombre, 0.0) * por_curso[curso_id]["norm"]
            for nombre, por_curso in normalizadas.items()
            if curso_id in por_curso
        )
        if curso_id in siguientes:
            total += config.BONO_SIGUIENTE_EN_RUTA
        if total <= 0:
            continue
        razones = {
            nombre: por_curso[curso_id]["razones"]
            for nombre, por_curso in normalizadas.items()
            if curso_id in por_curso and efectivos.get(nombre, 0.0) > 0
        }
        puntuados.append({"curso": curso, "curso_id": curso_id, "puntuacion": total,
                          "pesos": efectivos, "razones": razones})

    puntuados.sort(key=lambda p: (-p["puntuacion"], p["curso"].get("dificultad", 0), p["curso_id"]))
    elegidos = diversidad.mmr(
        puntuados,
        lambda a, b: contenido.similitud_entre_cursos(catalogo["cursos"][a], catalogo["cursos"][b]),
        max(int(limite), 0),
        config.LAMBDA_DIVERSIDAD,
    )

    salida["items"] = [
        {
            "curso_id": p["curso_id"],
            "codigo_curso": p["curso"]["codigo_curso"],
            "titulo": p["curso"]["titulo"],
            "puntuacion": round(p["puntuacion"], 4),
            "posicion": posicion,
            "explicacion": explicaciones.elegir(p["razones"], p["pesos"], p["curso_id"] in siguientes, perfil),
            "origen": origenes(p["razones"], p["pesos"]),
        }
        for posicion, p in enumerate(elegidos, start=1)
    ]
    return salida


# --- Orquestación con E/S ---------------------------------------------------


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(fecha: datetime) -> str:
    return fecha.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def acotar_limite(limite: Optional[int]) -> int:
    """`limite` dentro de `1..LIMITE_MAXIMO`; `LIMITE_POR_DEFECTO` si es None. **Pura.**"""
    if limite is None:
        return config.LIMITE_POR_DEFECTO
    return max(1, min(int(limite), config.LIMITE_MAXIMO))


def _tanda_vigente(usuario_id: str, ahora: datetime, grupo: str) -> List[dict]:
    """Última tanda registrada dentro de la ventana de estabilidad y aún válida; `[]` si no hay.

    Deja de valer si después hubo un evento relevante o cambió el grupo. Un fallo
    al leer no rompe la página: se recalcula.
    """
    try:
        tanda = registro.ultima_tanda(
            registro.recientes(usuario_id, ahora - timedelta(minutes=config.MINUTOS_ESTABILIDAD))
        )
        if not tanda or any(f.get("grupo") != grupo for f in tanda):
            return []
        if registro.hay_eventos_desde(usuario_id, EVENTOS_RELEVANTES, str(tanda[0]["creada_en"])):
            return []
        return tanda
    except Exception:
        logger.exception("No se pudo comprobar la ventana de estabilidad; se recalcula.")
        return []


def _respuesta(usuario_id: str, generado_en: datetime, motor: str, grupo: str,
               items: List[dict], continuar_: List[dict]) -> dict:
    return {
        "success": True,
        "usuario_id": usuario_id,
        "generado_en": _iso(generado_en),
        "motor": motor,
        "grupo": grupo,
        "recomendaciones": items,
        "continuar": continuar_,
    }


def respuesta_desde_tanda(usuario_id: str, tanda: List[dict], perfil: Perfil, catalogo: Catalogo,
                          limite: int, ahora: datetime) -> dict:
    """Reconstruye la respuesta con filas ya registradas, sin las de cursos ya inscritos. **Pura.**"""
    inscritos = {
        int(c) for c, i in (perfil.get("inscripciones") or {}).items()
        if (i or {}).get("estado") in ("activo", "completado")
    }
    filas = [
        f for f in tanda
        if int(f["curso_id"]) in catalogo["cursos"] and int(f["curso_id"]) not in inscritos
    ][:limite]
    items = [
        {
            "recomendacion_id": f["id"],
            "curso_id": int(f["curso_id"]),
            "codigo_curso": catalogo["cursos"][int(f["curso_id"])]["codigo_curso"],
            "titulo": catalogo["cursos"][int(f["curso_id"])]["titulo"],
            "puntuacion": round(float(f.get("puntuacion") or 0), 4),
            "posicion": int(f["posicion"]),
            "explicacion": f["explicacion"],
            "origen": list(f.get("origen") or []),
        }
        for f in filas
    ]
    creada = a_fecha(tanda[0].get("creada_en")) if tanda else None
    return _respuesta(
        usuario_id, creada or ahora, tanda[0]["motor"], tanda[0]["grupo"], items, continuar(perfil, catalogo)
    )


def _contexto(catalogo: Catalogo, ahora: datetime) -> Contexto:
    try:
        similitudes = colaborativo.cargar_similitudes()
    except Exception:
        logger.exception("No se pudieron cargar las similitudes; se recomienda sin colaborativo.")
        similitudes = {}
    return {
        "catalogo": catalogo,
        "reglas": reglas.cargar_reglas(),
        "similitudes": similitudes,
        "modelo": modelo.cargar_activo(config.MODELO_NOMBRE),
        "ahora": ahora,
    }


def recomendar_cursos(usuario_id: str, limite: int) -> dict:
    """Recomendaciones del usuario con E/S y registro; la respuesta de 00 §6.2. Paquete 08.

    Reutiliza la última tanda si es de los últimos `MINUTOS_ESTABILIDAD` minutos,
    tiene al menos `limite` filas y no ha pasado nada relevante desde entonces
    (guía, cap. 10). Si el registro falla, devuelve igualmente la lista.
    """
    limite = acotar_limite(limite)
    ahora = _ahora()
    grupo = experimento.grupo_asignado(usuario_id)
    perfil = obtener_perfil(usuario_id)
    catalogo = cargar_catalogo()

    tanda = _tanda_vigente(usuario_id, ahora, grupo)
    if tanda and len(tanda) >= limite:
        return respuesta_desde_tanda(usuario_id, tanda, perfil, catalogo, limite, ahora)

    contexto = _contexto(catalogo, ahora)
    if grupo == "motor":
        resultado, motor = recomendar(perfil, contexto, limite), config.MOTOR_VERSION
    else:
        resultado, motor = experimento.recomendar_control(perfil, contexto, limite), MOTOR_CONTROL

    # Una tanda corta que coincide con la nueva lista se reutiliza: no se registra dos veces lo mismo.
    if tanda and [i["curso_id"] for i in resultado["items"]] == [int(f["curso_id"]) for f in tanda]:
        return respuesta_desde_tanda(usuario_id, tanda, perfil, catalogo, limite, ahora)

    items = [{"recomendacion_id": registro.nuevo_id(), **item} for item in resultado["items"]]
    try:
        registro.registrar(usuario_id, items, motor, grupo, perfil)
    except Exception:
        logger.exception("No se pudieron registrar las recomendaciones de %s.", usuario_id)
    return _respuesta(usuario_id, ahora, motor, grupo, items, resultado["continuar"])
