"""manage.py evaluar_motor: evaluación offline del motor con partición temporal (paquete 10).

Lee solo los CSV de `--datos` (formato de `generar_sinteticos`); nunca toca la
base de datos. Imprime una tabla markdown y guarda el resultado completo en
`entrenamiento/modelos/evaluacion-<UTC %Y%m%d-%H%M>.json`.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def directorio_salida() -> Path:
    return Path(settings.BASE_DIR) / "entrenamiento" / "modelos"


class Command(BaseCommand):
    help = "Evaluación offline del motor de recomendación (solo CSV, sin base de datos)."

    def add_arguments(self, parser):
        parser.add_argument("--datos", default="entrenamiento/datos/sinteticos",
                            help="Directorio con alumnos/inscripciones/intentos/eventos.csv y catalogo.json.")
        parser.add_argument("--k", type=int, default=3)
        parser.add_argument("--semilla", type=int, default=42)
        parser.add_argument("--sin-modelo", dest="sin_modelo", action="store_true",
                            help="No entrena el árbol (no requiere scikit-learn).")

    def handle(self, *args, **options):
        from entrenamiento import evaluacion

        if options["k"] < 1:
            raise CommandError("--k debe ser al menos 1.")
        datos = Path(options["datos"])
        datos = datos if datos.is_absolute() else Path(settings.BASE_DIR) / datos
        if not datos.is_dir():
            raise CommandError(f"No existe el directorio {datos}.")

        try:
            resultado = evaluacion.ejecutar(
                datos, k=options["k"], con_modelo=not options["sin_modelo"], semilla=options["semilla"],
            )
        except ImportError as exc:
            raise CommandError(
                f"Falta una dependencia de requirements-ml.txt ({exc}). Instálala o usa --sin-modelo."
            ) from exc
        except (OSError, KeyError, ValueError) as exc:
            raise CommandError(f"No se pudieron evaluar los datos de {datos}: {exc}") from exc

        carpeta = directorio_salida()
        carpeta.mkdir(parents=True, exist_ok=True)
        base = f"evaluacion-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
        salida, n = carpeta / f"{base}.json", 2
        while salida.exists():  # dos ejecuciones en el mismo minuto no se pisan
            salida, n = carpeta / f"{base}-{n}.json", n + 1
        salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(evaluacion.tabla_markdown(resultado))
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Resultado (origen: {resultado['origen']}) en {salida}."))
