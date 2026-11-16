"""manage.py calcular_similitudes: recalcula la tabla `similitud_cursos`.

1. Lee todas las filas de `usuario_cursos`, paginadas de 1000 en 1000 (o
   `inscripciones.csv` con `--desde-csv`, formato de datos sintéticos de 07).
2. `interacciones` -> `calcular_similitudes`.
3. Upsert de cada par (ambas direcciones) con `calculado_en` = inicio de la
   ejecución; después invalida los pares anteriores a ese instante. La tabla
   nunca queda vacía.
4. Imprime cursos, pares y pares con soporte >= SOPORTE_MINIMO.

Los datos sintéticos nunca llegan a la tabla real: `--desde-csv` siempre simula.
"""

import csv
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from django.core.management.base import BaseCommand, CommandError

from core import supabase

from features.motor import config
from features.motor.estrategias import colaborativo

_TABLA = "similitud_cursos"


# --- Lectura y escritura (efectos) ------------------------------------------


def _leer_pagina_inscripciones(desde: int, tamano: int) -> List[Dict[str, Any]]:
    # `offset` es un parámetro de PostgREST que core.supabase.select no expone como
    # argumento; sus filtros se envían tal cual en la query string.
    return supabase.select(
        "usuario_cursos",
        columns="usuario_id,curso_id,estado,calificacion_final",
        filters=(("offset", str(desde)),),
        order="id.asc",
        limit=tamano,
        operation="motor:similitudes:inscripciones",
    )


def leer_inscripciones_bd() -> List[Dict[str, Any]]:
    return colaborativo.leer_paginado(_leer_pagina_inscripciones)


def leer_inscripciones_csv(directorio: str) -> List[Dict[str, Any]]:
    ruta = os.path.join(directorio, "inscripciones.csv")
    if not os.path.isfile(ruta):
        raise CommandError(f"No existe {ruta}.")
    with open(ruta, newline="", encoding="utf-8") as archivo:
        return [
            {
                "usuario_id": fila.get("usuario_id"),
                "curso_id": fila.get("curso_id"),
                "estado": fila.get("estado"),
                "calificacion_final": fila.get("calificacion_final"),
            }
            for fila in csv.DictReader(archivo)
        ]


def filas_a_escribir(similitudes, calculado_en: str) -> List[Dict[str, Any]]:
    """Una fila por dirección, con la similitud redondeada a numeric(5,4). **Pura.**"""
    return [
        {
            "curso_a": a,
            "curso_b": b,
            "similitud": round(par["similitud"], 4),
            "soporte": par["soporte"],
            "calculado_en": calculado_en,
        }
        for a, vecinos in sorted(similitudes.items())
        for b, par in sorted(vecinos.items())
    ]


def escribir_similitudes(filas: List[Dict[str, Any]], inicio: str) -> None:
    for fila in filas:
        supabase.upsert(
            _TABLA, fila, on_conflict="curso_a,curso_b", operation="motor:similitudes:upsert"
        )
    # core.supabase no tiene DELETE: los pares que no se recalcularon en esta
    # ejecución se invalidan con soporte 0, que cargar_similitudes ignora.
    supabase.update(
        _TABLA,
        {"similitud": 0, "soporte": 0},
        filters=(("calculado_en", f"lt.{inicio}"), ("soporte", "gt.0")),
        operation="motor:similitudes:invalidar_obsoletas",
    )


# --- Orden ------------------------------------------------------------------


def resumen(interacciones, similitudes) -> Dict[str, int]:
    """Cursos con interacciones, pares no ordenados y pares con soporte suficiente. **Pura.**"""
    pares = [
        par for a, vecinos in similitudes.items() for b, par in vecinos.items() if a < b
    ]
    return {
        "cursos": len({i["curso_id"] for i in interacciones}),
        "pares": len(pares),
        "pares_con_soporte": sum(1 for p in pares if p["soporte"] >= config.SOPORTE_MINIMO),
    }


class Command(BaseCommand):
    help = "Recalcula la tabla similitud_cursos (filtrado colaborativo)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--simular", action="store_true", help="Calcula e imprime, sin escribir nada."
        )
        parser.add_argument(
            "--desde-csv", metavar="DIR",
            help="Lee DIR/inscripciones.csv (datos sintéticos) en lugar de la base. Implica --simular.",
        )
        parser.add_argument(
            "--escribir", action="store_true",
            help="Sólo tiene sentido junto a --desde-csv, y está prohibido: los datos sintéticos nunca se escriben.",
        )

    def handle(self, *args, **options):
        directorio = options.get("desde_csv")
        if directorio and options.get("escribir"):
            raise CommandError(
                "--desde-csv no admite --escribir: los datos sintéticos nunca llegan a la tabla real."
            )
        simular = bool(options.get("simular")) or bool(directorio)

        inicio = datetime.now(timezone.utc).isoformat()
        inscripciones = leer_inscripciones_csv(directorio) if directorio else leer_inscripciones_bd()
        interacciones = colaborativo.interacciones(inscripciones)
        similitudes = colaborativo.calcular_similitudes(interacciones)
        totales = resumen(interacciones, similitudes)

        if not simular:
            escribir_similitudes(filas_a_escribir(similitudes, inicio), inicio)

        modo = "simulación, nada escrito" if simular else f"escrito en {_TABLA}"
        self.stdout.write(
            f"Cursos: {totales['cursos']}. Pares: {totales['pares']}. "
            f"Pares con soporte >= {config.SOPORTE_MINIMO}: {totales['pares_con_soporte']}. ({modo})"
        )
