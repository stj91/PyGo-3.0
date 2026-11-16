"""Evaluación offline del motor (paquete 10; guía, cap. 11). Solo librería estándar.

Partición temporal: `T` es el percentil 70 de `fecha_inscripcion`. El motor
solo conoce lo ocurrido **estrictamente antes de `T`** (perfiles, similitudes,
popularidad y el árbol); la verdad de cada alumno son los cursos en los que se
inscribió en `T` o después. Los alumnos sin inscripciones desde `T` se omiten.

Cada configuración pasa por `hibrido.recomendar` (o `recomendar_control`) para
que filtros, diversidad y desempates sean idénticos; solo cambian las
estrategias activas y los pesos. El entrenamiento del árbol (opcional) importa
pandas/scikit-learn de forma diferida.
"""

import contextlib
import csv
import hashlib
import json
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Set

from features.motor import config, experimento, hibrido
from features.motor.estrategias import colaborativo, contenido, modelo, reglas as reglas_estrategia
from features.motor.perfil import construir as perfil_construir
from features.motor.tipos import Catalogo, Contexto, ModeloActivo, Perfil, Regla

from . import dataset, sinteticos

RUTA_REGLAS_SEMILLA = Path(__file__).resolve().parent / "reglas_semilla.json"
PERCENTIL_CORTE = 0.70
ORIGEN = "sintetico"

PESOS_B = {"reglas": 0.2, "contenido": 0.2, "colaborativo": 0.3, "modelo": 0.3}

CONFIGURACIONES = [
    "popular",
    "temario",
    "reglas",
    "contenido",
    "reglas+contenido",
    "hibrido",
    "hibrido-sin-modelo",
    "hibrido-pesos-b",
]
#: Sin modelo, `hibrido-sin-modelo` sería idéntica a `hibrido`: se omite.
CONFIGURACIONES_CON_MODELO = frozenset({"hibrido-sin-modelo"})


# --- Métricas (puras) -------------------------------------------------------


def evaluar_k(recomendados: Dict[str, List[int]], reales: Dict[str, Set[int]], k: int) -> dict:
    """`precision@k`, `recall@k`, `hit_rate@k` medios y `n_alumnos`. **Pura.**

    Solo cuentan los alumnos con verdad no vacía; si uno no tiene lista, cuenta
    como lista vacía. `precision = aciertos / k` (aunque la lista sea más corta).
    """
    precisiones, recalls, aciertos_alguno = [], [], []
    for usuario, verdad in reales.items():
        if not verdad:
            continue
        lista = list(recomendados.get(usuario) or [])[:k]
        aciertos = len(set(lista) & set(verdad))
        precisiones.append(aciertos / k if k > 0 else 0.0)
        recalls.append(aciertos / len(verdad))
        aciertos_alguno.append(1.0 if aciertos else 0.0)
    n = len(precisiones)
    return {
        "precision": sum(precisiones) / n if n else 0.0,
        "recall": sum(recalls) / n if n else 0.0,
        "hit_rate": sum(aciertos_alguno) / n if n else 0.0,
        "n_alumnos": n,
    }


def cobertura(recomendados: Dict[str, List[int]], catalogo: Catalogo) -> float:
    """Proporción de cursos del catálogo recomendados al menos una vez. **Pura.**"""
    cursos = set(catalogo["cursos"])
    if not cursos:
        return 0.0
    vistos = {int(c) for lista in recomendados.values() for c in lista} & cursos
    return len(vistos) / len(cursos)


def diversidad(recomendados: Dict[str, List[int]], catalogo: Catalogo) -> Optional[float]:
    """Media de `1 − similitud media por pares` de cada lista (las de < 2 cursos no cuentan). **Pura.**

    `None` si ninguna lista tiene 2 cursos o más.
    """
    valores = []
    for lista in recomendados.values():
        cursos = [catalogo["cursos"][int(c)] for c in lista if int(c) in catalogo["cursos"]]
        if len(cursos) < 2:
            continue
        pares = [
            contenido.similitud_entre_cursos(cursos[i], cursos[j])
            for i in range(len(cursos)) for j in range(i + 1, len(cursos))
        ]
        valores.append(1.0 - sum(pares) / len(pares))
    return sum(valores) / len(valores) if valores else None


# --- Partición temporal (pura) ----------------------------------------------


def corte_temporal(inscripciones: Sequence[dict], percentil: float = PERCENTIL_CORTE) -> datetime:
    """Percentil de `fecha_inscripcion` (rango inferior: `orden[floor(p·(n−1))]`). **Pura.**"""
    fechas = sorted(i["fecha_inscripcion"] for i in inscripciones if i.get("fecha_inscripcion") is not None)
    if not fechas:
        raise ValueError("No hay inscripciones con fecha: no se puede elegir T.")
    return fechas[int(math.floor(percentil * (len(fechas) - 1)))]


def verdad_desde(inscripciones: Sequence[dict], t: datetime) -> Dict[str, Set[int]]:
    """usuario -> cursos en los que se inscribió en `t` o después. **Pura.**"""
    reales: Dict[str, Set[int]] = {}
    for i in inscripciones:
        if i.get("fecha_inscripcion") is not None and i["fecha_inscripcion"] >= t:
            reales.setdefault(str(i["usuario_id"]), set()).add(int(i["curso_id"]))
    return reales


def antes_de(filas: Sequence[dict], campo: str, t: datetime) -> List[dict]:
    """Filas con `campo < t`. **Pura.**"""
    return [f for f in filas if f.get(campo) is not None and f[campo] < t]


def estado_en(inscripcion: dict, t: datetime) -> dict:
    """La inscripción como se veía en `t`: completada solo si `completado_en < t`; si no, activa. **Pura.**

    El abandono no tiene fecha en los datos, así que antes de `t` no se puede
    saber: cuenta como activa (igual que 07 al reconstruir perfiles).
    """
    if inscripcion.get("estado") == "completado" and inscripcion.get("completado_en") is not None \
            and inscripcion["completado_en"] < t:
        return dict(inscripcion)
    return {**inscripcion, "estado": "activo", "calificacion_final": None, "completado_en": None}


def similitudes_en(inscripciones: Sequence[dict], t: datetime):
    """Similitudes ítem-ítem con las inscripciones previas a `t`, en su estado en `t`. **Pura.**"""
    previas = [estado_en(i, t) for i in antes_de(inscripciones, "fecha_inscripcion", t)]
    return colaborativo.calcular_similitudes(colaborativo.interacciones(previas))


def popularidad_en(inscripciones: Sequence[dict], t: datetime) -> Dict[int, int]:
    """curso_id -> número de inscripciones previas a `t`. **Pura.**"""
    cuenta: Dict[int, int] = {}
    for i in antes_de(inscripciones, "fecha_inscripcion", t):
        cuenta[int(i["curso_id"])] = cuenta.get(int(i["curso_id"]), 0) + 1
    return cuenta


def perfiles_en(alumnos: Sequence[dict], inscripciones: Sequence[dict], intentos: Sequence[dict],
                eventos: Sequence[dict], catalogo: Catalogo, t: datetime,
                usuarios: Optional[Set[str]] = None) -> Dict[str, Perfil]:
    """Perfil de cada alumno en `t`, con el mismo código que el dataset de 07. **Pura.**

    Acepta filas de CSV o ya normalizadas; `usuarios` limita a quiénes se calcula.
    """
    insc = dataset._por_usuario(inscripciones, dataset._inscripcion)
    intn = dataset._por_usuario(intentos, dataset._intento)
    evts = dataset._por_usuario(eventos, dataset._evento)
    perfiles: Dict[str, Perfil] = {}
    for alumno in (dataset._alumno(a) for a in alumnos):
        uid = alumno["usuario_id"]
        if usuarios is not None and uid not in usuarios:
            continue
        entrada = dataset.entrada_en(
            alumno, insc.get(uid, []), intn.get(uid, []), evts.get(uid, []), catalogo, t
        )
        perfiles[uid] = perfil_construir.construir_perfil(entrada, catalogo, ahora=t)
    return perfiles


def desenlaces_conocidos(inscripciones: Sequence[dict], eventos: Sequence[dict], t: datetime) -> Set[tuple]:
    """(usuario, curso) cuyo desenlace ya se conocía antes de `t`. **Pura.**

    Completado: `completado_en < t`. Abandonado: el último evento del alumno en
    ese curso (o la inscripción, si no hay eventos) es anterior a `t`.
    """
    ultimo: Dict[tuple, datetime] = {}
    for e in eventos:
        if e.get("curso_id") is None or e.get("fecha") is None:
            continue
        clave = (str(e["usuario_id"]), int(e["curso_id"]))
        if clave not in ultimo or e["fecha"] > ultimo[clave]:
            ultimo[clave] = e["fecha"]
    conocidos = set()
    for i in inscripciones:
        clave = (str(i["usuario_id"]), int(i["curso_id"]))
        if i.get("estado") == "completado":
            fin = i.get("completado_en")
        elif i.get("estado") == "abandonado":
            fin = max(filter(None, [ultimo.get(clave), i.get("fecha_inscripcion")]), default=None)
        else:
            continue
        if fin is not None and fin < t:
            conocidos.add(clave)
    return conocidos


# --- Configuraciones --------------------------------------------------------


def cargar_reglas_semilla(ruta: Path = RUTA_REGLAS_SEMILLA) -> List[Regla]:
    """Reglas de `reglas_semilla.json`, activas y válidas, en el orden de `cargar_reglas`."""
    with open(ruta, encoding="utf-8") as f:
        filas = json.load(f)
    validas = [r for r in filas if r.get("activa") and not reglas_estrategia.validar_regla(r)]
    return sorted(validas, key=lambda r: (-int(r["prioridad"]), int(r["id"])))


@contextlib.contextmanager
def pesos_temporales(pesos_por_modo: Optional[Dict[str, Dict[str, float]]]) -> Iterator[None]:
    """Sustituye `config.PESOS_ESTRATEGIA` mientras dura el bloque (08 lo lee al llamar)."""
    if pesos_por_modo is None:
        yield
        return
    anterior = config.PESOS_ESTRATEGIA
    config.PESOS_ESTRATEGIA = {**anterior, **pesos_por_modo}
    try:
        yield
    finally:
        config.PESOS_ESTRATEGIA = anterior


def _recomendar(perfil: Perfil, contexto: Contexto, k: int,
                estrategias: Optional[Dict[str, Callable]] = None,
                pesos: Optional[Dict[str, Dict[str, float]]] = None) -> List[int]:
    with pesos_temporales(pesos):
        resultado = hibrido.recomendar(perfil, contexto, k, estrategias=estrategias)
    return [int(i["curso_id"]) for i in resultado["items"]]


def _popular(perfil: Perfil, contexto: Contexto, k: int, popularidad: Dict[int, int]) -> List[int]:
    cursos = hibrido.candidatos_permitidos(perfil, contexto)
    orden = sorted(cursos, key=lambda c: (-popularidad.get(c["id"], 0), c.get("dificultad", 0), c["id"]))
    return [c["id"] for c in orden[:k]]


def _configuraciones(popularidad: Dict[int, int]) -> Dict[str, Callable[[Perfil, Contexto, int], List[int]]]:
    nuevo = config.PESOS_ESTRATEGIA["nuevo"]
    return {
        "popular": lambda p, c, k: _popular(p, c, k, popularidad),
        "temario": lambda p, c, k: [int(i["curso_id"]) for i in experimento.recomendar_control(p, c, k)["items"]],
        "reglas": lambda p, c, k: _recomendar(p, c, k, {"reglas": reglas_estrategia.puntuar}),
        "contenido": lambda p, c, k: _recomendar(p, c, k, {"contenido": contenido.puntuar}),
        "reglas+contenido": lambda p, c, k: _recomendar(
            p, c, k, {"reglas": reglas_estrategia.puntuar, "contenido": contenido.puntuar},
            {modo_: dict(nuevo) for modo_ in config.PESOS_ESTRATEGIA},
        ),
        "hibrido": lambda p, c, k: _recomendar(p, c, k),
        "hibrido-sin-modelo": lambda p, c, k: _recomendar(p, {**c, "modelo": None}, k),
        "hibrido-pesos-b": lambda p, c, k: _recomendar(
            p, c, k, None, {"con_historia": dict(PESOS_B), "con_modelo": dict(PESOS_B)},
        ),
    }


def recomendaciones(perfiles: Dict[str, Perfil], contexto: Contexto, popularidad: Dict[int, int],
                    k: int, nombres: Sequence[str] = CONFIGURACIONES) -> Dict[str, Dict[str, List[int]]]:
    """configuración -> usuario -> top `k` curso_ids. **Pura** (el cambio de pesos se deshace)."""
    funciones = _configuraciones(popularidad)
    return {
        nombre: {uid: funciones[nombre](perfil, contexto, k) for uid, perfil in sorted(perfiles.items())}
        for nombre in nombres
    }


# --- Modelo entrenado solo con lo conocido antes de T (efectos) --------------


def entrenar_modelo_en(alumnos, inscripciones, intentos, eventos, catalogo: Catalogo, t: datetime,
                       semilla: int) -> dict:
    """Árbol de 07 entrenado con las inscripciones cuyo desenlace se conocía antes de `t`.

    Usa `dataset.construir` + `entrenar.entrenar` (que exporta con
    `arbol_a_json`) en una carpeta temporal. Devuelve `{"modelo": ModeloActivo, "metricas"}`.
    """
    from . import entrenar  # pandas / scikit-learn

    conocidos = desenlaces_conocidos(inscripciones, eventos, t)
    filas = [
        f for f in dataset.construir(
            alumnos, antes_de(inscripciones, "fecha_inscripcion", t),
            antes_de(intentos, "fecha_intento", t), antes_de(eventos, "fecha", t), catalogo,
        )
        if (str(f["usuario_id"]), int(f["curso_id"])) in conocidos
    ]
    if not filas:
        raise ValueError("No hay inscripciones con desenlace conocido antes de T para entrenar el modelo.")

    with tempfile.TemporaryDirectory(prefix="pygo-evaluacion-") as carpeta:
        ruta = Path(carpeta) / "dataset.csv"
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=dataset.COLUMNAS_DATASET)
            escritor.writeheader()
            escritor.writerows(filas)
        anterior = entrenar.DIRECTORIO_MODELOS
        entrenar.DIRECTORIO_MODELOS = Path(carpeta) / "modelos"
        try:
            resultado = entrenar.entrenar(ruta, origen=ORIGEN, semilla=semilla)
        finally:
            entrenar.DIRECTORIO_MODELOS = anterior

    activo: ModeloActivo = {
        "nombre": config.MODELO_NOMBRE,
        "version": resultado["version"],
        "caracteristicas": list(modelo.CARACTERISTICAS),
        "arbol": resultado["arbol"],
    }
    return {"modelo": activo, "metricas": resultado["metricas"]}


# --- Ejecución completa -----------------------------------------------------


def huella_datos(datos_dir: Path) -> str:
    """SHA-256 de los CSV y `catalogo.json` del directorio, en orden fijo."""
    resumen = hashlib.sha256()
    for nombre in [*(f"{clave}.csv" for clave in sinteticos.COLUMNAS), "catalogo.json"]:
        resumen.update(nombre.encode("utf-8") + b"\0")
        resumen.update((Path(datos_dir) / nombre).read_bytes())
    return resumen.hexdigest()


def _normalizados(datos: Dict[str, List[dict]]):
    alumnos = [dataset._alumno(a) for a in datos["alumnos"]]
    inscripciones = [{**dataset._inscripcion(f), "usuario_id": str(f["usuario_id"])} for f in datos["inscripciones"]]
    intentos = [{**dataset._intento(f), "usuario_id": str(f["usuario_id"])} for f in datos["intentos"]]
    eventos = [dataset._evento(f) for f in datos["eventos"]]
    return alumnos, inscripciones, intentos, eventos


def ejecutar(datos_dir: Path, k: int = 3, con_modelo: bool = True, semilla: int = 42) -> dict:
    """Evalúa todas las configuraciones sobre los CSV de `datos_dir` (formato de 07). Sin base de datos."""
    datos_dir = Path(datos_dir)
    datos, catalogo = sinteticos.leer(datos_dir)
    alumnos, inscripciones, intentos, eventos = _normalizados(datos)

    t = corte_temporal(inscripciones)
    reales = {u: v for u, v in verdad_desde(inscripciones, t).items() if v}
    perfiles = perfiles_en(alumnos, inscripciones, intentos, eventos, catalogo, t, usuarios=set(reales))

    entrenado = entrenar_modelo_en(alumnos, inscripciones, intentos, eventos, catalogo, t, semilla) \
        if con_modelo else None
    contexto: Contexto = {
        "catalogo": catalogo,
        "reglas": cargar_reglas_semilla(),
        "similitudes": similitudes_en(inscripciones, t),
        "modelo": entrenado["modelo"] if entrenado else None,
        "ahora": t,
    }
    nombres = [n for n in CONFIGURACIONES if con_modelo or n not in CONFIGURACIONES_CON_MODELO]
    listas = recomendaciones(perfiles, contexto, popularidad_en(inscripciones, t), k, nombres)

    sin_candidatos = sum(1 for p in perfiles.values() if not hibrido.candidatos_permitidos(p, contexto))
    resultados = {
        nombre: {
            **evaluar_k(por_usuario, reales, k),
            "cobertura": cobertura(por_usuario, catalogo),
            "diversidad": diversidad(por_usuario, catalogo),
        }
        for nombre, por_usuario in listas.items()
    }
    return {
        "origen": ORIGEN,
        "T": t.isoformat(),
        "k": k,
        "semilla": semilla,
        "dataset_sha256": huella_datos(datos_dir),
        "con_modelo": con_modelo,
        "n_alumnos_total": len(alumnos),
        "n_alumnos_evaluados": len(reales),
        # Sin candidatos tras F01–F03 ninguna configuración puede acertar: acota todas las métricas.
        "n_alumnos_sin_candidatos": sin_candidatos,
        "modelo": (
            {"version": entrenado["modelo"]["version"], "metricas": entrenado["metricas"]}
            if entrenado else None
        ),
        "configuraciones": resultados,
    }


def tabla_markdown(resultado: dict) -> str:
    """Tabla markdown con una fila por configuración. **Pura.**"""
    k = resultado["k"]

    def num(valor) -> str:
        return "–" if valor is None else f"{valor:.3f}"

    origen = "SINTÉTICOS" if resultado["origen"] == ORIGEN else str(resultado["origen"]).upper()
    lineas = [
        f"Evaluación offline con datos {origen}, T = {resultado['T']}, k = {k}, "
        f"modelo = {'sí' if resultado['con_modelo'] else 'no'}",
        f"{resultado['n_alumnos_evaluados']} de {resultado['n_alumnos_total']} alumnos evaluados; "
        f"{resultado['n_alumnos_sin_candidatos']} sin ningún candidato tras los filtros.",
        "",
        f"| Configuración | precision@{k} | recall@{k} | hit_rate@{k} | cobertura | diversidad | n_alumnos |",
        "|---|---|---|---|---|---|---|",
    ]
    for nombre, m in resultado["configuraciones"].items():
        lineas.append(
            f"| {nombre} | {num(m['precision'])} | {num(m['recall'])} | {num(m['hit_rate'])} "
            f"| {num(m['cobertura'])} | {num(m['diversidad'])} | {m['n_alumnos']} |"
        )
    return "\n".join(lineas)
