"""manage.py generar_sinteticos: datos sintéticos de alumnos para desarrollar el modelo.

No toca la base de datos. Solo escribe dentro de `entrenamiento/datos/`.
"""

from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def ruta_en_datos(valor: str) -> Path:
    """Ruta absoluta (relativa a `backend/`) que debe quedar dentro de `entrenamiento/datos/`."""
    raiz = (Path(settings.BASE_DIR) / "entrenamiento" / "datos").resolve()
    ruta = Path(valor)
    ruta = (ruta if ruta.is_absolute() else Path(settings.BASE_DIR) / ruta).resolve()
    if ruta != raiz and raiz not in ruta.parents:
        raise CommandError(f"Solo se puede escribir dentro de {raiz}.")
    return ruta


class Command(BaseCommand):
    help = "Genera datos sintéticos de alumnos (CSV) en entrenamiento/datos/."

    def add_arguments(self, parser):
        parser.add_argument("--alumnos", type=int, default=2000)
        parser.add_argument("--semilla", type=int, default=42)
        parser.add_argument("--salida", required=True, help="Directorio dentro de entrenamiento/datos/.")
        parser.add_argument("--catalogo", default="entrenamiento/catalogo_ejemplo.json")
        parser.add_argument(
            "--inicio", default="2026-01-12T00:00:00+00:00",
            help="Fecha ISO-8601 desde la que empiezan los diagnósticos.",
        )

    def handle(self, *args, **options):
        from entrenamiento import sinteticos

        if options["alumnos"] < 1:
            raise CommandError("--alumnos debe ser al menos 1.")
        salida = ruta_en_datos(options["salida"])
        catalogo_ruta = Path(options["catalogo"])
        if not catalogo_ruta.is_absolute():
            catalogo_ruta = Path(settings.BASE_DIR) / catalogo_ruta
        if not catalogo_ruta.is_file():
            raise CommandError(f"No existe el catálogo {catalogo_ruta}.")
        try:
            inicio = sinteticos.fecha(options["inicio"]) or datetime.now(timezone.utc)
        except ValueError as exc:
            raise CommandError(f"--inicio no es una fecha ISO-8601: {exc}") from exc

        catalogo = sinteticos.cargar_catalogo_json(catalogo_ruta)
        datos = sinteticos.generar(catalogo, options["alumnos"], options["semilla"], inicio)
        sinteticos.escribir(datos, catalogo, salida)

        resumen = ", ".join(f"{len(filas)} {clave}" for clave, filas in datos.items())
        self.stdout.write(self.style.SUCCESS(f"Escrito en {salida}: {resumen}."))
