"""Generador de datos sintéticos de alumnos (solo librería estándar).

Sirve para desarrollar y evaluar el modelo mientras no hay datos reales. Es
determinista para una semilla dada: usa `random.Random(semilla)`, nunca el
`random` global.

Historia generativa, por alumno:

1. **Alumno.** `habilidad ~ U(0.3, 1.0)` (rasgo oculto: se exporta para
   análisis, nunca es una característica del modelo); 1–2 áreas de interés;
   una carrera al azar entre las de `catalogo["carrera_areas"]` y unas pocas sin
   áreas (`CARRERAS_SIN_AREAS`); `nivel_asignado` a partir de
   `habilidad + N(0, 0.1)`: < 0.55 Principiante, < 0.8 Intermedio, si no
   Avanzado. Un 10 % de los alumnos ignora los prerrequisitos al elegir.
2. **Diagnóstico.** Un evento `diagnostico` en `inicio + U(0..30 días)`. Cada
   ejercicio de `catalogo["ejercicios_diagnostico"]` se acierta con
   probabilidad `habilidad`.
3. **Elección de curso**, de 1 a 6 veces, entre los cursos aún no tomados:
   peso 0.7 si alguna de sus áreas es de interés, si no 0.15; × 3 si tiene
   todos los prerrequisitos completados, × 0.1 si no (los alumnos que ignoran
   prerrequisitos no aplican este factor). Se registra `curso_vista` y una
   inscripción con `origen = 'catalogo'`.
4. **Cursado.** Cada módulo tiene `EJERCICIOS_POR_MODULO` ejercicios
   sintéticos (ids `ejercicio_sintetico(tema_id, k)`). Por módulo, cada
   ejercicio se acierta con probabilidad
   `clamp(habilidad − 0.08 × dificultad + 0.25 × (media de notas de
   prerrequisitos / 100 − 0.8) − 0.15 × [falta un prerrequisito] + N(0, 0.05),
   0.05, 0.98)`; el ruido se sortea una vez por módulo y, sin prerrequisitos
   completados, la media vale 80 (término nulo). Cada envío escribe filas en
   `intentos` (100/0 por ejercicio) y un evento `quiz_intento`
   (valor = proporción de aciertos); aprobar (≥ `UMBRAL_APROBADO`) registra
   `tema_completado`. Hasta 3 envíos por módulo; tras el tercer suspenso el
   alumno abandona el curso con probabilidad 0.7, si no sigue con el siguiente
   módulo sin aprobarlo. El curso queda `completado` si aprobó todos los
   módulos (`calificacion_final` = media del último resultado por ejercicio,
   evento `curso_completado`); si no, `abandonado`.
5. **Tiempo.** 1–3 días por módulo, 1–20 horas entre reintentos y 2–10 días
   entre cursos.

Formato de salida (lo consumen 06 `--desde-csv` y 10): un CSV por clave, UTF-8,
con cabecera, fechas ISO-8601 UTC y `datos` en JSON, más `catalogo.json`.
"""

import csv
import json
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from features.motor import config
from features.motor.tipos import Catalogo

COLUMNAS: Dict[str, List[str]] = {
    "alumnos": ["usuario_id", "nivel_asignado", "carrera_clave", "intereses", "habilidad"],
    "inscripciones": [
        "usuario_id", "curso_id", "estado", "porcentaje_avance_global", "calificacion_final",
        "fecha_inscripcion", "completado_en", "origen",
    ],
    "intentos": ["usuario_id", "ejercicio_id", "tema_id", "tipo", "calificacion_obtenida", "fecha_intento"],
    "eventos": ["usuario_id", "tipo", "objeto_tipo", "objeto_id", "curso_id", "valor", "datos", "fecha"],
}

EJERCICIOS_POR_MODULO = 5
CARRERAS_SIN_AREAS = ["LDER", "LPSI", "LMED"]
PROPORCION_SALTA_PRERREQUISITOS = 0.10
MAX_ENVIOS_POR_MODULO = 3
PROB_ABANDONO_TRAS_SUSPENSOS = 0.7

TIPO_PRACTICA = "ejercicio_practico"
TIPO_DIAGNOSTICO = "evaluacion_tecnica"

_FRACCION = re.compile(r"\.(\d+)")


def ejercicio_sintetico(tema_id: int, k: int) -> int:
    """Id del ejercicio sintético `k` (1..N) de un módulo; no choca con 9001–9005."""
    return 100000 + tema_id * 100 + k


# --- Generación (pura salvo por el generador local de aleatorios) -----------


def _nivel(valor: float) -> str:
    if valor < 0.55:
        return "Principiante"
    if valor < 0.8:
        return "Intermedio"
    return "Avanzado"


def _evento(usuario_id: str, tipo: str, fecha: datetime, **campos: Any) -> dict:
    return {
        "usuario_id": usuario_id,
        "tipo": tipo,
        "objeto_tipo": campos.get("objeto_tipo"),
        "objeto_id": campos.get("objeto_id"),
        "curso_id": campos.get("curso_id"),
        "valor": campos.get("valor"),
        "datos": campos.get("datos", {}),
        "fecha": fecha,
    }


def _cursar(
    rng: random.Random,
    usuario_id: str,
    habilidad: float,
    curso: dict,
    completados: Dict[int, float],
    fecha_inscripcion: datetime,
) -> Tuple[dict, List[dict], List[dict], datetime]:
    """Simula un curso: `(inscripción, intentos, eventos, fecha de fin)`."""
    requeridos = [p["curso_id"] for p in curso["prerrequisitos"]]
    falta = any(r not in completados for r in requeridos)
    notas = [completados[r] for r in requeridos if r in completados]
    media_previa = (sum(notas) / len(notas) / 100) if notas else 0.8
    base = (
        habilidad
        - 0.08 * curso["dificultad"]
        + 0.25 * (media_previa - 0.8)
        - 0.15 * (1 if falta else 0)
    )

    intentos: List[dict] = []
    eventos: List[dict] = []
    ultimo_resultado: Dict[int, float] = {}
    aprobados = 0
    reloj = fecha_inscripcion

    for tema in curso["temas"]:
        reloj += timedelta(days=rng.uniform(1, 3))
        p = min(0.98, max(0.05, base + rng.gauss(0, 0.05)))
        ejercicios = [ejercicio_sintetico(tema["id"], k) for k in range(1, EJERCICIOS_POR_MODULO + 1)]
        aprobado = False
        for envio in range(MAX_ENVIOS_POR_MODULO):
            if envio > 0:
                reloj += timedelta(hours=rng.uniform(1, 20))
            aciertos = [rng.random() < p for _ in ejercicios]
            for ejercicio_id, acierto in zip(ejercicios, aciertos):
                nota = 100.0 if acierto else 0.0
                ultimo_resultado[ejercicio_id] = nota
                intentos.append({
                    "usuario_id": usuario_id, "ejercicio_id": ejercicio_id, "tema_id": tema["id"],
                    "tipo": TIPO_PRACTICA, "calificacion_obtenida": nota, "fecha_intento": reloj,
                })
            proporcion = sum(aciertos) / len(aciertos)
            eventos.append(_evento(
                usuario_id, "quiz_intento", reloj, objeto_tipo="tema", objeto_id=tema["id"],
                curso_id=curso["id"], valor=round(proporcion, 3),
                datos={"detalle": [
                    {"ejercicio_id": e, "es_correcta": a} for e, a in zip(ejercicios, aciertos)
                ]},
            ))
            if proporcion * 100 >= config.UMBRAL_APROBADO:
                aprobado = True
                eventos.append(_evento(
                    usuario_id, "tema_completado", reloj, objeto_tipo="tema",
                    objeto_id=tema["id"], curso_id=curso["id"],
                ))
                break
        if aprobado:
            aprobados += 1
        elif rng.random() < PROB_ABANDONO_TRAS_SUSPENSOS:
            break

    completado = aprobados == len(curso["temas"])
    calificacion = (
        round(sum(ultimo_resultado.values()) / len(ultimo_resultado), 2) if completado else None
    )
    if completado:
        eventos.append(_evento(
            usuario_id, "curso_completado", reloj, objeto_tipo="curso", objeto_id=curso["id"],
            curso_id=curso["id"], valor=calificacion,
        ))
    inscripcion = {
        "usuario_id": usuario_id,
        "curso_id": curso["id"],
        "estado": "completado" if completado else "abandonado",
        "porcentaje_avance_global": round(100.0 * aprobados / len(curso["temas"]), 2),
        "calificacion_final": calificacion,
        "fecha_inscripcion": fecha_inscripcion,
        "completado_en": reloj if completado else None,
        "origen": "catalogo",
    }
    return inscripcion, intentos, eventos, reloj


def _alumno(
    rng: random.Random, usuario_id: str, catalogo: Catalogo, inicio: datetime
) -> Dict[str, List[dict]]:
    areas = sorted(catalogo["areas"])
    carreras = sorted(catalogo["carrera_areas"]) + CARRERAS_SIN_AREAS
    cursos = [c for _, c in sorted(catalogo["cursos"].items()) if c["temas"]]

    habilidad = rng.uniform(0.3, 1.0)
    intereses = rng.sample(areas, rng.randint(1, min(2, len(areas)))) if areas else []
    carrera = rng.choice(carreras) if carreras else None
    nivel = _nivel(habilidad + rng.gauss(0, 0.1))
    ignora_prerrequisitos = rng.random() < PROPORCION_SALTA_PRERREQUISITOS

    eventos: List[dict] = []
    intentos: List[dict] = []
    inscripciones: List[dict] = []

    reloj = inicio + timedelta(days=rng.uniform(0, 30))
    resultados = {e: rng.random() < habilidad for e in sorted(catalogo["ejercicios_diagnostico"])}
    for ejercicio_id, acierto in resultados.items():
        intentos.append({
            "usuario_id": usuario_id, "ejercicio_id": ejercicio_id,
            "tema_id": catalogo["ejercicios_diagnostico"][ejercicio_id], "tipo": TIPO_DIAGNOSTICO,
            "calificacion_obtenida": 100.0 if acierto else 0.0, "fecha_intento": reloj,
        })
    eventos.append(_evento(
        usuario_id, "diagnostico", reloj,
        valor=round(sum(resultados.values()) / len(resultados), 3) if resultados else 0.0,
        datos={"resultados": {str(k): v for k, v in resultados.items()}, "nivel": nivel},
    ))

    completados: Dict[int, float] = {}
    tomados = set()
    for _ in range(rng.randint(1, 6)):
        candidatos = [c for c in cursos if c["id"] not in tomados]
        if not candidatos:
            break
        pesos = []
        for c in candidatos:
            peso = 0.7 if set(c["areas"]) & set(intereses) else 0.15
            if not ignora_prerrequisitos:
                tiene_todos = all(p["curso_id"] in completados for p in c["prerrequisitos"])
                peso *= 3 if tiene_todos else 0.1
            pesos.append(peso)
        curso = rng.choices(candidatos, weights=pesos)[0]
        tomados.add(curso["id"])

        reloj += timedelta(days=rng.uniform(2, 10))
        eventos.append(_evento(
            usuario_id, "curso_vista", reloj - timedelta(minutes=rng.uniform(1, 30)),
            objeto_tipo="curso", objeto_id=curso["id"], curso_id=curso["id"],
        ))
        inscripcion, nuevos_intentos, nuevos_eventos, reloj = _cursar(
            rng, usuario_id, habilidad, curso, completados, reloj
        )
        inscripciones.append(inscripcion)
        intentos.extend(nuevos_intentos)
        eventos.extend(nuevos_eventos)
        if inscripcion["estado"] == "completado":
            completados[curso["id"]] = inscripcion["calificacion_final"]

    return {
        "alumnos": [{
            "usuario_id": usuario_id,
            "nivel_asignado": nivel,
            "carrera_clave": carrera,
            "intereses": intereses,
            "habilidad": round(habilidad, 4),
        }],
        "inscripciones": inscripciones,
        "intentos": sorted(intentos, key=lambda i: i["fecha_intento"]),
        "eventos": sorted(eventos, key=lambda e: e["fecha"]),
    }


def generar(catalogo: Catalogo, n_alumnos: int, semilla: int, inicio: datetime) -> Dict[str, List[dict]]:
    """Datos sintéticos `{"alumnos", "inscripciones", "intentos", "eventos"}`. Determinista por semilla.

    Las fechas son `datetime` con zona horaria; `escribir` las pasa a CSV.
    """
    rng = random.Random(semilla)
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    salida: Dict[str, List[dict]] = {clave: [] for clave in COLUMNAS}
    for i in range(1, n_alumnos + 1):
        datos = _alumno(rng, f"sint-{i:06d}", catalogo, inicio)
        for clave in COLUMNAS:
            salida[clave].extend(datos[clave])
    return salida


# --- Lectura y escritura (efectos) ------------------------------------------


def _a_texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.astimezone(timezone.utc).isoformat()
    if isinstance(valor, dict):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    if isinstance(valor, (list, tuple)):
        return ";".join(str(v) for v in valor)
    return str(valor)


def escribir(datos: Dict[str, List[dict]], catalogo: Catalogo, directorio: Path) -> None:
    """Escribe `<clave>.csv` por cada tabla y `catalogo.json` en `directorio`."""
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    for clave, columnas in COLUMNAS.items():
        with open(directorio / f"{clave}.csv", "w", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            escritor.writerow(columnas)
            for fila in datos.get(clave, []):
                escritor.writerow([_a_texto(fila.get(c)) for c in columnas])
    guardar_catalogo(catalogo, directorio / "catalogo.json")


def leer(directorio: Path) -> Tuple[Dict[str, List[dict]], Catalogo]:
    """Lee un directorio escrito por `escribir`: `(filas como texto, catálogo)`."""
    directorio = Path(directorio)
    datos: Dict[str, List[dict]] = {}
    for clave in COLUMNAS:
        with open(directorio / f"{clave}.csv", newline="", encoding="utf-8") as f:
            datos[clave] = list(csv.DictReader(f))
    return datos, cargar_catalogo_json(directorio / "catalogo.json")


def catalogo_desde_json(crudo: dict) -> Catalogo:
    """Convierte a `int` las claves que JSON guarda como texto. **Pura.**"""
    return {
        "cursos": {int(k): v for k, v in crudo["cursos"].items()},
        "conceptos": dict(crudo["conceptos"]),
        "areas": dict(crudo["areas"]),
        "carrera_areas": dict(crudo["carrera_areas"]),
        "ejercicios_diagnostico": {int(k): int(v) for k, v in crudo["ejercicios_diagnostico"].items()},
    }


def cargar_catalogo_json(ruta: Path) -> Catalogo:
    with open(ruta, encoding="utf-8") as f:
        return catalogo_desde_json(json.load(f))


def guardar_catalogo(catalogo: Catalogo, ruta: Path) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2, sort_keys=True)


def fecha(valor: Any) -> Optional[datetime]:
    """`datetime` UTC a partir de un `datetime` o de texto ISO-8601 (admite `Z`); vacío -> None."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    texto = str(valor).strip().replace("Z", "+00:00").replace(" ", "T", 1)
    # Python 3.9 solo acepta 3 o 6 decimales; PostgREST puede devolver otros.
    texto = _FRACCION.sub(lambda m: "." + m.group(1)[:6].ljust(6, "0"), texto)
    resultado = datetime.fromisoformat(texto)
    return resultado if resultado.tzinfo else resultado.replace(tzinfo=timezone.utc)
