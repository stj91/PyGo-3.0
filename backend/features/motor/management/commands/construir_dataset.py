"""manage.py construir_dataset: una fila por inscripción con desenlace, sin fugas de datos.

`--desde-csv <dir>` lee la salida de `generar_sinteticos`. `--desde-bd` lee las
mismas formas de Supabase (solo lectura); es para cuando haya datos reales.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Construye el dataset de entrenamiento (CSV) a partir de CSV sintéticos o de la base."

    def add_arguments(self, parser):
        origen = parser.add_mutually_exclusive_group(required=True)
        origen.add_argument("--desde-csv", dest="desde_csv")
        origen.add_argument("--desde-bd", dest="desde_bd", action="store_true")
        parser.add_argument("--salida", required=True)

    def handle(self, *args, **options):
        from entrenamiento import dataset, sinteticos

        if options["desde_csv"]:
            directorio = self._ruta(options["desde_csv"])
            if not directorio.is_dir():
                raise CommandError(f"No existe el directorio {directorio}.")
            datos, catalogo = sinteticos.leer(directorio)
            alumnos, inscripciones = datos["alumnos"], datos["inscripciones"]
            intentos, eventos = datos["intentos"], datos["eventos"]
        else:
            from features.motor.catalogo import cargar_catalogo

            catalogo = cargar_catalogo()
            alumnos, inscripciones, intentos, eventos = dataset.leer_desde_bd()

        filas = dataset.construir(alumnos, inscripciones, intentos, eventos, catalogo)
        salida = self._ruta(options["salida"])
        salida.parent.mkdir(parents=True, exist_ok=True)
        with open(salida, "w", newline="", encoding="utf-8") as f:
            escritor = csv.DictWriter(f, fieldnames=dataset.COLUMNAS_DATASET)
            escritor.writeheader()
            escritor.writerows(filas)

        positivos = sum(f["aprobo"] for f in filas)
        self.stdout.write(self.style.SUCCESS(
            f"{len(filas)} filas ({positivos} aprobadas) escritas en {salida}."
        ))

    @staticmethod
    def _ruta(valor: str) -> Path:
        ruta = Path(valor)
        return ruta if ruta.is_absolute() else Path(settings.BASE_DIR) / ruta
