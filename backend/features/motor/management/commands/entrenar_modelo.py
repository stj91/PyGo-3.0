"""manage.py entrenar_modelo: entrena el árbol y lo exporta a entrenamiento/modelos/.

Sin `--guardar` solo escribe ficheros. Con `--guardar` inserta además una fila
en `modelos` con `activo = false`; activarla es cosa de `activar_modelo`.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Entrena el árbol de decisión de aprobación y lo exporta a JSON."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", required=True)
        parser.add_argument("--origen", required=True, choices=["sintetico", "real"])
        parser.add_argument("--semilla", type=int, default=42)
        parser.add_argument("--guardar", action="store_true")

    def handle(self, *args, **options):
        try:
            from entrenamiento.entrenar import entrenar
        except ImportError as exc:
            raise CommandError(
                f"Faltan dependencias de entrenamiento ({exc}). Instala requirements-ml.txt."
            ) from exc

        ruta = Path(options["dataset"])
        ruta = ruta if ruta.is_absolute() else Path(settings.BASE_DIR) / ruta
        if not ruta.is_file():
            raise CommandError(f"No existe el dataset {ruta}.")

        resultado = entrenar(ruta, options["origen"], options["semilla"])
        m = resultado["metricas"]
        self.stdout.write(json.dumps(
            {k: m[k] for k in ("version", "origen", "n_train", "n_test", "accuracy", "precision",
                               "recall", "f1", "f1_cv_media", "f1_baseline_mayoritaria",
                               "f1_baseline_regla", "matriz_confusion")},
            ensure_ascii=False, indent=2,
        ))
        for archivo in resultado["archivos"].values():
            self.stdout.write(f"  {archivo}")
        if m["origen"] == "sintetico":
            self.stdout.write(self.style.WARNING("Modelo entrenado con datos SINTÉTICOS."))

        if options["guardar"]:
            from core import supabase
            from features.motor import config

            supabase.insert(
                "modelos",
                {
                    "nombre": config.MODELO_NOMBRE,
                    "version": resultado["version"],
                    "algoritmo": "DecisionTreeClassifier",
                    "parametros": resultado["arbol"],
                    "caracteristicas": m["caracteristicas"],
                    "metricas": m,
                    "activo": False,
                },
                returning=False,
                operation="motor:modelo:guardar",
            )
            self.stdout.write(self.style.SUCCESS(
                f"Guardado {config.MODELO_NOMBRE}@{resultado['version']} (inactivo)."
            ))
